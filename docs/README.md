# Azuma Documentation

Documentation for the Azuma web form and authentication flow analyzer.

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Stack, project layout and data flow |
| [api.md](api.md) | REST and WebSocket API reference |
| [development.md](development.md) | Running, environment variables and verification |
| [ui-architecture.md](ui-architecture.md) | Frontend layout and the zoneless change-detection rule |

## Quick orientation

- Azuma is a self-contained web application: an Angular 22 frontend (:4230) and a FastAPI backend (:8030).
- Local mode is the default and uses SQLite; PostgreSQL is only used by the docker mode.
- The pipeline discovers forms, traces redirects, maps OAuth/OIDC flows and profiles session cookies.
- Live stream events use the xwa-sdk `Event` envelope with the persisted `analysis_id`; REST errors use the xwa-sdk `Error` envelope.
- The UI follows the Nothing Design System shared across XWA modules.
- The frontend is zoneless (no `zone.js`); async handlers that touch plain
  properties must call `ChangeDetectorRef.markForCheck()` (see
  [ui-architecture.md](ui-architecture.md)).

## Quick start

```bash
./azuma.sh local all      # native run (SQLite): backend :8030 + frontend :4230
./azuma.sh docker all     # full stack with PostgreSQL 17
```

See [development.md](development.md) for all execution modes and
[api.md](api.md) for the endpoint reference.
