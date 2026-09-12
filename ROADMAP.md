# Azuma Development Roadmap

This document tracks the strategic steps required to evolve the Azuma application into a full-scale web form and authentication flow analyzer.
This file is formatted to be synced automatically with GitHub Issues using the `xgh` roadmap standard.

## Infrastructure & Core Initialization <!-- phase:infrastructure -->

- [x] Scaffold backend and frontend project structure
- [x] Dockerize environments with local development HMR support
- [x] Configure Docker-compose for rapid local development
- [x] Define shared flow data model aligned with xwa-sdk
- [x] Local-first mode: SQLite + uv venv + xwa-sdk editable install (`./azuma.sh local`)

## Form Discovery <!-- phase:form-discovery -->

- [x] Extract forms, inputs, and submission endpoints from DOM
- [x] Classify field types and validation rules
- [x] Detect hidden fields and CSRF token placement
- [x] Analyze form submission flows and redirect chains

## OAuth Mapping <!-- phase:oauth-mapping -->

- [x] Detect OAuth 2.0 / OIDC authorization endpoints
- [x] Map authorization and token exchange flows
- [x] Identify redirect URI and state parameter handling
- [x] Detect OAuth implementation weaknesses and misconfigurations

## Session Analysis <!-- phase:session-analysis -->

- [x] Profile session cookie attributes (flags, scope, lifetime)
- [ ] Detect session fixation (cookie rotation after authentication) — not possible in the passive single-fetch model; requires stateful pre/post-login requests. Hijacking indicators (HttpOnly/Secure/SameSite) are covered by cookie profiling. See docs/architecture.md
- [ ] Analyze logout and session invalidation behavior
- [ ] Map session persistence across subdomains

## Reporting & Production Hardening <!-- phase:production-hardening -->

- [x] Build authentication flow report generator
- [x] Create JSON/CSV export for analysis results (server-side, `Content-Disposition`)
- [x] Persisted history API: list, detail, delete one/all
- [x] Wrap backend routes with JWT Authentication middleware (optional via `AZUMA_JWT_SECRET`)
- [x] Implement rate limiting and access controls (`AZUMA_RATE_LIMIT_MAX`, `/api/health` exempt)
- [x] Correct xwa-sdk `Event.analysis_id` (persisted id), `seq` and UTC `ts`

## Frontend <!-- phase:frontend -->

- [x] Restructure to `core/` (api, live WS, theme, i18n, export) + `shared/` (terminal, metric-card, status-badge, export-actions, detail-table)
- [x] Lazy router with sidebar navigation: analyzer, history list/detail, exports console
- [x] Consume `/api/forms/live` xwa-sdk `Event` stream (forms/OAuth/cookies progress + terminal); `POST /api/forms/discover` kept as fallback
- [x] Server-side export links + client JSON/CSV/PDF (jsPDF lazy chunk)
- [x] Nothing tokens with `--gold` (no hardcoded `#FFD700`), self-hosted fonts, no Google Fonts at runtime
- [x] Vitest suite: ApiService, `parseLiveEvent()`, CSV builder, analyzer component, app shell
