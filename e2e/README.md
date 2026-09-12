# Azuma Browser E2E

Real-Chromium smoke test for the zoneless Angular frontend. It proves that
async state renders **without extra interaction** — the failure mode of the
zoneless change-detection bug ([ LOADING... ] stuck, empty lists).

## Files

| File | Purpose |
|------|---------|
| `browser_smoke.py` | Playwright test (starts/kills the fixture automatically) |
| `fixture_server.py` | Deterministic target site: 2 forms, CSRF token, session cookie, OAuth + OIDC discovery |

## Requirements

1. The stack is running:

   ```bash
   ./azuma.sh local        # backend :8030 + frontend :4230
   ```

2. An interpreter with Playwright and Chromium installed. In this workspace:

   ```bash
   /home/x/Documents/xwebanalysis/samurai/backend/.venv/bin/python -m playwright --version
   ```

   (Any Python with `playwright` + `playwright install chromium` works.)

## Run

```bash
/home/x/Documents/xwebanalysis/samurai/backend/.venv/bin/python e2e/browser_smoke.py
```

Options:

| Flag | Default | Meaning |
|------|---------|---------|
| `--frontend URL` | `http://127.0.0.1:4230` | Frontend base URL |
| `--fixture-port N` | `8104` | Fixture port (started automatically if closed) |
| `--no-fixture` | off | Assume the fixture is already running |
| `--headed` | off | Show the Chromium window |

The script terminates the fixture it started; the `./azuma.sh local` stack is
left running.

## What it checks

1. **Shell health, no clicks** — `[BACKEND ONLINE]` appears after the async
   `health()` call, with no interaction.
2. **REST discovery** — `POST /api/forms/discover` against the fixture renders
   2 forms (`POST /login`, `GET /search`), the OAuth endpoint, the session
   cookie and the metric cards. `[ LOADING... ]` must be gone.
3. **Live WebSocket discovery** — `/api/forms/live` streams ≥ 5 terminal lines,
   all phases end `done`, and the detail view renders.
4. **History** — rows render on entry without clicks; the detail page loads by
   URL (`/history/<id>`).
5. **Exports** — client JSON/CSV and server JSON/CSV downloads verify the
   suggested filenames.
6. **i18n** — EN→ES→EN keeps the history rows rendered.
7. **Console** — no `console.error` and no uncaught page errors.

## Fixture routes

| Route | Response |
|-------|----------|
| `GET /` | HTML with the two forms, OAuth link, OIDC link and `Set-Cookie: sessionid=abc; HttpOnly; SameSite=Lax` |
| `GET /search` | Static results page (GET form redirect-chain target) |
| `GET /oauth/authorize?...` | Static consent page |
| `GET /.well-known/openid-configuration` | OIDC discovery JSON |
| `POST /login` | Static welcome page + session cookie |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `frontend not reachable at ...` | Start `./azuma.sh local` first |
| Port 8104 busy | Use `--fixture-port 8114` or `--no-fixture` with your own server |
| Playwright import error | Run with an interpreter that has `playwright` installed |
| A check fails with a stale value | The app is zoneless: a missing `cdr.markForCheck()` in an async callback is the usual cause |
