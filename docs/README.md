# Azuma Documentation

Documentation for the Azuma web form and authentication flow analyzer.

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Stack, project layout and data flow |
| [api.md](api.md) | REST and WebSocket API reference |
| [development.md](development.md) | Running, environment variables and verification |

## Quick orientation

- Azuma is a self-contained web application: an Angular 22 frontend and a FastAPI backend.
- The backend can run with PostgreSQL (Docker Compose) or SQLite (native mode, zero external services).
- Form discovery results are persisted in the database; live analysis can be streamed over WebSocket.
- Live stream events use the xwa-sdk `Event` envelope, the shared data contract of the XWA ecosystem.

## Quick start

```bash
./azuma.sh docker all     # full stack on localhost:4200 / localhost:8000
./azuma.sh local all      # native run (SQLite), two processes
```

See [development.md](development.md) for all execution modes.
