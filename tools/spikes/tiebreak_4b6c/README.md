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
search enough to cost more than it saves? **Measured answer: yes.** See
`SESSION_CLOSEOUT.md` and docs/04's 2026-07-27 amendment.

## Files

| file | what it is |
|------|------------|
| `arm_harness.py` | the five-arm sweep. One code path (a transcription of `build_rolling_view`'s window-0 solve); only the objective varies. RESUMABLE — re-running the same command skips rows already in the output. |
| `compressor.py` | C, the scratch sequence-preserving left-shift post-processor, plus its CP-SAT re-validation |
| `run_compressor.py` | drives C over A0's and A2h's solutions |
| `analyze.py` / `analyze_c.py` | produce `TABLE.txt` / `TABLE_C.txt` |
| `infeasibility_core.py` | the assumption-literal diagnostic that found the missing sequence-dependent setup transition constraint |
| `arm_results.jsonl` | 148 raw arm runs |
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
