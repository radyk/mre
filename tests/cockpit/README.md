# Cockpit screenshot harness (CU5)

The Playwright harness promoted from the frontend bake-off spike into production
test infra (docs/07 Phase 3, CU5; docs/04 2026-07-11 "Session 3.1b CU5"). It
drives the read-only cockpit through six scripted states, screenshots each, and
asserts **machine-checked numbers** — including the standing **C1 label-vs-bar
drift regression** so a vis-timeline version bump trips a test, not the demo.

## Hermetic by construction

CI runs it **with no Python solver**. `tools/build_cockpit_fixture.py` captures
a deterministic `multi_route` solve into `fixtures/{schedule,meta,asks}.json`
(committed); `fixture-server.mjs` serves the built cockpit + those fixtures with
the exact API envelopes. The spec points the cockpit at that server.

## Run

```sh
cd tests/cockpit
npm install
npm run install:browser   # once: playwright install chromium
npm test                  # builds src/cockpit, serves it, runs the 6 states headless
```

Screenshots land in `tests/cockpit/shots/` (gitignored). To regenerate the
fixtures after a scenario/contract change:

```sh
PYTHONHASHSEED=0 python tools/build_cockpit_fixture.py
```

## The states

`load · select · ask+highlight (the acceptance frame) · C1 drift · mid-pan
frame · registers`. The **live** acceptance moment (real API, not the fixture)
is driven separately per the docs/04 amendment — this harness is the standing
regression, not the demo of record.
