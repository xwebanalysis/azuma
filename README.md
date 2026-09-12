<h1 align="center">Azuma</h1>

<div align="center">
<p><em>Web form and authentication flow analyzer — part of the <a href="https://github.com/xwebanalysis">XWA ecosystem</a></em></p>
</div>

<hr>

<p><strong>Status: <em>In development</em></strong> (v0.3.0)</p>

<p>Discovery and analysis of web forms and authentication flows: form mapping, OAuth flows, session and cookie analysis, live streaming and server-side exports.</p>

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Angular 22 (standalone, SCSS, Node 24) |
| Backend | FastAPI (Python 3.13) + SQLAlchemy 2 + SQLite (PostgreSQL optional) |
| Data contracts | xwa-sdk (shared `Event`/`Error` envelopes) |

## Features (current)

- Form discovery: fetch a target, extract forms, actions, methods and fields
- CSRF detection: hidden fields and token placement flagged by name and value heuristics
- Redirect chains: GET form actions traced with bounded hop tracking
- OAuth / OIDC mapping: authorization endpoints from HTML parameters and well-known discovery documents, with flow classification and weakness flags (implicit flow, missing state, suspicious redirect_uri)
- Session analysis: Set-Cookie profiling (HttpOnly, Secure, SameSite, Max-Age, session-relevant filtering)
- Live streaming of pipeline progress as xwa-sdk Events over WebSocket (`/api/forms/live`) with the persisted analysis id, rendered in the UI terminal and phase row
- REST API with persisted history, detail, delete (one/all) and server-side JSON/CSV export, plus client-side JSON/CSV/PDF (jsPDF, lazy-loaded)
- Angular UI structured as `core/` + `shared/` + `features/` with lazy routes and a sidebar: analyzer (`/`), history list/detail (`/history`, `/history/:id`) and exports console (`/exports`)
- Nothing Design System: self-hosted Doto / Space Grotesk / Space Mono fonts, `--gold` token, dark/light mode, ALL CAPS labels
- Optional JWT authentication and in-memory rate limiting (default 120/min)
- Configurable CORS (`XWA_CORS_ORIGINS`) with credentials disabled

## Quick start (local, default)

```bash
./azuma.sh local all        # backend :8030 (SQLite) + frontend :4230
```

or in two terminals:

```bash
./azuma.sh local backend    # terminal 1 — FastAPI on :8030 (SQLite)
./azuma.sh local frontend   # terminal 2 — Angular on :4230
```

- Frontend: http://localhost:4230
- Backend API: http://localhost:8030
- Swagger docs: http://localhost:8030/docs
- SQLite database: `backend/azuma.db` (WAL, foreign keys, busy timeout 5000 ms)

The script creates/updates `backend/.venv` with `uv` (Python 3.13), installs the
sibling `xwa-sdk` binding in editable mode when available, and falls back to the
git repository documented in `backend/requirements.txt` otherwise.

## Quick start (Docker, PostgreSQL)

```bash
./azuma.sh docker all       # frontend :4230, backend :8030, PostgreSQL :5443
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/api/health` | Health check with real database status (`200`/`503`) |
| POST | `/api/forms/discover` | Run the full analysis pipeline on a target |
| GET | `/api/analyses` | List the 50 most recent analyses |
| GET | `/api/analyses/{id}` | Analysis detail |
| GET | `/api/analyses/{id}/export?format=json\|csv` | Download full analysis (attachment) |
| DELETE | `/api/analyses/{id}` | Delete one analysis |
| DELETE | `/api/analyses` | Delete all analyses |
| POST | `/api/auth/token` | Issue a JWT (when `AZUMA_JWT_SECRET` is set) |
| WS | `/api/forms/live?target=...` | Stream discovery events (xwa-sdk `Event`) |

## Project layout

```
backend/
├── app/
│   ├── analyzer.py      # fetch + HTML parsing (httpx + BeautifulSoup/lxml)
│   ├── database.py      # SQLite default/PostgreSQL switch, ping, PRAGMAs
│   ├── main.py          # FastAPI app, REST + WebSocket
│   ├── models.py        # FormAnalysis, Form, FormField, OAuthFlow, SessionCookie
│   ├── schemas.py       # Pydantic v2 response models
│   └── security.py      # CORS, optional JWT auth, rate limiting
└── requirements*.txt
frontend/
├── src/app/
│   ├── core/            # api.service, live.service (parseLiveEvent), export.service, theme, i18n
│   ├── shared/          # terminal, metric-card, status-badge, export-actions, detail-table
│   ├── features/        # analyzer, history (list + detail), exports
│   ├── app.ts/html/scss # sidebar shell with lazy router outlets
│   └── environments/environment.ts
├── public/fonts/        # self-hosted woff2 (Doto, Space Grotesk, Space Mono)
└── package.json         # Angular 22 + jsPDF
```

## Documentation

- [docs/README.md](docs/README.md) — documentation index
- [docs/architecture.md](docs/architecture.md) — stack, layout and data flow
- [docs/api.md](docs/api.md) — REST and WebSocket API reference
- [docs/development.md](docs/development.md) — execution modes, environment variables, verification

## Roadmap

See [ROADMAP.md](ROADMAP.md) — next: session fixation analysis (requires stateful flows), logout/subdomain session mapping.
