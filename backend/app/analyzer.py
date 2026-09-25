"""Analysis core — phase 2: form discovery with CSRF detection, redirect tracing,
OAuth flow mapping, session cookie profiling, logout behavior and cookie-domain
scope findings (passive single-fetch model)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List

import httpx
from bs4 import BeautifulSoup
from xwa_sdk import map_severity

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

REDIRECT_LIMIT = 5


class TargetError(Exception):
    """Raised when the target cannot be fetched or parsed."""


# ── Form discovery ───────────────────────────────────────────────────────────

CSRF_NAME_RE = re.compile(
    r"csrf|authenticity|_token|verificationtoken|__requestverification|xsrf|nonce",
    re.IGNORECASE,
)
CSRF_VALUE_RE = re.compile(r"^[A-Za-z0-9+/=_\-.]{20,}$")

METHODS_SUBMIT = ("submit", "button", "image", "reset")


@dataclass
class FormFieldData:
    name: str | None
    input_type: str | None
    value: str | None
    required: bool
    autocomplete: str | None
    placeholder: str | None
    is_csrf: bool = False


@dataclass
class FormData:
    page_url: str
    action: str | None
    method: str
    enctype: str | None
    is_secure: bool
    fields: List[FormFieldData] = field(default_factory=list)
    redirect_chain: List[dict] = field(default_factory=list)


def _field_is_csrf(name: str | None, input_type: str | None, value: str | None) -> bool:
    if name and CSRF_NAME_RE.search(name):
        return True
    if input_type == "hidden" and value and CSRF_VALUE_RE.match(value):
        return True
    return False


def _looks_like_csrf(field: FormFieldData) -> bool:
    return _field_is_csrf(field.name, field.input_type, field.value)


def parse_forms(final_url: str, html: str) -> List[FormData]:
    """Extract forms and fields from HTML, flagging CSRF tokens."""
    soup = BeautifulSoup(html, "lxml")
    forms: List[FormData] = []

    for tag in soup.find_all("form"):
        action = tag.get("action") or None
        method = (tag.get("method") or "get").upper()
        enctype = tag.get("enctype") or None
        is_secure = not action or action.startswith("https:") or action.startswith("//")

        fields: List[FormFieldData] = []
        for control in tag.find_all(["input", "textarea", "select"]):
            name = control.get("name")
            if control.name == "input":
                input_type = control.get("type") or "text"
                if input_type in METHODS_SUBMIT:
                    continue
            elif control.name == "textarea":
                input_type = "textarea"
            else:
                input_type = "select"

            field = FormFieldData(
                name=name,
                input_type=input_type,
                value=control.get("value"),
                required=control.get("required") is not None,
                autocomplete=control.get("autocomplete"),
                placeholder=control.get("placeholder"),
            )
            field.is_csrf = _looks_like_csrf(field)
            fields.append(field)

        forms.append(
            FormData(
                page_url=final_url,
                action=action,
                method=method,
                enctype=enctype,
                is_secure=is_secure,
                fields=fields,
            )
        )

    return forms


async def trace_redirects(base_url: str, action: str | None, client: httpx.AsyncClient) -> List[dict]:
    """Follow a form action's redirect chain (GET only, bounded). Returns [{url, status}]."""
    if not action or action.startswith(("mailto:", "javascript:", "#", "tel:")):
        return []
    if action.lower().startswith("http"):
        url = action
    elif action.startswith("//"):
        url = f"https:{action}"
    else:
        url = str(httpx.URL(base_url).join(action))

    chain: List[dict] = []
    current = url
    for _ in range(REDIRECT_LIMIT):
        try:
            response = await client.get(current, follow_redirects=False)
        except httpx.HTTPError:
            break
        chain.append({"url": current, "status": response.status_code})
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if not location:
                break
            current = str(httpx.URL(current).join(location))
        else:
            break
    return chain


# ── OAuth / OIDC detection ───────────────────────────────────────────────────

OAUTH_PARAM_RE = re.compile(
    r"(https?://[^\s\"'<>]+)(?:\?[^\s\"'<>]*)?"
    r"(?:[?&](client_id|redirect_uri|response_type|scope|state|code_challenge)=)",
    re.IGNORECASE,
)
OAUTH_PATH_RE = re.compile(
    r"(?:https?://[^\s\"'<>]*)?(/[^\s\"'<>]*(?:/oauth|/authorize|/authorization|/token|/oidc)[^\s\"'<>]*)",
    re.IGNORECASE,
)
WELL_KNOWN_PATHS = (
    "/.well-known/openid-configuration",
    "/.well-known/oauth-authorization-server",
)

FLOW_FROM_RESPONSE_TYPE = {
    "code": "authorization_code",
    "token": "implicit",
    "id_token": "oidc",
    "code+token": "hybrid",
}

WEAKNESS_RULES = [
    ("implicit", "implicit flow: token exposed in URL fragment"),
    ("no_state", "authorization request without state parameter (CSRF on the flow)"),
    ("wildcard_redirect", "redirect_uri allows wildcard or missing"),
]


@dataclass
class OAuthFlowData:
    endpoint: str
    flow_type: str
    client_id: str | None
    redirect_uri: str | None
    scope: str | None
    uses_state: bool
    weakness: List[str] = field(default_factory=list)


def detect_oauth_in_html(html: str, page_url: str) -> List[OAuthFlowData]:
    """Find OAuth/OIDC authorization endpoints referenced in a page."""
    found: dict[str, OAuthFlowData] = {}

    for match in OAUTH_PARAM_RE.finditer(html):
        raw = match.group(0).rstrip("&,;\")")
        url = raw.split("?")[0]
        query = raw.split("?", 1)[1] if "?" in raw else ""
        params = dict(re.findall(r"([a-zA-Z_]+)=([^&\s\"'<>]*)", query))

        flow_type = FLOW_FROM_RESPONSE_TYPE.get(params.get("response_type", ""), "unknown")
        uses_state = "state" in params
        weakness = _weakness_for(flow_type, uses_state, params.get("redirect_uri"))

        key = (url, params.get("client_id"))
        flow = found.get(key) or OAuthFlowData(
            endpoint=url,
            flow_type=flow_type,
            client_id=params.get("client_id"),
            redirect_uri=params.get("redirect_uri"),
            scope=params.get("scope"),
            uses_state=uses_state,
            weakness=weakness,
        )
        if not flow.weakness:
            flow.weakness = weakness
        found[key] = flow

    for match in OAUTH_PATH_RE.finditer(html):
        path = match.group(1)
        url = _absolute(page_url, path)
        if "authorize" in path or "authorization" in path:
            flow_type = "authorization_code"
        elif "token" in path:
            flow_type = "client_credentials"
        else:
            flow_type = "unknown"
        found[(url, None)] = OAuthFlowData(
            endpoint=url, flow_type=flow_type, client_id=None,
            redirect_uri=None, scope=None, uses_state=False,
        )

    return list(found.values())


def _weakness_for(flow_type: str, uses_state: bool, redirect_uri: str | None) -> List[str]:
    weakness: List[str] = []
    if flow_type == "implicit":
        weakness.append("implicit flow: token exposed in URL fragment")
    if not uses_state:
        weakness.append("authorization request without state parameter")
    if redirect_uri and any(ch in redirect_uri for ch in ("*", "..")):
        weakness.append("suspicious redirect_uri (wildcard or path traversal)")
    return weakness


async def detect_oauth_discovery(base_url: str, client: httpx.AsyncClient) -> List[OAuthFlowData]:
    """Probe well-known OIDC/OAuth discovery documents and record endpoints."""
    flows: List[OAuthFlowData] = []
    for path in WELL_KNOWN_PATHS:
        url = _absolute(base_url, path)
        try:
            response = await client.get(url, follow_redirects=True, timeout=10.0)
            if response.status_code != 200:
                continue
            data = response.json()
        except (httpx.HTTPError, ValueError):
            continue

        for key, flow_type in (
            ("authorization_endpoint", "authorization_code"),
            ("token_endpoint", "client_credentials"),
            ("end_session_endpoint", "logout"),
        ):
            endpoint = data.get(key)
            if endpoint:
                flows.append(
                    OAuthFlowData(
                        endpoint=endpoint, flow_type=flow_type, client_id=None,
                        redirect_uri=None, scope=None, uses_state=False,
                    )
                )
    return flows


# ── Session cookie profiling ─────────────────────────────────────────────────

SESSION_NAME_RE = re.compile(
    r"session|sessid|jsession|phpsess|asp\.net_session|connect\.sid|auth|token|sid",
    re.IGNORECASE,
)


@dataclass
class SessionCookieData:
    name: str
    value_preview: str
    domain: str | None
    path: str | None
    http_only: bool
    secure: bool
    same_site: str | None
    max_age: str | None


def profile_session_cookies(response: httpx.Response) -> List[SessionCookieData]:
    """Profile Set-Cookie headers from an HTTP response."""
    cookies: List[SessionCookieData] = []
    seen: set[str] = set()

    for header in response.headers.get_list("set-cookie"):
        parts = [p.strip() for p in header.split(";")]
        name_value = parts[0].split("=", 1)
        name = name_value[0].strip()
        value = name_value[1].strip() if len(name_value) > 1 else ""
        if not name or name in seen:
            continue
        seen.add(name)

        attrs = {p.split("=", 1)[0].strip().lower(): (p.split("=", 1)[1].strip() if "=" in p else None)
                 for p in parts[1:] if p}

        same_site = attrs.get("samesite")
        if same_site is None and not SESSION_NAME_RE.search(name):
            continue  # only session-relevant cookies

        cookies.append(
            SessionCookieData(
                name=name,
                value_preview=(value[:40] + "…") if len(value) > 40 else value,
                domain=attrs.get("domain"),
                path=attrs.get("path"),
                http_only="httponly" in attrs,
                secure="secure" in attrs,
                same_site=same_site or ("none" if "samesite" in attrs else None),
                max_age=attrs.get("max-age") or attrs.get("expires"),
            )
        )

    return cookies


# ── Session findings (logout behavior + cookie domain scope) ────────────────
# Passive single-fetch observations reported as xwa-sdk Findings with
# category "session". Stateful fixation detection is intentionally out of scope
# (see ROADMAP.md — requires pre/post-login requests).

SESSION_FINDING_CATEGORY = "session"

LOGOUT_URL_RE = re.compile(
    r"(?:[/=?&]|^)(?:logout|signout|sign-out|sign_out|logoff|signoff|salir|cerrar[-_]?sesion)"
    r"(?:[/?#.&]|$)",
    re.IGNORECASE,
)


@dataclass
class SessionFindingData:
    kind: str  # "logout" | "domain_scope"
    severity: str  # xwa-sdk unified severity (info/low/medium/high/critical)
    title: str
    description: str
    category: str = SESSION_FINDING_CATEGORY
    target_url: str | None = None
    method: str | None = None
    csrf_present: bool | None = None
    evidence: dict | None = None

    def __post_init__(self) -> None:
        # Validate against the xwa-sdk unified severity scale.
        self.severity = map_severity("azuma", self.severity)


def _is_logout_url(url: str | None) -> bool:
    return bool(url) and bool(LOGOUT_URL_RE.search(url))


def _control_csrf(soup: BeautifulSoup, tag) -> bool:
    """Whether a form control carries a CSRF token (mirrors parse_forms)."""
    name = tag.get("name")
    input_type = (tag.get("type") or "text") if tag.name == "input" else None
    return _field_is_csrf(name, input_type, tag.get("value"))


def detect_logout_behavior(html: str, page_url: str) -> List[SessionFindingData]:
    """Passively detect logout endpoints in forms and links.

    - GET logout (link or form) → weakness: state-changing GET.
    - POST logout without a CSRF token → weakness: logout CSRF.
    - POST logout with a CSRF token → positive informational report.
    """
    soup = BeautifulSoup(html, "lxml")
    findings: List[SessionFindingData] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind_url: str, method: str, csrf: bool | None, source: str) -> None:
        key = (kind_url, method)
        if key in seen:
            return
        seen.add(key)

        if method == "GET" or csrf is None:
            findings.append(
                SessionFindingData(
                    kind="logout",
                    severity="low",
                    title="Logout uses state-changing GET",
                    description=(
                        f"Logout endpoint {kind_url} is reachable via GET "
                        f"({source}): state-changing logout can be triggered by "
                        "prefetching, crawlers or an attacker-supplied link and "
                        "leaks the URL in logs and Referer headers."
                    ),
                    target_url=kind_url,
                    method=method,
                    csrf_present=csrf,
                    evidence={"source": source, "method": method, "csrf_present": csrf},
                )
            )
        elif not csrf:
            findings.append(
                SessionFindingData(
                    kind="logout",
                    severity="medium",
                    title="Logout form without CSRF token",
                    description=(
                        f"Logout endpoint {kind_url} is POSTed from a form without "
                        "a CSRF token: an attacker can force session invalidation "
                        "(logout CSRF)."
                    ),
                    target_url=kind_url,
                    method=method,
                    csrf_present=False,
                    evidence={"source": source, "method": method, "csrf_present": False},
                )
            )
        else:
            findings.append(
                SessionFindingData(
                    kind="logout",
                    severity="info",
                    title="Logout form with CSRF protection",
                    description=(
                        f"Logout endpoint {kind_url} is POSTed from a form carrying "
                        "a CSRF token."
                    ),
                    target_url=kind_url,
                    method=method,
                    csrf_present=True,
                    evidence={"source": source, "method": method, "csrf_present": True},
                )
            )

    for form in soup.find_all("form"):
        action = form.get("action") or None
        if not _is_logout_url(action):
            continue
        method = (form.get("method") or "get").upper()
        url = _absolute(page_url, action) if action else page_url
        csrf = any(
            _control_csrf(soup, control)
            for control in form.find_all(["input", "textarea", "select"])
        )
        _add(url, method, csrf if method == "POST" else None, "form")

    for link in soup.find_all("a"):
        href = link.get("href") or None
        if not _is_logout_url(href):
            continue
        url = _absolute(page_url, href)
        _add(url, "GET", None, "link")

    return findings


def analyze_cookie_domain_scope(
    cookies: List["SessionCookieData"], host: str
) -> List[SessionFindingData]:
    """Map Set-Cookie Domain attributes against the response host.

    A Domain attribute broader than the host (leading dot or parent domain)
    widens session persistence to the covered subdomains and is reported as a
    weakness with the exact scope in the evidence.
    """
    findings: List[SessionFindingData] = []
    host = (host or "").lower().strip(".")
    seen: set[str] = set()

    for cookie in cookies:
        raw = (cookie.domain or "").strip().lower()
        if not raw:
            continue
        leading_dot = raw.startswith(".")
        domain = raw.lstrip(".")
        if not domain or domain in seen:
            continue
        seen.add(domain)

        # Same-host Domain without widening, or narrowing to a subdomain: not a weakness.
        if (domain == host and not leading_dot) or domain.endswith(f".{host}"):
            continue

        covered = [domain, f"*.{domain}"]
        if domain == host:  # leading dot only
            severity, title, scope = (
                "low",
                "Session cookie Domain uses a leading dot",
                f"leading-dot Domain=.{domain} widens the cookie to {domain} and "
                f"every subdomain ({', '.join(covered)})",
            )
        elif host.endswith(f".{domain}"):
            severity, title, scope = (
                "medium",
                "Session cookie Domain widened to parent domain",
                f"Domain={domain} on host {host} persists the session across "
                f"{domain} and all its subdomains ({', '.join(covered)})",
            )
        else:
            severity, title, scope = (
                "high",
                "Session cookie Domain points outside the host",
                f"Domain={domain} while the page is served from {host} shares the "
                f"session with {domain} and all its subdomains ({', '.join(covered)})",
            )

        findings.append(
            SessionFindingData(
                kind="domain_scope",
                severity=severity,
                title=title,
                description=f"Cookie '{cookie.name}': {scope}.",
                target_url=f"https://{host}/" if host else None,
                evidence={
                    "cookie": cookie.name,
                    "domain": cookie.domain,
                    "host": host,
                    "leading_dot": leading_dot,
                    "covered_subdomains": covered,
                },
            )
        )

    return findings


# ── Fetch helpers ────────────────────────────────────────────────────────────

def _absolute(base_url: str, path: str) -> str:
    if path.startswith("http"):
        return path
    if path.startswith("//"):
        return f"https:{path}"
    return str(httpx.URL(base_url).join(path))


async def fetch_html(target: str, timeout: float = 20.0) -> tuple[httpx.Response, str]:
    """Fetch the target and return (response, html)."""
    url = target if "://" in target else f"https://{target}"
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": DEFAULT_USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response, response.text
    except httpx.HTTPError as exc:
        raise TargetError(f"Failed to fetch target: {exc}") from exc


async def analyze_target(target: str) -> dict:
    """Run the full pipeline: forms, redirects, OAuth, session cookies, findings.

    Returns a dict with page info plus the four result lists.
    """
    response, html = await fetch_html(target)
    final_url = str(response.url)

    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(15.0),
        headers={"User-Agent": DEFAULT_USER_AGENT},
    ) as client:
        forms = parse_forms(final_url, html)
        for form in forms:
            if form.method == "GET":
                form.redirect_chain = await trace_redirects(final_url, form.action, client)
        oauth_flows = detect_oauth_in_html(html, final_url)
        oauth_flows.extend(await detect_oauth_discovery(final_url, client))

    session_cookies = profile_session_cookies(response)
    host = httpx.URL(final_url).host or ""
    session_findings = detect_logout_behavior(html, final_url)
    session_findings.extend(analyze_cookie_domain_scope(session_cookies, host))

    return {
        "final_url": final_url,
        "title": title,
        "forms": forms,
        "oauth_flows": oauth_flows,
        "session_cookies": session_cookies,
        "session_findings": session_findings,
    }


def serialize_redirect_chain(chain: List[dict]) -> str | None:
    return json.dumps(chain) if chain else None
