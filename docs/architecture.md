# Architecture

## Overview

Azuma is a two-tier web application: an Angular single-page application in the frontend and a FastAPI service in the backend. The backend owns all analysis logic and persistence; the frontend is a thin client that triggers analysis and renders results.

```
+--------------------+      HTTP/JSON       +---------------------------+
| Angular 22 SPA     | -------------------> | FastAPI (uvicorn)          |
| (localhost:4230)   | <------------------- | (localhost:8030)           |
+--------------------+    WebSocket        +--------------+-------------+
                                                    |     |
                                                    v     v
                                              SQLite (default) / PostgreSQL
```

## Backend

Layout:

```
backend/
├── app/
│   ├── __init__.py
│   ├── analyzer.py      # target fetching and HTML parsing
│   ├── database.py      # SQLite default/PostgreSQL switch, ping, PRAGMAs
│   ├── main.py          # FastAPI app, REST routes, WebSocket endpoint
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic v2 request/response models
│   └── security.py      # CORS config, optional JWT auth, rate limiting
├── tests/               # analyzer unit tests + API integration tests
├── Dockerfile           # python:3.13-slim (PostgreSQL mode)
├── requirements.txt             # runtime (SQLite by default)
├── requirements-postgres.txt    # + psycopg2-binary (docker mode)
└── requirements-dev.txt         # + pytest/anyio (tests)
```

### Components

- **main.py** — application factory, configurable CORS, database initialization on startup via the lifespan hook, global exception handlers that convert errors into the xwa-sdk `Error` envelope, service version in `SERVICE_VERSION`.
- **analyzer.py** — the analysis core:
  - `fetch_html(target)` — resolves the target (adding `https://` when the scheme is missing), follows redirects, returns the response and HTML.
  - `parse_forms(final_url, html)` — extracts every `<form>` with its fields using BeautifulSoup with the `lxml` parser.
  - `analyze_target(target)` — orchestrates fetch, form parsing, CSRF flagging, GET redirect tracing, OAuth/OIDC detection (HTML params plus well-known discovery documents) and session cookie profiling.
  - Field classification: inputs are classified by `type` (submit/button/image/reset controls are skipped), textareas as `textarea`, selects as `select`. The `required`, `autocomplete` and `placeholder` attributes are captured.
- **models.py** — **five tables**:
  - `form_analyses` — the analysis session (target, status, timestamps, error message).
  - `forms` — one row per discovered form (page URL, action, method, enctype, secure flag, redirect chain).
  - `form_fields` — one row per field (name, input type, value, required, autocomplete, placeholder, CSRF flag).
  - `oauth_flows` — one row per detected OAuth/OIDC endpoint (flow type, client id, redirect URI, scope, state usage, weaknesses).
  - `session_cookies` — one row per profiled cookie (name, value preview, domain, path, flags, SameSite, Max-Age).
- **database.py** — SQLite by default (`DB_DRIVER=sqlite`, path `DB_PATH`) or PostgreSQL (`DB_DRIVER=postgresql`). SQLite connections enable `foreign_keys`, `journal_mode=WAL` and `busy_timeout=5000`; `ping()` backs the health endpoint.
- **schemas.py** — Pydantic v2 models with `from_attributes`, used for typed API responses.
- **security.py** — `cors_settings()` builds the CORSMiddleware arguments from `XWA_CORS_ORIGINS` (localhost/LAN regex by default, credentials disabled), `auth_middleware` enforces an optional HS256 Bearer token, `rate_limit_middleware` implements a 120 req/min sliding window (`/api/health` exempt), and `validate_ws_token()` guards WebSockets via `?token=`.

### Analysis flow

1. The client calls `POST /api/forms/discover` with a target.
2. A `FormAnalysis` row is created with status `RUNNING`.
3. The pipeline runs: fetch and parse forms, flag CSRF tokens, trace GET redirect chains, detect OAuth/OIDC endpoints, profile session cookies from `Set-Cookie`.
4. Results are persisted (forms, fields, OAuth flows, session cookies) and linked to the analysis.
5. The analysis is marked `COMPLETED` (or `ERROR` with an error message, returning a `502` envelope) and returned.

A WebSocket variant (`/api/forms/live`) persists the analysis first and streams
xwa-sdk `Event` envelopes with the **persisted id** as `analysis_id` (string),
monotonic `seq` and UTC `ts`: `analysis_started`, `analysis_progress`, one
`item_found` per form / OAuth flow / session cookie, `analysis_completed` or
`analysis_error`.

## Frontend

Layout (core / shared / features):

```
frontend/
├── src/
│   ├── app/
│   │   ├── app.config.ts       # providers (router, HttpClient)
│   │   ├── app.routes.ts       # lazy routes: '', 'history', 'history/:id', 'exports'
│   │   ├── app.ts/html/scss    # sidebar shell: brand, nav, health, theme, locale
│   │   ├── core/
│   │   │   ├── api.service.ts  # typed REST/WS client + xwa-sdk Event types
│   │   │   ├── live.service.ts # WebSocket wrapper + parseLiveEvent()
│   │   │   ├── export.service.ts # client JSON/CSV/PDF (jsPDF lazy)
│   │   │   ├── i18n.service.ts # en/es labels (Angular Signals)
│   │   │   └── theme.service.ts# dark/light mode with Angular Signals
│   │   ├── shared/
│   │   │   ├── terminal/       # live log panel
│   │   │   ├── metric-card/    # Doto hero metric
│   │   │   ├── status-badge/   # PENDING/RUNNING/COMPLETED/ERROR
│   │   │   ├── export-actions/ # client JSON/CSV/PDF + server JSON/CSV
│   │   │   └── detail-table/   # generic flat data table
│   │   └── features/
│   │       ├── analyzer/       # target input, REST + WS runs, phase row, terminal
│   │       ├── history/        # list + detail (forms, OAuth flows, cookies)
│   │       └── exports/        # export console for recent analyses
│   ├── environments/
│   │   └── environment.ts      # apiBaseUrl / wsBaseUrl (host resolved at runtime)
│   ├── _fonts.scss             # self-hosted Doto / Space Grotesk / Space Mono
│   ├── styles.scss             # Nothing tokens (incl. --gold)
│   └── index.html              # no Google Fonts at runtime
├── public/fonts/               # woff2 files served as static assets
├── scripts/test.sh         # maps `npm test -- --run` onto the Angular builder
├── Dockerfile              # node:24 (dev server)
├── nginx.conf              # SPA fallback for production serving
└── package.json            # Angular 22.1 + jsPDF
```

- Standalone components with the modern control-flow syntax (`@if`, `@for`, `@empty`).
- The UI follows the **Nothing Design System** (shared across XWA modules): monochrome instrument-panel dark mode with a light "printed manual" mode, Doto / Space Grotesk / Space Mono typography, dot-grid motif, all-caps monospace labels, flat surfaces and no shadows or gradients. Tokens (including `--gold`) live in `src/styles.scss`; fonts are self-hosted from `public/fonts`; `ThemeService` manages dark/light mode with Angular Signals.
- Navigation is a left sidebar with three lazy routes: analyzer (`/`), history
  list/detail (`/history`, `/history/:id`) and the exports console (`/exports`).
- **Live WebSocket**: the analyzer can run `/api/forms/live` and consumes the
  xwa-sdk `Event` envelopes (`analysis_started`, `analysis_progress`,
  `item_found` for forms/OAuth/cookies, `analysis_completed`, `analysis_error`)
  through `LiveService`; `parseLiveEvent()` validates each frame. The
  synchronous `POST /api/forms/discover` remains as fallback.
- **Exports**: client-side JSON/CSV/PDF (PDF via lazily imported jsPDF) plus
  server-side JSON/CSV links to `/api/analyses/{id}/export`; the exports console
  applies the same actions to any recent analysis.
- `ApiService` reads `environment.apiBaseUrl` / `environment.wsBaseUrl` (host
  resolved at runtime, backend port `8030`).

## Data contracts

Live stream events conform to the xwa-sdk `Event` schema (seq, type, tool,
analysis_id, ts, payload) and REST errors use the xwa-sdk `Error` envelope. The
backend consumes the `xwa-sdk` Python package installed local-first by
`azuma.sh` (editable sibling repo) with the git fallback documented in
`requirements.txt`.

## Roadmap decision: session fixation

`ROADMAP.md` previously marked "Detect session fixation and hijacking
indicators" as done. Hijacking *indicators* are covered by the cookie flag
profiling (HttpOnly/Secure/SameSite), but true fixation detection requires
observing whether the session cookie **rotates after an authentication
transition**, which needs stateful pre/post-login requests and credentials. In
the current passive single-fetch model that is not possible, so the item is
back to `[ ]` and tracked as future work (stateful authenticated flows).
