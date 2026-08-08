"""Form discovery core — phase 1: fetch a target and extract forms with their fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import httpx
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class TargetError(Exception):
    """Raised when the target cannot be fetched or parsed."""


@dataclass
class FormFieldData:
    name: str | None
    input_type: str | None
    required: bool
    autocomplete: str | None
    placeholder: str | None


@dataclass
class FormData:
    page_url: str
    action: str | None
    method: str
    enctype: str | None
    is_secure: bool
    fields: List[FormFieldData] = field(default_factory=list)


async def fetch_html(target: str, timeout: float = 20.0) -> tuple[str, str]:
    """Fetch the target and return (final_url, html)."""
    url = target if "://" in target else f"https://{target}"
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": DEFAULT_USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return str(response.url), response.text
    except httpx.HTTPError as exc:
        raise TargetError(f"Failed to fetch target: {exc}") from exc


def parse_forms(final_url: str, html: str) -> List[FormData]:
    """Extract forms and fields from HTML."""
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
                if input_type in ("submit", "button", "image", "reset"):
                    continue
            elif control.name == "textarea":
                input_type = "textarea"
            else:
                input_type = "select"

            fields.append(
                FormFieldData(
                    name=name,
                    input_type=input_type,
                    required=control.get("required") is not None,
                    autocomplete=control.get("autocomplete"),
                    placeholder=control.get("placeholder"),
                )
            )

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


async def discover(target: str) -> tuple[str, str, List[FormData]]:
    """Fetch a target and return (final_url, title, forms)."""
    final_url, html = await fetch_html(target)
    forms = parse_forms(final_url, html)
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    return final_url, title, forms
