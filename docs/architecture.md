# Architecture

## Overview

Azuma is a two-tier web application: an Angular single-page application in the frontend and a FastAPI service in the backend. The backend owns all analysis logic and persistence; the frontend is a thin client that triggers analysis and renders results.

```
+--------------------+      HTTP/JSON       +---------------------------+
| Angular 22 SPA     | -------------------> | FastAPI (uvicorn)          |
| (localhost:4200)   | <------------------- | (localhost:8000)           |
+--------------------+    WebSocket        +--------------+-------------+
                                                    |     |          |
                                                    v     v          v
                                                 SQLite / PostgreSQL  (persistence)
```

## Backend

Layout:

```
backend/
├── app/
│   ├── __init__.py
│   ├── analyzer.py      # target fetching and HTML parsing
│   ├── database.py      # engine setup, SQLite/PostgreSQL switch
│   ├── main.py          # FastAPI app, REST routes, WebSocket endpoint
│   ├── models.py        # SQLAlchemy ORM models
│   └── schemas.py       # Pydantic v2 request/response models
├── Dockerfile           # python:3.13-slim
└── requirements.txt
```

### Components

- **main.py** — application factory, CORS (open during development), database initialization on startup via the lifespan hook, service version in `SERVICE_VERSION`.
- **analyzer.py** — the analysis core:
  - `fetch_html(target)` — resolves the target (adding `https://` when the scheme is missing), follows redirects, returns the final URL and the HTML.
  - `parse_forms(final_url, html)` — extracts every `<form>` with its fields using BeautifulSoup with the `lxml` parser.
  - `discover(target)` — orchestrates fetch and parse, returns the final URL, page title and form data.
  - Field classification: inputs are classified by `type` (submit/button/image/reset controls are skipped), textareas as `textarea`, selects as `select`. The `required`, `autocomplete` and `placeholder` attributes are captured.
- **models.py** — three tables:
  - `form_analyses` — the analysis session (target, status, timestamps, error message).
  - `forms` — one row per discovered form (page URL, action, method, enctype, secure flag).
  - `form_fields` — one row per field (name, input type, required, autocomplete, placeholder).
- **database.py** — selects SQLite (`DB_DRIVER=sqlite`) or PostgreSQL by environment. SQLite mode enables WAL and foreign keys.
- **schemas.py** — Pydantic v2 models with `from_attributes`, used for typed API responses.

### Analysis flow

1. The client calls `POST /api/forms/discover` with a target.
2. A `FormAnalysis` row is created with status `RUNNING`.
3. The pipeline runs: fetch and parse forms, flag CSRF tokens, trace GET redirect chains, detect OAuth/OIDC endpoints (HTML params plus well-known discovery documents), profile session cookies from `Set-Cookie`.
4. Results are persisted (forms, fields, OAuth flows, session cookies) and linked to the analysis.
5. The analysis is marked `COMPLETED` (or `ERROR` with an error message) and returned.

A WebSocket variant (`/api/forms/live`) performs the same analysis while streaming xwa-sdk `Event` envelopes: `analysis_started`, `analysis_progress`, one `item_found` per form / OAuth flow / session cookie, `analysis_completed` or `analysis_error`.

### Security middleware

- `security.py` provides two `http` middlewares. When `AZUMA_JWT_SECRET` is set, routes require an HS256 Bearer token (`POST /api/auth/token` issues one). A sliding-window rate limiter caps requests per client IP (`AZUMA_RATE_LIMIT_MAX`, default 30/min).

## Frontend

Layout:

```
frontend/
├── src/
│   ├── app/
│   │   ├── app.config.ts       # providers (router, HttpClient)
│   │   ├── app.routes.ts
│   │   ├── app.ts              # dashboard component (signal state)
│   │   ├── app.html            # target form, form cards, field tables
│   │   ├── app.scss            # dark terminal-style theme
│   │   ├── app.spec.ts
│   │   └── services/
│   │       └── api.service.ts  # typed REST client (health, discover)
│   └── index.html
├── Dockerfile                  # node:24
├── nginx.conf                  # SPA fallback for production serving
└── package.json                # Angular 22.1
```

- Standalone components with the modern control-flow syntax (`@if`, `@for`, `@empty`).
- The UI follows the **Nothing Design System** (shared across XWA modules): monochrome instrument-panel dark mode with a light "printed manual" mode, Doto / Space Grotesk / Space Mono typography, dot-grid motif, all-caps monospace labels, flat surfaces and no shadows or gradients. Design tokens live in `src/styles.scss`; `ThemeService` manages dark/light mode with Angular Signals.
- `ApiService` targets `http://<current hostname>:8000` (CORS is open in development).
- The dashboard shows backend health, runs discovery and renders forms as accordion panels with field tables.

## Data contracts

Live stream events conform to the xwa-sdk `Event` schema (seq, type, tool, analysis_id, ts, payload). The backend consumes the `xwa-sdk` Python package installed from the XWA SDK repository, which makes Azuma the first module of the ecosystem using the shared contracts.
