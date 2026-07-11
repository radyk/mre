# The Reasoning Cockpit (interim-A, read-only)

The Phase-3 cockpit's read-only board + ask panel (docs/07 Phase 3, CU3+CU4).
A vis-timeline render of a **contract-1.2 schedule document from the live API**,
with the M10 explainer embedded and cited-bar highlighting. **No drag handlers —
read-only is the law until interim-B.** Stack decisions are recorded in the
docs/04 2026-07-11 "Session 3.1b" amendments.

## Layout

```
index.html          shell (top strip · board · ask panel)
vite.config.mjs     Vite 5; dev/preview PROXY the API (no CORS on the core)
src/tokens.css      DESIGN TOKENS — the one file feel-iteration edits
src/cockpit.css     layout + component styling (references tokens only)
src/api.js          envelope-unwrapping client (relative paths)
src/board.js        vis-timeline board + citation overlay (CU3, highlight/select for CU4)
src/askpanel.js     M10 ask panel: registers, cited highlight, deictic select (CU4)
src/main.js         boot: resolve schedule → fetch doc + grade → render
```

## Run against a live API

```sh
# 1. start the API (from repo root), solve a submission, note its schedule id
MRE_DATA_ROOT=./_data uvicorn mre.api.app:create_app --factory --app-dir src --port 8000

# 2. run the cockpit, proxying that API
cd src/cockpit && npm install
MRE_API=http://localhost:8000 npm run dev
# open http://localhost:5175/?schedule=<id>
#   optional: &ask=why%20is%20ORD-000012%20on%20F001-RES002%3F  (auto-runs one question)
```

The built app (`npm run build`) fetches the same relative paths, so it also runs
behind the API or the test fixture server unchanged.

## Tests

The screenshot harness lives in `tests/cockpit/` (CU5). `npm run test:e2e` here
delegates to it. `npm run fixture` regenerates its captured `multi_route`
fixture.
