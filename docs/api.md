# API Reference

Base URL (local): `http://localhost:8000`. OpenAPI/Swagger UI: `http://localhost:8000/docs`.

## REST

### GET /

Service information.

```json
{
  "status": "ok",
  "service": "azuma",
  "version": "0.2.0"
}
```

### GET /api/health

Health check including database connectivity.

```json
{
  "status": "ok",
  "database": "ok",
  "version": "0.2.0"
}
```

`database` is `error` when the engine cannot execute a query (for example PostgreSQL not reachable).

### POST /api/auth/token

Issues a signed JWT (HS256). Only available when `AZUMA_JWT_SECRET` is set; returns `403` when auth is disabled.

Request:

```json
{ "password": "..." }
```

Response `200 OK`:

```json
{
  "token": "<jwt>",
  "expires_in": 86400
}
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

### GET /api/analyses/{id}/export

Full analysis as a downloadable JSON document (`Content-Disposition: attachment`). Same shape as the detail endpoint, minus internal ids. `404` when not found.

### POST /api/forms/discover

Runs form discovery on a target and persists the results.

Request:

```json
{
  "target": "https://example.com"
}
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

Errors:

| Status | Condition |
|--------|-----------|
| `422` | Missing or empty `target` (request validation) |
| `502` | The target could not be fetched (DNS, connection, HTTP error status) — body carries `detail` |

The `analysis.status` field is `ERROR` and `error_message` is populated when the fetch fails before the response is returned.

## WebSocket

### WS /api/forms/live?target=...

Streams discovery progress. Query parameter `target` is required.

Events (xwa-sdk `Event` envelope):

```json
{
  "seq": 1,
  "type": "analysis_started",
  "tool": "azuma",
  "analysis_id": "https://example.com",
  "ts": "2026-08-08T10:00:00Z",
  "payload": { "target": "https://example.com" }
}
```

| seq order | type | payload |
|-----------|------|---------|
| 1 | `analysis_started` | `{ "target": ... }` |
| 2 | `analysis_progress` | `{ "page": <final URL>, "title": <page title> }` |
| 3..n | `item_found` | one form object per discovered form (same shape as `forms[]` above) |
| n+1 | `analysis_completed` | `{ "form_count": <int> }` |

On fetch failure the terminal event is `analysis_error` with `{ "code": "TARGET_ERROR", "message": ... }`. The server closes the connection after the terminal event.

## Authentication

When `AZUMA_JWT_SECRET` is set, every `/api/*` route except `/`, `/api/health` and `/api/auth/token` requires an `Authorization: Bearer <token>` header. Tokens are HS256-signed, valid for 24 hours. When the secret is unset (default), the API is open.

## Rate limiting

All routes share an in-memory sliding window: `AZUMA_RATE_LIMIT_MAX` requests per client IP per 60 s (default 30). Exceeding the limit returns `429`.
