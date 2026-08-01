# Session 4B.24 — the sandbox measurements (MEASUREMENT + VERIFICATION ONLY)

Nothing here is reachable from `src/`. This directory exists so the tables in
`docs/closeouts/4B.24.md` can be re-derived rather than believed.

**The question.** The founder's four-hour nudge inside an overtime window the
operation already occupied was priced at **-$50,784.33** with four unrelated
orders relocated by weeks. The R-T2 amendment (docs/04, 2026-07-31) rules that
"your move" is priced LOCALLY and that every sandbox solve is deterministic.
Its budgets had to be MEASURED numbers, not liked ones.

## Files

| file | what it is |
|------|------------|
| `ctx.py` | loads a registered board exactly as the API's sandbox endpoints do (registry row, run dir, rolling gesture context) |
| `measure.py` | Item 1's four measurements: (a) beat one's deterministic cost, (b) the window search's trace, (c) the local price, (d) the wall-per-unit exchange rate |
| `try_local.py` | drives `price_local_move` over one gesture — the tool the refusal families were developed against |
| `gestures.py` | Item 6: the five gestures, driven through the LIVE API in exactly the sequence `controller.js` issues |
| `measurements.jsonl` | the raw rows behind every table in the close-out |

## Reproducing

```
set PYTHONHASHSEED=0
python tools/spikes/sandbox_4b24/measure.py --part a
python tools/spikes/sandbox_4b24/measure.py --part b --det-ceiling 1.0
python tools/spikes/sandbox_4b24/measure.py --part c
python tools/spikes/sandbox_4b24/try_local.py --target 2026-01-21T08:00:00Z
```

Item 6 needs the API running (`.\src\cockpit\dev_api.ps1`, or uvicorn on any
port):

```
python tools/spikes/sandbox_4b24/gestures.py --api http://localhost:8000
```

**Wall times are machine-specific; the DETERMINISTIC time consumed is the
reproducible measure and is recorded beside them** (the 4B.6c convention). Part
(b) records its solution trace on the WALL axis deliberately:
`CpSolverSolutionCallback.DeterministicTime()` returns a constant for every
solution of a run, so the deterministic axis is unreadable per solution and only
the terminal `ResponseProto().deterministic_time` means anything.
