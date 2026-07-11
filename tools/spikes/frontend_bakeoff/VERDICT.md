# Frontend bake-off — VERDICT

**Session 3.0 SPIKE · 2026-07-11 · throwaway code, verdict is the deliverable.**
Nothing in `tools/spikes/frontend_bakeoff/` ships. This picks the rendering
substrate for the Phase-3 reasoning cockpit's three-tier drag surface
(docs/07 Phase 3). Decision rule (from the brief): **LIBRARY WINS TIES**;
custom wins only if the library hard-fails criterion 1, 3, or 5, or its feel
ceiling is *clearly disqualifying with evidence*.

> **[3.0 banner — now superseded]** Do not update docs/07's frontend line on
> this alone — review together first.
>
> **[3.0b update, 2026-07-11]** The follow-up ran and settled it — see the
> **[3.0b addendum](#30b-addendum--the-drop-rulings-four-killer-criteria)** at
> the foot of this file. vis-timeline cleared all four drop-ruling criteria
> clean; **docs/07's frontend line IS now updated (v1.8)** per the 3.0b brief's
> instruction. The recommendation below is the 3.0 record; the addendum is the
> final word.

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

---
---

# 3.0b ADDENDUM — the drop ruling's four killer criteria

**Session 3.0b · 2026-07-11 · half-day timebox · same spike, same directory,
throwaway code.** The 3.0 recommendation was *adopt vis-timeline conditional on
a short follow-up proving a stable always-on overlay layer, with custom React as
the zero-blocker fallback if the overlay (or magnet feel) proved fragile.* 3.0b
**is that follow-up**, widened by a new ruling (docs/04 pending):

> A drag is a literal must — the bar lands exactly where dropped or returns home;
> proven-illegal zones must **visibly REFUSE the drop mid-drag** (no post-hoc
> dialog); semantic snap with generous tolerance interprets within legal zones.

**Decision rule (from the 3.0b brief, final):** vis-timeline is adopted **only
if all four criteria pass clean**. Any failure or fragile workaround → Candidate
A (custom React/SVG + dnd-kit) is selected, on the evidence it cleared every 3.0
criterion in one day with headroom.

Only vis-timeline was under test (the 3.0 sheet already cleared A). New surface:
`candidate_b_3b.html` + `src_b/main_3b.js` (zoom/pan **enabled**, unlike 3.0's
frozen window, so the overlay's tracking is actually exercised) + a new
evidence harness `harness/run_3b.mjs` writing `shots/report_3b.json` and
`shots/b3b_*.png`. Same shared fixture + `shared/geometry.js` as 3.0.

## Result: **all four PASS clean → vis-timeline is ADOPTED.**

| | Criterion | Verdict | Machine-checked evidence |
|---|---|---|---|
| **C1** | Always-on overlay layer (labels + hatch, tracks pan/zoom, no drift) | **PASS** | ghost labels legible at every zoom; **max drift 0.0 px** across 3 windows (default 4-day → 30 h → 16 h) |
| **C2** | Mid-drag rejection of illegal zones + return-home | **PASS** | scripted + **real-pointer**: bar pins at the legal boundary, refuses the dim row, `phase=returned_home` on release |
| **C3** | One real magnet with falloff via `onMoving` | **PASS** | monotonic falloff `0→0→0.27→0.5→0.73→0.9→1.0` to a single anchor; 0 outside tolerance; Alt frees; **no throttle (0.95 call:step)** |
| **C4** | 20 consecutive headless drag runs | **PASS** | **20 / 20** (deterministic; every run `dropped`, 14 `onMoving` calls) |

Reproduce: `node harness/run_3b.mjs http://localhost:5173` → `shots/report_3b.json`.

### C1 — always-on overlay layer  ·  `b3b_c1_*` , `overlayProbe()`
The 3.0 blemish (vis clips **all** in-bar text, so "+$53" → "+") is **resolved**.
A positioned layer (`.spk-overlay`, mounted inside vis's `centerContainer`)
carries the priced ghost labels and the tentative hatch, and is redrawn from
vis's **public `getWindow()`** on `rangechange` / `rangechanged` / `changed`.
The honest drift test compares each overlay label's centre-x against the
**vis-rendered** ghost bar's centre-x (not against our own math): **0.0 px at
the default 4-day window, at a 30 h zoom, and at a 16 h zoom** — the overlay and
vis share the identical linear time→x map, so they cannot separate under
zoom/pan. Labels `+$19 / +$11 / +$53` are fully legible at every level
(`b3b_c1_2_zoomed.png`). *Residual, disclosed:* the overlay reads vis DOM
geometry (`centerContainer.offsetWidth`, `.vis-foreground .vis-group` rects) — a
stable public-ish surface, and the redraw is wired to vis's own pan events; I
verified settled-window drift across three zoom levels, not a single mid-flight
pan frame. Not fragile under the evidence gathered.

### C2 — mid-drag rejection  ·  `b3b_c2_*`
vis-timeline's `onMoving(item, cb)` is called continuously with the tentative
**group** under the cursor; calling **`cb(null)`** refuses that frame's move, so
the bar **will not enter an illegal (dim) row** — it pins at the last legal
boundary while the cursor + a banner go `not-allowed` (`b3b_c2_3_realdrag_over_dim.png`:
dragging up from the green home row toward a dim F001 row, the bar stops at the
amber F002 boundary, "⃠ illegal row — drop refused"). On release over an illegal
row, `onMove`'s `cb(null)` **returns the bar home** (`b3b_c2_4/…_2`,
`phase=returned_home`, origin row 12, `+$0`). Proven both scripted **and** by a
real Playwright pointer drag. The ruling's "visibly refuse mid-drag, no post-hoc
dialog, land-or-return" is satisfied through documented public API — not a
workaround.

### C3 — one real magnet with falloff  ·  `b3b_c3_*` , `magnetTo()`
A single magnet (the shift-start / ghost anchor at Wed 07:00, a real calendar
opening) implemented through the **only** per-drag seam, `onMoving`: shift-start
anchor, 30-min tolerance radius, **Alt-disable**, and a proximity **falloff**
line drawn in the overlay (opacity/width ∝ strength). Isolated-anchor sweep:
strength rises **cleanly and monotonically** from 0 (outside tolerance) to 1.0
(on the anchor) — `b3b_c3_1_magnet_falloff.png` shows the pull line on Wed 07:00
with "tentative · ghost · +$53.2"; Alt frees the snap (`b3b_c3_2_alt_free.png`).
The granularity question — *does the single coarse hook fight falloff?* — is
answered by counting `onMoving` calls against emitted pointer steps: **42 / 44 =
0.95**, i.e. **vis fires `onMoving` per pointer-move and does not throttle it**,
so hook granularity equals input rate. The hook carries falloff; it does not
fight it. *(Custom React still has a higher feel ceiling — a dedicated rAF loop
vs one library hook — but the hook is not the bottleneck here.)*

> **Honest correction (recorded, not hidden).** My *first* 3.0b C3 pass reported
> C3 **FAIL** on two counts. Both were **probe artifacts**, corrected exactly as
> the 3.0 criterion-5 Hammer diagnosis was: (1) "non-monotonic falloff" — the
> sweep measured *nearest-of-all-targets*, so passing near an unrelated
> `adjacency` edge broke monotonicity; the criterion asks about **one** magnet,
> so the corrected probe measures distance to the single anchor. (2) "21 Hz, too
> coarse" — that number was **Playwright's synthetic ~45 ms/step pacing**, not a
> vis throttle; the call:step ratio (0.95) is the throttle-free measurement.
> Corrected numbers above; the raw first run is in git history.

### C4 — headless reliability  ·  `report_3b.json.C4`
**20 / 20** consecutive real-pointer drags engaged Hammer.js, moved the grab
item across groups, and committed a drop. Deterministic: every run reached
`phase=dropped` with 14 `onMoving` calls. *The number behind "finicky":* 20/20 —
**conditional on the diagonal, group-crossing engage gesture** the 3.0 spike
identified (a naïve small horizontal drag still does not reliably trigger
Hammer). That gesture is now encoded in the surviving harness, so the headless
drag is repeatable — the tax is a prescriptive engage motion, not per-run flake.

## What this does to the 3.0 recommendation
3.0 said *vis-timeline, conditional on proving a stable overlay; custom React the
fallback if the overlay or magnet feel proved fragile.* 3.0b **discharged that
condition**: the overlay is stable (0 px), the magnet feel is reachable and
un-throttled, illegal-zone refusal works, headless drag is 20/20. Per the
decision rule, **the tie no longer needs the tiebreaker — vis-timeline passes on
its own merits. Adopt vis-timeline.** Custom React/SVG + dnd-kit stays on record
as the proven zero-blocker fallback (higher feel ceiling, no library to fight)
should later feel-iteration on the bespoke overlay surface change the calculus.
docs/07 frontend line updated (v1.8); this is the spike's final word.
