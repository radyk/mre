# frontend_bakeoff — SPIKE (Session 3.0)

**Throwaway.** Timeboxed research to choose the rendering substrate for the
Phase-3 reasoning cockpit's three-tier drag surface. **Nothing here ships**;
the deliverable is [`VERDICT.md`](./VERDICT.md). Precedent: the chunking spikes
(docs/04 2026-07-10 amendment) — spike code lives here, is not production-wired.

## Read this first
- **[`VERDICT.md`](./VERDICT.md)** — the scored 7-criterion sheet, screenshots,
  the recommendation, and the honest fixture caveat.

## Layout
```
build_fixture.py     builds fixture/{schedule,anchors}.json from a real solve (documented header)
fixture/             schedule.json + anchors.json (committed); messy_run/ + messy_submission/ gitignored
shared/geometry.js   the fair-comparison core: time<->px + semantic snap, imported by BOTH candidates
shared/bakeoff.css   shared styling so both read as one system
candidate_a.html + src_a/   Candidate A — custom React: SVG timeline + dnd-kit
candidate_b.html + src_b/   Candidate B — library: vis-timeline
harness/run.mjs      candidate-agnostic Playwright screenshot harness (SURVIVES as interim-A infra)
shots/               captured state series (a_*, b_*) + report.json (evidence for VERDICT.md)
```

## What SURVIVES the spike
`harness/run.mjs` — the candidate-agnostic screenshot driver (page contract:
`window.__spike.{grab,moveToGhost,moveToTime,setAlt,drop,reset,getState}`). It
becomes Phase-3 interim-A infrastructure. Everything else is throwaway.

See `VERDICT.md` → "Reproduce" for the exact commands.
