"""Security middleware: optional JWT auth and in-memory rate limiting."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

import jwt as pyjwt
from fastapi import Request
from fastapi.responses import JSONResponse

JWT_SECRET = os.getenv("AZUMA_JWT_SECRET") or None
AUTH_PASSWORD = os.getenv("AZUMA_AUTH_PASSWORD", "azuma")
TOKEN_TTL_HOURS = 24

RATE_LIMIT_MAX = int(os.getenv("AZUMA_RATE_LIMIT_MAX", "30"))
RATE_LIMIT_WINDOW = 60.0

_hits: dict[str, deque[float]] = defaultdict(deque)

EXEMPT_PATHS = {
    "/",
    "/api/health",
    "/api/auth/token",
    "/docs",
    "/redoc",
    "/openapi.json",
}

AUTH_REQUIRED = JWT_SECRET is not None


def is_exempt(path: str) -> bool:
    return path in EXEMPT_PATHS


async def rate_limit_middleware(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _hits[client]
    while hits and now - hits[0] > RATE_LIMIT_WINDOW:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded, try again later."})
    hits.append(now)
    return await call_next(request)


async def auth_middleware(request: Request, call_next):
    if not AUTH_REQUIRED or is_exempt(request.url.path):
        return await call_next(request)

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing bearer token."})
    try:
        pyjwt.decode(auth.removeprefix("Bearer ").strip(), JWT_SECRET, algorithms=["HS256"])
    except pyjwt.PyJWTError:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token."})
    return await call_next(request)


def issue_token() -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "azuma-user", "iat": now, "exp": now + TOKEN_TTL_HOURS * 3600},
        JWT_SECRET,
        algorithm="HS256",
    )
