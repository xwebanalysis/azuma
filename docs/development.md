# Development

## Requirements

| Component | Requirement |
|-----------|-------------|
| Node.js | >= 24.15 (Angular 22 CLI minimum) |
| Python | 3.13 (managed with `uv`); the Docker image uses 3.13 |
| uv | `~/.local/bin/uv` (used to create the venv and install packages) |
| Docker | optional — only for the compose mode |
| Database | none for local mode (SQLite); PostgreSQL 17 for docker mode |

## Execution modes

`azuma.sh` is the entry point. `local` is the default:

| Command | Description |
|---------|-------------|
| `./azuma.sh` | Same as `./azuma.sh local all` |
| `./azuma.sh local all` | Native backend :8030 (SQLite) + frontend :4230 |
| `./azuma.sh local backend` | Backend only, foreground |
| `./azuma.sh local frontend` | Frontend only |
| `./azuma.sh docker all` | Full stack on :4230/:8030 plus PostgreSQL 17 on :5443 |
| `./azuma.sh docker backend` | Backend plus its `depends_on` service (PostgreSQL) |
| `./azuma.sh docker frontend` | Frontend only |

Legacy aliases `--sqlite`, `--native` and `--fast` are accepted as `local`.

The `local` mode:

1. Creates/updates `backend/.venv` with `uv venv --python 3.13 --seed`.
2. Installs `requirements-dev.txt` (runtime + pytest/anyio).
3. Installs the sibling `xwa-sdk` binding in editable mode when
   `/home/x/Documents/xwebanalysis/xwa-sdk/bindings/python` exists; otherwise
   falls back to the git spec documented in `requirements.txt`.
4. Starts uvicorn on :8030 with `DB_DRIVER=sqlite`, waits for `/api/health`,
   then starts Angular on :4230.

Manual equivalents:

```bash
# backend (native, SQLite)
cd backend
~/.local/bin/uv venv --python 3.13 --seed .venv
~/.local/bin/uv pip install --python .venv/bin/python -r requirements-dev.txt
~/.local/bin/uv pip install --python .venv/bin/python -e ../../xwa-sdk/bindings/python
export DB_DRIVER=sqlite DB_PATH=./azuma.db
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8030 --reload

# frontend (native)
cd frontend
npm ci
npm start                        # ng serve --host 0.0.0.0, port 4230 (angular.json)
```

## Environment variables (backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_DRIVER` | `sqlite` | `sqlite` or `postgresql` |
| `DB_PATH` | `./azuma.db` | SQLite database file (used when `DB_DRIVER=sqlite`) |
| `DB_HOST` | `db` | PostgreSQL host |
| `DB_NAME` | `azuma` | PostgreSQL database name |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASS` | `postgres` | PostgreSQL password |
| `XWA_CORS_ORIGINS` | unset | Comma-separated allowed origins; unset = localhost + LAN regex |
| `AZUMA_JWT_SECRET` | unset | When set, all `/api/*` routes require an HS256 Bearer token |
| `AZUMA_AUTH_PASSWORD` | `azuma` | Password accepted by `POST /api/auth/token` |
| `AZUMA_RATE_LIMIT_MAX` | `120` | Requests per client IP per 60 s window (`XWA_RATE_LIMIT_MAX` also accepted) |

`azuma.sh` also honors `AZUMA_BACKEND_PORT`, `AZUMA_FRONTEND_PORT`, `AZUMA_DB_PATH` and `XWA_SDK_DIR`.

Example with auth enabled:

```bash
export AZUMA_JWT_SECRET=change-me-to-at-least-32-bytes
export AZUMA_AUTH_PASSWORD=change-me
./azuma.sh local backend
# obtain a token:
curl -X POST http://localhost:8030/api/auth/token \
  -H 'Content-Type: application/json' -d '{"password":"change-me"}'
# use it:
curl -H 'Authorization: Bearer <token>' http://localhost:8030/api/analyses
# WebSocket (token in the query string):
#   ws://localhost:8030/api/forms/live?target=https://example.com&token=<token>
```

The backend waits for PostgreSQL to become available at startup (30 retries, 1.5 s apart).

## Tests and verification

```bash
# backend tests (isolated SQLite temp DB, no network)
cd backend
.venv/bin/python -m pytest -q

# smoke test
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8030 &
curl -s http://localhost:8030/api/health
curl -s -X POST http://localhost:8030/api/forms/discover \
  -H 'Content-Type: application/json' -d '{"target":"https://example.com"}'
curl -s http://localhost:8030/api/analyses
curl -sD - -o /dev/null "http://localhost:8030/api/analyses/1/export?format=csv"

# frontend
cd frontend
npm ci
npm test -- --run        # vitest via the Angular builder
npm run build
npm audit --omit=dev     # must report 0 vulnerabilities

# browser smoke (Playwright, real Chromium; requires ./azuma.sh local running)
cd ..
/home/x/Documents/xwebanalysis/samurai/backend/.venv/bin/python e2e/browser_smoke.py
```

The frontend test suite covers the typed `ApiService` (REST + URL builders), the
`parseLiveEvent()` xwa-sdk envelope parser, the client CSV export builder, the
analyzer component (REST fallback + live WS form/OAuth/cookie events) and the
app shell/router.

The browser smoke run is the zoneless regression gate: it asserts that shell
health, discovery (REST + WS), history, exports and i18n render without extra
clicks and that the console stays clean. See [../e2e/README.md](../e2e/README.md)
and the change-detection rule in [ui-architecture.md](ui-architecture.md).

The UI is served with self-hosted fonts from `public/fonts` (`src/_fonts.scss`);
`index.html` loads no external font providers. jsPDF is only fetched when a PDF
export is requested (lazy chunk), so the initial bundle stays lean.

WebSocket stream (Python):

```bash
python -m pip install websockets
python - <<'EOF'
import asyncio, json, websockets

async def main():
    async with websockets.connect(
        "ws://localhost:8030/api/forms/live?target=https://en.wikipedia.org"
    ) as ws:
        for _ in range(8):
            print(json.loads(await ws.recv())["type"])

asyncio.run(main())
EOF
```

## Cleanup

```bash
./clean.sh
```

Stops compose services (with volumes) and removes the venv, the SQLite file
(plus `-wal`/`-shm`), `node_modules`, `dist`, `.angular` and caches.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Frontend shows "backend offline" | Backend not running on :8030, or the browser origin is not allowed — use `XWA_CORS_ORIGINS` |
| `502` on discover | Target unreachable (DNS, TLS, non-2xx). Check `error_message` in the response |
| `429` on repeated requests | Rate limit hit (`AZUMA_RATE_LIMIT_MAX`, default 120/min) |
| PostgreSQL connection refused in compose | `db` healthcheck not finished — the backend retries for up to 45 s |
| Angular CLI version mismatch | Node below 24.15 — `azuma.sh` prepends the mise Node 24 directory |
| `xwa-sdk` install fails | Sibling repo missing and no network access to GitHub — see `requirements.txt` for both options |
