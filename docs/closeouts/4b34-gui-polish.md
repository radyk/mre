# Session 4B.34 — GUI polish: six items from the interrogation pass

2026-08-03 · cockpit-only (no Python, no solver, no contract change) ·
docs/04 **R-GP1** ruled and built · contract unchanged **1.15**

Six small independent items from Daryn's live interrogation of the Khalil board,
plus one measurement. All seven closed. Two of the six did not hold up as
briefed and are reported as measured rather than as assumed — see §7.

---

## 0. MEASUREMENT — the flagship button on an accepted child

**IT ROUTES AND TESTIFIES. The finding is closed for the demo path.**

Driven through the real door on the live dev API: child `caff8efa` opened in the
cockpit, the moved bar (`0947fa39…`, ORD-000029 op10 on CUT-03) clicked, then the
job panel's **"Why is this here?"** button pressed. Verbatim:

> ORD-000029 op10 couldn't start before Tuesday 2026-01-06 07:00: it needs 57m in
> one piece and CUT-03 had only 23m left when it came free at 2026-01-05 18:37,
> and it can't be split.
>
> What pushed it, in order:
>   2026-01-05 00:00  release date [docs/05 A4] — its release date is 2026-01-05 00:00
>   2026-01-05 07:00  the machine's calendar [docs/05 C1/C2] — CUT-03 is closed until 2026-01-05 07:00
>   2026-01-06 07:00  no window long enough [docs/05 C3] — it needs 57m in one piece and CUT-03 had only 23m left when it came free at 2026-01-05 18:37
>
> Not weighed here (docs/05): B3/B5 secondary and cumulative resources (tools,
> operator pools); B7/B8 sequence-dependent changeover; C4 time-window operation
> restrictions; F3 SameResource linkage.
>
> `[rendered by: template — authored copy — rendered verbatim | register: testimony]`
> `lit 1 bar(s) · on: CUT-03 · alternatives weighed: CUT-01, CUT-02`

4B.33 §7(c) reported the TYPED question landing on CLARIFY `no-subject`. That
remains true and remains a ladder/parse matter. **The cockpit's own path — click a
bar, press the button — supplies the subject and lands on `why-here` correctly on
an accepted child.** No demo-blocking finding.

**One thing this measurement nearly got wrong, recorded because it matters.** The
first run returned the capability-list floor ("I can't answer this question yet")
— which would have been reported as a demo-blocking defect. It was an artifact of
**my own setup**: I had started uvicorn directly without loading `.env.local`, so
the parse layer had no key and fell to the honest floor exactly as designed. The
measurement was re-run against a properly keyed API. A tooling artifact reported
as a product defect is worse than no measurement.

---

## 1. Dock collapse must reclaim space — FIXED

**Measured at HEAD on the Khalil board: `#tl` stayed 555px tall whether the tray
and coarse docks were open or collapsed. 248px of dead space.**

| state | tray box | coarse box | board `#tl` |
|---|---|---|---|
| all open | 116px | 132px | 555px |
| tray shut | **116px** | 132px | **555px** |
| both shut | **116px** | **132px** | **555px** |

**The cause was one CSS property.** `.dock.collapsed` set `height:
var(--dock-edge-h)`, but the tray and the coarse band are FLEX CHILDREN carrying
`flex: 0 0 <their own height>` — and a fixed flex-basis wins over `height`
outright. Both docks went on reserving their full height while showing nothing
but an edge. The ask column reclaimed correctly only because its size is set by
its PARENT's grid template, a second mechanism.

**Two more layers had to be fixed before the space could land anywhere:**

- `#app` was `grid-template-rows: auto 1fr` — an assumption that the shell has
  exactly two children. Every banner the app prepends (superseded, newer-schedule,
  auto-follow) is a THIRD, which pushed `.split` into an implicit AUTO row where
  it sized to its own content. **The banner was live on the Khalil board**, so
  this was the operative state, not a corner case. Now a flex column, which names
  the flexible child instead of counting rows.
- `.split`'s row was auto-sized; now `minmax(0, 1fr)`.

**After, measured to the pixel:** board `483.1 → 573.1 → 679.1` as the tray
(90px) then the coarse band (106px) collapse — exactly what each gave back. On
the demo board this is the difference between a board that scrolls internally and
one that does not.

**ONE MECHANISM, and `.dock.collapsed` is the only state.** The three `onChange`
handlers collapsed to a single `relayout()`; the ask column's grid template is
now derived via `:has()` from the same class. A fourth dock inherits the
behaviour by existing.

**Found on the way, and it is a real one:** the collapsed ASK edge was clickable
only in a **26×26 corner**. The generic height collapse is wrong for a dock that
folds SIDEWAYS — `.ask` clipped to a 26×26 square, and since its edge is a 900px
strip rotated into that column, `document.elementFromPoint` returned `.split`, not
the button, at every point down the strip. **A planner who collapsed the ask panel
could not reopen it except by hitting one corner.** The collapse axis is now on
the element (`data-collapse-axis`) and the CSS collapses the right dimension.
This was pre-existing, not introduced here; it surfaced because the guard clicks
the control the way a hand does.

---

## 2. The legend's home — FIXED

**The chosen home: normal flow, its own strip directly beneath the board, inside
`.board-chrome`.**

**The rule that decided it:** the legend may never overlap interactive content at
ANY viewport width the cockpit supports. An absolutely-positioned row can satisfy
that only by arithmetic — a `bottom` ladder recomputed for every combination of
docks — and there were five such rules, already wrong for the bars themselves:
measured at HEAD the legend sat on the board's last 46px at **every** width
tested. In flow the invariant is structural: the row occupies its own strip, so
there is no width at which it can intersect a bar, a tray chip or a coarse cell.

It costs the board the row's own height, which is the honest price of not
covering the thing the planner is reading. The scrim, border and blur are gone —
they existed to keep it readable over bars — taking the row from 90px to **72px**
at 1540, 96px at 1100.

**Daryn's report was "the legend floats over the tray chips"; the measurement
found it floating over the BARS instead.** The tray was cleared by the ladder's
arithmetic; the bars never were. The fix covers both by construction, and the
guard asserts zero intersection with the tray body, the coarse band, the timeline
foreground, and **every individual bar**.

---

## 3. Popups that hide what they describe — FIXED, both classes

**(a) TRANSIENT tooltips — smart-positioned.** The card was placed at pointer +
(14,14) and flipped only when it would leave the HOST; nothing in that says
anything about the one rectangle it must not sit on. It now flips to the side of
its SUBJECT with the most free space (horizontal first — a board is wide and its
rows are short), with a vertical fallback, and the **no-intersection test decides
rather than an assumption that the flip worked**. The subject rectangle is read
from the renderer that already owns the geometry (vis's item DOM for a bar; vis's
`toScreen` + group foreground for a capacity band), so no second coordinate
system is kept in step.

**(b) PERSISTENT panels — draggable.** The job panel is dragged by its header via
real pointer events, clamped so the header always stays grabbable, and its
position is **owned outside the subtree `show()` rebuilds** and reapplied on every
render — the 4B.28 boundary-grip lesson. An explicit ✕ retires the placement; the
next selection opens at the anchor.

**The guard had to be rewritten twice, and the reason is the finding.** A
five-bar sample passed cleanly against the *reverted* code. Measuring the
pre-fix placement across the whole board: **only 4 of 366 bars** actually ended
up under their own card (worst overlap 556px²) — it needs a bar low enough that
the card, offered downward, would leave the host and got flipped UP onto it. The
guard now sweeps **every** bar and asserts zero. A sample that misses a 1%
defect is a guard that certifies it.

---

## 4. The ASK chevron's axis — FIXED

Every dock drew the vertical disclosure pair (▾/▸), right for the tray and the
coarse band and wrong for the ask column, which collapses SIDEWAYS: "▾" promised
a fold that never came. The axis is now declared per dock; `x` draws ▸ open / ◂
collapsed, and the collapsed ask edge (rotated 90°) counter-rotates its chevron so
it points where it actually goes **on screen**. `data-dir` carries the direction
semantically, so the guard asserts a DIRECTION rather than a character.

---

## 5. Compression — the 3-state cycle SHIPPED; the state loss DID NOT REPRODUCE

**(b) THE CYCLE IS LIVE:** `linear → folded → clean → linear`, persisted per
browser, and a browser carrying 4B.28's boolean is honoured as `folded` so an
existing choice survives the change.

**THE LABEL IS THE DISCLOSURE** and names the active view in every state:

| state | label | axis | fold marks |
|---|---|---|---|
| linear | `⇤ linear` | nothing hidden | 0 |
| folded | `⇥ compressed · folds marked` | 23 hidden ranges | 23 |
| clean | `⇥ compressed · clean` | 23 hidden ranges | **0** |

`clean` carries the strongest emphasis (dashed border) because it is the state
that looks most like an ordinary board and is least like one: time has been
removed from the shared axis and no fold mark says so. 4B.28's plant-wide-fold
disclosure is untouched and remains a debt.

**(a) THE STATE LOSS DID NOT REPRODUCE.** Driven through the real button on the
live Khalil board, the mode, the hidden ranges and the label survived **nine**
paths: zoom (button), dock collapse, window resize, resize back, axis pan,
bar selection, theme toggle, **full page reload**, and **`board.rebind`**. The
mechanism is vis's own: `hiddenDates` lives in `this.options` and every
`setOptions` re-applies it from there, so the merge cannot drop it. Reported as
measured; no fix invented for a defect I could not produce.

**A RELATED REAL DEFECT WAS FOUND AND FIXED, and it is the same species.** The
label was a COPY written by the click handler, not a VIEW of board state — so
compression reached by any route other than the button left the button asserting
a view the board was not in. Measured live before the fix: `board.setCompressed(true)`
gave `compressed: true` with the label still reading `⇤ linear`. The mode is now
the state, `compressed` is derived from it, and the control subscribes
(`onViewMode`) instead of painting itself. **Its negative control is proven red.**

---

## 6. R-GP1 — the picker can now tell a demo board from a ceremony artifact

Ruled verbatim in `docs/04-design-history.md`, 2026-08-03. Cockpit-only: **no
schema change, no contract bump, no Python touched.**

**CURRENT means the most recent PLACEMENT-BEARING state of a lineage.** An
authority-only child is shown in the lineage, never outranks its parent, and never
fires the banner. The banner fires only when PLACEMENTS differ.

**THE LEDGER CANNOT DO THIS JOB, and that is measured.** On the live lineage:

| schedule | bars | ledger | plan digest | badge |
|---|---|---|---|---|
| `rolling-db5395dc-2ae` (Khalil) | 386 | $1,667,467.80 | `884cdc3a1feb` | — (root) |
| `rolling-b9adc31c560b` (thaw) | 386 | $1,667,467.80 | `884cdc3a1feb` | AUTHORITY-ONLY |
| `rolling-b4dd3010751f` (re-freeze) | 386 | $1,667,467.80 | `884cdc3a1feb` | AUTHORITY-ONLY |
| `caff8efa` (zero-move accept) | 386 | $1,667,467.80 | `884cdc3a1feb` | ACCEPTED-EDIT |
| `e2e18e8c` (+24h accept) | 386 | $1,667,467.80 | **`6ea1361c3f8d`** | PLACEMENTS-CHANGED |

**Five rows, one ledger, and exactly one different plan.** A picker showing the
ledger shows five identical rows.

**Proven live, with its control.** A freshly minted authority-only child
(`rolling-b12762371b3a`, minted by a real thaw on the ceremony board the brief
sanctions for mutation) became the newest row. Bound to the Khalil board:

- **pre-R-GP1** (`findNewerSchedule` with no predicate): offers
  `rolling-b12762371b3a` — a copy of the board you are already on.
- **with R-GP1**: `copies skipped: ["rolling-b12762371b3a"]`, offers `e2e18e8c` —
  a genuinely different plan.

**THE SCOPE IS THE LINEAGE, and the existing suite is what taught me that.** My
first implementation compared ANY newer schedule's placements against the bound
board, and `deeplink.spec.mjs`'s auto-follow guard went red: it injects a
RESUBMIT — a fresh solve under a new submission, serving the same fixture document
— which the unscoped rule swallowed as a copy. A resubmit is a different plan of
record even when placements coincide. Suppression now requires the candidate to be
a **descendant** of the bound board AND placement-identical. A guard for that case
is added.

**A zero-move accepted edit is not a plan change.** `caff8efa`'s key is its
parent's to the character. It earns its own badge (a decision WAS recorded) but
does not fire the banner or take CURRENT. **This was a judgement call the
three-badge vocabulary did not settle, and it is recorded as one** in docs/04
clause (5).

---

## 7. What the summary would undersell

- **Two of the six items were not what the brief described.** Item 5(a)'s state
  loss did not reproduce across nine paths; item 2's legend was occluding the
  BARS, not the tray chips. Both are reported as measured. The fixes shipped
  address what was actually there.
- **The negative-control harness was itself broken, and its first run was a
  false green — all seven "passed" in 2–4 seconds.** The Playwright config
  reuses a running fixture server, which serves a previously built `dist`; the
  controls patched source that was never rebuilt. This is 4B.28 §5a.123's lesson
  from a third side: **a control that does not reach the code under test proves
  nothing, and it fails by looking exactly like success.** With a rebuild in the
  loop, two more controls were revealed as partial reverts that still passed.
  All seven are now proven red against physically reverted code.
- **The ASK re-expand defect was found by the guard, not by the brief** — and it
  was the more serious of item 1's two problems. Dead space is ugly; a panel you
  cannot reopen is a trap.
- **Item 1 needed three fixes in three different layers** (the dock's flex-basis,
  the split's row, the shell's row model), and the shell one only bites when a
  banner is showing — which it was, on the demo board, because of item 6.

## 8. Carry-forwards (named, not fixed)

- **The reclaimed space is not FILLED.** vis renders 15 lanes at their natural
  height and leaves the remainder blank, so on the demo board collapsing both
  docks removes internal scrolling but leaves white space below the last row.
  Making lanes stretch is a `--lane-min-h` / vis `height:100%` question this
  session did not open — it would change every bar height and every screenshot.
- **`has-tray` / `has-coarse-band` are now dead classes.** Nothing reads them
  since the `bottom` ladder went. Left in place as host markers; a future session
  should remove them or give them a reader.
- **Item 3(b)'s "survives a data refresh" is close to a standing invariant.**
  `show()` rebuilds the panel's CHILDREN, not the panel element, so the inline
  position survives even without the explicit reapply. The negative control that
  IS red removes the drag entirely. If a refactor ever rebuilds `el` itself, the
  reapply is what will save it.
- **The plan digest is derived per tab and never stored.** A picker open on a
  data root with many schedules fetches one ~400KB document per row (progressive,
  cached, rows paint first). A registry column would make it free and is a schema
  change this session was walled off from.
- **The fold set is still plant-wide only** (4B.28 debt (c)) — disclosure kept,
  fix still queued. The `clean` state does not change this.
- **`cockpit.spec.mjs:111` (the deictic pair) is still red**, both themes,
  pre-existing since 4B.23 and not this session's test.
- **A stray submission** was created in the dev data root by a boundary preview
  during verification (`rolling-b12762371b3a`, a real authority-only child of
  `rolling-b4dd3010751f`). It is a legitimate ceremony child on the board the
  brief sanctioned for mutation, and it is now a useful live R-GP1 specimen.
  **`rolling-db5395dc-2ae` and `rolling-c362baa4-1b0` were not touched.**

## 9. Verification

- **Cockpit Playwright: 361 passed / 2 failed of 363.** Baseline was 306/2/308.
  **+55 tests** (15 pure-logic in `lineage.spec.mjs`, 20 browser in
  `guipolish.spec.mjs` × 2 themes). The 2 failures are the known deictic pair.
  No other test regressed.
- **`boundary.spec.mjs:322` was carried forward, not regressed.** It asserted the
  two-state toggle returning to linear in one click; item 5(b)'s ruling puts a
  state between them. Every assertion it made is still made, plus the new `clean`
  state, via the correct number of clicks.
- **Seven negative controls, all proven RED** against physically reverted code:
  dock reclaim, legend in flow, chevron axis, tooltip subject-avoidance, panel
  drag through the header, label-as-a-view, R-GP1's copy predicate.
- **Premise tests:** an authority-only child really is placement-identical (and
  its own negative: a moved operation changes the key); the two injected fixture
  children really do differ, compared through the same derivation the product
  uses.
- **Python suite: 2415 passed / 291 skipped / 0 failed** in 965.9s — exactly the
  4B.33 baseline. **No Python file was modified this session** (`git status`
  confirms: every changed source file is under `src/cockpit/src/`), so the run is
  a proof of no accidental drift rather than a re-anchoring.
