# Session 4B.35 — one clock, and the refused nudge

Night before the Khalil cold demo. Two items in strict priority order.

---

## §2 — THE VERDICT (written before any fix, per the brief)

The brief offered three branches. **The measurement chose none of them cleanly:
the drop instant is CORRECT, and two of the three live specimens do not
reproduce at HEAD.** What is real and reproducible is the two clocks
(Specimen A) and the labelling of refusal cards.

### (a) Specimen A — CONFIRMED, mechanism named

Stored instants carry `Z` and are true UTC:

```
ORD-000128 op20  2026-01-13T16:09:00Z -> 2026-01-13T18:29:00Z
ORD-000128 op30  2026-01-14T07:00:00Z -> 2026-01-14T08:30:00Z
```

* the **ask testimony** renders the stored UTC verbatim → "op20 finishes at
  2026-01-13 18:29";
* the **board and job panel** render through `toLocaleString(undefined, …)`,
  i.e. **browser-local**, which in January in Toronto is UTC−5 → "Jan 13,
  11:09 → Jan 13, 13:29".

Exactly 5h, on every pair, and **neither surface is labelled**. Daryn's
observation is exact and the mechanism is a one-line-per-site rendering choice
repeated across the cockpit.

### (b) The drop instant is NOT shifted — branch (ii) is KILLED

Driven through the user's door (a real pointer drag on the real bar, Playwright
at `timezoneId: America/Toronto`, the live API over the real Khalil board):

```
ORD-000128 op30 on HEAT-01, +2h nudge (30px at 15.19 px/h)
  vis round-trip error        : 0 ms
  carry instant (UTC)         : 2026-01-14T10:00:00.000Z
  carry as DRAWN              : Jan 14, 05:00 AM
  beat one pin_start_iso      : 2026-01-14T10:00:00.000Z   <-- identical
  beat two pin_start_iso      : 2026-01-14T10:00:00.000Z   <-- identical
```

The gesture surface works in epoch milliseconds end to end
(`geometry.eventToTarget` → `magnets.snap` → `new Date(t).toISOString()`); the
carry tracks the pointer to within the grid snap. **The gate evaluates exactly
the instant the board drew.** The display clock never enters the arithmetic.

### (c) Specimen B — DOES NOT REPRODUCE

The same +2h nudge **prices cleanly**: beat one `possible`, beat two a
`$0` card reading *"Same cost · VERDICT · PROVEN WITHIN BUDGET"*.

Swept every tier-0-legal instant for that bar, 2h steps, Jan 13 → Jan 17:

```
tier-0-legal instants probed: 15;  beat-one refusals among them: 0
```

`op30`'s `eligible_resource_ids` is **`['HEAT-01']` alone**, so no cross-row
drag can reach another machine except as a *capability* refusal (a tier-0
card, corner "proven", not "beat 1"). **The beat-one refusal branch is
unreachable on this bar.** The card Daryn saw cannot be produced from a
tier-0-legal drop on `ORD-000128 op30` at HEAD, and its provenance is not
established. It is NOT a stale `dist` — `dist` is newer than every source file.

### (d) Specimen C — reproduces in shape, but the refusal is NOT nameless

A 30px drag at the board's own default 31-day window (= **+20.4h**, snapped by
the *calendar* magnet to exactly **+24h**, `2026-01-15T07:00:00.000Z`) refuses
— and **names its blocker**:

> Can't go here · VERDICT · PROVEN WITHIN BUDGET
> "the next step in this order is already scheduled before this one would
> finish — and this price holds every other job exactly where it is, so the
> scheduler might still fit it here by moving other work"

That is a **beat-two** refusal in 4B.31's vocabulary, and Daryn's diagnosis of
the cause (op40 held at Jan 15 07:00Z) is correct. It is not the nameless card.

### (e) What the sweep exposed on the way — the axis a planner cannot read

HEAT-01's open window is `07:00Z–19:00Z`. Rendered browser-local that is
**02:00–14:00**, so on Daryn's screen every machine on this plant appears to
start its shift at **2 AM**. Bars, closure shading and the axis are all drawn
from the same epoch and are internally consistent — but the *labels* are five
hours from what the plant means. This is the same defect as (a), seen on the
axis instead of in a sentence, and it is what makes a correct board feel wrong.

### Verdict

> **The clock is wrong on the surfaces, not in the arithmetic.** The drag path,
> the gate and the pricer all agree on the instant to the millisecond; every
> planner-facing *rendering* disagrees with the testimony by exactly the
> browser's UTC offset. Item 1 (R-TZ1) is therefore the whole of the clock fix,
> and it is a RENDERING change. Item 2's branch is (iii)-adjacent: nothing was
> hiding a real blocker, because at HEAD there was no refusal to explain.


---

## §3 — ITEM 1: R-TZ1, ONE CLOCK (BUILT)

Ruling verbatim in `docs/04` (2026-08-03). The clock is the FACILITY's, declared
in the IDS manifest (`timezone`, docs/06 §3), delivered on `/meta` with its
provenance, labelled once on the board chrome. Stored instants are untouched.

**The Khalil board declares `timezone: UTC`**, so the board and the testimony now
agree by construction — and the shifts read `07:00–19:00` instead of the
`02:00–14:00` a Toronto browser was drawing.

### The census — every time-rendering site, clock before and after

| # | site | what it renders | at HEAD | after |
|---|------|-----------------|---------|-------|
| 1 | `board.js` `fmtClock` | row strip booked-through / next gap | browser | declared |
| 2 | `board.js` vis `moment` | **the axis itself** | browser | declared |
| 3 | `hovercards.js` `fmtDay` | bar hover start/end | browser | declared |
| 4 | `hovercards.js` `fmtHM` | downtime window span | browser | declared |
| 5 | `hovercards.js` `fmtWeekdayTime` | "reopens …" | browser | declared |
| 6 | `jobpanel.js` `fmtClock` | **the specimen-A surface** | browser | declared |
| 7 | `jobpanel.js` `fmtDay` | due dates | browser | declared |
| 8 | `tray.js` `fmtDue` | beyond-horizon due dates | browser | declared |
| 9 | `coarse.js` `fmtBucket` | coarse bucket labels | browser | declared |
| 10 | `markers.js` `labelFor` | frozen-boundary drag label | browser | declared |
| 11 | `drag/controller.js` `_cardWhen` | card context instant | browser | declared |
| 12 | `drag/sandboxui.js` `_shortDate` | delta-card placement line | browser | declared |
| 13 | `main.js` identity chip | solve timestamp | browser | declared |
| 14 | `schedulepicker.js` `whenLabel` | picker rows | browser | declared |
| — | ask testimony (Python) | every answer | **UTC** | **UTC (unchanged)** |

`src/cockpit/src/clock.js` is now the only place a stored instant becomes text.

### Live confirmation, Khalil board, real pointer, browser on America/Toronto

```
clock chip     : All times UTC          (provenance: declared)
op20 stored    : 2026-01-13T16:09:00Z -> 2026-01-13T18:29:00Z
axis (minor)   : 10:00 11:00 12:00 13:00 14:00 15:00 16:00 17:00 18:00
delta card     : ORD-000128 → HEAT-01 · Jan 14, 10:00 a.m.
                 (before R-TZ1 the same card read "Jan 14, 05:00 AM")
```

### Guard

`tests/cockpit/oneclock.spec.mjs`, 4 tests, stated as an INVARIANCE — *the
browser's timezone does not change what the board says* — in a browser pinned to
`America/Toronto`, with the disagreement asserted as a premise so the spec cannot
pass vacuously in a UTC container. **Three negative controls proven RED, each on
its own half:**

| control (physically reverted) | red |
|---|---|
| A — `fmt()` drops `timeZone`, back to the browser clock | render, axis, panel (3) |
| B — the vis `moment` option removed | axis alone (1) |
| C — the label removed from the strip | label alone (1) |

Control A's first run was GREEN against a **stale `dist`** — the harness reuses a
running fixture server. 4B.34's own false-green, from the other side; the server
is killed and rebuilt before every control now.

---

## §3b — ITEM 1b: A REFUSAL CARRIES ITS BLOCKER (BUILT)

**The brief's hypothesis was right: the checker returned a bare boolean.** CP-SAT's
`INFEASIBLE` carries no attribution, so `feasibility_message(IMPOSSIBLE, …)` was a
CONSTANT string. Fixed at the checker (`local_price.relaxed_refusal`), restricted
to the families that survive beat one's relaxation — reasoning verbatim in
docs/04. Labels: `proven impossible` on both refusal registers, replacing a
"Can't go here" card that wore `verdict · proven within budget`.

---

## §5 — THE 20-PROBE RE-MEASURE (report only)

Khalil board, 20 single-chunk active bars spread across the plan, each nudged
**+3h on its own machine** — one gesture each, beat one then beat two.

```
refusals : 18      priced : 2      no price : 0
```

* **Every beat-one refusal is NAMED** — 10 of 10, all `C1/C2`
  ("the machine is not open at that time"). At HEAD all ten read the constant
  sentence.
* Beat-two refusals are all `B1` **with `holds_others` set** — "not without
  moving other work", never "no".
* **BOTH prices are NON-ZERO: $75.00 each** (ORD-000128 op40, ORD-000043 op40,
  both FINISH-02). 4B.32 measured 4 prices, **every one exactly $0.00**, and
  §5a.132 recorded the ledger-MOVED branch as *unreachable from a drag on this
  board*. It is reachable, and now observed. The 90%-refusal ratio itself stands
  (4B.32: 50/54; here 18/20) — §2 already established the drop instant was never
  shifted, so those numbers were never artifacts.

---

## §6 — SUITES

| suite | this session | baseline |
|---|---|---|
| Python | **2416 passed / 291 skipped / 0 failed** | 2415 / 291 / 0 (4B.33) |
| Cockpit | **364 passed / 3 failed of 367** | 361 / 2 / 363 (4B.34) |

The Python `+1` is `test_corpus.py::TestCurrency::test_index_matches_the_live_docs`,
which was **RED AT HEAD**: 4B.34 amended `docs/04` and did not rebuild the corpus
index. Not caused here, fixed here (`python tools/build_corpus_index.py`).

Cockpit `+4` is `oneclock.spec.mjs`. Of the 3 failures, 2 are the known deictic
pair. The third —
`beat_two.spec.mjs:200 "the failure card's 'Try again' really re-runs the SAME pin"`
— **passes 11/11 in isolation** and did not fail in this session's earlier
full-suite run. It is a **SEVENTH member of the standing parallel-load flake
class**, recorded as such and not as a pass.

---

## §7 — WHAT WAS CUT AND CARRIED

* **The Python answer surfaces still render stored UTC verbatim.** This AGREES
  with R-TZ1 wherever the facility declares UTC — which both pinned worlds do,
  so board and testimony agree today — but it is not GOVERNED. A facility
  declaring `Europe/Istanbul` would get a correct board and testimony five hours
  from it. The fix is the same shape (one formatting boundary, the declared zone
  threaded to the renderers) and is the largest single thing this session did
  not do. Named, per the brief's minimum bar.
* **Specimen B's provenance is unresolved.** It does not reproduce at HEAD from
  any tier-0-legal drop on that bar (0 of 15 measured), it is not a stale
  `dist`, and `op30` is eligible on one machine so no cross-row drag exists. It
  may have been a different bar or an earlier board state. Recorded as
  unexplained rather than closed.
* **`relaxed_refusal` cannot attribute a refusal that no surviving family
  explains**, and says so. On the 20-probe sweep every beat-one refusal WAS
  attributable (10 of 10, all C1/C2), so the unattributed branch is proven by
  unit path only, not observed live — the §5a.11 limit again.
* **The ask-ladder findings** from the briefing exchange (undisclosed
  earlier-assumption; premise correction not firing on "can't be moved";
  two-direction answer shape) are on the ledger, untouched, per §6 of the brief.
* **A monolithic board's clock label is unexercised live** — the chip is on
  `/meta`, which every board has, but only rolling boards were driven here.

---

## ADDENDUM (2026-08-03, demo-prep sweep) — THE UNNAMED CHILD

A registry sweep before the Khalil demo found a schedule this close-out does not
account for: **`6ff7d6da-275e-4867-bd49-1efc2dd91275`**, parent
**`rolling-b12762371b3a`** (the R-F1 boundary-move child of the Khalil lineage),
minted `2026-08-03T00:56:40Z` — inside this session's own working window, ~30
minutes after 4B.34's commit and two hours before 4B.35's.

**What it is.** A real `planner_edit` accept, and the sharpest R-DP13 specimen in
the data root:

```
run e6b9c2c6-…  kind=accept  authority=dev-planner
pin  ORD-000126 op30 -> FINISH-01 @ 2026-01-15T12:30:00.000Z
     (incumbent 2026-01-15T10:29:00Z; +121 min, one 30-min grid step past a first try)
Decision (M4, headline, basis=observed):
     "Planner edit: pinned op 58b160c5 to c3459e27 @ 2026-01-15T12:30:00+00:00 (+$403)"
     driver = PLANNER_DIRECTIVE       verdict = OPTIMAL      objective_cleared = true
     moved_count = 1, resource unchanged, start_delta_min = +121
     ledger 1,667,467.80 -> 1,667,871.13   total_delta +403.33, ALL tardiness
     (production_delta 0.00, setup_delta 0.00);  delta_abs = null  (R-DP12)
```

**What gesture minted it.** A live pointer drag in the cockpit, priced twice and
then accepted — the trail is in the parent run's sandbox, and the *two* beat-one
model builds are what identify it as a hand rather than a script:

```
00:52:33Z  beat one, pin_start_min 15120  (Jan 15 12:00Z, +91 min)   1.892 s
00:52:43Z  beat two, priced
00:56:25Z  beat one, pin_start_min 15150  (Jan 15 12:30Z, +121 min)  0.889 s
00:56:33Z  beat two, priced (FEASIBLE, 7.71 s)
00:56:38Z  ACCEPT  ->  child 6ff7d6da minted in 1.70 s
```

Dragged, priced, nudged one grid notch further, priced again, accepted. The
`.000Z` millisecond form of `pin_start_iso` is `Date.prototype.toISOString`'s,
i.e. it came through `drag/controller.js`, not through Python.

**Why this close-out missed it.** Two reasons, and the second is the one worth
keeping.

1. **4B.35 has no housekeeping section.** 4B.32 closed with a `§11 Housekeeping`
   that listed every row and directory it created or deleted and proved the data
   root clean afterwards; 4B.34 and 4B.35 did not carry one forward. A child that
   no section owns is a child no reader can find.

2. **Every gesture in this session's narrative is a *measurement*, and this one
   *committed*.** §2 reports carry instants and beat-one/beat-two verdicts; §5
   reports 18 refusals and 2 prices. All of those are read-only — pricing mints
   nothing. Exactly one gesture in the session pressed **Accept**, and pressing
   Accept is not a measurement: it mints a schedule, a run, a snapshot, a
   `PLANNER_DIRECTIVE` Decision and (at 00:57:17Z) an `alternatives` pool. The
   session was watching the *card* and did not look at the *registry*. The board
   this session was measuring against was `rolling-b12762371b3a`; from 00:56:40Z
   onward the newest row in the lineage was `6ff7d6da`, and nothing said so.

**The irony worth recording.** 4B.33 §5a.135 named as a limit that *"no exam bank
can reach `PLANNER_DIRECTIVE` — neither pinned world holds a single `planner_edit`
Decision, so the specimen needs a new pinned world."* This session produced, by
accident and without noticing, the first `PLANNER_DIRECTIVE` accept on this board
with a **non-zero ledger delta and a real move** — 4B.33's own two live children
(`caff8efa`, `e2e18e8c`) both left the ledger at $1,667,467.80. It is being
deleted with the rest of the demo-prep sweep; its Decision is transcribed above
so the specimen survives the row.
