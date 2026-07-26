ERRAND SESSION CLOSE-OUT
The rolling exam run becomes one command
2026-07-26

Repo: C:\dev\mre, branch master. Scope: one tool + three diagnosed failures +
docs + tests. Solver behavior UNCHANGED in cost; one golden regenerated (a tie,
not a price -- see CU2b).

======================================================================
SUMMARY
======================================================================
The founder can now type one command and end with a rolling run selectable in
the cockpit, its schedule id printed. Getting there turned up a real defect that
had nothing to do with the errand: the rolling world's "deterministic" solve was
not deterministic, in three separate ways at once. All three are fixed at the
source, and the builder now re-proves it on every build.

  CU1  --register  -> health probe, build/reuse, verify, submit, solve, print
  CU2a pilot_scale -> not a defect: it is a profile dir, not a submission
  CU2b determinism -> two hash-order leaks + the wall clock acting as the budget
  CU2c intake      -> "there is nothing here" arrives before the cascade
  CU3  CLAUDE.md   -> a dev API quick reference, so nobody reconstructs it again
  CU4  guard       -> every committed dataset must still pass its own gate

======================================================================
CU1 -- --register: one command, end to end
======================================================================
tools/build_rolling_exam_run.py gained --register (plus --api-base, --fresh,
--poll-timeout). Default with no flag is unchanged: harness fixture only.

With --register it probes /health FIRST -- an unreachable API costs nothing but
the message and exits 2, so there is never a half-registered state -- then builds
(or reuses) the pinned world's submission, verifies its determinism, submits it
through the LIVE dev API, waits for the async solve, and prints the certificate
grade, the schedule id, and the select line.

The pinned world's IDS submission is now persisted at
_ai_exam_scratch/rolling_pinned/submission/ and REUSED across invocations (the
generator stamps a fresh extract_timestamp into every manifest, so regenerating
gives a byte-different submission for the same world). --fresh forces a rebuild.

Request field names were READ from SolveRequest in src/mre/api/app.py, not
guessed: the sliced solve is {"policy","deterministic","sliced","window_days",
"frozen_days","time_limit"}.

THE PROOF (live stack, this machine, verbatim)

Your dev API on port 8000 was running modules loaded before this session's edits,
so its sliced solve failed on the new SolveResult.wall_truncated field. Stopping
and starting a server was blocked by the permission classifier; you approved the
restart, it was restarted via .\src\cockpit\dev_api.ps1, and the command was then
run against it:

  $ python tools/build_rolling_exam_run.py --register
  rolling-exam: API at http://localhost:8000 is ok
  rolling-exam: reusing submission at C:\dev\mre\_ai_exam_scratch\rolling_pinned\submission
  rolling-exam: solving window 0 (window=14d frozen=3d, deterministic, seed=42, det budget=2.0s) ...
  rolling-exam: 56 bars, 42 committed, 14 active, 14 in the tray
  rolling-exam: snapshot snap-rolling
  rolling-exam: -> C:\dev\mre\_ai_exam_scratch\rolling_pinned
  rolling-exam: verifying determinism (a second spine + window-0 solve)...
  rolling-exam: determinism verified (identical split and placements)
  rolling-exam: submitting C:\dev\mre\_ai_exam_scratch\rolling_pinned\submission ...
  rolling-exam: certificate grade ACCEPTED (costing C2), submission 2f47ec9c-9156-427e-8bfe-b1d0c77b92a0
  rolling-exam: solving sliced (window=14d frozen=3d, deterministic) ...
  rolling-exam: run 279dec02-4119-411d-bec9-4e8cb08c090a succeeded in 87s (44 committed, 14 in the tray)

    certificate grade : ACCEPTED
    schedule id       : rolling-279dec02-411
    select rolling-279dec02-411 in the cockpit

Confirmed selectable, against the same live API:

  GET /schedules  -> LISTED: rolling-279dec02-411 proposed contract 1.8
  GET /schedules/rolling-279dec02-411
                  -> bars 56 | committed 44 | active 12 | tray 14

The registered run is the API's OWN solve of the same world, window and seed: it
uses the API's deterministic budget of 4.0s where the harness fixture uses 2.0s,
so the two are the same world but not a bit-identical solve. That is deliberate,
stated in the tool, and is why the harness reports 42/14 and the registered run
44/12.

======================================================================
CU2a -- datasets/pilot_scale REJECTED: a wrong path, not a defect
======================================================================
datasets/pilot_scale is NOT a submission. It holds the calibration profile the
pilot_scale GENERATOR SCENARIO is sized against -- pilot_profile.json,
PREDICTIONS.md, PROFILE_PROVENANCE.md. There are no IDS files in it at all, which
is exactly what the gate said:

  REJECTED  required files missing: ['manifest.json', 'orders.csv',
            'routings.csv', 'routing_lines.csv', 'products.csv',
            'resources.csv', 'calendars.csv', 'cost_model.json'] ;
            zero valid orders ; zero resources ; ...

WHAT THE GATE NEEDS is a directory of IDS files: manifest.json plus the seven
required tables (orders.csv, routings.csv, routing_lines.csv, products.csv,
resources.csv, calendars.csv, cost_model.json), optionally the four doorway
files (customers, setup_transitions, locks, wip_status). Two ways to get one:

  - committed and hand-authored: datasets/glass_box -- grades ACCEPTED / C2
    against the current gate, verified this session;
  - generated from a scenario:
      python tools/generate_erp_dataset.py --scenario pilot_scale --out <dir>
    which is what --register now materializes at
    _ai_exam_scratch/rolling_pinned/submission/.

No dataset and no manifest needed fixing. Nothing predates a rule it now fails.

======================================================================
CU2b -- the determinism finding (the real one)
======================================================================
The builder printed different committed/active splits across same-seed
invocations because THREE things were wrong at once, none of them the seed.

LEAK 1 -- the M1 adapter's entity write order. ids_adapter iterated
pairs_needed, a SET of (route_id, product_id) string tuples, to write Process /
OperationSpec / PrecedenceEdge entities. Nothing downstream re-sorts the edges,
so the precedence list a solve model is built from arrived in PYTHONHASHSEED
order. The line immediately above it already sorted the same set, for the same
reason.

LEAK 2 -- the admitted-demand set. rolling_horizon.build_rolling_view and
run_rolling_horizon iterated the `admitted` demand-id SET straight into
_build_window, so CP-SAT's variable creation order moved with the hash seed too.

Measured, identical submission (same sha256 over its CSVs), seed 42,
deterministic=True:

  PYTHONHASHSEED=1   committed=43 active=13 beyond=14
  PYTHONHASHSEED=2   committed=38 active=18 beyond=14
  PYTHONHASHSEED=3   committed=46 active=10 beyond=14

LEAK 3, and the worst -- the wall clock WAS the budget. SolveRunner always sets
max_time_in_seconds, whether or not max_deterministic_time is also set. At the
builder's 10.0s ceiling the WALL CLOCK stopped the solve every single time --
measured wall=10.01s limit=10.0 det=2.0, i.e. the deterministic budget of 2.0 was
never reached. "Deterministic mode" was returning whatever CP-SAT happened to
reach in ten seconds of real time on this machine. Two runs at the SAME hash seed
differing is what exposed it.

FIXES

  - ids_adapter.py: for route_id, ext_pid in sorted(pairs_needed)
  - rolling_horizon.py: for did in sorted(admitted), at both call sites
  - solve_runner.py: SolveResult.wall_truncated (additive, defaults False) --
    True when a deterministic-budget solve was actually stopped by the wall
    clock. Propagated through solver_builder.solve_two_stage and rolling's
    private _two_stage_solve; surfaced as RollingView.wall_truncated.
  - build_rolling_exam_run.py: WALL_CEILING_S = 900.0. The wall limit is a SAFETY
    CEILING, never the budget; the 2.0s deterministic budget now binds, at ~11-12s
    of wall.

After the fixes the same submission under hash seeds 1/2/3/random gives one
answer.

THE DETERMINISM ASSERTION (CU2b, as asked)

Every build re-runs the ENTIRE pinned path -- a second prepare_plant plus a
second window-0 solve from the same submission -- and fails nonzero unless the
committed set, the active set, the beyond-horizon tray and EVERY placement
(resource, start, end) are identical. It also fails if either solve reports
wall_truncated. A second pass through prepare_plant, not a second solve of the
same plant, deliberately: leak 1 lived in the adapter, and a plant-reusing check
would have sailed straight past it.

Also pinned as a test: test_rolling_determinism_is_not_hashseed_dependent (slow)
runs the golden driver under PYTHONHASHSEED=1 and =2 and requires identical
output. The pre-existing golden test pinned PYTHONHASHSEED=0 on BOTH sides, which
is precisely why it could not see any of this.

GOLDEN REGENERATED. tests/fixtures/baselines/rolling_pilot_golden.json --
changing the model's variable order changes which tie CP-SAT breaks. The drift is
placement-only and benign: every priced quantity is byte-identical across the
change (production 12744.05, setup 2160.00, tardiness 0.00, total 14904.05, 54
committed, 24 on-time, 0 late). Only schedule_digest moved.

======================================================================
CU2c -- the gate's intake answer
======================================================================
ConformanceGate.run now answers path-not-found / not-a-directory /
empty-directory as ONE deficiency with intake_error on the certificate, ahead of
the deficiency cascade, instead of rendering a page-long REJECTED certificate
about every missing file and zero orders and zero resources and zero routings.
It is still a first-class evidence run: one HEADLINE finding carrying the
standard ids.submission_files_present rule id, grade REJECTED, go=False.

Deliberately narrow -- a directory that HAS files still gets the full cascade,
however un-IDS those files are. Deciding what counts as a plausible-but-wrong
submission is the Gatehouse thread's surface, not this errand's. Five tests in
tests/test_conformance.py::TestIntake pin both the new answer and the narrowness.

======================================================================
CU3 -- CLAUDE.md dev API quick reference
======================================================================
New block after "## Repository layout": how to start the dev API, the two-step
submit+solve with a working sliced body (field names from SolveRequest), where
schedule ids appear (GET /runs/{id} -> data.result.schedule_id), what a
submission directory actually is, the note that time_limit is a wall ceiling and
not the budget, and the one-command rolling exam line.

======================================================================
CU4 -- the standing dataset guard
======================================================================
tests/test_committed_datasets_conform.py. Every directory under datasets/ holding
a manifest.json runs the CURRENT gate and must grade != REJECTED (slow). It pins
the FLOOR, not the grade, so a dataset may move ACCEPTED <-> CONDITIONAL as
quality rules land without a test edit.

Two guards keep it from going vacuous: one test asserts at least one committed
submission dataset exists, and one asserts that any manifest-less directory under
datasets/ also has no IDS CSVs -- so a genuinely broken submission cannot be
skipped for the very reason it is broken.

======================================================================
SUITE
======================================================================
  fast          1487 passed, 202 skipped   (python -m pytest -q)
  slow ladder   1664 passed,  21 skipped   (python -m pytest -q --runslow)
                with ANTHROPIC_API_KEY set

Without the key, four ask-path tests fail:
  test_edit_question_domain.py::TestEditDomainEndToEnd (x3)
  test_api_endpoints.py::TestRollingTwoBeatAPI::test_rolling_questions_answer_through_ask
They exercise the LLM-first parse layer through the real /ask with no parse
double, so with no key the honest floor answers "I can't answer this question
yet". Environmental, not a regression -- verified by re-running those four with
the key loaded from .env.local: 9 passed.

======================================================================
UNDERDELIVERED / NAMED
======================================================================
Nothing in CU1-CU4 was cut. What did not go to plan, and what is left open:

  - The live-stack proof needed your dev API restarted (it held pre-edit
    modules), and process control was blocked by the permission classifier until
    you approved it. The proof above is from the restarted server.

  - The registered run and the harness fixture are the same world but not the
    same solve (API deterministic budget 4.0s vs the harness's 2.0s --
    SolveRequest has no det_time field and this errand did not add one). Named in
    the tool. Adding the field is a small, separate API change if the two splits
    ever need to match exactly.

  - SolveResult.wall_truncated is REPORTED but nothing except the builder ACTS on
    it. The API's rolling worker can still run deterministic=True under a
    wall-bound time_limit and produce a non-reproducible schedule without
    complaint. Surfacing it was in scope; deciding what the API should do about
    it is a ruling, not an errand.

  - The intake answer covers only missing / not-a-directory / empty. A directory
    of plausible-but-wrong files still produces the full cascade -- by design,
    per the Gatehouse boundary.
