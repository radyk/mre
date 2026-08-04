# Mobility Box — the fenced specimen world

A small hand-authored IDS submission built for **one purpose**: to hold a live
specimen of the two mobility verdicts this product could compute and had never
observed.

`mobility_premise.assess` (Session 4A.x, the listening docket) returns five
verdicts. Four of them were reachable on the pinned boards. Two were not:

| verdict | demo board (386 bars) | exam board (56 bars) |
|---|---|---|
| `held` | 24 | 45 |
| `later-open` | 361 | 9 |
| `undecidable` | 1 | 2 |
| **`boxed-in`** | **0** | **0** |
| **`earlier-open`** | **0** | **0** |

Both zeroes have the *same* cause, and it is a property of the boards rather
than of the code: `later_at` is computed over each machine's resolved open
calendar padded a fortnight past the last placement, so on a plant that keeps
working there is **always** room later — and `later-open` therefore absorbs
every bar that is neither held nor chunked. `boxed-in` and `earlier-open` are
the two verdicts that require `later_at` to be **None**, and nothing on a plant
that keeps working can produce that.

So this world contains a plant that **stops**.

## Run it

```
# 1. The gate. ACCEPTED, costing_grade C2, 0 findings.
python -m mre.gate datasets/mobility_box

# 2. The solve (deterministic — same flags, same schedule, every time).
python -m mre --submission datasets/mobility_box \
    --out _ai_exam_scratch/mobility_pinned --snapshot-id snap-mobility \
    --solver-workers 1 --solver-seed 0 --time-limit 600

# 3. The census — one line per bar, one verdict each.
python tools/spikes/teaching_graft_c/census_mobility.py
```

Reference date is **Monday 2026-01-05**. The work week is Mon–Fri, 07:00–19:00.
The solve is deterministic and reproduces byte-identically across
`PYTHONHASHSEED` 0 and 1 — `schedule.csv` sha256 `54ddd7f596a7780c…`.

**An operation occupies one minute more than it declares** — 700 declared
minutes is a 701-minute bar. That is the pipeline's arithmetic, not a rounding
here; every duration below is stated as declared, and every instant below is
what the solve actually produces.

## The plant

| Machine  | Calendar  | What runs there |
|----------|-----------|-----------------|
| `FEED-01`| Mon–Fri   | the boxed order's first step |
| `BOX-01` | Mon–Fri **+ Sat 2026-01-10 overtime**, then **closed from 2026-01-14** | five fillers, the early specimen, the boxed specimen |
| `PACK-01`| Mon–Fri   | the two controls |

`BOX-01` goes down for a rebuild on **Wednesday 2026-01-14** and does not come
back inside anything this plan can see (the closure rows run to 2026-02-13; the
analysis window ends 2026-01-27). Rates are a flat **$60/h ($1/min)** on every
machine, tardiness is **$25/h**, and **overtime bills at 1.5×** — that last
number is load-bearing, see story 2.

## The four stories (written before the solve)

### 1. `ORD-BOX` op20 is **BOXED IN** — the specimen that did not exist

`ORD-BOX` is released **2026-01-13**, the last day `BOX-01` ever works. Its op10
runs on `FEED-01` 07:00→09:51; its op20 needs 520 minutes on `BOX-01` and starts
at **09:52**, the minute op10 frees it, and ends **18:33**.

* **Earlier is refused, and by precedence.** The blocker ladder computes
  release 2026-01-13 00:00, precedence 09:51, resource 09:51, calendar 09:51,
  chunk-fit 09:51 — binding family **precedence**, actual start 09:52, verdict
  **`could_not`**.
* **Later is refused, and by the calendar.** `BOX-01` has **no open window at
  all** after 2026-01-13 19:00. The 27 minutes left on its own last shift do not
  hold a 521-minute bar.

Both directions shut ⇒ **`boxed-in`**. The planner who says *"this can't be
moved"* about this bar is **right**, and this is the first board on which the
product can agree with them from measurement rather than from a unit test.

### 2. `ORD-EARLY` is **EARLIER-OPEN** — and the earlier room is *overtime*

`ORD-EARLY` needs 420 minutes on `BOX-01` and is due 2026-01-30, so nothing
about lateness pushes it anywhere. It lands **Monday 2026-01-12 07:00→14:01**.

The five fillers are each due on the day they run (Mon 5 → Fri 9) and each takes
701 of the 720-minute shift, so Monday-to-Friday is spoken for, and moving a
filler costs three days of tardiness. What that leaves free before Monday the
12th is exactly one thing: **the Saturday 2026-01-10 overtime window**.

* The blocker ladder's binding family is **chunk-fit at 2026-01-10 07:00** —
  *"it needs 7h01m in one piece and BOX-01 had only 19m left when it came free
  at 2026-01-09 18:41"*. Actual start 2026-01-12 07:00, **slack 2,880 minutes**,
  verdict **`chose`**.
* Later is shut for the same reason story 1 is: 14:01→19:00 on the Monday is 299
  minutes, the Tuesday morning is 191, and after 2026-01-13 19:00 there is
  nothing at all. **`later_at` is None.**

Nothing prevented this bar going earlier; **the solver chose**, because the only
earlier room is a Saturday that bills at 1.5× and the schedule is not late.
That is what `earlier-open` was built to say, and it had never said it.

**Strip the one calendar row `CAL-BOX,exception,,07:00,19:00,2026-01-10,added,overtime`
and this bar becomes `boxed-in`.** The earlier room *is* that row.

### 3. `ORD-PACK` — the `later-open` control

240 minutes on `PACK-01`, which never closes. It runs 2026-01-05 07:00→11:01,
could not have gone earlier, and has room later for the rest of the padded
window ⇒ **`later-open`**, the verdict 361 of the demo board's 386 bars carry.
It is here so that "this world produces strange verdicts" is not a way to
explain away stories 1 and 2.

### 4. `ORD-SPAN` — the `undecidable` control

900 declared minutes, `splittable=true`, `min_chunk=60`, on `PACK-01`. It pauses
at the Monday close and resumes Tuesday — two chunks ⇒ **`undecidable`**,
because `local_price` declines to price a chunked move by name and this product
will not claim a direction it cannot test.

### What this world cannot show

`held` — a bar inside a committed frozen front or carrying a pin. This is a
**monolithic** solve: it has no rolling boundary and no pins, so `held` is
unreachable here by construction, and it is the one verdict of the five with
live specimens on both pinned rolling boards already (24 and 45). Nothing is
missing that is not already measured elsewhere.

## The order roster

| Order | Product | Machine | Due | Story |
|-------|---------|---------|-----|-------|
| ORD-FILL-1..5 | P-FILL | BOX-01 | Jan 5,6,7,8,9 | the week is spoken for (story 2's mechanism) |
| ORD-EARLY | P-EARLY | BOX-01 | Jan 30 | **#2 `earlier-open`** |
| ORD-BOX | P-BOX | FEED-01 → BOX-01 | Jan 16 | **#1 `boxed-in`** |
| ORD-PACK | P-PACK | PACK-01 | Jan 30 | #3 `later-open` control |
| ORD-SPAN | P-SPAN | PACK-01 | Jan 30 | #4 `undecidable` control |

## The guard

`tests/test_mobility_box.py` pins all four stories **and their mechanisms** —
not just the verdict strings but the binding family, the slack, the absence of
any later open window, and the fact that the Saturday row is what makes story 2
true. It carries two negative controls that mutate this dataset and prove the
premise tests go **red** when the world drifts:

* delete the closure rows ⇒ `ORD-BOX` op20 stops being `boxed-in`;
* delete the overtime row ⇒ `ORD-EARLY` stops being `earlier-open`.

If the solve ever contradicts a prediction above, that is a **finding**. Do not
quietly rewrite the prediction to match.
