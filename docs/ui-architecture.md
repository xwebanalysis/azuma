# Azuma Frontend — UI Architecture

Status: current as of the Angular 22 zoneless consolidation.

## Stack

| Layer | Choice |
|-------|--------|
| Framework | Angular 22 (standalone components, zoneless — `zone.js` is not a dependency) |
| Build | `@angular/build:application` (esbuild) |
| Tests | `@angular/build:unit-test` + Vitest 4 (jsdom) |
| Language | TypeScript 6 (strict templates) |
| Styling | SCSS + Nothing Design tokens |
| PDF | `jspdf`, loaded lazily through a dynamic `import()` |

Ports follow the XWA convention: frontend `4230`, backend `8030`
(`src/environments/environment.ts` resolves the hostname at runtime).

## Directory layout

```
frontend/
├── public/fonts/                  # self-hosted woff2 (no Google Fonts at runtime)
├── scripts/test.sh                # npm test wrapper (`--run` accepted and ignored)
└── src/
    ├── _fonts.scss                # @font-face declarations
    ├── styles.scss                # Nothing Design tokens + typography utilities
    └── app/
        ├── app.*                  # shell: sidenav, health dot, theme/locale toggles
        ├── app.config.ts          # provideRouter, provideHttpClient, global error listeners
        ├── app.routes.ts          # lazy `loadComponent` routes per feature
        ├── core/                  # singleton, framework-level concerns
        │   ├── api.service.ts     # typed REST client + WS URL builders
        │   ├── live.service.ts    # WebSocket wrapper + `parseLiveEvent()`
        │   ├── export.service.ts  # client JSON/CSV/PDF builders
        │   ├── i18n.service.ts    # en/es dictionary, `locale` signal
        │   └── theme.service.ts   # dark/light `currentTheme` signal
        ├── shared/                # presentation-only components
        │   ├── terminal/          # live log panel (auto-scroll)
        │   ├── detail-table/      # flat table for fields/oauth/cookies
        │   ├── metric-card/       # hero number + label
        │   ├── status-badge/      # [ COMPLETED ] with status color
        │   └── export-actions/    # client JSON/CSV/PDF + server JSON/CSV
        └── features/              # one folder per route
            ├── analyzer/          # REST fallback + live WS discovery dashboard
            ├── history/           # persisted analyses list + detail-by-URL
            └── exports/           # per-analysis download table
```

Rules:

- `core/` never imports from `features/`; `shared/` never injects state services.
- Every REST call is typed in `ApiService`; components never build URLs.
- WebSocket frames are parsed by `parseLiveEvent()` before reaching a component.

## Runtime data flow

1. `ApiService` reads `environment.apiBaseUrl`/`wsBaseUrl` and exposes typed
   methods: `health`, `discoverForms`, `listAnalyses`, `getAnalysis`,
   `deleteAnalysis`, `deleteAllAnalyses`, `exportUrl`, `liveUrl`.
2. The analyzer opens `liveUrl(target)`; each frame is `parseLiveEvent()`-d
   (malformed frames are ignored) and handled as
   `analysis_started → analysis_progress → item_found* →
   analysis_completed|analysis_error`. On completion the persisted analysis is
   fetched and rendered by `AnalysisDetailComponent`.
3. `I18nService.locale` and `ThemeService.currentTheme` are signals, so locale
   and theme toggles schedule their own change detection.
4. Async component state follows the zoneless rule below.

## Zoneless change detection (mandatory rule)

Azuma runs **without zone.js**: Angular only re-renders a view when a signal it
read changes, when a template event fires, or when the view is explicitly
marked. Async callbacks that mutate plain component properties (`HttpClient`
subscribes, WebSocket/`Observable` handlers, `setTimeout`, `await`
continuations) do **not** trigger a render on their own.

**Rule:** inject `ChangeDetectorRef` and call `this.cdr.markForCheck()` after
**every** batch of plain-property mutations inside an async callback.

```typescript
private readonly cdr = inject(ChangeDetectorRef);

protected load(): void {
  this.loading = true;
  this.api.listAnalyses().subscribe({
    next: (items) => {
      this.history = items;
      this.loading = false;
      this.cdr.markForCheck();       // <- required (zoneless)
    },
    error: () => {
      this.error = this.t('error.backend');
      this.loading = false;
      this.cdr.markForCheck();       // <- required (zoneless)
    },
  });
}
```

Symptom when missing: a stuck `[ LOADING... ]` banner, empty lists or stale
status until the next click. Audited and fixed call sites:

| File | Async source |
|------|--------------|
| `app.ts` | `health()` subscription |
| `features/analyzer/analyzer.ts` | REST discovery, WS event stream, completion fetch, cancel |
| `features/history/history.ts` | list / delete / delete-all subscriptions |
| `features/history/detail.ts` | detail-by-URL subscription |
| `features/exports/exports.ts` | list + per-analysis fetch, `busyId` reset in `Promise.finally` |
| `shared/export-actions/export-actions.ts` | `pdfBusy` around the lazy jsPDF `await` |

New code should prefer signals for render-relevant state (then `markForCheck()`
is unnecessary); the rule applies to any remaining plain properties. See
[kensei/docs/ui-architecture.md](../../kensei/docs/ui-architecture.md) for the
same contract in the sibling module.

## Nothing Design rules in this app

- Tokens live only in `src/styles.scss`; fonts are self-hosted (no external
  providers in `index.html`).
- Labels are Space Mono uppercase (`.t-label`); Doto is reserved for hero
  metrics; the dot-matrix background is the sanctioned exception.
- Errors are inline bracket text (`[ERROR: ...]`), never toasts.

## Testing

`npm test` builds the app for the test target and runs Vitest once
(`scripts/test.sh` maps `--run` for suite consistency):

- `core/api.service.spec.ts` — endpoint URLs, WS URL encoding.
- `core/live.service.spec.ts` — xwa-sdk frame parsing/rejection.
- `core/export.service.spec.ts` — CSV builder and blob downloads.
- `features/analyzer/analyzer.spec.ts` — REST fallback + live form/OAuth/cookie events.
- `app.spec.ts` — shell + router.

Real-browser validation lives in `e2e/browser_smoke.py` (Playwright +
`e2e/fixture_server.py`); it asserts that async state renders **without extra
clicks**, exports download, and the console stays clean. See `e2e/README.md`.

## Commands

```bash
export PATH="$HOME/.local/share/mise/installs/node/24/bin:$PATH"
npm ci
npm test
npm run build
npm audit --omit=dev
npm start                      # dev server on 0.0.0.0:4230

# browser smoke (app must be running via ./azuma.sh local)
python e2e/browser_smoke.py    # use an interpreter with Playwright + Chromium
```
