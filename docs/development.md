# Development

## Requirements

| Component | Requirement |
|-----------|-------------|
| Node.js | >= 24.15 (Angular 22 CLI minimum) |
| Python | >= 3.10 (locally); the Docker image uses 3.13 |
| Docker | optional — only for the compose mode |
| Database | none for native mode (SQLite); PostgreSQL for compose mode |

## Execution modes

`azuma.sh` is the entry point. Modes:

| Command | Description |
|---------|-------------|
| `./azuma.sh docker all` | Full stack: frontend, backend, PostgreSQL |
| `./azuma.sh docker backend` | Backend plus its `depends_on` service (PostgreSQL) |
| `./azuma.sh docker frontend` | Frontend only |
| `./azuma.sh local backend` | Native backend on :8000 with SQLite |
| `./azuma.sh local frontend` | Native frontend on :4200 |
| `./azuma.sh local all` | Both processes (backend in background) |

Manual equivalents:

```bash
# backend (native, SQLite)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DB_DRIVER=sqlite
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# frontend (native)
cd frontend
npm install
npm start          # ng serve --host 0.0.0.0 --poll 2000
```

## Environment variables (backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_DRIVER` | `postgresql` | `postgresql` or `sqlite` |
| `DB_PATH` | `./azuma.db` | SQLite database file (used when `DB_DRIVER=sqlite`) |
| `DB_HOST` | `db` | PostgreSQL host |
| `DB_NAME` | `azuma` | PostgreSQL database name |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASS` | `postgres` | PostgreSQL password |

The backend waits for PostgreSQL to become available at startup (30 retries, 1.5 s apart).

## Verification

### Backend

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/forms/discover \
  -H 'Content-Type: application/json' \
  -d '{"target":"https://en.wikipedia.org"}'
```

WebSocket stream (Python):

```bash
python -m pip install websockets
python - <<'EOF'
import asyncio, json, websockets

async def main():
    async with websockets.connect(
        "ws://localhost:8000/api/forms/live?target=https://en.wikipedia.org"
    ) as ws:
        for _ in range(8):
            print(json.loads(await ws.recv())["type"])

asyncio.run(main())
EOF
```

### Frontend

```bash
cd frontend
npm run build        # production build into dist/
npx ng test          # unit tests (default spec)
```

Open http://localhost:4200, wait for the backend badge to show "backend online", enter a target and run Discover.

## Cleanup

```bash
./clean.sh
```

Stops compose services (with volumes), removes the local venv, the SQLite file, `node_modules` and `dist`.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Frontend shows "backend offline" | Backend not running, or CORS blocked — run backend first; CORS is open in development |
| `502` on discover | Target unreachable (DNS, TLS, non-2xx). Check `error_message` in the response |
| PostgreSQL connection refused in compose | `db` healthcheck not finished — the backend retries for up to 45 s |
| Angular CLI version mismatch | Node below 24.15 — use a version manager (e.g. `fnm use 24`) |
| `xwa-sdk` install fails | The backend dependency is fetched from the XWA SDK git repository; network access to GitHub is required |
