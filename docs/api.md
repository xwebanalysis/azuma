# API Reference

Base URL (local): `http://localhost:8000`. OpenAPI/Swagger UI: `http://localhost:8000/docs`.

## REST

### GET /

Service information.

```json
{
  "status": "ok",
  "service": "azuma",
  "version": "0.1.0"
}
```

### GET /api/health

Health check including database connectivity.

```json
{
  "status": "ok",
  "database": "ok",
  "version": "0.1.0"
}
```

`database` is `error` when the engine cannot execute a query (for example PostgreSQL not reachable).

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
        "fields": [
          {
            "id": 1,
            "name": "search",
            "input_type": "search",
            "required": false,
            "autocomplete": null,
            "placeholder": null
          }
        ]
      }
    ]
  },
  "form_count": 1
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
