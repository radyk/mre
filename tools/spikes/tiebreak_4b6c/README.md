# Session 4B.6c — the tiebreak measurement (MEASUREMENT ONLY)

Nothing here is reachable from `src/`. This directory exists so the table in
`SESSION_CLOSEOUT.md` (repo root) can be re-derived rather than believed.

**The question.** R-SC3(1) makes earliness a zero-cost lexicographic tiebreak.
Session 4B.2d implemented that as a two-stage solve. **Candidate B** was the
obvious single-objective encoding of the same clause —

```
BIG = n_free_ops * start_range + 1        # strictly > max sum(starts)
minimize( BIG * cost_expr + sum(start_vars) )
```

— whose argmin is cost-optimal by construction. Does it degrade CP-SAT's
search enough to cost more than it saves? **Measured answer: yes.** See docs/04's
2026-07-27 4B.6c amendment.

**Session 4B.7 re-used this harness for the arm 4B.6c never ran.** `A0s` is
STAGED COST-ONLY — stage 1 minimizes cost alone, stage 2 caps it and minimizes
Σ starts — i.e. the shipped two-stage shape with the R-SC3(2) price removed, and
what 4B.7 shipped. It reproduces the cost-only PROVEN OPTIMUM to the cent at
5/8/15/40 orders while spending 45.53% fewer start-minutes at 40. It records BOTH
stages' ledgers, because the cap guarantees "stage 2 ≤ stage 1" only WITHIN a
run: comparing A0s to A0 also crosses a budget split (stage 1 gets 4.0, A0 gets
6.0), and conflating the two would misattribute a budget fact to a units defect.
See `SESSION_CLOSEOUT.md` and docs/04's 2026-07-27 R-SC3 AMENDMENT.

## Files

| file | what it is |
|------|------------|
| `arm_harness.py` | the six-arm sweep. One code path (a transcription of `build_rolling_view`'s window-0 solve); only the objective varies. RESUMABLE — re-running the same command skips rows already in the output. |
| `analyze_a0s.py` | **Session 4B.7 item 1** — the A0s table, per seed, with both conditions stated pass/fail |
| `fixture_account.py` | **Session 4B.7 item 5** — the fixture accounting, keyed by OPERATION IDENTITY rather than list position |
| `compressor.py` | C, the scratch sequence-preserving left-shift post-processor, plus its CP-SAT re-validation |
| `run_compressor.py` | drives C over A0's and A2h's solutions |
| `analyze.py` / `analyze_c.py` | produce `TABLE.txt` / `TABLE_C.txt` |
| `infeasibility_core.py` | the assumption-literal diagnostic that found the missing sequence-dependent setup transition constraint |
| `arm_results.jsonl` | 178 raw arm runs (148 from 4B.6c + 30 A0s) |
| `compressor_results.jsonl` | 28 raw compressor runs |
| `probe.jsonl`, `probe200.jsonl` | the 200-order / 14-day window budget probes (UNKNOWN at 6.0 and at 20.0 deterministic units) |

## Reproducing

```
set PYTHONHASHSEED=0
python tools/spikes/tiebreak_4b6c/arm_harness.py --orders 5 8 15 40 120 \
    --arms A0 A1 A2 A2h A2x --seeds 42 43 44 45 46 --det 6.0
python tools/spikes/tiebreak_4b6c/arm_harness.py --orders 200 --window 7 --frozen 3 \
    --arms A0 A1 A2 A2h A2x --seeds 42 43 44 45 46 --det 6.0
python tools/spikes/tiebreak_4b6c/run_compressor.py --orders 40 --seeds 42 43 44 45 46 --arms A0 A2h
python tools/spikes/tiebreak_4b6c/analyze.py
python tools/spikes/tiebreak_4b6c/analyze_c.py
```

`--max-seconds N` stops cleanly at a wall budget; the run is resumable, so
chunking costs nothing. Generated submissions and run dirs land in
`_4b6c_scratch/` at the repo root (gitignored) — the first run generates them,
later runs reuse them.

**Wall times are machine-specific; the DETERMINISTIC time consumed is the
reproducible measure and is recorded beside them.**

## Session 4B.7 additions

```
set PYTHONHASHSEED=0
python tools/spikes/tiebreak_4b6c/arm_harness.py --orders 5 8 15 40 120 \
    --arms A0s --seeds 42 43 44 45 46 --det 6.0
python tools/spikes/tiebreak_4b6c/arm_harness.py --orders 200 --window 7 --frozen 3 \
    --arms A0s --seeds 42 43 44 45 46 --det 6.0
python tools/spikes/tiebreak_4b6c/analyze_a0s.py
```

`fixture_account.py` is not part of the arm sweep; it is the golden-accounting tool
the 4B.6a CU4 protocol calls for, generalized so a future session does not have to
rewrite it:

```
python tools/spikes/tiebreak_4b6c/fixture_account.py snapshot BEFORE.json
PYTHONHASHSEED=0 python tools/build_rolling_fixture.py
python tools/spikes/tiebreak_4b6c/fixture_account.py snapshot AFTER.json
python tools/spikes/tiebreak_4b6c/fixture_account.py compare BEFORE.json AFTER.json
```
