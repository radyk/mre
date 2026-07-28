# Session 4B.8 spikes — the budget split and the 14-day cliff

MEASUREMENT ONLY. Nothing here is reachable from any shipped path. Each script
answers one question with evidence; the answers are in `docs/04-design-history.md`
(2026-07-28) and `docs/07-roadmap.md` §5a.15/.19/.21/.23.

The world, the window build, gravity admission and the extractor pass are all
REUSED from `tools/spikes/tiebreak_4b6c/arm_harness.py` rather than rebuilt, so a
difference between a 4B.6c row and a 4B.8 row is a difference in the thing under
test and not in the harness.

NB `arm_harness.run_arm` itself cannot be called against HEAD — it imports
`rolling_horizon._earliness_coeff_scaled`, which 4B.7 deleted on purpose. The
staged loop is re-expressed here over that module's still-live primitives rather
than by resurrecting the dead symbol.

| script | question | output |
|---|---|---|
| `policy_harness.py` | CU1 — how should a fixed deterministic budget be SPLIT between the two stages? | `policy_results.jsonl` |
| `analyze.py` | CU1 — the policy table, and the 120-order question specifically | stdout |
| `satisfiability_probe.py` | CU5(a) — does a feasible schedule EXIST at 200 orders / 14 days? | `satisfiability.jsonl` |
| `feasibility_probe.py` | CU5(a), THE WRONG QUESTION — minimize cost under a huge budget. Kept as the record of a three-hour dead end: it conflates "does a schedule exist" with "what is the cheapest schedule". | `feasibility.jsonl` |
| `cliff_sweep.py` | CU5(b)(c) — where does the cost proof fail, and is the threshold general? | `cliff.jsonl`, `cliff_gen.jsonl` |
| `coarse_across_depths.py` | CU5(d) — does narrowing the window MOVE work into the coarse zone, or lose it? | `coarse_depths.jsonl` |
| `account_goldens.py` | CU6 — account a moved schedule BY OPERATION IDENTITY, not by row position | stdout |

Reproduce (deterministic; `PYTHONHASHSEED=0`, workers 1, seeds 42-46):

```
python tools/spikes/alloc_4b8/policy_harness.py \
    --instances 5 8 15 40 120 200:7 --policies P1 P2 P3 --seeds 42 43 44 45 46
python tools/spikes/alloc_4b8/analyze.py
python tools/spikes/alloc_4b8/satisfiability_probe.py --orders 200 --windows 14 --first-only
python tools/spikes/alloc_4b8/cliff_sweep.py --orders 200 --windows 7 8 9 10 11 12 14
python tools/spikes/alloc_4b8/cliff_sweep.py --orders 40 120 --windows 7 8 9 10 11 12 14 \
    --out tools/spikes/alloc_4b8/cliff_gen.jsonl
python tools/spikes/alloc_4b8/coarse_across_depths.py --orders 200 --windows 7 8 9 10 11 12 14
```

Every sweep is RESUMABLE: a row already present for a given key is skipped, and
each run is individually deterministic, so a chunked sweep and a single long one
produce the same rows. The first run generates and caches its worlds under
`_4b6c_scratch/` (shared with the 4B.6c spike, and gitignored).
