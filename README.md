<h1 align="center">Azuma</h1>

<div align="center">
<p><em>Web form and authentication flow analyzer — part of the <a href="https://github.com/xwebanalysis">XWA ecosystem</a></em></p>
</div>

<hr>

<p><strong>Status: <em>In development</em></strong> (v0.2.0)</p>

<p>Discovery and analysis of web forms and authentication flows: form mapping, OAuth flows, session and cookie analysis.</p>

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Angular 22 (standalone, SCSS, Node 24) |
| Backend | FastAPI (Python 3.12+) + SQLAlchemy 2 + PostgreSQL/SQLite |
| Data contracts | xwa-sdk (Event envelope over WebSocket) |

## Features (current)

- Form discovery: fetch a target, extract forms, actions, methods and fields
- CSRF detection: hidden fields and token placement flagged by name and value heuristics
- Redirect chains: GET form actions traced with bounded hop tracking
- OAuth / OIDC mapping: authorization endpoints from HTML parameters and well-known discovery documents, with flow classification and weakness flags (implicit flow, missing state, suspicious redirect_uri)
- Session analysis: Set-Cookie profiling (HttpOnly, Secure, SameSite, Max-Age, session-relevant filtering)
- Live streaming of pipeline progress as xwa-sdk Events over WebSocket (`/api/forms/live`)
- REST API with persisted analysis history, detail and JSON export endpoints
- Optional JWT authentication and in-memory rate limiting (see docs/development.md)

## Quick start (Docker)

```bash
./azuma.sh docker all
```

- Frontend: http://localhost:4200
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs

## Quick start (local)

```bash
./azuma.sh local backend    # terminal 1 — FastAPI on :8000 (SQLite)
./azuma.sh local frontend   # terminal 2 — Angular on :4200
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/api/health` | Health check with database status |
| POST | `/api/forms/discover` | Run the full analysis pipeline on a target |
| GET | `/api/analyses` | List the 50 most recent analyses |
| GET | `/api/analyses/{id}` | Analysis detail |
| GET | `/api/analyses/{id}/export` | Download full analysis as JSON |
| POST | `/api/auth/token` | Issue a JWT (when AZUMA_JWT_SECRET is set) |
| WS | `/api/forms/live?target=...` | Stream discovery events (xwa-sdk Event format) |

## Project layout

```
backend/
├── app/
│   ├── analyzer.py      # fetch + HTML parsing (httpx + BeautifulSoup/lxml)
│   ├── database.py      # SQLite/PostgreSQL switch
│   ├── main.py          # FastAPI app, REST + WebSocket
│   ├── models.py        # FormAnalysis, Form, FormField
│   └── schemas.py       # Pydantic v2 response models
└── requirements.txt
frontend/
├── src/app/
│   ├── app.ts           # dashboard component
│   ├── app.html         # target input + form cards
│   └── services/api.service.ts
└── package.json         # Angular 22
```

## Documentation

- [docs/README.md](docs/README.md) — documentation index
- [docs/architecture.md](docs/architecture.md) — stack, layout and data flow
- [docs/api.md](docs/api.md) — REST and WebSocket API reference
- [docs/development.md](docs/development.md) — execution modes, environment variables, verification

## Roadmap

See [ROADMAP.md](ROADMAP.md) — next: OAuth flow mapping, session analysis, production hardening.
