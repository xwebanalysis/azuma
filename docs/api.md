# API Reference

Base URL (local): `http://localhost:8030`. OpenAPI/Swagger UI: `http://localhost:8030/docs`.

## Conventions

- Responses use JSON. Timestamps in events are UTC ISO-8601 (`+00:00`).
- Errors follow the xwa-sdk `Error` envelope:

```json
{
  "error": {
    "code": "UPSTREAM_ERROR",
    "message": "Failed to fetch target: ...",
    "detail": null,
    "retryable": true
  }
}
```

| Status | Code | Condition |
|--------|------|-----------|
| `401` | `UNAUTHORIZED` | Bearer token missing/invalid (only when auth is enabled) |
| `404` | `NOT_FOUND` | Analysis does not exist |
| `422` | `VALIDATION_ERROR` | Request/query validation failed |
| `429` | `RATE_LIMITED` | Rate limit exceeded (default 120 req/min per IP; `/api/health` exempt) |
| `502` | `UPSTREAM_ERROR` | Target fetch failed (DNS, TLS, non-2xx) |
| `503` | `SERVICE_UNAVAILABLE` | Database not reachable (`/api/health`) |

CORS is configurable through `XWA_CORS_ORIGINS` (comma-separated origins); when
unset, localhost and private LAN ranges are allowed. Credentials are disabled —
use `Authorization: Bearer`.

## REST

### GET /

Service information.

```json
{ "status": "ok", "service": "azuma", "version": "0.3.0" }
```

### GET /api/health

Health check including real database connectivity. Returns `200` when the
database answers and `503` otherwise (the `status` and `database` fields both
become `"error"`).

```json
{ "status": "ok", "database": "ok", "version": "0.3.0", "tool": "azuma" }
```

### POST /api/auth/token

Issues a signed JWT (HS256). Only available when `AZUMA_JWT_SECRET` is set;
returns `403` when auth is disabled.

Request:

```json
{ "password": "..." }
```

Response `200 OK`:

```json
{ "token": "<jwt>", "expires_in": 86400 }
```

### GET /api/analyses

Lists the 50 most recent analyses.

```json
[
  {
    "id": 1,
    "target": "https://example.com",
    "status": "COMPLETED",
    "analysis_type": "form_scan",
    "created_at": "2026-08-08T10:00:00Z",
    "form_count": 1,
    "oauth_flow_count": 0,
    "session_cookie_count": 1
  }
]
```

### GET /api/analyses/{id}

Full analysis detail (forms with fields, OAuth flows, session cookies). `404` when not found.

### GET /api/analyses/{id}/export?format=json|csv

Downloadable export with `Content-Disposition: attachment`:

- `format=json` (default) — same shape as the detail endpoint, minus internal ids; `azuma-analysis-<id>.json`.
- `format=csv` — one row per entity (`kind` column): forms (one row per field), OAuth flows and session cookies; `azuma-analysis-<id>.csv`.

Any other `format` value returns `422`. `404` when not found.

### DELETE /api/analyses/{id}

Deletes one analysis and all its forms, fields, OAuth flows and cookies.
Returns `204`; `404` when not found.

### DELETE /api/analyses

Deletes all analyses and their child rows. Returns `204`.

### POST /api/forms/discover

Runs form discovery on a target and persists the results.

Request:

```json
{ "target": "https://example.com" }
```

- `target` — domain or full URL. A missing scheme is completed with `https://`.

Response `200 OK`:

```json
{
  "analysis": {
    "id": 1,
    "target": "https://example.com",
    "status": "COMPLETED",
    "analysis_type": "form_scan",
    "created_at": "2026-08-08T10:00:00Z",
    "started_at": "2026-08-08T10:00:00Z",
    "finished_at": "2026-08-08T10:00:02Z",
    "error_message": null,
    "forms": [
      {
        "id": 1,
        "page_url": "https://example.com/",
        "action": "/search",
        "method": "GET",
        "enctype": null,
        "is_secure": false,
        "redirect_chain": null,
        "fields": [
          {
            "id": 1,
            "name": "search",
            "input_type": "search",
            "value": null,
            "required": false,
            "autocomplete": null,
            "placeholder": null,
            "is_csrf": false
          }
        ]
      }
    ],
    "oauth_flows": [],
    "session_cookies": [
      {
        "id": 1,
        "name": "sessionid",
        "value_preview": "abc123",
        "domain": null,
        "path": "/",
        "http_only": true,
        "secure": true,
        "same_site": "Lax",
        "max_age": "3600"
      }
    ]
  },
  "form_count": 1,
  "oauth_flow_count": 0,
  "session_cookie_count": 1
}
```

On fetch failure the analysis is stored with status `ERROR`/`error_message` and
the request returns `502` with the error envelope.

## WebSocket

### WS /api/forms/live?target=...

Persists the analysis and streams discovery progress. Query parameters:
`target` (required) and `token` (required only when `AZUMA_JWT_SECRET` is set —
WebSocket clients cannot send headers).

Every message is an xwa-sdk `Event` envelope. `analysis_id` is the **persisted
analysis id serialized as a string** (never the target), `seq` starts at 1 and
is monotonic, and `ts` is UTC ISO-8601.

```json
{
  "seq": 1,
  "type": "analysis_started",
  "tool": "azuma",
  "analysis_id": "42",
  "ts": "2026-08-08T10:00:00.123456+00:00",
  "payload": { "target": "https://example.com" }
}
```

| seq order | type | payload |
|-----------|------|---------|
| 1 | `analysis_started` | `{ "target": ... }` |
| 2 | `analysis_progress` | `{ "page": <final URL>, "title": <page title> }` |
| 3..n | `item_found` | one per form / OAuth flow / session cookie |
| n+1 | `analysis_completed` | `{ "form_count": ..., "oauth_flow_count": ..., "session_cookie_count": ... }` |

On fetch failure the analysis is marked `ERROR`, a terminal `analysis_error`
event is sent with the xwa-sdk `Error` shape
(`{ "code": "TARGET_ERROR", "message": ..., "retryable": true }`), and the
server closes the connection. If the client disconnects mid-run the analysis is
marked `CANCELLED`.

## Authentication and rate limiting

- When `AZUMA_JWT_SECRET` is set, every `/api/*` route except `/`, `/api/health`
  and `/api/auth/token` requires an `Authorization: Bearer <token>` header
  (HS256, 24 h). When unset (default) the API is open.
- All non-exempt routes share an in-memory sliding window:
  `AZUMA_RATE_LIMIT_MAX` requests per client IP per 60 s (default `120`).

## Frontend consumption

The Angular UI (port `4230`) uses these endpoints as follows:

- `/api/health` — sidebar `BACKEND ONLINE` indicator on startup.
- `POST /api/forms/discover` — **ANALYZE** button (synchronous fallback).
- `WS /api/forms/live` — **LIVE STREAM** button; frames are validated by
  `parseLiveEvent()` in `core/live.service.ts` and rendered in the terminal and
  phase row (fetch → forms → OAuth → cookies). On `analysis_completed` the UI
  fetches the persisted analysis with `GET /api/analyses/{id}` and renders the
  detail view (forms accordion, OAuth and cookie tables).
- `GET /api/analyses` — history list and exports console.
- `GET /api/analyses/{id}/export?format=json|csv` — `SERVER` links in the
  export actions; additionally the client builds JSON/CSV/PDF files locally with
  `core/export.service.ts` (PDF via lazily imported jsPDF).
- `DELETE /api/analyses/{id}` and `DELETE /api/analyses` — history actions.
