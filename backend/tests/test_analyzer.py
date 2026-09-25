"""Unit tests for azuma analyzer (no network)."""

import httpx
import pytest
from xwa_sdk import SEVERITIES

from app.analyzer import (
    SessionCookieData,
    analyze_cookie_domain_scope,
    detect_logout_behavior,
    detect_oauth_in_html,
    parse_forms,
    profile_session_cookies,
)

SAMPLE_HTML = """
<html>
<head><title>Test Site</title></head>
<body>
  <form method="post" action="/login" enctype="application/x-www-form-urlencoded">
    <input type="hidden" name="authenticity_token" value="aB3xY9qW7eR2tU5iO8pL1kM4nJ6hG0vC">
    <input type="text" name="username" required autocomplete="username">
    <input type="password" name="password" required>
    <input type="submit" value="Log in">
  </form>
  <form method="get" action="https://example.com/search">
    <input type="search" name="q">
  </form>
  <a href="https://accounts.example.com/oauth/authorize?client_id=app-123&response_type=code&redirect_uri=https://app.example.com/cb&scope=openid&state=xyz">
    Sign in
  </a>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, headers):
        self.headers = httpx.Headers([("set-cookie", h) for h in headers])


def test_parse_forms_with_csrf_detection():
    forms = parse_forms("https://example.com/", SAMPLE_HTML)
    assert len(forms) == 2

    login = forms[0]
    assert login.method == "POST"
    assert login.action == "/login"
    assert not login.is_secure

    fields = login.fields
    assert len(fields) == 3
    hidden = fields[0]
    assert hidden.input_type == "hidden"
    assert hidden.is_csrf is True
    assert hidden.value == "aB3xY9qW7eR2tU5iO8pL1kM4nJ6hG0vC"

    assert fields[1].input_type == "text"
    assert fields[1].required is True
    assert fields[1].is_csrf is False

    search = forms[1]
    assert search.is_secure is True
    assert search.fields[0].input_type == "search"


def test_csrf_value_heuristic():
    html = """
    <form method="post" action="/x">
      <input type="hidden" name="payload" value="s3cr3tL0ngT0k3nV4lu3w1thNumb3rs1nIt">
    </form>
    """
    forms = parse_forms("https://example.com/", html)
    assert forms[0].fields[0].is_csrf is True


def test_detect_oauth_in_html():
    flows = detect_oauth_in_html(SAMPLE_HTML, "https://example.com/")
    oauth_flows = [f for f in flows if f.client_id]
    assert len(oauth_flows) == 1

    flow = oauth_flows[0]
    assert flow.endpoint == "https://accounts.example.com/oauth/authorize"
    assert flow.flow_type == "authorization_code"
    assert flow.client_id == "app-123"
    assert flow.uses_state is True
    assert "implicit" not in " ".join(flow.weakness)


def test_oauth_without_state_flags_weakness():
    html = """
    <a href="https://accounts.example.com/authorize?client_id=x&response_type=token&redirect_uri=https://app.example.com/cb">
    """
    flows = detect_oauth_in_html(html, "https://example.com/")
    flow = [f for f in flows if f.client_id][0]
    assert flow.flow_type == "implicit"
    assert any("state" in w for w in flow.weakness)
    assert any("implicit" in w for w in flow.weakness)


def test_profile_session_cookies():
    response = FakeResponse([
        "sessionid=abc123; HttpOnly; Secure; Path=/; SameSite=Lax; Max-Age=3600",
        "csrftoken=xyz789; Path=/",
        "analytics_uid=1234; Path=/",
    ])
    cookies = profile_session_cookies(response)
    names = [c.name for c in cookies]
    assert "sessionid" in names
    assert "csrftoken" in names
    assert "analytics_uid" not in names  # not session-relevant

    session = next(c for c in cookies if c.name == "sessionid")
    assert session.http_only is True
    assert session.secure is True
    assert session.same_site == "Lax"
    assert session.max_age == "3600"
    assert session.path == "/"


def test_profile_session_cookie_flags_missing():
    response = FakeResponse(["JSESSIONID=deadbeef; Path=/"])
    cookies = profile_session_cookies(response)
    assert len(cookies) == 1
    cookie = cookies[0]
    assert cookie.http_only is False
    assert cookie.secure is False
    assert cookie.same_site is None


# ── Logout behavior detection ────────────────────────────────────────────────

LOGOUT_HTML = """
<html><body>
  <form method="get" action="/logout">
    <input type="submit" value="Sign out">
  </form>
  <form method="post" action="/account/cerrar-sesion">
    <input type="hidden" name="csrfmiddlewaretoken" value="aB3xY9qW7eR2tU5iO8pL1kM4nJ6hG0vC">
    <input type="submit" value="Salir">
  </form>
  <form method="post" action="/signout">
    <input type="submit" value="Sign out">
  </form>
  <a href="https://example.com/salir">Salir</a>
</body></html>
"""


def test_detect_logout_get_form_is_weakness():
    findings = [f for f in detect_logout_behavior(LOGOUT_HTML, "https://example.com/")
                if "/logout" in (f.target_url or "")]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == "session"
    assert finding.severity == "low"
    assert finding.method == "GET"
    assert "state-changing GET" in finding.title.lower() or "GET" in finding.title
    assert finding.evidence["source"] == "form"


def test_detect_logout_post_with_csrf_is_informational():
    findings = [
        f for f in detect_logout_behavior(LOGOUT_HTML, "https://example.com/")
        if f.method == "POST"
    ]
    with_csrf = [f for f in findings if "cerrar-sesion" in (f.target_url or "")]
    assert len(with_csrf) == 1
    assert with_csrf[0].severity == "info"
    assert with_csrf[0].csrf_present is True


def test_detect_logout_post_without_csrf_is_weakness():
    findings = [
        f for f in detect_logout_behavior(LOGOUT_HTML, "https://example.com/")
        if f.method == "POST"
    ]
    no_csrf = [f for f in findings if "/signout" in (f.target_url or "")]
    assert len(no_csrf) == 1
    assert no_csrf[0].severity == "medium"
    assert no_csrf[0].csrf_present is False
    assert "csrf" in no_csrf[0].title.lower()


def test_detect_logout_link_is_weakness():
    findings = [
        f for f in detect_logout_behavior(LOGOUT_HTML, "https://example.com/")
        if f.evidence and f.evidence["source"] == "link"
    ]
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].method == "GET"
    assert findings[0].target_url == "https://example.com/salir"


def test_detect_logout_ignores_unrelated_links():
    html = '<a href="/settings">Settings</a><a href="/download">Download</a>'
    assert detect_logout_behavior(html, "https://example.com/") == []


def test_session_finding_severities_follow_xwa_sdk_scale():
    findings = detect_logout_behavior(LOGOUT_HTML, "https://example.com/")
    for finding in findings:
        assert finding.severity in SEVERITIES


# ── Cookie domain scope mapping ──────────────────────────────────────────────

def _cookie(name="sessionid", domain=None):
    return SessionCookieData(
        name=name,
        value_preview="abc123",
        domain=domain,
        path="/",
        http_only=True,
        secure=True,
        same_site="Lax",
        max_age="3600",
    )


def test_cookie_domain_parent_widens_scope():
    findings = analyze_cookie_domain_scope(
        [_cookie(domain=".example.com")], "www.example.com"
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "domain_scope"
    assert finding.severity == "medium"
    covered = finding.evidence["covered_subdomains"]
    assert "example.com" in covered
    assert "*.example.com" in covered
    assert finding.evidence["host"] == "www.example.com"


def test_cookie_domain_leading_dot_same_host_is_low():
    findings = analyze_cookie_domain_scope([_cookie(domain=".example.com")], "example.com")
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].evidence["leading_dot"] is True


def test_cookie_domain_same_host_not_flagged():
    assert analyze_cookie_domain_scope([_cookie(domain="example.com")], "example.com") == []


def test_cookie_domain_subdomain_narrowing_not_flagged():
    assert (
        analyze_cookie_domain_scope([_cookie(domain="www.example.com")], "example.com")
        == []
    )


def test_cookie_domain_foreign_domain_is_high():
    findings = analyze_cookie_domain_scope([_cookie(domain="example.org")], "example.com")
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "outside the host" in findings[0].title.lower()


def test_cookie_domain_missing_not_flagged():
    assert analyze_cookie_domain_scope([_cookie(domain=None)], "example.com") == []
