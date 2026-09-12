#!/usr/bin/env python3
"""Deterministic HTTP fixture for Azuma browser E2E.

Serves a page with:
  * two forms (POST /login with a CSRF token + password, GET /search)
  * a session cookie (`Set-Cookie: sessionid=abc; HttpOnly; SameSite=Lax`)
  * an OAuth authorize link and a well-known OpenID configuration document

Run standalone:  python fixture_server.py [port]
Default port: 8104
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8104

INDEX_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Azuma Fixture Login</title></head>
<body>
  <h1>Demo App</h1>
  <form method="post" action="/login">
    <input type="hidden" name="csrf_token"
           value="3f9a1c2d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b" />
    <input type="text" name="username" autocomplete="username" required />
    <input type="password" name="password" autocomplete="current-password" required />
    <button type="submit">Sign in</button>
  </form>
  <form method="get" action="/search">
    <input type="text" name="q" placeholder="Search" />
    <button type="submit">Search</button>
  </form>
  <a href="/oauth/authorize?client_id=demo&amp;redirect_uri=https%3A%2F%2Fapp.example%2Fcallback&amp;response_type=code&amp;state=xyz">
    Login with OAuth
  </a>
  <a href="/.well-known/openid-configuration">OpenID configuration</a>
</body>
</html>
"""

SEARCH_HTML = """<!doctype html>
<html><head><title>Search results</title></head>
<body><h1>Results for fixture query</h1></body></html>
"""

OAUTH_HTML = """<!doctype html>
<html><head><title>Authorize demo</title></head>
<body><h1>OAuth consent</h1></body></html>
"""

OPENID_CONFIG = {
    "issuer": "http://127.0.0.1:8104",
    "authorization_endpoint": "http://127.0.0.1:8104/oauth/authorize",
    "token_endpoint": "http://127.0.0.1:8104/oauth/token",
    "end_session_endpoint": "http://127.0.0.1:8104/oauth/logout",
    "response_types_supported": ["code"],
    "subject_types_supported": ["public"],
    "id_token_signing_alg_values_supported": ["RS256"],
}

SESSION_COOKIE = "sessionid=abc; HttpOnly; SameSite=Lax; Path=/"


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "XwaFixture/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        print(f"[azuma-fixture] {fmt % args}", flush=True)

    def _send(
        self,
        status: int,
        body: str | bytes,
        content_type: str = "text/html; charset=utf-8",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        payload = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, INDEX_HTML, extra_headers={"Set-Cookie": SESSION_COOKIE})
        elif path == "/search":
            self._send(200, SEARCH_HTML)
        elif path == "/oauth/authorize":
            self._send(200, OAUTH_HTML)
        elif path == "/.well-known/openid-configuration":
            self._send(200, json.dumps(OPENID_CONFIG), "application/json")
        else:
            self._send(404, "not found")

    do_HEAD = do_GET

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        path = self.path.split("?", 1)[0]
        if path == "/login":
            self._send(
                200,
                "<html><head><title>Welcome</title></head><body>ok</body></html>",
                extra_headers={"Set-Cookie": SESSION_COOKIE},
            )
        else:
            self._send(404, "not found")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), FixtureHandler)
    print(f"[azuma-fixture] listening on http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
