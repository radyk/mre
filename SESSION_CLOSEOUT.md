SESSION 4B.9 CLOSE-OUT
INTELLIGENCE: THE PLANT CALIBRATED AGAINST THE REAL BOOK
2026-07-28

Repo: C:\dev\mre, branch master. READ-ONLY session. No pipeline, no gate, no
solver, no code changes. Nothing was submitted; RawAdapter was not revived;
R-SC1 stands untouched. The extract was read with pandas, counted, and reported.

Scope note: this close-out is the whole deliverable. docs/04 and docs/07 were
NOT amended -- the brief asked for SESSION_CLOSEOUT.md and nothing else. If
these numbers are to become durable, docs/07 sec 5a is where they belong, and
that is the next session's first act, not a thing this one did quietly.
(4B.8's close-out text is superseded here but preserved in git at fa9ced3.)


======================================================================
1. THE HEADLINE -- THE DUE-DATE HISTOGRAM
======================================================================

Source: raw_data/OpenWorkOrder.csv, 3,472 open work orders, 11 facilities.
Reference point REF = 2025-03-25 (= max CreatedDate, normalized; the extract
date). Due date = ScheduleDate, which is the mapping the retired RawAdapter
itself used (raw_adapter.py:748, "due: ScheduleDate as end-of-day UTC") -- so
this reading is the repository's own, not one invented here.

  bucket        count     share      cumulative
  PAST DUE        272     7.83%          7.83%
  0-7 days      1,466    42.22%         50.06%
  8-14 days     1,386    39.92%         89.98%
  15-30 days      299     8.61%         98.59%
  31-60 days       49     1.41%        100.00%
  61-90 days        0     0.00%        100.00%
  90+ days          0     0.00%        100.00%

  min = -1573 d   p25 = 2 d   MEDIAN = 7 d   p75 = 9 d   p90 = 15 d   max = 34 d

  DUE WITHIN 7 DAYS  (incl. past due):  50.06%
  DUE WITHIN 14 DAYS (incl. past due):  89.98%
  ALREADY PAST DUE:                      7.83%  (272 orders)

THE SHAPE IN ONE LINE: this book has no long tail. Ninety percent of open
demand is due inside fourteen days and half of it inside seven. Nothing at all
is due beyond 60 days. The p90 is 15 days -- the entire order book lives inside
the horizon the engine already calls "fine".

Note the 7.83% past-due bucket. The retired RawAdapter EXCLUDED these
(raw_adapter.py:7, "Demand <- OpenWorkOrder rows with ScheduleDate >=
reference_date only"), so any earlier figure derived through that path silently
dropped 272 orders. They are counted here.

Per facility (the planning unit -- see section 2):

  fac    n   past_due  <=7d  <=14d   p25  median  p75  max   %<=7d  %<=14d
  F006  851        1    329    805   2.0     8.0  9.0   20    38.7    94.6
  F00A  638       13    464    616   2.0     2.0  8.0   20    72.7    96.6
  F00Z  504       18    212    471   3.0     8.0  9.0   16    42.1    93.5
  F005  400      101    248    347  -1.0     2.0  9.0   30    62.0    86.8
  F008  354       52     86    279   8.0     9.0 14.0   34    24.3    78.8
  F004  276        5    150    259   3.0     3.0  9.0   20    54.3    93.8
  F001  261       65    122    170   0.0     9.0 21.0   31    46.7    65.1
  F00B  108       14     75     99   2.0     3.0  8.0   28    69.4    91.7
  F00D   76        1     49     74   2.0     2.5  8.2   20    64.5    97.4
  F00Y    3        2      2      3 -33.0   -32.0 -9.5   13    66.7   100.0
  F002    1        0      1      1   3.0     3.0  3.0    3   100.0   100.0

The shape is consistent across the nine facilities carrying real volume: every
one has 65%+ of its book due within 14 days, and seven of the nine are above
91%. F001 is the loosest (65.1% within 14d, p75 = 21 d) and F00A the tightest
(72.7% within SEVEN days). F005 carries 101 past-due orders, a quarter of its
book.


======================================================================
2. ITEM 0 -- LOCATION AND INVENTORY
======================================================================

FOUND, at the expected path: C:\dev\mre\raw_data\ (gitignored via
.gitignore:14; it survived because this working copy is not a fresh clone).
No search of mre-OLD-do-not-use or the OneDrive tree was needed.

Authoritative read paths confirmed from the retired adapter
(src/mre/modules/raw_adapter.py:177-193), which opened exactly five of the six:
OpenWorkOrder.csv, Routing.csv, RoutingLines.csv, Product.csv, BOM.csv.
SalesOrder.csv it never opened.

  file                rows      cols   size      columns
  BOM.csv           11,044        6    0.27 MB   ProductNo, MaterialNo, UPS, CUT,
                                                 FixedWastage, Wastage%
  OpenWorkOrder.csv  3,472        8    0.33 MB   Wono, JobCategory, RouteCode,
                                                 ProductNo, WoQuantity, ScheduleDate,
                                                 CreatedDate, FacilityCode
  Product.csv       20,743       11    1.19 MB   ProductNo, RetailerID, Facility,
                                                 ProductGroup, ProductType, CostPrice,
                                                 PricePer, CostingLotSize, SetUpMinutes,
                                                 ProductionMinutes, UOM
  Routing.csv        3,856        9    0.26 MB   RouteCode, FacilityCode, ProductNo,
                                                 IsDefault, JobCategory, Status,
                                                 ApprovedStatus, ApprovedBy, ApprovedDate
  RoutingLines.csv  30,594        8    1.83 MB   Ref, RoutingCode, Workcenter, TrackMode,
                                                 TargetTime, Sequence, Active, ResourceCode
  SalesOrder.csv   919,568       19  198.59 MB   SOSerial, ProductNo, Source, OrderDate,
                                                 ShipoutDate, EDDate, BillAddrNo,
                                                 ShipAddrNo, OrderQty, ShippedQty,
                                                 FacilityCode, SellPrice, CostPrice,
                                                 PricePer, WoNo, OrderCategory, SONo,
                                                 RequestedShipDate, ReleasedDate

Row counts reproduce raw_data_profile.md exactly. They also reproduce
datasets/pilot_scale/pilot_profile.json exactly on every dimension it records
(3,472 backlog / 20,743 products / 3,856 routes / 174 workcenters / 8.0 median
ops per route / 14 facilities / 11 backlog facilities, and the per-facility
backlog counts line for line). That is an independent confirmation of the
extraction, arrived at without reading the profile first.

CROSS-FACILITY PROBE -- the gap probe's finding STILL READS TRUE, and more
strongly than "zero cross-facility work packages":

  * routes whose lines span more than one facility prefix: 1 of 3,856
  * restricted to the 134 routes actually used by open work orders: 0 of 134
  * open WOs whose FacilityCode disagrees with their route's workcenter
    facility: 0 of 3,472

ONE FACILITY IS THE PLANNING UNIT. Confirmed on live work, not just on the
master. Every number in section 3 is therefore reported per facility.


======================================================================
3. ITEM 1 -- THE SIX NUMBERS
======================================================================

(1) OPEN ORDERS PER FACILITY

  total 3,472 across 11 facilities.
  min = 1   p25 = 92   MEDIAN = 276   p75 = 452   max = 851   mean = 315.6

  F006 851, F00A 638, F00Z 504, F005 400, F008 354, F004 276, F001 261,
  F00B 108, F00D 76, F00Y 3, F002 1.

  IS 200 LOW, TYPICAL, OR HIGH? 200 orders is BELOW the median facility and
  sits around the 40th percentile of the eleven. Six of the eleven carry more.
  So the 200-order instance 4B.8 measured is a plausible small-to-mid facility
  -- but it is NOT the median one, and it is under a quarter of the largest.
  Read it as "a real but modest facility", not "the plant".

  CAVEAT, stated plainly: 200 REAL orders and 200 SYNTHETIC orders are not the
  same amount of work. See (4) and section 4 -- the real order carries roughly
  twice the operations.

(2) DUE-DATE SPREAD -- see section 1. Median 7 days, p25 2 days.

(3) ARRIVAL RATE

  A created date EXISTS (OpenWorkOrder.CreatedDate), so the number is not
  absent -- but the naive read of it is a trap, and it is reported here with
  its bias named rather than as a figure.

  OpenWorkOrder is a SNAPSHOT OF OPEN ORDERS. Completed work orders are gone
  from it. Counting CreatedDate backwards therefore measures survivorship, not
  arrival, and the further back you look the more wrong it gets:

    last  1w: 3,082 WOs created  ->  3,082.0 /week
    last  2w: 3,313              ->  1,656.5 /week
    last  4w: 3,393              ->    848.2 /week
    last 13w: 3,456              ->    265.8 /week
    last 52w: 3,471              ->     66.8 /week

  The 52-week figure is meaningless -- it is the backlog size divided by 52.
  Only the shortest window approaches an unbiased rate, and even that is a
  floor. What the decay DOES establish robustly is a churn fact: 3,082 of 3,472
  open work orders -- 88.8% -- were created in the last seven days. This
  backlog turns over weekly.

  THE UNBIASED SERIES, from SalesOrder.csv (919,568 rows, OrderDate spanning
  2022-01-02 to 2025-03-27). pilot_profile.json deliberately does not read this
  file; for an arrival rate it is the only honest source, because it is a log,
  not a snapshot.

    sales-order lines/week, last   4w:  6,337.0
                            last  13w:  5,239.6
                            last  26w:  5,275.5
                            last  52w:  5,495.7
                            last 104w:  5,391.4

  Stable at roughly 5,300-5,500 lines/week across two years -- no growth trend
  and no seasonality large enough to show at this resolution. Per facility,
  last 52 weeks: F006 1,326, F005 883, F00Z 794, F00A 791, F00D 440, F004 440,
  F001 413, F007 218, F00B 189 lines/week.

  CAUTION ON UNITS. These are sales-order LINES, not work orders. Distinct
  WoNo per week over the same period is 5,217 -- close enough to the line count
  that WoNo is evidently near-unique per line rather than grouping lines into
  shared work orders. The line-to-work-order collapse ratio in this extract is
  therefore about 1:1, and cross-checking that against the ~3,082 WOs/week
  implied by the open-order snapshot is NOT possible from these files. I am not
  reconciling the two: they count different objects and the join that would
  reconcile them is not present.

  REPORTED AS ABSENT: work-order arrivals per week per facility.

(4) ROUTE LENGTH

  Two different numbers, and the difference matters.

  Per ROUTE in the master (all 3,856 routes, 30,594 lines):
    median = 8   p90 = 10   p95 = 10   max = 13   mean = 7.93
  (Active is "1" on 100% of lines, so active-only is identical.)

  Per OPEN ORDER (joining each WO's RouteCode to its lines):
    median = 4   p90 = 8   p95 = 8   max = 12   mean = 4.94
    zero open WOs have a RouteCode with no routing lines -- the join is clean.
    total operations across all 3,472 open orders: 17,154

  THE MASTER OVERSTATES BY ROUGHLY 2x. Only 134 distinct routes (of 3,856) are
  used by open work, across 858 distinct products, and the routes that get used
  are the SHORT ones -- 2,221 of 3,472 orders run a 4-op route. Sizing the
  solver off the master's median of 8 would double the modelled op count.
  4.94 ops/order is the number that turns an order count into an op count.

(5) MACHINE / WORKCENTER COUNT

  Distinct Workcenter strings in RoutingLines: 174. Workcenter is written
  "F001/D3001" -- facility-prefixed, so it decomposes cleanly. There are only
  59 distinct workcenter NAMES (the suffix), i.e. the same name recurs across
  facilities and the 174 is genuinely 174 facility-machine pairs.

  THE 174 FIGURE IS RECONCILED. It is the WHOLE-BOOK total across all 14
  facility prefixes, not a per-facility count. Per facility:

    F001 39, F00B 31, F005 16, F00Y 15, F00Z 15, F00A 13, F00D 9, F007 9,
    F002 6, F006 6, F004 5, F010 4, F008 3, F009 3
    (min 3, median 9, max 39, mean 12.4)

  Restricted to workcenters actually touched by routes that open work orders
  use -- the number a planner would schedule against:

    F001 26, F00B 14, F00Y 12, F00Z 12, F005 10, F00D 8, F00A 6, F006 4,
    F004 4, F002 3, F008 3   -- TOTAL 102

  So "174 workcenters at pilot volume" is correct as a corporate total and
  wrong as a planning-unit figure by a factor of about twelve. A median
  facility schedules 8-12 machines; the largest schedules 26.

  AND THE 13 IS RECONCILED TOO. The brief says pilot_scale runs 13 machines,
  and 4B.8's own table says "the same 13 machines" (docs/04:11234,
  docs/07:1583, 4B.8 close-out line 125). The pilot_scale plant actually
  defines FIFTEEN machines (_PILOT_MACHINES: CUT 3, PRESS 2, MILL 2, PAINT 2,
  HEAT 2, FINISH 3, ASM 1 = 15; the preset declares resources=15; generated
  submissions on disk carry 15 rows in resources.csv). The 13 is n_machines
  from the cliff sweep, and that field counts machines CARRYING ADMITTED OPS in
  a window (cliff_sweep.py:72-76, 105) -- it reads 13 at every depth from w7 to
  w14. Both figures are right about different things and no doc is wrong in
  substance, but "13 machines" phrased as a plant property is a misreading
  waiting to happen. The plant has 15; 13 get loaded.

  Against the book: pilot_scale's 15 sits ABOVE the median real facility
  (9 defined / 8-12 scheduled) and well below the largest (39 / 26). Of the six
  axes this is the closest match.

(6) DERIVED -- OPS IN A 7-DAY vs 14-DAY WINDOW

  ARITHMETIC: for each facility, take open WOs with (ScheduleDate - REF) <= W
  days, and sum the active RoutingLines count of each WO's route. Past-due
  orders are INCLUDED -- they are work that must be done, and the fine window
  is where it would be done.

  fac    orders<=7d   ops<=7d    orders<=14d   ops<=14d   ops/order
  F006          329     1,316            805      3,220        4.00
  F00A          464     1,906            616      2,518        4.09
  F00Z          212       957            471      1,993        4.23
  F005          248     1,974            347      2,766        7.97
  F008           86       258            279        837        3.00
  F004          150       600            259      1,036        4.00
  F001          122     1,045            170      1,488        8.75
  F00B           75       610             99        812        8.20
  F00D           49       307             74        482        6.51
  F00Y            2        24              3         36       12.00
  F002            1         3              1          3        3.00
  ------------------------------------------------------------------
  TOTAL       1,738     9,000          3,124     15,191

  MEDIAN FACILITY = F004 (276 orders, the median of the eleven):
    7-day window  ->    150 orders,   600 operations
    14-day window ->    259 orders, 1,036 operations
    (F004's whole backlog is 1,104 ops, so 14 days already covers 94% of it)

  THE BRIDGE TO 4B.8. 4B.8 measured, at 200 synthetic orders on a 6.0-unit
  deterministic budget: w7 = 99 free ops (OPTIMAL, 4.54 units), w14 = 313 free
  ops (UNKNOWN -- no solution at all).

    median real facility, w7:    600 ops =  6.1x the 99 that solved
    median real facility, w14: 1,036 ops =  3.3x the 313 that returned nothing
    largest real facility, w7: 1,316 ops = 13.3x
    largest real facility, w14: 3,220 ops = 10.3x

  ASSUMPTIONS, ALL FOUR NAMED:
    (a) One facility is the planning unit. VERIFIED in section 2, not assumed.
    (b) Ops per order = count of that route's active RoutingLines. The extract
        has no operation-level status, so a 4-op route contributes 4.
    (c) EVERY OPEN ORDER IS ENTIRELY UNSTARTED. The extract carries no WIP,
        progress, or completed-operation field of any kind. Real free-op counts
        would be LOWER by however much work is already in flight -- an unknown
        this data cannot bound. THIS OVERSTATES.
    (d) Only due-date filtering is applied. The engine's real admission also
        pulls work in by gravity and carries spillover, which 4B.8's n_free
        includes and this does not. THIS UNDERSTATES.

  (c) and (d) push in opposite directions and neither is quantifiable from this
  extract. The ratios above are therefore an ORDER-OF-MAGNITUDE BRIDGE, not a
  prediction of n_free. What survives the uncertainty is the sign and the
  scale: a real median facility's 14-day window is several times larger than
  the instance that already fails, and the largest facility is an order of
  magnitude larger.


======================================================================
4. ITEM 2 -- IS pilot_scale GROUNDED OR INVENTED?
======================================================================

VERDICT: CALIBRATED. There is a recorded, reproducible derivation, and it is
unusually well documented.

  CITATION CHAIN:
    tools/extract_pilot_profile.py  reads raw_data/{OpenWorkOrder, Product,
      Routing, RoutingLines}.csv and emits
    datasets/pilot_scale/pilot_profile.json  (measured shapes) plus
    datasets/pilot_scale/PROFILE_PROVENANCE.md  (a MEASURED-vs-AUTHORED table,
      written out verbatim by the tool itself, extract_pilot_profile.py:161)
    tools/generate_erp_dataset.py::_apply_pilot_scale  loads that JSON at
      line 1078 and uses it for order size and the lead-time band
    docs/04-design-history.md:6359-6363 records CU1 of Session 4B.2 doing this
    docs/07-roadmap.md:672-673 records the R-SC1 demotion to a profile source

The provenance document is explicit that the calibration is PARTIAL BY DESIGN:
volumes, order-size distribution, family cardinality, machine count and
lead-time shape are MEASURED; all plant physics (calendars, capability groups,
alternates, setup families, priorities, splittable jobs) is AUTHORED, because
the extract has none. That division is correct and is exactly what R-SC1
preserved.

So the answer to the brief's binary is CALIBRATED -- but the useful product is
the GAP, because on two of the six axes the generator departs from the measured
value, and on one of those the departure is large.

  axis                    BOOK (measured)          pilot_scale         verdict
  ---------------------------------------------------------------------------
  order count        median facility 276      400 (preset)         ABOVE median
                     range 1-851              200 in the exam      within range
  machine count      9 median / 39 max        15 defined           ABOVE median,
                     8-12 scheduled median    13 loaded            below max
  route length       4.94 ops/order mean      2.48 ops/order       HALF the book
                     median 4                 weighted median 3
  due-date spread    median 7 d, p25 2 d      median 15 d, p25 12  DIVERGENT
                     50.1% <=7d               6.1% <=7d            -36 pp at 7d
                     90.0% <=14d              45.9% <=14d          -44 pp at 14d
                     7.8% past due            0% (impossible)      absent
  order quantity     p50 500, p99 200,000     truncated to fit     NAMED in
                                              a 720-min shift      PREDICTIONS.md
  arrival rate       ~5,300 SO lines/wk       not modelled         ABSENT both

THE DUE-DATE DIVERGENCE IS DELIBERATE AND DOCUMENTED, NOT AN ERROR. The
generator's own comment (generate_erp_dataset.py:1197-1200) says it: "Spread
WIDER than the raw median so the plant is moderately loaded (most orders
feasible on time, a tight/late minority) rather than front-loaded and
saturated -- the regime where a longer look-ahead actually buys cost."

The mechanism, read off the source and reproduced here exactly:

    lead_p50 (mode) = max(14, int(profile p50) * 2) = max(14, 7*2) = 14
    lead_p90        = int(profile p90) = 17
    lead_min        = 4
    lead_max        = max(lead_p90 + 12, 30) = 30
    due lead        = int(triangular(4, 30, mode=14)), clamped

Simulated at n = 400,000 draws:
    min 4, p25 12, median 15, p75 19, p90 23, max 29
    within 7d: 6.13%     within 14d: 45.91%     past due: 0.00%

  bucket        BOOK      pilot_scale      delta
  PAST DUE      7.83%          0.00%     -7.83 pp
  0-7 days     42.22%          6.13%    -36.09 pp
  8-14 days    39.92%         39.78%     -0.14 pp
  15-30 days    8.61%         54.09%    +45.47 pp
  31-60 days    1.41%          0.00%     -1.41 pp

Note the 8-14 bucket matches almost exactly (-0.14 pp). The divergence is not
diffuse: it is mass moved out of 0-7 and into 15-30.

TWO CONSEQUENCES WORTH NAMING, neither a criticism of the choice:

  * lead_min = 4 makes a PAST-DUE ORDER STRUCTURALLY IMPOSSIBLE in pilot_scale.
    The real book is 7.83% past due and one facility (F005) is 25%. Whatever
    the engine does with already-late work at intake, no pilot_scale instance
    has ever exercised it.
  * The doubling (int(p50) * 2) is what moves the mass. The measured p50 is
    7.54 days; the generator plans around 14. So pilot_scale's 14-day window
    sits at its own MODE, where the real plant's 14-day window sits at its p90.
    The two windows are not doing the same job.

The ROUTE-LENGTH gap is separate and is NOT documented as deliberate. Weighted
by the generator's own family mix (fam_weights [4,3,3,3,3,1,3,3,1,1] over
widget/bracket/panelR/panelB/shaft/spacer/gear/plate/housing/hub with route
lengths 3/1/2/2/4/1/3/2/4/3), pilot_scale averages 2.48 ops/order against the
book's 4.94. pilot_profile.json records the master's 7.93 ops/route and the
generator did not use it -- reasonably, since alternates multiply the search --
but the figure it landed on is half the book's real per-ORDER number, and
nothing records that comparison. A 200-order pilot_scale instance carries ~496
operations where 200 real orders carry ~988.


======================================================================
5. ITEM 3 -- THE WINDOW QUESTION, ANSWERED FROM DEMAND
======================================================================

From the due-date distribution alone. No solver behaviour is used here.

  FRACTION OF OPEN DEMAND DUE WITHIN 7 DAYS:   50.06%  (1,738 of 3,472 orders;
                                                        9,000 of 17,154 ops)
  FRACTION DUE WITHIN 14 DAYS:                 89.98%  (3,124 orders;
                                                        15,191 ops)

  By facility the 14-day figure never falls below 65%, and is above 91% in
  seven of the nine facilities carrying real volume.

HOW DEEP MUST THE FINE WINDOW BE TO COVER COMMITTED WORK? The extract answers
this directly, because it holds a RELEASED work-order backlog rather than a
forecast: every row in OpenWorkOrder is work already committed to a route, a
product, a quantity and a date. On that reading the committed book is 3,472
orders deep and 90% of it lies within 14 days. There is no provisional tail to
exclude -- nothing is due past 60 days at all, and only 1.41% past 30.

THE BUSINESS FACT:

  This plant's demand is concentrated at SEVEN DAYS -- median 7, p25 2, half
  the book due inside a week and 8% already late. A fine window of 7 days
  covers half of committed demand; a fine window of 14 days covers 90% of it.
  Fourteen days is operationally sufficient for this plant in the sense that
  matters -- it is not a partial look at a long book, it is very nearly the
  WHOLE book. Seven days is not: it leaves 40% of committed work, 1,386 orders,
  outside the fine window with real due dates inside the month.

  The corollary, and it is the uncomfortable one: at a median facility that
  90%-coverage window contains roughly 1,036 operations. 4B.8 measured the cost
  objective returning nothing at all on 313.

NO RECOMMENDATION IS MADE ABOUT window_days. This session supplies the demand
half only. The two halves point in opposite directions and reconciling them is
Daryn's call with 4B.8's measurements in hand.


======================================================================
6. WHAT THE EXTRACT CANNOT SUPPLY -- NAMED, NOT ESTIMATED
======================================================================

Every item below was checked in the data, not assumed from the specs.

ABSENT ENTIRELY -- no column exists:

  * CALENDARS, SHIFTS, WORKING HOURS, HOLIDAYS, DOWNTIME. No file carries a
    time-of-day, a shift pattern, or a closure. The 720-minute working day is
    wholly authored.
  * MACHINE ALTERNATES / CAPABILITY GROUPS. Checked directly: of 30,594
    (RoutingCode, Sequence) pairs, exactly ZERO have more than one row. Every
    routing step names ONE workcenter. The priced cross-machine choice the cost
    model turns on has no counterpart in this extract at all.
  * SETUP FAMILIES AND THE CHANGEOVER MATRIX. No family column anywhere; no
    transition table.
  * PRIORITY / CUSTOMER WEIGHT / COMMITMENT CLASS. No priority column in
    OpenWorkOrder, Product or SalesOrder. Product.RetailerID identifies a
    retailer but carries no rank.
  * PER-MACHINE COST RATES. Product.CostPrice is a product cost, not a resource
    rate. There is no resource-rate source of any kind.
  * WIP / PROGRESS / PERCENT-COMPLETE. Nothing distinguishes an order that has
    finished three of four operations from one not started. This is the
    assumption doing the most work in section 3(6)(c).
  * SPLITTABLE / RESUMABLE FLAGS, MIN CHUNK. Absent.
  * DWELL / CURE / COOLING TIME. Absent -- as the retired adapter itself
    recorded ("no_dwell_source_in_raw_data", raw_adapter.py:728).
  * PRECEDENCE BEYOND A LINEAR CHAIN. RoutingLines.Sequence gives a total order
    per route. No parallel branches, no cross-route edges, no assembly joins.
  * OVERTIME WINDOWS, MAINTENANCE WINDOWS. Absent.
  * EARLINESS PREFERENCE. Absent (already recorded in PROFILE_PROVENANCE.md as
    a business declaration, not an extract fact).

PRESENT BUT EMPTY -- the column exists and carries nothing:

  * RoutingLines.TargetTime is "00:00:00.0000000" on 100.00% of 30,594 rows.
    ONE distinct value. There is NO operation-level duration in this extract.
  * RoutingLines.ResourceCode is 100.0% null, 0 distinct values.
  * RoutingLines.TrackMode has one distinct value, "Default".

  This is the sentinel / repeated-identical-value fingerprint the
  carry-forwards already warn about, and it appears here in its purest form: a
  duration column that is entirely zero.

PRESENT AT THE WRONG GRAIN:

  * Product.SetUpMinutes (97.24% nonzero, median 36) and
    Product.ProductionMinutes (97.47% nonzero, median 288) are the only
    duration content in the extract, and they are per PRODUCT, not per
    OPERATION. A 4-operation route has one setup figure and one production
    figure for the whole product. Splitting them across operations is an
    authored act, not a measurement.

CANNOT BE RECONCILED FROM THESE FILES:

  * Work-order arrivals per week. OpenWorkOrder.CreatedDate is survivorship-
    biased (section 3(3)); SalesOrder gives 5,217 distinct WoNo/week against
    the snapshot's implied ~3,082/week, and the two count different objects.
    The join that would reconcile them is not present. REPORTED AS ABSENT.


======================================================================
7. FINDINGS, IN ORDER OF WHAT THEY CHANGE
======================================================================

F1. THE BOOK HAS NO LONG TAIL. 90% of open demand is due within 14 days, 50%
    within 7, nothing beyond 60 days. The 14-day convention is not a partial
    view of this plant -- it is nearly the whole plant.

F2. AND THAT IS THE PROBLEM. A median facility's 14-day window holds ~1,036
    operations. 4B.8's cost objective returned UNKNOWN at 313. The window depth
    the business needs and the window depth the solver survives are separated
    by roughly 3x at the median facility and 10x at the largest. Section 3(6)
    states the four assumptions behind that arithmetic.

F3. pilot_scale IS CALIBRATED, WITH ONE LARGE DELIBERATE DIVERGENCE AND ONE
    UNDOCUMENTED ONE. The due-date spread is intentionally widened (mode 14 vs
    measured median 7.54) and the reason is written in the source. The route
    length -- 2.48 ops/order against the book's 4.94 -- is not recorded as a
    comparison anywhere. A pilot_scale order is half a real order's work.

F4. PAST-DUE WORK HAS NEVER BEEN EXERCISED. lead_min = 4 makes it structurally
    impossible in pilot_scale; the real book is 7.83% past due and F005 is 25%.
    The retired RawAdapter also excluded past-due rows on intake, so this blind
    spot has two independent sources.

F5. "174 WORKCENTERS" IS A CORPORATE TOTAL, NOT A PLANNING FIGURE. A median
    facility schedules 8-12 machines; the largest schedules 26. pilot_scale's
    15 is a reasonable median-to-large facility. Separately, the "13 machines"
    in docs/04:11234 and docs/07:1583 is n_machines-carrying-ops from the cliff
    sweep, not the plant's machine count, which is 15. Both are correct about
    different things; the phrasing invites a misread.

F6. THE MASTER'S ROUTE LENGTH OVERSTATES BY 2x. Median 8 ops/route across 3,856
    routes, but only 134 routes are used by open work and they are the short
    ones -- 4.94 ops/order actual. Anything sized off the master doubles.

F7. THIS BACKLOG TURNS OVER WEEKLY. 88.8% of open work orders were created in
    the last seven days. Sales-order intake is flat at ~5,300-5,500 lines/week
    across two years with no visible trend.


======================================================================
8. WHAT WAS NOT DONE
======================================================================

  * Nothing was submitted, gated, solved, or routed through the pipeline.
    RawAdapter was read for its file paths and field mapping only.
  * No generator default, no pilot_scale parameter, and no window rule was
    changed. No recalibration was performed -- establishing provenance was the
    product, per the brief.
  * docs/04 and docs/07 were not amended. If these numbers should persist
    beyond this file, that is the next session's first act.
  * No value was invented, imputed, or estimated. Section 6 is the list of what
    stayed absent.

Scratch scripts (three, read-only pandas) were written to the session
scratchpad, not to the repo.
