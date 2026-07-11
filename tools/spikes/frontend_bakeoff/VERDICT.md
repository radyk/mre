# Frontend bake-off — VERDICT

**Session 3.0 SPIKE · 2026-07-11 · throwaway code, verdict is the deliverable.**
Nothing in `tools/spikes/frontend_bakeoff/` ships. This picks the rendering
substrate for the Phase-3 reasoning cockpit's three-tier drag surface
(docs/07 Phase 3). Decision rule (from the brief): **LIBRARY WINS TIES**;
custom wins only if the library hard-fails criterion 1, 3, or 5, or its feel
ceiling is *clearly disqualifying with evidence*.

> **Do not update docs/07's frontend line on this alone — review together first.**

---

## TL;DR

| | Candidate A — custom React (SVG + dnd-kit) | Candidate B — vis-timeline |
|---|---|---|
| Verdict | **GREEN** | **GREEN (qualified)** |
| Hard fails on 1/3/5 | none | none |
| Blemishes | none material | **C2** ghost/label clipping · **C6** feel-ceiling frictions |
| License | MIT | Apache-2.0 OR MIT |

**Recommendation (rule-applied): adopt _vis-timeline_ (B) — it wins the tie,
because it hard-failed none of the killer criteria — _conditional on a short
follow-up proving a stable always-on label/overlay layer._** vis-timeline clips
**all** in-bar text to the bar width, so the priced-ghost labels ("+$53") — a
centrepiece of the Tier-1 "three priced ghosts glow" demo moment — render as
a truncated "+". The workaround (an absolutely-positioned overlay layer synced
to vis's pan/zoom) is legitimate but fragile (the brief's noted hazard). **If
that overlay proves fragile, or early feel-iteration finds the single
`onMoving` hook too coarse for magnet feel, Candidate A is the proven,
zero-blocker fallback** with a higher feel ceiling. This is a genuinely close
call; the evidence to overturn it is in criteria 2 and 6 below.

---

## What both candidates share (fair comparison)

Both consume the **same fixture** (`fixture/schedule.json` — a real
`messy_realistic` deterministic solve, 475 assignments / 16 resources) and the
**same** `shared/geometry.js` (identical time↔pixel mapping and identical
semantic-snap logic). They differ **only** in the rendering host. Both are
driven by the **same** candidate-agnostic Playwright harness (`harness/run.mjs`),
which is the surviving interim-A deliverable.

Machine-checked results (`shots/report.json`, stable across 3 runs):

```
A: latency 17–23ms · snap-on-ghost=ghost · ghost Δ shown=+$53.2 · drop=dropped · realPointer=OK
B: latency 30–45ms · snap-on-ghost=ghost · ghost Δ shown=+$53.2 · drop=dropped · realPointer=OK
```

---

## Scored sheet (evidence in `shots/`)

### 1 — Tier-0 shading at grab, and grab→shade latency (<100ms target)
- **A — GREEN.** Green/amber/dim row tint paints on grab; measured **17–23 ms**
  grab→shade (SVG written directly, no reconciliation of the 388 bars).
  Evidence: `a_2_grab_shaded.png` (1 green / 7 amber / 8 dim, matching anchors).
- **B — GREEN.** Same shading via vis-timeline **background items** injected on
  grab; measured **30–45 ms** (DataSet.add + a redraw of the item set).
  Evidence: `b_2_grab_shaded.png`.
- *Both pass; A ~2× faster, neither near the 100 ms ceiling.*

### 2 — Ghost overlays: positioned accurately with legible cost labels
- **A — GREEN.** Three ghosts (+$19 / +$11 / +$53) render as dashed bars with
  the price **as SVG text placed outside the bar** → fully legible even though
  each ghost is only ~13 px wide. Evidence: `a_2_grab_shaded.png`.
- **B — YELLOW.** Ghosts are **positioned correctly** (right rows, right times),
  but vis-timeline **clips item `content` to the bar box**, so "+$53" shows as
  a bare "**+**" — and the same clipping hits the grab item's own WO label
  ("ORD-…" → "0"). Evidence: `b_2_grab_shaded.png`. This is the single most
  material difference in the bake-off, because narrow bars are the *norm* in a
  high-mix shop and the priced-ghost label is demo-critical. Fixable only with
  an overlay label layer (see criterion 6).

### 3 — Dynamic semantic snap: per-drag targets injectable, magnet, Alt-disable
- **A — GREEN.** Per-frame control in dnd-kit's `onDragMove`: raw pointer time →
  `snapTime()` → magnet to predecessor-finish / shift-openings / neighbour edges
  / priced ghosts, 30-min grid fallback, **Alt disables** (`predecessor_finish`
  → `free`, machine-verified). Evidence: `a_3_snap_ghost.png`,
  `a_4_snap_predfinish.png`.
- **B — GREEN (mechanics) / feel-limited.** The **only** per-drag seam is
  `onMoving(item, cb)`; we override `item.start` there. Snap works, Alt works
  (`predecessor_finish` → `free`, verified). But magnet *feel* is reachable only
  through that one coarse hook — no per-frame "pull"/indicator without the same
  fragile overlay layer. Evidence: `b_3_snap_ghost.png`, `b_4_snap_predfinish.png`.
- *Both pass the mechanic; A has materially more feel headroom.*

### 4 — Tentative-bar state renderable as visually distinct
- **A — GREEN.** Hatched purple SVG rect + a "tentative · <snap>" caption and a
  drop line. Evidence: `a_5_tentative_drop.png`.
- **B — GREEN.** `grabitem.dropped` CSS (repeating-linear-gradient hatch +
  dashed border). Evidence: `b_5_tentative_drop.png`.

### 5 — Screenshot-harness friendliness (Playwright) — a HARD-FAIL gate
- **A — GREEN.** Driveable two ways: the scripted page contract *and* a **real
  dnd-kit pointer drag** (Playwright `mouse.*`), robustly, every run.
- **B — GREEN, with a caveat.** Also driveable both ways. The real
  **vis-timeline (Hammer.js) drag engaged via Playwright** — `onMoving` fired,
  the grab item moved rows, shading appeared (`b_6_realdrag_mid.png`). *Caveat,
  honestly recorded:* Hammer.js is **finicky to drive** — it engaged only with a
  diagonal, multi-step, group-crossing gesture; a naïve small horizontal drag
  did **not** trigger it (three failed diagnostic techniques before the
  harness's diagonal drag worked). So B is not a criterion-5 hard fail — my
  first instinct that it was, was a diagnostic artifact, corrected by driving
  the real gesture — but its headless drag is less forgiving than dnd-kit's, a
  tax on the iteration workflow.
- *Neither hard-fails. Both produce the full state series headlessly.*

### 6 — Feel ceiling (honest judgment, where each will fight us)
- **A — GREEN / high ceiling.** SVG + React gives total reach: label placement,
  overlays, shading nuance, magnet indicators, tentative styling are all just
  more elements. dnd-kit is used **only as the pointer-lifecycle/sensor** (its
  DOM-CSS-transform model doesn't fit SVG, so we read its `delta` and own the
  geometry — a clean, revealing marriage, not a fight). *Cost:* we build the
  axis, zoom/pan, and (at large N) virtualization ourselves — but the entire
  Tier-0/1/2 interaction is bespoke anyway, so little is "saved" by a library.
  Minor: the React state model makes the harness read state a render-tick late
  (imperative candidates read immediately).
- **B — YELLOW / lower ceiling for *this* surface.** vis-timeline hands us a
  polished axis + zoom/pan/day-labels for free (genuinely nicer than A's out of
  the box — see `b_*` axes). But the differentiated cockpit is *all* overlays,
  and vis fights exactly there: (a) **every** in-bar label clips (criterion 2) →
  an always-on overlay layer is needed for prices *and* narrow-bar labels;
  (b) that overlay must track vis's internal pan/zoom transforms — **fragile**;
  (c) magnet feel is one `onMoving` hook; (d) styling is by fighting vis's CSS
  and DOM structure; (e) per-drag dynamic overlays couple our interaction state
  to vis's DataSet/redraw. Over *weeks* of feel iteration on a bespoke surface,
  the friction is concentrated on the highest-value bits. Real, but **not
  "clearly disqualifying"** — the spike proved vis can host the whole
  interaction, price-label legibility excepted.

### 7 — Licensing (the Bryntum lesson)
- **A — GREEN.** react, react-dom, @dnd-kit/core all **MIT**. SaaS redistribution fine.
- **B — GREEN.** vis-timeline + vis-data **(Apache-2.0 OR MIT)**. SaaS redistribution fine.
- *No OEM blocker either way. Bryntum stays out of scope (OEM licensing).*

---

## The honest caveat about the fixture (a real spike finding)

The board is a **real** unmodified `messy_realistic` solve. But every generator
scenario — verified — **routes each operation to exactly one resource**
(eligibility-size distribution `{1: 475}`; single `resource_id` per routing
line). Consequences for a *drag* fixture:

1. **No legal cross-machine move exists in generated data.** A moved task's only
   real degree of freedom is *time on its own row*. The whole Tier-0/Tier-1
   value proposition ("+$120 on the *other* press") has no legal target.
2. **The solution pool is flat here.** On this slack schedule the pool yields
   **9 movers at cost-delta $0, none in a precedence chain** — no priced,
   successor ghosts to render.

So: board **geometry** anchors (the grab bar, its real predecessor's finish,
its row's real neighbours, the real calendar openings) are **derived from real
data**; cross-row **legality + ghost placements** are an authored
`spike_capability_overlay` (same-facility workcentres as an eligibility pool),
**priced with the real cost model's per-resource rates**, and labelled as such
in `anchors.json._meta`. Per the brief, anchor *computation* is interim-A work
and static anchors are the honest scope — this makes the stand-in transparent.

**Carry-forward for W1/Phase-3:** the generator has **no capability-based
multi-eligible routing**, so it cannot yet produce a faithful drag fixture. A
capability-routed scenario (or a routing overlay) is a prerequisite for real
Tier-0/Tier-1 anchor computation. Filed as a spike finding, not fixed here.

---

## Reproduce

```
# from repo root, PYTHONHASHSEED=0
python tools/generate_erp_dataset.py --seed 7 --scenario messy_realistic \
    --out tools/spikes/frontend_bakeoff/fixture/messy_submission
python -m mre --submission tools/spikes/frontend_bakeoff/fixture/messy_submission \
    --out tools/spikes/frontend_bakeoff/fixture/messy_run --snapshot-id snap-messy \
    --solver-workers 1 --solver-seed 42 --time-limit 40
cd tools/spikes/frontend_bakeoff
PYTHONHASHSEED=0 python build_fixture.py        # -> fixture/{schedule,anchors}.json
npm install
npm run dev                                      # http://localhost:5173
node harness/run.mjs                             # -> shots/*.png + report.json
```
