# SESSION W2.3 — the third-generation demo world

**2026-08-06.** W2 (docs/07 §5b), arbitrated by Daryn the same day. One subject:
mint and pin the board every demo runs on between now and the pilot. **No
ruling, no contract change** (1.17 unchanged), **prompts unchanged** (parse v19,
synthesis v9). docs/04 carries the two measurements that bind a later session;
docs/07 §5a.237-242 the position and the debts.

**THE BOARD IS `rolling-9fdee7aa-ec5`.**

---

## 0. The predicate audit, stated first — and both guards had holes

W2.2 shipped two predicates and its own §0 is the reason this is the first
section: *the builder is the worst-placed observer.* Both were **green at HEAD**.
Both are **incomplete**, and neither was found by reading — the reading suggested
where to push, and an injection settled it.

**(1) `unsourcedFigures` is hand-enumerated while `sourcesOf` walks.** W2.2's
audit found the first `sourcesOf` listing four branches by hand, rewrote it to
walk the model recursively, and wrote `unsourcedFigures` as the converse — *by
hand, over three shapes.* It fixed the defect in one sibling and reproduced it in
the other, in the same commit. Stripping `portfolioModel`'s only source string:

```
injected  src/cockpit/src/summarymodel.js  (62c428ee17cb9e28)
  ✓ every figure the model produces names a stored document field
  ✓ ...and nothing the model shows is left uncited
  ✓ THE GUARD WALKS THE MODEL - a new branch is covered by existing
restored  sha256 b02e3e0e3e9cbd39  (13,822 bytes, LF) — byte-identical
```

Three green, and the portfolio's winner total, spread and every member's ledger
total now render as money with **no citation**. Two mechanisms let it through:
`unsourcedFigures` inspects `stats.stats[].value`, `utilization.source` and
`money.total` and nothing else — so `money.rows[]`, the tardiness split, the
portfolio block and twelve progress figures are never looked at — and the
`sourcesOf` test is a **subset test**, asserting every source *used* is declared
and never that every declared source is *used*. Deleting a citation shrinks the
set silently. That is 4A-(d.2)'s `RECORDS_FROM` finding at a second site.

**(2) The zone guard is asserted in one direction.** Rendering a solver-units
figure *outside* `#sm-trail-zone`, in the region the screen declares to be
currency's:

```
injected  src/cockpit/src/summary.js  (578d8e7bc9cf224a)
  ✓ no dollar sign touches the SOLVER-UNITS ZONE (R-DP12 / R-SP1 clause 3)
  ✓ the zone stays money-free even when the headline is PRICED
restored  sha256 04862bdaa16c5204 — byte-identical
```

Money may not enter the zone; nothing stops the scaled objective leaving it.
W2.2 §6 names this exact risk — *"a future contributor adding one figure to the
wrong side would not obviously break anything"* — and says `#sm-trail-zone`
"exists so a test can catch it". It catches one of the two directions. Worth
adding: in the unpriced regime the whole `#sm-progress` section is asserted
money-free, and **that** assertion, not the zone, is what closed W2.1's original
`#sm-window-key` hole. The zone absorbed the table, cap note and curve; the
clauses and the window-key line still sit outside it.

**(3) A methodological finding, and it bit inside this very audit.**
**`git checkout --` is not a byte-identical restore in this repo.**
`core.autocrlf=true` returned `summarymodel.js` as **14,138 bytes of CRLF**
against the **13,822-byte LF** original — 316 lines rewritten, `git status`
clean, sha256 wrong. This is 4A-(a)'s newline lesson at a **fourth** site and
the first where the thing that broke was the *restore step of a negative
control* — the step whose entire job is to prove nothing was left behind. Both
files were restored by writing the captured bytes back, and both hashes match.

**Stale-process check:** dev API PID 20744 started 04:01:56, after HEAD's commit
(00:00:36), uvicorn **without `--reload`**, no uncommitted source. Serving HEAD.

---

## 1. The mint, and the STOP that was not taken

The brief required a **STOP** if placements moved, and the risk was real rather
than ceremonial: between gen-2 (1.15, 2026-08-04) and gen-3 (1.17, today) every
solve gained a solution callback recording a search history *and* an
unconditional first-incumbent `extract`. R-SP1's clause that the callback must
not perturb was ruled on an eight-job specimen.

It holds on 386 bars. The same committed recipe, re-run at HEAD:

```
placement digest  8071cdaaf953bc17a952b679c2d055c5ae414264720edae229a4a1eb17ed583a
```

— gen-2's digest, exactly. Sixteen assertions, every one green: 386 bars,
ledger **$1,667,467.80**, 24 committed / 122 tray, K=3 at 10.0 units, seed0 42,
winner **seed 44**, spread **$467,901.83 = 28.0606%**, members $2,135,369.63 /
$1,801,222.70 / $1,667,467.80, gap **89.6092%**, ACCEPTED / C2.

The mechanism is worth stating because it is the reason the result is not luck:
the callback costs **wall** time, and wall time is not what binds a deterministic
solve. Which is also why the mint ran **alone** — `time_limit` is a 900s wall
ceiling and gen-2's seed 42 used 481s of it, so a heavily loaded machine could
have pushed a member into truncation and produced a different board with no
error anywhere.

**The instrument was written before the mint and control-run against gen-2
first**: identity 16/16 green (it *is* gen-2), the new-at-HEAD half **13/14
red**. A verifier that only ever agrees proves nothing;
`tools/spikes/gen3_demo_world/verify_gen3.py` is committed with the gen-2
figures quoted from committed sources, so it cannot be back-fitted.

---

## 2. What gen-3 carries that gen-2 could not

| | |
|---|---|
| trail | **$2,128,903.83 → $1,667,467.80**, 21.7%, **2 incumbents** (180.09s, 180.91s) |
| bridge | `final_plan_cost` == the shipped ledger **to the cent**, on 386 bars |
| clause (1) | `window_key` `2026-01-05T00:00:00+00:00` |
| rollups | 102 late / 56 on-time / 158 counted · 6,886 changeover minutes · 15 machines |

The live cockpit — the real one on the real board, not the fixture harness —
renders the **priced** state in both themes: nine stat tiles each carrying its
`data-source`, **zero named gaps**, and the solver-units zone money-free in both.

**Two incumbents is the honest number and it is the interesting one.** A fixture
produces a 46-point curve; this board's search took 180 seconds to find anything
legal at all, improved once 0.8s later, and never improved again inside its
budget — with the gap still at 89.6%. That is what a real 386-bar plant looks
like, and the screen shows it without dressing it up.

**The brief expected 82–92% on the top machines; the measurement is 78.9% /
78.3% / 66.4%.** Since the plan is gen-2's to the digest, the board cannot have
changed — so this is a difference of *measure*, not of board. The server's
figure is horizon-wide; the cockpit's per-row figure is per-visible-window; the
screen already says the two answer different questions and may differ. Recorded
as a correction to the brief rather than rounded into agreement.

---

## 3. THE LARGEST FINDING IS NOT THE BOARD

**The `--runslow` ladder is 14 red at HEAD.**

The brief's reference baseline (2968/305/0) is the *no-`--runslow`* number. I ran
the full ladder. **284 tests that every recorded baseline has skipped for at
least six sessions came alive, and 14 of them fail.** Four causes:

* **Four stale contract literals** — `assert doc.contract_version == "1.14"`,
  four bumps behind. W2.2 bumped eight `"1.16"` literals and could only see the
  ones that run.
* **Three stale signatures** — *unexpected keyword argument `det_time`*. **One is
  `test_relaxation_guard_negative_control_goes_red`.** R-SC2's negative control
  has not been passing; it has been unable to execute.
* **One genuine contradiction** — `test_document_is_byte_identical_with_the_store_on_and_off`
  fails on the trail's `elapsed_s`, which vary by design. R-SP1 clause (6) says
  elapsed times are never asserted by a test; this test asserts the *whole
  document*. **Not adjudicated** — it is a ruling question for R4, not a patch.
* **Six live-LLM failures** — **not diagnosed**, named so silence is not read as
  a clean bill.

None are mine; no `src/` file was changed this session. **The rule this earns: a
suite result names the ladder it ran.** "2968/305/0" and "3239/21/14" are the
same tree, and only one of them had ever been written down.

---

## 4. The pin

```
capsule  C:\dev\mre_worlds\rolling-9fdee7aa-ec5.zip
  62 entries · 600,503 bytes
  sha256 b25503bbdb72cfa4015927de4a133e8094cc69de1679b831d0260107929ec8f1
```

Verified **by content, not presence**: the document *inside* the capsule
recomputes to `8071cdaa…`, and carries the trail, the statistics and the
alternatives evidence. It was pinned **twice** — the first capsule
(`359dc838…`) was taken before the alternatives step and was therefore
incomplete; it was removed only after its sha256 was checked against the one
this session wrote, and re-pinned.

Recipe, its required data-root state and the added `/alternatives` step are in
`docs/worlds/LEDGER.md`. The profile was verified byte-identical to 4x's record
(`119979563951d742…`, grid `ec5ffcef9009f423…`) **before** minting — without it
the same command lands on a different board, which is R-PW1(3)'s whole point.

---

## 5. The deferral, stated as a decision

**Lineage pending R4-accept.** The accept path on a rolling board currently mints
a monolithic, uncalibrated child; replaying lineage now would bake defective
children into a pinned world. No accept was attempted on gen-3. Recorded in the
world ledger so the gap is a *state*, not an oversight.

---

## 6. The rider, and a finding it turned up

**Mechanism verdict: none exists.** 28 API routes, **zero DELETE verbs**; no
removal helper in `api/registry.py`; no tool issuing a schedule deletion. The
registry is append-only by construction. Per the rider's own instruction:
**nothing was removed.**

**Picker before 9 → after 10**, the only change being gen-3. `65beb694` was
already absent — 4x moved it off-tree intact. `ab695e51` and `5cd014ed` remain.

Establishing that verdict surfaced something better than the sweep: those two
scratch boards are **the only two schedules in the registry with an alternatives
pool**. Neither gen-2 nor any pinned world has one. Which raised the question the
brief's W1 assumed was already answered.

**The demo board cannot carry drag ghosts.** Taken through `POST /alternatives`
(budget 8) for the first time: pool status **`empty`** — 8 targets, **8
INFEASIBLE** (`infeasible_this_horizon`), 0.63s each, 0 publishable members. Not
for want of candidates: **154 of the 386 placed bars are multi-eligible.** This
is 4x's *160 planner nudges refused, 160 of 160* arriving through a second,
independent door on the same world.

The first instrument I pointed at this returned **0 of 695 multi-eligible** by
reading a field that does not exist. A zero from an instrument that cannot see
the value is not a zero — (d.2)'s rule, caught on this session's own rider, and
the correct answer came from calling the module's own `_eligible_refs`.

---

## 7. Suites

| | | collected |
|---|---|---|
| reference at `37a7a37` (W2.2) | 2968 / 305 / 0 | 3273 |
| **baseline on THIS tree**, no `--runslow`, post-mint | **2969 / 305 / 1** in 893s | 3275 |
| **after**, no `--runslow` | **2970 / 305 / 0** in 930s | 3275 |
| **`--runslow`** (§3) | **3239 / 21 / 14** in 3125s | 3274 |

**Every term accounted, and one of them is not mine.** Collection moved
**3273 → 3275, +2**, entirely from
`test_evidence_index_roundtrip.py::test_roundtrip_on_a_real_run` — one
parametrized case per run dir under `_data/runs` holding a `runs/` subdir, of
which there are now **10** against 8 when W2.2 measured. The two new ones are
`7fa8f1e6` (Daryn's `dev_cockpit -Fresh` boot at 04:16, **before this session**)
and `9fdee7aa` (this session's mint). Baseline → after is **+1 passed / −1
failed**: the same flake, red under load and green on the rerun. **No residual;
this session's own code adds zero tests, which is what a session that changed no
`src/` file should add.**

**The one failure is the standing flake class, and its root cause was
confirmed rather than assumed.** `test_scenario_untouched_moves_bounded` passed
**alone in 3.06s**; its fixture solves under `time_limit_seconds=30.0` — a
wall-clock limit with **no pinned workers and no pinned seed**, which the hard
rules already call irreproducible. Named debt, not a regression.

Cockpit: **not run as a suite** — no cockpit source file was changed (both audit
injections restored byte-identically). The four guards touched during the audit
were run individually and are green at HEAD.

---

## 8. Children minted, all named

| what | id |
|---|---|
| submission | `84f2e8cb-7add-4acf-9656-9b55ba2451db` |
| run | `9fdee7aa-ec5c-4e8d-9fce-b30fe35c96fc` |
| **schedule** | **`rolling-9fdee7aa-ec5`** |
| alternatives pool | `alt-59f5047474e7` (status `empty`, kept as evidence) |

**Every existing pinned world is untouched** — not re-solved, not re-minted, not
re-pointed. Two committed scripts added (`verify_gen3.py`, `shoot_summary.mjs`);
screenshots in gitignored `_w23_scratch/`.

**R-CM1 disclosure, as the rule requires.** The CLAUDE.md diff is **+19 / −7**
lines, and 19 is over the ~15-line threshold at which a session is presumptively
doing it wrong — so this says so. Mitigating, and offered as fact rather than
excuse: the net is **+12 lines and −47 characters** (37,741 → 37,694), every
added line is pointer-form, and 7 of the 19 replace the demo-board block rather
than extending it. The prose is in docs/04 and docs/07, born there.

`src/cockpit/src/summarymodel.js` and `summary.js` appear in `git status` with
**zero content change** (`git diff --numstat` empty, sha256 equal to pre-session)
— the autocrlf stat-cache artifact left by §0(3), recorded here so it is not
read as a stray edit.

---

## 9. What a summary would undersell

**The digest matching is the entire result, and it is a negative.** Nothing
visibly happened: the same recipe produced the same plan. But the two mints
straddle a change that injects a callback into every search and an extra
`extract` into every solve, and R-SP1's licence to put a **dollar figure on a
planner's screen** rests on that change being invisible to the search. Sixteen
figures agreeing to the cent is what "invisible" looks like when it is checked
instead of asserted.

**The session's biggest finding is one it went looking for by accident.** Running
`--runslow` was not asked for; it happened because the brief's reference number
did not say which ladder it came from. Fourteen red tests, a dead negative
control on a live ruling, and a contradiction between R-SP1 and a byte-identity
assertion had been sitting behind the word `skipped` in six consecutive
close-outs — each of which correctly reported "0 failed".

**The demo now needs two boards, and that is new.** The brief's premise was one
board carrying cockpit, drag ghosts, ask layer, dollar story and statistics.
Four of the five are on `rolling-9fdee7aa-ec5`. The ghosts are not, cannot be,
and the product is right to say so — which makes it a question about what the
demo shows, not a bug to fix.
