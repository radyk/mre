# demo_board_4b22a -- the errand that minted a demo board worth dragging

Errand **4B.22a**, 2026-07-31. Narrative and every measured figure:
`docs/closeouts/4B.22a.md`. Roadmap entries: docs/07 5a.84-88.

**A TOOLS AND FIXTURE ERRAND. Nothing under `src/mre/` was changed**, so no
defect surfaced here was fixed here -- a fix bundled into a world-minting errand
cannot be attributed to the change that caused it. Findings are named in the
close-out and left.

## What it produced

* a generator preset, **`demo_board`** (`tools/generate_erp_dataset.py`) --
  pilot_scale's authored physics at a density where a planner's drag has a
  consequence, with past-due work and a tighter due-date median;
* the measurements that chose its density, rather than an assertion about it;
* a third knob, `splittable_weight`, **measured and REJECTED** -- raising it to
  buy R-C3 chunked bars turns a FEASIBLE 386-bar board into an empty one. The
  knob is kept so the result reproduces; no preset declares a value.

`pilot_scale` is **byte-identical** across the change and that is checked, not
claimed. The pinned exam world `rolling-c362baa4-1b0` is untouched.

## The scripts, in the order they were used

| script | what it does |
|---|---|
| `prove_pilot_scale_unchanged.py` | regenerates `pilot_scale` under the new code and diffs every file the solver reads against a baseline generated from the previous commit. `manifest.json` and `feel_fixture.json` are excluded and the exclusion is printed. |
| `measure_candidates.py` | the candidate sweep. Each candidate goes through the SAME path the board is minted through -- generate -> `prepare_plant` -> `build_rolling_view` -> `build_coarse_zone` -> `assemble_rolling_document` -- at the API's own budgets, and every figure is read off the solved window or the assembled document. |
| `opener_probe.py` | what the OPENER's concentration band sees, at the opener's own denominator (`Explainer._open_windows`), which is not the sweep's. |
| `mint_demo_board.py` | mints the chosen world through the live API's two steps (gate, then sliced deterministic coarse solve) and prints the schedule id and its deep link. |
| `reproduce_across_hashseeds.py` | re-runs the whole path in CHILD PROCESSES under `PYTHONHASHSEED` 0/1/2 and compares a digest of the split, every placement, and the reported proof. A single-process determinism check cannot see a hash-order leak; this can. |
| `sandbox_move.py` | one collision drag against a registered board, printing both beats of the R-T2 interaction in full. Built to be run against the OLD board and the NEW one so the two delta cards are comparable -- and the gesture it picks was itself corrected mid-errand, because the first one (a six-week backward drag) was INFEASIBLE on the dense board for a reason no planner would have hit. Both boards were re-measured with the corrected gesture. |
| `verify_demo_surfaces.py` | the errand's Item 4: the opener, a lateness question, the counterfactual, the past-due question, and the sandbox move, against the live API. |

## Three denominators, none interchangeable

Reading any utilisation figure from this directory requires knowing which one it
is measured against (4B.20's ruling: a capacity figure names its denominator).

| where | denominator |
|---|---|
| `measure_candidates.py` | the machine's open calendar minutes over the **board extent** -- `window_start` to the last placement end anywhere on the board. The same interval for every machine, so the machines are comparable to each other. |
| `evidence_tools.machine_load` (the product) | that **machine's own** first-to-last placement interval. Answers "how hard is this machine working while it is working"; not comparable across machines. |
| `Explainer._opener_load` (the concentration band) | the machine's **whole resolved calendar**, which on these boards runs 28,080 minutes against a plan occupying about 25 days. This is why the band does not fire at any density measured here. |

An earlier draft of the sweep used the ACTIVE WINDOW as its denominator and
reported CUT-01 at 174.2% -- an impossible number, and the reason the choice is
written down. `build_rolling_view` classifies a placement as active on its START,
and the window solve's horizon runs past the window end.
