# facility_real provenance — MEASURED vs. AUTHORED

The `facility_real` plant (`tools/generate_erp_dataset.py::_apply_facility_real`,
Session 4B.10) is calibrated to the historical extract as measured in Sessions
4B.9 and 4B.10 and recorded durably in **docs/07 §5a.24 and §5a.25**.

Under **R-SC1** (docs/04, Session 4B.2) the extract is *intelligence*, not a
fixture: it supplies **shapes**, never plant physics. Nothing here is read from
`raw_data/` at generation time — the measured values are transcribed into the
generator as constants, with this file as the audit trail.

## Why it exists, and what it does NOT replace

Session 4B.9 found that every scale number the programme holds was taken on the
wrong axis. `pilot_scale` runs **13–15 machines at ~24 ops/machine**; the real
planning unit is **4 machines carrying 250–800 operations each**.

Both presets keep their purpose and both are labelled:

| preset | purpose |
|---|---|
| `pilot_scale` | the **look-ahead** preset. Its due-date spread is *deliberately* wider than the book's (`generate_erp_dataset.py:1197-1200`: "the regime where a longer look-ahead actually buys cost"). It carries every regression golden we own and is **UNTOUCHED** by 4B.10. |
| `facility_real` | the **realistic** preset. The measured shape: few machines, deep queues, the book's due-date histogram, and **past-due orders** — which no fixture has ever produced. |

## Variants

| scenario | orders | machines | alternates | past-due | models |
|---|---|---|---|---|---|
| `facility_real` | 276 | 4 | 1 | 7.83% | **F004**, the MEDIAN facility |
| `facility_real_large` | 851 | 4 | 1 | 7.83% | **F006**, the LARGEST facility |
| `facility_real_alt` | 276 | 4 | 2 | 7.83% | F004 with CROSS-TRAINED machines |
| `facility_real_pastdue` | 400 | 4 | 1 | 25.2% | **F005**, a quarter of its book already late |

`--fr-machines` (4–6), `--fr-alternates` and `--fr-past-due` override the preset.

**A CONDITIONAL gate grade is CORRECT for this preset, not a defect.** Because
`facility_real` produces past-due orders by design, the M0 gate raises one
`TEMPORAL_IMPOSSIBILITY` / WARNING (rule
`ids.order_dates_internally_consistent`, `disposition = proceeded_flagged`)
covering them and grades the submission **CONDITIONAL with `go = True`**;
costing completeness is **C2**. `pilot_scale`, which cannot produce a past-due
order, grades ACCEPTED. A reviewer seeing CONDITIONAL here should check that the
finding count equals the past-due count and nothing else — see docs/07 §5a.26,
which records that the validator then *excludes* the very orders the gate said
to proceed with.

## What is MEASURED

Every row cites where the measurement is recorded. Values marked **exact** are
reproduced to the value, not to a distribution family.

| Dimension | Measured value | Source |
|---|---|---|
| Orders per facility | median **276** (F004), max **851** (F006); p25 92, p75 452 | §5a.24(c) |
| Scheduled machines | **4** at both F004 and F006 (book: median 8–12, max 26) | §5a.24(c) |
| Ops per order | **exactly 4**, on 100% of orders, at every 4-machine facility (F004/F006/F00A, n=1,720) | §5a.24(c) |
| Route structure | routes NEVER revisit a workcenter — lines/distinct = **1.00** across all 134 used routes | §5a.25 |
| Alternates | **1** eligible machine per step: of 30,594 `(RoutingCode, Sequence)` pairs, **exactly ZERO** carry more than one row | §5a.24 |
| Duration formula | `setup + (qty / lot) × production_minutes`, applied per operation | §5a.25(a) |
| Setup minutes | median **5**, p75 **20**, p90 **30**, p99 56, mean **12.4** (F006, normal tier) | §5a.25 |
| Run minutes | median **0.5**, p90 **4.7**, mean **2.0** (F006); operations are SHORT | §5a.25 |
| Operation minutes | mean **13.2** (F004) / **14.4** (F006) including setup | §5a.25 |
| Order quantity | median 244 (F006) / 450 (F004); book p25 147, median 500 | §5a.24 |
| Due-date histogram | past due **7.83%**, 0–7 d **42.22%**, 8–14 d **39.92%**, 15–30 d **8.61%**, 31–60 d **1.41%** | §5a.24(a) |
| Due-date quantiles | p25 **2 d**, median **7 d**, p75 **9 d**, p90 **15 d**, max **34 d** | §5a.24(a) |
| Past-due depth | 41.2% ≤7 d late, 76.8% ≤30 d late | §5a.25 |
| Utilisation | F004 **32.6%**, F006 **112.5%** over a 14-day window | §5a.25(c) |

Calibration is **checked, not asserted**:
`tools/spikes/density_4b10/verify_facility_real.py <submission_dir>` prints the
generated shape beside each target above.

## What is AUTHORED

Everything a schedule's *physics* turns on. The extract contains **none** of
this — §5a.24 lists each absence, checked in the data rather than assumed.

- **The 720-minute working day, and the Mon–Fri week.** The extract carries no
  time-of-day, shift pattern, holiday, closure or downtime of any kind.
  *Consequence, stated:* §5a.25's utilisation ratios use a 7-day denominator
  (`window_days × 720`), so the solver's calendar is **5/7** of that capacity
  and the plant's effective utilisation is ≈1.4× the §5a.25 figure at the same
  density. The density sweep reports utilisation against the **actual**
  calendar.
- **No maintenance closure and no overtime window.** `pilot_scale` authors both;
  `facility_real` deliberately does not, because it exists to measure DENSITY
  and a closure day is a confound.
- **Machine cost rates** ($52–67/h). The extract has no resource-rate source at
  all (`Product.CostPrice` is a product cost, not a rate). The spread is authored
  so a cross-machine choice has a real price when alternates are enabled.
- **Alternates as CROSS-TRAINING.** When `alternates > 1` an operation becomes
  eligible on its own stage plus the next stages cyclically. **Machine count and
  total load are identical across alternate settings**, so the pair is a
  controlled experiment on assignment combinatorics alone. The extract's
  single-workcenter routings are *believed to be an extract limitation rather
  than a plant fact*, so both settings are built and neither is assumed real.
- **Customers and priority classes.** The extract has no priority, customer
  weight or commitment class anywhere. They are populated deliberately — an
  empty priority column is a silent lie (the Glass Box's standing warning).
- **Setup families and the changeover matrix.** Absent from the extract; none
  are authored, so `facility_real` carries no changeover cost.
- **Splittable / resumable flags.** Absent from the extract; none are authored.
  *Named consequence:* the 13 real orders whose single operation exceeds a
  14-day window (§5a.25(b)) have no counterpart here.
- **Coarse-horizon coefficients** (`bucket_days: 7`, `capacity_derate: 0.85`).
  The 7-day bucket matches the book's measured 7-day median lead; the derate is
  authored. They are declared so the coarse zone runs on a DECLARED rho rather
  than the defaulted 1.0 no-op (the 4B.6b debt).
- **Order-quantity truncation at 5,000 units.** The extract's p99 is 200,000 and
  its max 10,000,000 — both inside the sentinel class (below).
- **Past-due depth truncated at 60 days.** The book's minimum is −1,573 days, a
  stale outlier; truncation keeps past-due work late-but-plausible rather than a
  data defect the gate would flag.
- **No `earliness_value` is declared.** The extract carries no earliness
  preference, and since 4B.7 the coefficient is a REPORTING rate only.
  `pilot_scale` declares 0.05 as an authored demo choice; authoring one here
  would invent a business fact.

## Named departures from the book

Three. The first two are forced by the data rather than chosen; the third is a
known coarseness, named rather than hidden:

1. **Route length p90/max.** The book is p90 **8**, max **12** ops per order —
   but those routes occur ONLY at facilities with 10–26 machines, because no
   route ever revisits a workcenter. At 4 machines the measured route length is
   exactly 4, on 100% of orders. Route length and machine count are **coupled**
   in the book, and the preset couples them the same way
   (`_FR_ROUTE_MIX`: 4 machines → 4-op routes; 5 → mean 4.45; 6 → mean 4.80).
   Building a 4-machine plant with 8-op routes would model a facility that does
   not exist in the extract.
2. **The operation-duration TAIL is coarser than the book's.** Products are
   authored one per `(route length, starting stage)` pair, so a 4-machine plant
   has **4 products and 16 routing steps** — and setup/run values are drawn once
   per step and then reused by every order running that product. Median and mean
   land on target (at 851 orders: setup median 5, run median 0.5, op mean 12.6
   against F004's 13.2 / F006's 14.4), but the upper quantiles are lumpy where
   the book's are smooth (setup p90 20 here against F006's 30), because 16 draws
   cannot resolve a distribution. The real book carries 858 distinct products
   across the open orders. *Fix shape, if it matters:* several product variants
   per `(length, start)` pair with independent duration draws. **Not done in
   4B.10** — it would have invalidated a sweep already in flight, and the
   headline calibration (ops/order, the due-date histogram, median and mean
   durations, utilisation) is unaffected.
3. **The sentinel class is not reproduced.** 1,434 of 20,743 products (6.9%)
   read `CostingLotSize = SetUpMinutes = ProductionMinutes = 1` — all three
   exactly 1 on 100.0% of those rows — and the 227 open orders using them carry
   **93.56% of all computed machine-minutes** (§5a.25(b)). These are placeholder
   rows, not measurements, and every duration figure above is taken on the
   normal tier with them removed. `facility_real` generates no sentinel rows; a
   preset that reproduced them would be calibrated to a data defect.
