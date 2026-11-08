# Phase 12B Final Implementation Report — Frontend Dashboard

**Date:** 2026-10-19
**Scope delivered:** React 19 + Vite 7 + TypeScript SPA in `frontend/`, replacing the Phase 0 static stub, consuming only the Phase 12A API contract. Zero Git/GitHub write operations (no commits, no pushes, no branch changes).

## What was built

### Stack decision
- React ^19.2.0, react-dom (runtime deps only); dev-only Vite ^7.3.5, @vitejs/plugin-react, TypeScript ~5.9.3, Vitest ^4.0.13, jsdom, @testing-library/react.
- **No extra runtime libraries**: custom history-API router (`src/router.ts`), custom SVG charts (`src/components/Charts.tsx`), no state management library, no `dangerouslySetInnerHTML`, no `eval`, no third-party scripts.
- npm 12 allowScripts initially blocked the esbuild postinstall; resolved via `npm install-scripts approve esbuild` + `npm rebuild esbuild`. `npm audit` clean (0 vulnerabilities).

### Application surface
- 11 routes/pages: Overview, Forecasts, Inventory, Suppliers, Procurement, Risk, Simulation, Decision Replay, Optimization, AI Copilot, Settings.
- Single typed client (`src/api/client.ts`): every request flows through `request()`; injects `Authorization: Bearer <key>`; unwraps the `{success,data,meta}` envelope; maps failures to `ApiError` families (`unauthorized`/`forbidden`/`validation`/`rate_limited`/`server`/`network`/`malformed`/`api`); surfaces `Retry-After` and prefers the server's `details.reason`.
- Auth: opaque Bearer key only. Key in per-tab **sessionStorage** (`ssn.api_key`; documented tradeoff, never localStorage/cookies/logging), base-URL override (`ssn.base_url`, default `http://localhost:8010`). Identity/role exclusively from `GET /auth/me` — never fabricated. 401 marks the key rejected via an event bus; analysts honestly blocked from compute POSTs by a planner gate mirroring the API's 403.
- Data-labeling discipline: `meta.data_source_label` chips everywhere + persistent footer legend (derived / forecast (estimated) / synthetic data / simulated); compute pages carry "simulated/illustrative" banners; error/empty states are honest — the UI never invents values.
- AI Copilot is real: `POST /ai/chat` works with the offline mock provider (`provider: mock`); shows confidence/evidence/limitations; approval recording via `POST /ai/approval` never executes actions.

### Legacy handling
- Phase 0 stub moved (not deleted) to `frontend/legacy/` with a README explaining why.

## Verification (all executed, none claimed)

| Check | Result |
| --- | --- |
| `npx tsc --noEmit` | 0 errors |
| `npm test` (5 files) | **35 passed** |
| `npm run build` | OK; `dist/` ~94 KB gzip JS, 3 KB CSS |
| Backend regression `pytest backend/app/tests` | **838 passed** (12:05 min) |
| `python -m ruff check backend scripts` | All checks passed |
| Playwright live validation | see below |

### Playwright validation (backend `--loop none --port 8010`, Vite 5173)
- Unauthenticated state shows the key gate + label legend (verified snapshot).
- All 11 pages visited with a real key; **zero console errors** after fixes below.
- Analyst key: planner gate visible on Simulation/Replay/Optimization (correct).
- Planner key: **live UI runs** — Simulation report ~4 s, Optimization report ~4 s, Replay comparison ~2 s, one AI Copilot chat (mock provider) — all rendered with report content and labels.
- Invalid key → 401 rejection banner; Authorization sent as `Bearer …` header only; the key never appears in rendered page text.
- Screenshots captured at 1440×900, 2048×1320 (desktop), 390×844 (mobile) in `.playwright-mcp/shots/`.

### Live-validation defects found and fixed
1. **Optimization report crash** — API can omit `current_plan` / `current_plan_plus_optimized_orders` / `deltas` blocks in some configurations; frontend assumed them always present (`TypeError: reading 'served_demand_units'` / `'unmet_delta'`). Fixed with defensive rendering ("plan block not reported by the API") and optional types.
2. **White-screen risk** — render errors unmounted the whole app. Added `RouteErrorBoundary` (`src/App.tsx`) showing a diagnostic panel instead.
3. **Duplicate React keys** — assumption lists keyed by their text collide when the API lists the same `key = value` twice. Now index-prefixed keys.
4. **Unrounded floats** in Procurement lead-time/concentration tables — now formatted via `formatNumber`.
5. **favicon 404 console noise** — inline SVG data-URI icon in `frontend/index.html`.
6. **Missing `DataSourceLabelChip` import in Suppliers.tsx** (from an earlier bulk edit) — restored; typecheck clean.

## Honest limitations
- Replay validation keys: two local validation users were provisioned (`ui-analyst@...`, `ui-planner@...`) in the dev DB. Keys used during browser validation appeared in session tooling logs, so **both keys were rotated after validation** and rotation was verified (old keys 401, new keys 200). Keys themselves live only in a temp-dir file; never in the repo or chat output.
- 429 rate-limit behavior is covered by unit tests (Retry-After propagation) and backend tests; it was not triggered live on purpose (would require hundreds of compute calls).
- Mobile nav collapses visually via CSS; the print/desktop experience is the primary target (matches Phase 12 scope).
- GSD / cc-safety-net skills referenced in the work order are not present in this session's environment; the phase was executed with built-in verification instead.
- The `.playwright-mcp/` scratch directory (snapshots, console logs, shots) is gitignored and not part of deliverables.

## Files touched (frontend)
- New: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `.gitignore`, `src/**` (api/{types,auth,client,endpoints}.ts + 2 test files, state/{AuthContext,useApiQuery}, router/routes/App/main, components/{DataSourceLabel,StateViews,DataTable,Ui,Charts,PageGate,ScenarioForm} + 3 test files, pages/11 pages, styles/global.css), `frontend/legacy/**`.
- Docs: `docs/development-guide.md` (new Frontend section), `docs/roadmap.md` (Phase 12B notes), this report. Plus repo `.gitignore` gained `.playwright-mcp/`.

## Final confirmation
- Commits: **0** · Pushes: **0** · Branch changes: **0** · GitHub operations: **0** — per the explicit Git hard rule ("do not checkout/commit/push/rebase, do not invoke Github MCP").
