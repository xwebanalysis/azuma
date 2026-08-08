"""Unit tests for azuma analyzer (no network)."""

import httpx
import pytest

from app.analyzer import (
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
