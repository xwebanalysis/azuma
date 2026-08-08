# Azuma Development Roadmap

This document tracks the strategic steps required to evolve the Azuma application into a full-scale web form and authentication flow analyzer.
This file is formatted to be synced automatically with GitHub Issues using the `xgh` roadmap standard.

## Infrastructure & Core Initialization <!-- phase:infrastructure -->

- [ ] Scaffold backend and frontend project structure
- [ ] Dockerize environments with local development HMR support
- [ ] Configure Docker-compose for rapid local development
- [ ] Define shared flow data model aligned with xwa-sdk

## Form Discovery <!-- phase:form-discovery -->

- [ ] Extract forms, inputs, and submission endpoints from DOM
- [ ] Classify field types and validation rules
- [ ] Detect hidden fields and CSRF token placement
- [ ] Analyze form submission flows and redirect chains

## OAuth Mapping <!-- phase:oauth-mapping -->

- [ ] Detect OAuth 2.0 / OIDC authorization endpoints
- [ ] Map authorization and token exchange flows
- [ ] Identify redirect URI and state parameter handling
- [ ] Detect OAuth implementation weaknesses and misconfigurations

## Session Analysis <!-- phase:session-analysis -->

- [ ] Profile session cookie attributes (flags, scope, lifetime)
- [ ] Detect session fixation and hijacking indicators
- [ ] Analyze logout and session invalidation behavior
- [ ] Map session persistence across subdomains

## Reporting & Production Hardening <!-- phase:production-hardening -->

- [ ] Build authentication flow report generator
- [ ] Create JSON export for analysis results
- [ ] Wrap backend routes with JWT Authentication middleware
- [ ] Implement rate limiting and access controls
