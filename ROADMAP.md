# Azuma Development Roadmap

This document tracks the strategic steps required to evolve the Azuma application into a full-scale web form and authentication flow analyzer.
This file is formatted to be synced automatically with GitHub Issues using the `xgh` roadmap standard.

## Infrastructure & Core Initialization <!-- phase:infrastructure -->

- [x] Scaffold backend and frontend project structure
- [x] Dockerize environments with local development HMR support
- [x] Configure Docker-compose for rapid local development
- [x] Define shared flow data model aligned with xwa-sdk

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
- [x] Detect session fixation and hijacking indicators
- [ ] Analyze logout and session invalidation behavior
- [ ] Map session persistence across subdomains

## Reporting & Production Hardening <!-- phase:production-hardening -->

- [ ] Build authentication flow report generator
- [ ] Create JSON export for analysis results
- [ ] Wrap backend routes with JWT Authentication middleware
- [ ] Implement rate limiting and access controls
