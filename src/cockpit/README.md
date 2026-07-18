# The Reasoning Cockpit (interim-B, the gesture surface)

The Phase-3 cockpit's board + ask panel + **drag/sandbox gesture surface**
(docs/07 Phase 3). A vis-timeline render of a **contract-1.3 schedule document
from the live API**, with the M10 explainer embedded, cited-bar highlighting,
and the interim-B gesture layer (grab → shade → ghosts → magnets → drop →
sandbox verdict → traces). Stack + interaction decisions are recorded in the
docs/04 "Session 3.1b" (read-only board) and "Session 3.2a/3.2b" (data spine +
gesture surface) amendments.

## Layout

```
index.html          shell (top strip · board · ask panel)
vite.config.mjs     Vite 5; dev/preview PROXY the API (no CORS on the core)
src/tokens.css      DESIGN TOKENS (visual) — feel-iteration edits these
src/cockpit.css     layout + component styling (references tokens only)
src/api.js          envelope-unwrapping client (relative paths)
src/board.js        vis-timeline board + citation overlay (highlight/select)
src/askpanel.js     M10 ask panel: registers, cited highlight, deictic select
src/interaction.js  background Tier-0 payload fetch → stands up the gesture layer
src/legality/       client-side Tier-0 legality library (tier0.js, pure)
src/drag/           the gesture surface: shade · ghosts · magnets · controller ·
                    sandboxui · traces · feel.js (numeric knobs) · tuning.js (dev)
src/main.js         boot: resolve schedule → fetch doc + grade → render → wire drag
```

## Dev startup: the gesture cockpit against a solved `busy_board`

**Run these two scripts** (PowerShell), one per terminal, from the repo root —
each resolves the repo root from its own location, so running them from anywhere
works. Terminal 1 runs the API; terminal 2 prepares one solved schedule with its
priced ghosts and then runs the Vite dev server proxied at it.

```powershell
# Terminal 1 — generate a submission + start the API (leave running).
# Defaults to the busy_board FEEL fixture; -Scenario overrides it, e.g.
#   .\src\cockpit\dev_api.ps1 -Scenario multi_route_distinct
.\src\cockpit\dev_api.ps1

# Terminal 2 — submit -> solve -> build ghosts -> print URL -> npm run dev
.\src\cockpit\dev_cockpit.ps1
```

`dev_cockpit.ps1` prints the cockpit URL it minted — open
`http://localhost:5175/?schedule=<id>`. The board renders read-only first; the
Tier-0 interaction payload arrives in the background and the gesture layer enables
(`data-drag-enabled="true"` on the board host). Because `vite dev` sets
`import.meta.env.DEV`, the **CU6 feel tuning panel** and the **question-ledger
refusal panel** (Session 4A.1 CU3, bottom-right) mount (both stripped from
`npm run build`). Probe drag from the console via `window.__cockpit.drag`
(`grab/dragTo/drop/dropAt/discard`) — the same hooks the harness drives.

The refusal panel reads `GET /ledger/refusals`, which the API serves **only when
`MRE_DEV` is set** in its environment (404 otherwise) — so the ledger's refusal
view never ships to production. It lists the questions the AI layer couldn't
answer, clustered by frequency, with a "↳ rephrased" marker where a later
rephrase in the same session succeeded (the free labeled data of R-AI1(d)).

The scripts set env the PowerShell way (`$env:MRE_DATA_ROOT`, `$env:MRE_API`),
resolve the repo root from their own location (run them from anywhere), and drive
the API with `Invoke-RestMethod` so PowerShell handles the JSON quoting. Override
the API base by setting `$env:MRE_API` before `dev_cockpit.ps1` (default
`http://localhost:8000`).

Optional `&ask=<question>` on the URL auto-runs one M10 question after load, e.g.
`?schedule=<id>&ask=why%20is%20ORD-000012%20on%20F001-RES002%3F`.

Why `busy_board` (the default): it is a **feel fixture** — not a truth-bearing
test scenario (it seeds no anomalies and writes a `feel_fixture.json` marker, not
a `truth_manifest.json`), tuned for the qualities feel-iteration needs. 30–50
orders spread across the six resources; near-equivalent but strictly distinct
machine rates ($50.0–$51.0/h, ~2% apart) so tardiness dominates and the optimum
spreads work across the machines, yet every cross-machine ghost still carries a
nonzero price; multi-eligible ops throughout; a rush cohort due tomorrow on an
over-subscribed window (so some demands run late) plus a comfortable green tail —
so lateness coloring and consequence traces have material; and a few precedence
chains that cross machines. `dev_cockpit.ps1` asks for `budget=8` forced alternatives (over the
service default of 4) so the board surfaces a full set of priced ghosts.

For the forced-alternative **counterfactual** instead — distinct rates + light
load, where the near-optimal pool converges so the priced ghosts are provably the
forced service's roads-not-taken and not a saturated pool's artifacts — run
`-Scenario multi_route_distinct` (docs/04 Session 3.2a).

The built app (`npm run build`) fetches the same relative paths, so it also runs
behind the API or the test fixture server unchanged (production build = no tuning
panel).

### Manual steps (reference — what the scripts do)

If you are not on PowerShell, or want to run the chain by hand, this is the same
recipe in **Git Bash** (inline `VAR=val` env, `curl`, `python` for id extraction —
no `jq` needed).

**Terminal 1 — generate a submission, then start the API (leave running):**

```sh
# from repo root (--scenario busy_board is dev_api.ps1's default; swap in any
# generator scenario, e.g. multi_route_distinct, here)
python tools/generate_erp_dataset.py --scenario busy_board --out _data/mrd

MRE_DATA_ROOT=./_data uvicorn mre.api.app:create_app --factory --app-dir src --port 8000
```

**Terminal 2 — submit → solve → build ghosts, then run the cockpit:**

```sh
# from repo root; the API from terminal 1 must be up (curl localhost:8000/health)
API=http://localhost:8000

# 1. intake the submission through the M0 gate → submission id
SUB=$(curl -s -XPOST $API/submissions -H content-type:application/json \
      -d '{"path":"_data/mrd"}' \
      | python -c "import sys,json;print(json.load(sys.stdin)['data']['submission_id'])")

# 2. solve it — sync (blocks until done) + deterministic (workers 1 / seed 0,
#    the reproducibility discipline) → run id, then the schedule id off the run
RUN=$(curl -s -XPOST $API/submissions/$SUB/solve -H content-type:application/json \
      -d '{"sync":true,"deterministic":true}' \
      | python -c "import sys,json;print(json.load(sys.stdin)['data']['run_id'])")
SCH=$(curl -s $API/runs/$RUN \
      | python -c "import sys,json;print(json.load(sys.stdin)['data']['result']['schedule_id'])")

# 3. build the forced-alternative ghosts (the priced cross-machine bars CU2 draws).
#    WITHOUT this the drag surface still stands up, but Tier-0-green-only — no ghosts.
#    budget=8 (over the service default of 4) to fill the lively busy_board board.
curl -s -XPOST $API/schedules/$SCH/alternatives -H content-type:application/json \
     -d '{"sync":true,"budget":8}' >/dev/null

echo "cockpit URL: http://localhost:5175/?schedule=$SCH"

# 4. run the dev server, proxying the API (first time: npm install)
cd src/cockpit && npm install
MRE_API=$API npm run dev
```

## LLM answers (optional, dev only)

The ask panel's answers are rendered **deterministically from templates by
default**. The M10 `LLMRenderer` (Anthropic) is wired but **fail-closed** and
gated three ways, so it can only ever improve fluency, never fabricate:

- **Dev build only.** `src/main.js` sends the `llm` flag to `POST
  /schedules/{id}/ask` only when `import.meta.env.DEV` is true (i.e. `vite dev`).
  The production `npm run build` the harness serves always renders templates.
- **Key required, in the environment.** The API honors the flag only when
  `ANTHROPIC_API_KEY` is set in the **API server's** environment (terminal 1).
  The intended way — **no terminal typing** — is a gitignored `.env.local` at the
  repo root, which `dev_api.ps1` loads on startup:

  ```powershell
  cp .env.local.example .env.local      # then edit .env.local, set ANTHROPIC_API_KEY
  .\src\cockpit\dev_api.ps1             # loads .env.local into the API's environment
  ```

  `.env.local` is `KEY=VALUE` per line (`#` comments and blank lines ignored,
  surrounding quotes stripped); an already-set environment variable is never
  overwritten, so an exported key still wins. It is **gitignored** and CI's
  gitleaks scan guards against a commit — see `.env.local.example` (committed,
  no real secret). Equivalently, export it by hand before the script:

  ```powershell
  $env:ANTHROPIC_API_KEY = "sk-ant-…"   # NEVER commit this — gitleaks scans for it
  .\src\cockpit\dev_api.ps1
  ```

  With no key set, the server drops back to `use_llm=False` and the template
  renderer — silently and correctly.
- **Validated, or it falls back.** `LLMRenderer.render` validates every prose
  answer against the evidence bundle (timestamps, durations, machine names). On a
  validation failure — even after one regeneration — it renders the deterministic
  template instead and stamps `[LLM validation failed … fell back to template]`.
  There is no path from a missing key or a bad generation to an error or to
  unvalidated prose.

The key is read from the process environment only; it is never written to a file
in this repo, and CI's gitleaks scan guards against an accidental commit.

## Tests

The screenshot harness lives in `tests/cockpit/` (CU5). `npm run test:e2e` here
delegates to it. `npm run fixture` regenerates its captured `multi_route`
fixture.
