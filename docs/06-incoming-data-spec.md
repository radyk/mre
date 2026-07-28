# Incoming Data Specification (IDS)

**Document 6** · Status: Draft v0.6 (living document) · Companions: *01 Canonical Model*, *02 Evidence Contract*, *03 PoC Plan*, *04 Design History*, *05 Constraint Catalog (in progress)*

**v0.6 changes (Session 4.5):** new rule **#34 `ids.order_quantities_are_positive`** (conditional integrity, VALUE_OUT_OF_RANGE, §5.1) — a zero/negative order quantity is an invalid demand (you cannot make -60 units); it degrades the grade to CONDITIONALLY ACCEPTED and the order is excluded downstream (registry now **34 rules**). And a **severity-semantics** change with docs/02 §4.3: the gate's finding severity now derives from the **disposition** (`finding_severity`), not the rule outcome — a `degraded` rule that proceeds flagged emits a `warning` finding (the grade still degrades via the outcome), so an `error`/`blocker` severity always carries an acting disposition.

**v0.2 changes:** cost model REQUIRED with a minimal core (§5.9); customer and priority doorways (§5.10, §3); setup transitions (§5.11); locks (§5.12); overtime expression (§5.6, §5.9); extension & pipeline-proof clause (§8); costing-completeness grade on the certificate (§4).

**v0.7 change (Session 4B.11):** §5.9 records `past_due_age_threshold_days` as **DECLARED IN NEITHER DIRECTION** — R-PD1 clause (5)'s age finding is OPEN, not implemented, and the entry states the full §8 pipeline-proof chain it would require rather than emitting evidence with no pathway. **Registry unchanged at 36 rules.** Separately: past-dueness at intake is no longer an exclusion anywhere (R-PD1 clauses (1)/(2)), so the §5.13 `wip_status` doorway is no longer an ESCAPE from exclusion — it keeps its other meaning untouched (an in-flight operation still constrains placement).

**v0.6a change (Session 4B.6a):** a **remediation entry** for an *absent* `capacity_derate` (§5.9, "NO CAPACITY MARGIN DECLARED") — **informational, NOT a registry rule**. It fires nothing and moves no verdict; the registry stays at **36 rules**. It records what the absence costs (the planning run mirrors the proof run, so capacity figures assume full utilization) and names the surfaces that now say so.

**v0.6 changes:** `coarse_horizon` coefficient doorway (§5.9) — the far-horizon look-ahead's declared bucket length and capacity derate (rho), with a gate check (`ids.coarse_horizon_coefficients_sane`, §4), adapter translation onto the canonical CostModel, a pilot_scale truth manifest and an anomaly generator: pipeline-proven per §8, not model-proven. Registry v0.3 → v0.4 (36 rules).

**v0.3 changes:** `wip_status.csv` doorway for in-flight work / soft-start rescheduling (§5.13); `wip_progress_basis` manifest declaration (§3); WIP gate checks (§4 Tier 2); the reschedule-from-a-point invariant amendment (§5.13).

**v0.5 changes:** §5.3 **alternative groups** made real — repeated (route_id, sequence) rows carry a **per-alternative time model** (`setup_minutes`/`run_minutes_per_unit` read per row → `ResourceRequirement.rate_overrides`, docs/01 §5.5; the solver builds per-resource durations, the extractor prices the chosen machine's honest rate), while `setup_family`/`dwell`/`splittable`/`min_chunk` are **STEP attributes that must agree** across the group (new rule `ids.alternative_step_attributes_agree`, AMBIGUOUS_SOURCE, first-row-wins) — registry now **33 rules**; `active=false` removes a row; zero active rows = unroutable; identical triples remain duplicates; `role` column RESERVED (B3). Empty overrides ⇒ byte-identical solves (the no-map guarantee). Before v0.5 the adapter silently DROPPED every non-first row's time (a per-alternative rate never reached the solver) — the latent silent-wrong this closes.

**v0.4 changes:** §4 rewritten as the **Rule Registry** (32 named rules, registry v0.2), replacing the prose tier list — closed outcome vocabulary (satisfied/flagged/degraded/violated), grade as a pure function of outcomes, naming convention + governance + permanent status column; seven checks made real (required_columns_parse, key_fields_populated, routes_resolve_to_lines [unfolded from orders_resolve_to_routes], order_dates_internally_consistent, facility_references_consistent, decision_relevant_attributes_populated, optional_columns_are_not_sparse); the transition-matrix converse split; `manifest_semantics_declared` recoded MALFORMED_FIELD→AMBIGUOUS_SOURCE.

---

## 1. Purpose and position

All scheduling data enters the system through this specification. Regardless of acquisition — API pull, SQL extraction, file drop, ERP-native export — data is first landed in IDS format and must pass the **conformance gate** before translation to the canonical model.

```
 Acquisition connectors          Conformance gate           Canonical translation
 (API / SQL / files / ...)  ──►  (this specification)  ──►  (M1 adapter, unchanged)
        many, thin                 one, rigorous                 one, hardened
```

The IDS is the system's **narrow waist**: N acquisition methods on one side, one canonical model on the other. Adding a source means adding a connector and running the gate — never touching the core.

The IDS is also the **sales-qualification surface**: "can we model this plant?" is answered by walking the plant's reality against this document. It therefore includes first-class doorways for high-probability needs and a demonstrated, versioned mechanism (§8) for everything else.

**Design rules:**
- Connectors are transport only: authenticate, fetch, reshape. No semantic judgments.
- Every submission faces the same gate — including live feeds and our own generator.
- **The gate checks; it never repairs.** Transport artifacts may be normalized (encoding, delimiters, stray characters), each normalization recorded. Semantics are never invented: no fallback rates, no guessed units, no defaulted capacity. Repair is a human decision made against the certificate, or a documented waiver.
- The spec is ours and versioned, written to be read by submitters: whoever builds a connector codes against this document.

## 2. Submission structure

A **submission** is a directory (or archive):

```
manifest.json           REQUIRED — declared semantics (§3)
orders.csv              REQUIRED — demand (§5.1)
routings.csv            REQUIRED — route headers (§5.2)
routing_lines.csv       REQUIRED — operation sequences (§5.3)
products.csv            REQUIRED — product master (§5.4)
resources.csv           REQUIRED — workcenters/machines (§5.5)
calendars.csv           REQUIRED — shifts, exceptions, overtime (§5.6)
cost_model.json         REQUIRED — economics, minimal core (§5.9)
customers.csv           OPTIONAL* — customer master & priorities (§5.10)
setup_transitions.csv   OPTIONAL* — dependent setup matrix (§5.11)
locks.csv               OPTIONAL* — frozen/pinned future assignments (§5.12)
wip_status.csv          OPTIONAL* — in-flight work / soft-start state (§5.13)
bom.csv                 OPTIONAL — material structure (§5.7)
sales_history.csv       OPTIONAL — demand history (§5.8)
```

\* Conditionally expected: consistency checks fire when related columns are populated but the table is absent (§4 Tier 2).

Format: CSV, UTF-8 (BOM stripped as normalization), comma-delimited, one header row, RFC 4180 quoting. Alternative containers may be admitted by later versions; the logical schema governs.

**Absence of any REQUIRED file or the manifest is automatic rejection.** No schedule exists without demand, routes, times, resources, capacity, and economics.

## 3. The manifest — declared semantics

Interpretation ambiguities are resolved by the submitter's declaration, never by our guesswork.

```json
{
  "ids_version": "0.2",
  "source_system": "ERPName vX.Y",
  "submitter": "org/team identifier",
  "extract_timestamp": "2025-03-25T18:00:00Z",
  "reference_date": "2025-03-22",
  "timezone": "Europe/Istanbul",
  "facility_scope": ["F001", "F005"],
  "semantics": {
    "production_minutes_basis": "per_operation | per_route | per_bottleneck_op",
    "production_minutes_per": "costing_lot",
    "due_date_time_of_day": "end_of_day | as_stated",
    "quantity_uom_source": "products.uom",
    "setup_minutes_scope": "per_operation | per_order",
    "priority_precedence": "order_over_customer | customer_over_order | max | multiply",
    "unlisted_transition_default": "base_setup | zero | forbidden",
    "wip_progress_basis": "remaining_minutes | quantity_complete"
  },
  "notes": "free text"
}
```

Rules:
- `reference_date` is the scheduling "now"; all temporal validation is relative to it (historical replay is a feature).
- `timezone` applies to naive timestamps; the gate converts to UTC on landing and records it.
- Every `semantics` field relevant to submitted tables is REQUIRED (`priority_precedence` iff both customer and order priorities are present; `unlisted_transition_default` iff setup_transitions.csv is present; `wip_progress_basis` iff wip_status.csv is present). Missing required declarations are Tier-1: we do not divine meaning.

## 4. Conformance gate and certificate

The gate runs as an evidence-emitting module (standard finding vocabulary). Output: a **Submission Certificate**, graded:

| Grade | Meaning |
|---|---|
| **REJECTED** | Scheduling would be dishonest. Deficiency list returned; nothing proceeds. |
| **CONDITIONALLY ACCEPTED** | Quantified gaps within thresholds; submitter triages each class: fix / waive-with-exclusion / block. |
| **ACCEPTED** | Proceeds; quality flags disclosed. |

### 4.1 The Rule Registry (v0.4 of the registry; IDS v0.6; 36 rules)

The gate is a **registry of named rules**, not a prose tier list. The registry
below is the constitution; `src/mre/contracts/ids_rules.py` is its executable
form (the single source both this table and the gate read), and the end-to-end
coverage matrix parametrizes over it, so a rule cannot be claimed here without a
gate check and an anomaly generator behind it.

**Naming convention (lint-bound):** rule IDs are positive present-tense
conditions in IDS domain vocabulary (§2/§5 nouns); no digits, no
threshold/band/severity words, no implementation words (check/validate/parse —
`required_columns_parse` is the one grandfathered exception).

**Governance:** rule IDs are stable identifiers; never renamed for style;
retired-never-reused; a superseded rule carries `superseded_by` and stays
resolvable. Thresholds (Appendix A) are versioned rule *parameters*; a change of
*meaning* is a new rule_id, never a repurpose.

**Outcome vocabulary (closed enum):** `satisfied` / `flagged` / `degraded` /
`violated`. Certificate grade is a **pure function of outcomes**: any `violated`
→ REJECTED; else any `degraded` → CONDITIONALLY ACCEPTED; else ACCEPTED (flags
disclosed = the set of `flagged` findings). For banded rules the measured
outcome determines the certificate consequence; boolean structural rules resolve
to satisfied/violated only, and quality rules to satisfied/flagged only —
quality rules **structurally cannot degrade a grade** (a quality flag is
informational). A banded rule always records its measurement as a **Metric**;
a **Finding** is emitted only when the outcome is not satisfied, so a clean
submission carries no spurious "100% resolved" findings. Finding severity is a
function of **(outcome, category)**, not outcome alone: flagged→WARNING,
degraded→ERROR, violated→BLOCKER for every non-quality category, while a
**quality**-category flag is emitted at INFO (its fixed informational
consequence). The two arguments are irreducible — the category is what
distinguishes an informational quality flag from a WARNING flag at the same
outcome.

**Status column** (implemented / unimplemented) — the same honesty convention as
docs/05's MP/PP column. All 35 read *implemented*; the column is permanent: the
registry never again silently claims a check the gate does not have.

**Boolean structural — satisfied/violated:**

| rule_id | finding code | IDS ref | status |
|---|---|---|---|
| ids.submission_files_present | MISSING_REFERENCE | §2 | implemented |
| ids.manifest_schema_valid | MALFORMED_FIELD | §3 | implemented |
| ids.manifest_semantics_declared | AMBIGUOUS_SOURCE | §3 | implemented |
| ids.required_columns_parse | MALFORMED_FIELD | §5 | implemented |
| ids.key_fields_populated | MALFORMED_FIELD | §5 | implemented |
| ids.in_scope_orders_exist | MISSING_REFERENCE | §4 | implemented |
| ids.in_scope_resources_exist | MISSING_REFERENCE | §4 | implemented |
| ids.calendar_patterns_exist | MISSING_REFERENCE | §5.6 | implemented |
| ids.cost_model_core_present | MISSING_REFERENCE | §5.9 | implemented |

**Banded — full outcome range; declared measurement; thresholds → Appendix A:**

| rule_id | measures | finding code | IDS ref | status |
|---|---|---|---|---|
| ids.orders_resolve_to_products | order_product_resolution_rate | ORPHAN_ENTITY | §5.1, App A | implemented |
| ids.orders_resolve_to_routes | order_route_resolution_rate | ORPHAN_ENTITY | §5.2, App A | implemented |
| ids.routes_resolve_to_lines | route_line_resolution_rate | ORPHAN_ENTITY | §5.3, App A | implemented |
| ids.operation_durations_computable | duration_computability_rate | VALUE_OUT_OF_RANGE | §5.3, App A | implemented |

`orders_resolve_to_routes` measures pure order→route-*header* resolution;
`routes_resolve_to_lines` is the independent route→line leg (a route header that
resolves but has zero active lines fails only the latter). The two were folded
until 2026-07-10; unfolding them re-derived the affected anomaly manifests from
the new definitions (recorded in the anomaly catalog, not hand-tuned).

**Conditional integrity — satisfied/flagged/degraded:**

| rule_id | finding code | IDS ref | status |
|---|---|---|---|
| ids.order_identities_unique | DUPLICATE_IDENTITY | §5.1, App A | implemented |
| ids.order_quantities_are_positive | VALUE_OUT_OF_RANGE | §5.1 | implemented |
| ids.order_dates_internally_consistent | TEMPORAL_IMPOSSIBILITY | §5.1 | implemented |
| ids.facility_references_consistent | ORPHAN_ENTITY | §3, §5.5 | implemented |
| ids.orders_use_active_routes | LOW_CONFIDENCE_INPUT | §5.2 | implemented |
| ids.priority_classes_priced | UNMAPPABLE_VALUE | §5.9, App A | implemented |
| ids.earliness_value_sane | VALUE_OUT_OF_RANGE | §5.9 | implemented |
| ids.coarse_horizon_coefficients_sane | VALUE_OUT_OF_RANGE | §5.9 | implemented |
| ids.setup_families_have_transition_matrix | AMBIGUOUS_SOURCE | §5.11 | implemented |
| ids.transition_matrix_references_declared_families | AMBIGUOUS_SOURCE | §5.11 | implemented |
| ids.customer_references_have_master | AMBIGUOUS_SOURCE | §5.10 | implemented |
| ids.locks_reference_known_entities | ORPHAN_ENTITY | §5.12 | implemented |
| ids.wip_references_known_entities | ORPHAN_ENTITY | §5.13 | implemented |
| ids.wip_progression_respects_sequence | LOW_CONFIDENCE_INPUT | §5.13 | implemented |
| ids.wip_in_progress_rows_carry_progress | MALFORMED_FIELD | §5.13 | implemented |
| ids.wip_actual_starts_are_at_or_before_reference_date | VALUE_OUT_OF_RANGE | §5.13 | implemented |
| ids.wip_completion_is_internally_consistent | VALUE_OUT_OF_RANGE | §5.13 | implemented |
| ids.alternative_step_attributes_agree | AMBIGUOUS_SOURCE | §5.3 | implemented |

`customer_references_have_master` fires only when customer weighting is declared
in the manifest (`priority_precedence`) — §3-correct silence otherwise, recorded
so it is documented, not mysterious. The two transition-matrix rules are the
converse split of one §5.11 doorway (matrix missing for used families; matrix
present but no families used), honoring one-condition-per-rule.

**Quality — satisfied/flagged; fixed informational consequence:**

| rule_id | finding code | IDS ref | status |
|---|---|---|---|
| ids.durations_within_plausible_range | STATISTICAL_OUTLIER | §4 | implemented |
| ids.due_dates_within_planning_horizon | VALUE_OUT_OF_RANGE | App A | implemented |
| ids.backlog_is_current | VALUE_OUT_OF_RANGE | App A | implemented |
| ids.decision_relevant_attributes_populated | LOW_CONFIDENCE_INPUT | §4 | implemented |
| ids.optional_columns_are_not_sparse | LOW_CONFIDENCE_INPUT | §4 | implemented |

`durations_within_plausible_range` today measures run-rate outliers vs. the
family median (thresholds calibrated from recorded distributions, never fixed
constants); the rule's condition is stated broadly and the check may grow into
it — this note describes what is measured today.

**Costing-completeness grade (new, reported on every certificate):**
| Level | Meaning |
|---|---|
| C0 | Core only — plant-default rate, base setup & tardiness costs, priority multipliers |
| C1 | + per-resource rates |
| C2 | + overtime premiums, transition-specific costs |
| C3 | + scrap/inventory elements |

C0 is sufficient to schedule; the certificate states what refinement toward C3 buys. **Tardiness-only optimization is not a legal steady state** — it exists only as an explicitly waived diagnostic mode, recorded as such.

Certificates are retained per source; intake quality is trendable over time. Recurring sources are gated on every acquisition.

**Permitted normalizations (recorded):** encoding/BOM; unambiguous delimiter & quoting repair; key whitespace trimming; header-artifact stripping; timezone conversion per manifest. Nothing beyond transport repair.

## 5. Dataset schemas

Types: `string`, `int`, `decimal`, `date` (YYYY-MM-DD), `datetime` (ISO 8601; naive per manifest timezone).

### 5.1 orders.csv — demand
| Column | Type | Req | Notes |
|---|---|---|---|
| order_id | string | ✓ | Unique external demand identity |
| product_id | string | ✓ | → products |
| route_id | string | ✓ | → routings |
| quantity | decimal | ✓ | > 0; UoM per products |
| due_date | date/datetime | ✓ | Per manifest `due_date_time_of_day` |
| created_date | datetime |  | Earliest-start floor if release_date absent |
| release_date | datetime |  | Explicit earliest start |
| facility_id | string | ✓ | Resource namespace |
| customer_id | string |  | → customers when present |
| priority_class | string |  | Order-level ladder; interacts with customer priority per manifest `priority_precedence` |
| commitment_class | string |  | standard / rush / firm (or declared mapping) |

### 5.2 routings.csv
route_id ✓ · facility_id ✓ · product_id (blank/0 = generic route: valid) · status ✓ · approved · version, effective_from.

### 5.3 routing_lines.csv
route_id ✓ · sequence ✓ · resource_id ✓ (→ resources) · active ✓ · setup_minutes, run_minutes_per_unit, dwell_minutes (optional; when present they OVERRIDE product-level times — the preferred, per-operation time model) · setup_family · splittable, min_chunk_minutes.

**Eligible sets / alternative groups (docs/05 B2, no schema change):** an operation's *eligible resource set* is expressed as **multiple active rows sharing one (route_id, sequence) but naming different resource_id** — the adapter groups them into one OperationSpec whose ResourceRequirement is `explicit_set` over the whole set (`routing_lines.resource_id → explicit_set`). A repeated (route_id, sequence) **always** means an OR-group of eligible machines; a **single active row per sequence — the common case — is a single-element set, byte-identical to the pre-grouping behaviour** (the defaults-reproduce-baseline gate).

Within a group, columns split into two kinds:

- **Per-alternative time model** — `setup_minutes` and `run_minutes_per_unit` are read **per row**: an alternative machine may run the operation at its own speed (a faster machine, a slower spill valve). The first row's values are the operation's DEFAULT; any alternative whose row resolves to a different (setup, run) carries a `rate_override` keyed by its resource (docs/01 §5.5, `ResourceRequirement.rate_overrides`). The solver builds a per-resource duration and the extractor prices the chosen machine at its own honest rate. An all-agree group carries no overrides and is byte-identical to a single-rate group. A multi-eligible operation's cost differential therefore lives on **both** the *resource* (per-resource `cost_rate`, §5.5, and/or `calendar_id`, §5.6) **and** its own per-alternative time — the choice of machine carries the price, whether through rate or duration.
- **Step attributes** — `setup_family`, `dwell_minutes`, `splittable`, `min_chunk_minutes` describe the **operation**, not the machine that runs it, so every row in a group **must agree**. Disagreement is a Tier-2 finding (`ids.alternative_step_attributes_agree`, AMBIGUOUS_SOURCE); it is resolved **first-row-wins** downstream (the operation proceeds) but the contradiction is disclosed on the certificate rather than silently absorbed.

**Row lifecycle within a group:** `active=false` removes a row from the eligible set (a decommissioned or not-yet-qualified machine); a sequence with **zero active rows is an unroutable step** (it fails `ids.operation_durations_computable` / route→line resolution — the operation has no machine). **Identical triples** (same route_id, sequence, resource_id) remain **duplicates**, not an eligible set of one machine listed twice — first occurrence wins. The column name `role` is **RESERVED** (docs/05 B3, capability/tool roles); it is not read today and must not be repurposed.

### 5.4 products.csv
product_id ✓ · uom ✓ · facility_id · product_group · costing_lot_size, setup_minutes, production_minutes (REQUIRED as a set iff routing_lines omit per-op times; semantics per manifest) · cost_price.

### 5.5 resources.csv
resource_id ✓ (namespacing convention noted in manifest) · facility_id ✓ · resource_type (default workcenter) · parallel_units ✓ (≥1) · calendar_id ✓ · pool_id · cost_rate (per-resource override of the cost-model default).

### 5.6 calendars.csv
calendar_id ✓ · **pattern rows**: day_of_week, start_time, end_time · **exception rows**: exception_date, exception_type (closure / added), start_time, end_time, reason. `added` exceptions with reason `overtime` are the expression of overtime capacity; their premium prices via cost_model (§5.9). Zero pattern rows ⇒ Tier-1: **capacity is not optional.**

### 5.7 bom.csv (optional)
parent_product_id ✓ · component_id ✓ · quantity_per · scrap fields. Observed structure; no scheduling role until material constraints activate.

### 5.8 sales_history.csv (optional)
Demand history for trend/forecast work; not used for scheduling. Loose schema; profiled and stored.

### 5.9 cost_model.json — REQUIRED, minimal core
The mission is **cost-optimized scheduling**; economics are not optional. The required core is deliberately obtainable by any prospect on day one:

```json
{
  "version": "customer-v1",
  "currency": "USD",
  "core": {
    "default_resource_rate_per_hour": 60.0,
    "setup_cost_per_setup": 40.0,
    "tardiness_cost_per_hour": 25.0,
    "priority_multipliers": { "standard": 1.0, "high": 3.0, "critical": 8.0 }
  },
  "refinements": {
    "resource_rates": { "F001/D3001": 85.0 },
    "overtime_premium_multiplier": 1.5,
    "transition_costs": "see setup_transitions.csv",
    "scrap_cost_per_unit": null,
    "inventory_carrying": null,
    "earliness_value": 0.05,
    "coarse_horizon": { "bucket_days": 7, "capacity_derate": 0.85 }
  }
}
```

`core` is Tier-1 required in full. `priority_multipliers` keys must cover every priority/commitment class used in orders/customers (Tier-2 check otherwise). Customer priority **is a cost coefficient**: there is a priced cost to failing high-priority customers, and it enters the objective as the per-demand tardiness weight.

**`earliness_value` (optional refinement; R-SC3, AMENDED 2026-07-27).** Currency **per minute** of op-start earliness, applied plant-wide (`>= 0`; **absent ⇒ 0**). **It is a REPORTING coefficient. It is no longer a price.**

**What it does.** Among cost-optimal schedules the solver prefers earlier starts — **always, unconditionally, and at every value of this field including 0 and undeclared** (R-SC3(1)). That tiebreak is free and it is not gated by this coefficient. What a *declared* value adds is a **valuation of what the tiebreak recovered**: the start-minutes the tiebreak pulled forward, priced at the declared rate and emitted as **its own labelled line**. That figure never enters `cost_summary.total`, never enters any cost-ledger line, and never enters a delta card's money. Two ledgers, never fused.

**What it no longer does.** It does not enter the primary objective, it does not bias placement, and it will not buy a dearer-but-earlier machine. **The SCHEDULE is byte-identical across every setting of this field** — asserted, not assumed (`tests/test_rolling_horizon.py::test_the_schedule_is_identical_across_every_earliness_value`, at 0 / declared / 100× declared). A declared value that changed a placement would mean the coefficient had leaked back into the objective, which is the defect this amendment removed.

**Why it changed (measured, not argued).** R-SC3(2) — "when positive, earliness enters the primary objective at that price" — is RETIRED. Against a cost-only arm whose seed spread is **exactly zero**, the priced term cost **+73.20%** of ledger total at 40 orders and **+97.61%** at 120, almost all of it tardiness. Mechanism: with zero tardiness the cost objective is start-INDEPENDENT, so cost-only is a feasibility problem CP-SAT closes in ~2.5% of its budget; adding a start-sum to the *primary* objective turns it into an optimization it cannot close. See docs/04's 2026-07-27 R-SC3 amendment.

R-SC3(3) is untouched and is the reason this field must still be *declared* rather than assumed: no internal, undeclared weight may move placement, and what a start-minute is worth is a business judgment only a human may state. Units matter — a value dearer than the cheapest resource's per-minute rate is almost certainly an hours-vs-minutes slip, and the gate flags it (rule `ids.earliness_value_sane`, §4). **The rule count does NOT move: 36 rules, unchanged** — the sanity check on the declared number is exactly as needed for a reporting rate as for a price (a mis-scaled rate produces a mis-scaled valuation, which is a claim about money either way). The full pipeline-proof rule of §8 continues to apply: the declared value must be shown reaching the surface that consumes it — now the tiebreak's reporting line rather than the objective.

**`coarse_horizon` (optional refinement; R-SC2 coarse-zone amendment).** Governs the **far-horizon look-ahead** — the coarse capacity model that places known work BEYOND the current scheduling window into fixed-length buckets, so beyond-horizon demand is coarsely *placed* rather than merely listed. Two coefficients: **`capacity_derate`** (rho) is the FRACTION of calendar capacity the planning run may use (`0 < rho <= 1`), and **`bucket_days`** is the bucket length in days (`>= 1`). Both optional; **absent ⇒ the stated defaults**, `rho = 1.0` and 7-day buckets. The default derate is deliberately a **no-op**: an undeclared plant is never given an invented safety margin, and the certificate prints each coefficient beside its **provenance** (`declared` / `defaulted`) so a coefficient we chose can never read as one the plant chose. rho is a *declared* coefficient for exactly the reason `earliness_value` is (R-SC3(3), amendment clause 3): capacity held back for the unknown is a business judgment, and only a human declaration may make it. **The asymmetry the coefficient serves:** the coarse model is a RELAXATION of the real one, so a coarse INFEASIBLE proves the real schedule cannot fit the work, while a coarse placement proves nothing — and only the run at `rho = 1.0` may be cited as such a proof. An out-of-band or unparseable value cannot be honored: it is defaulted downstream, **loses its declared status**, and degrades the grade (rule `ids.coarse_horizon_coefficients_sane`, §4).

**REMEDIATION ENTRY — NO CAPACITY MARGIN DECLARED (informational; NOT a registry rule).** Added Session 4B.6a (2026-07-27). An absent `capacity_derate` is **not a data defect**: it is an undeclared optional coefficient, and the stated default of `1.0` is a deliberate no-op. It therefore **fires no rule, moves no verdict, and does not appear in the registry** — the rule count stays at 36, and `ids.coarse_horizon_coefficients_sane` continues to check only *declared* values' sanity. What the absence DOES cost is worth saying out loud, and every surface now says it:

- At `rho = 1.0` the **planning run mirrors the proof run**. An undeclared plant therefore gets **no planning signal at all** — its two coarse runs are one run — and every coarse capacity figure it sees assumes **every available minute is usable**. That is the *optimistic* direction, which is the one we do not want to be wrong in.
- **We do not cover it with an invented margin** (amendment clause 3 stands): a hidden derate would be exactly the undeclared weight R-SC3(3) forbids. We make the absence loud instead.
- **Where it is voiced:** the certificate carries a **declaration note** beside the coefficient (`coarse_capacity_derate_note` on the coefficients block), the cockpit's density band header reads *"no capacity margin declared — figures assume every available minute is usable"*, and every capacity answer states the same in words and names the remedy (declare `refinements.coarse_horizon.capacity_derate`).
- **Fix looks like:** declare a planning derate — the fraction of calendar time the plant is willing to plan against. **Verify:** resubmit; the certificate's provenance for the coefficient reads `declared`, and the planning run stops mirroring the proof run.


**`past_due_age_threshold_days` — DECLARED IN NEITHER DIRECTION, AND DELIBERATELY SO (R-PD1 clause (5), Session 4B.11, 2026-07-28). NOT IMPLEMENTED; THIS ENTRY EXISTS TO SAY WHY, AND WHAT IMPLEMENTING IT WOULD REQUIRE.**

R-PD1 clause (5) rules that **AGE IS NOT LATENESS**: a demand past due beyond a *declared* threshold raises a data-quality finding about its **age** — informational, and the demand is still scheduled. The distinction the clause draws is real and the pilot data shows why it matters: the book's minimum due date is **−1573 days** (docs/07 §5a.24). An order three days overdue is the plant's normal position; an order four years overdue is very likely a record nobody closed, and *that* is a data-quality question with a real fix.

**Clause (5) is OPEN.** No coefficient is emitted, no finding is raised, and no threshold is assumed — because the threshold **is a business judgment only a human may state**, exactly as `earliness_value` (R-SC3(3)) and the coarse zone's `capacity_derate` are. There is no defensible default: "past due beyond N days is suspicious" depends entirely on the plant's own close-out discipline, and choosing an N here would author a business fact we do not have. The coarse zone's rule applies unchanged — **an undeclared plant is never given an invented margin** — and emitting an age finding with no declared pathway would be evidence with nothing behind it.

**The rule count does NOT move: 36 rules, unchanged.** Nothing in this entry is a registry rule.

**What implementing it requires — the full §8 pipeline-proof chain, none of it done:**

1. **The doorway.** `cost_model.json` `refinements.past_due_age_threshold_days` (integer, `>= 1`), optional. Absent ⇒ **no age finding is ever raised**, which must be the stated default rather than a fallback constant.
2. **The gate check.** A sanity rule on the *declared* value only (a threshold of 0 or a negative one is a slip; so is one longer than the extract's own history). Adding it moves the registry to 37 rules and is a reviewed change.
3. **The adapter translation.** Carried onto the canonical CostModel with its provenance recorded (`declared` / absent), and printed beside the value on the certificate so a coefficient we chose can never read as one the plant chose.
4. **The finding.** A new code — `PAST_DUE_AT_INTAKE` must NOT be stretched to also mean "suspiciously old", for precisely the reason that code exists at all (docs/02 §4.3): one code, one meaning. INFO severity, `proceeded_flagged`, and **the demand is still scheduled** (clause (5) is explicit).
5. **The authored remediation note.** Unlike `PAST_DUE_AT_INTAKE` — which carries `remediation_applies: false` because a genuinely late order has no fix — an *age* finding DOES have one: close or re-date the stale record at source. The note must say so concretely.
6. **A truth manifest and an anomaly generator**, so the coefficient is pipeline-proven per §8 rather than model-proven.

Until all six exist, the honest position is that the plant is told nothing about the age of its backlog, and that silence is deliberate. Carried in docs/07 §5a.28.

### 5.10 customers.csv (optional*, doorway)
customer_id ✓ · name · priority_class ✓ (→ priority_multipliers) · notes. Order-level priority interacts per manifest `priority_precedence`.

### 5.11 setup_transitions.csv (optional*, doorway)
from_family ✓ · to_family ✓ · setup_minutes ✓ · setup_cost (optional; else minutes × rate) · scrap_units (optional). Unlisted pairs per manifest `unlisted_transition_default`. Presence without any `setup_family` values in routing_lines ⇒ Tier-2 flag (unused matrix); the reverse ⇒ Tier-2 flag (keys without a lock).

### 5.12 locks.csv (optional*, doorway)
order_id ✓ · sequence (blank = whole order) · resource_id ✓ · start ✓ (datetime) · lock_type ✓ (frozen = immovable | pinned_resource | pinned_start) · authority ✓ (who imposed it) · expiry (optional). Translates to frozen_assignment / pinned constraints with provenance human_override or erp_data. **Locks are human decisions about future work.** For work already underway, use wip_status.csv (§5.13) — different truth, different provenance.

### 5.13 wip_status.csv (optional*, doorway) — soft starts / reschedule-from-a-point
The observed shop-floor state at reference_date, enabling rescheduling from the plant's actual position rather than a blank slate. Provenance: **observed (erp_data)** — facts, not decisions.

| Column | Type | Req | Notes |
|---|---|---|---|
| order_id | string | ✓ | → orders |
| sequence | int | ✓ | → routing_lines of the order's route |
| status | string | ✓ | complete / in_progress / not_started |
| actual_start | datetime | ✓ for in_progress & complete | May legitimately precede reference_date |
| actual_resource_id | string | ✓ for in_progress & complete | Where it actually ran — reality may differ from any prior plan |
| remaining_minutes | decimal | per manifest basis | one of the two progress expressions |
| quantity_complete | decimal | per manifest basis | the other; manifest `wip_progress_basis` declares which is authoritative |

Scheduling semantics: **complete** operations consume no capacity and satisfy precedence; **in_progress** operations become fixed intervals on actual_resource_id for their remaining duration from reference_date; downstream operations chain from this fixed reality **by walking PrecedenceEdge records** (docs/01 §5.4a, docs/05 R-A2/A3) — the same edges the Solver Builder reads for ordinary precedence, so a fixed in-flight operation's successor is found via its outgoing edge, not by re-deriving sequence order. Canonical landing: WorkPackage.state (planned / frozen / in_progress / complete — the seam cut in the founding design).

**Invariant amendment (supersedes the blanket pre-reference clamp):** *no newly scheduled operation may start before reference_date; observed in-flight starts are exempt and rendered as observed history.* Both clamp sites (solver horizon derivation and calendar flattening) honor the amended form.

Absent wip_status.csv, all in-scope orders are treated as not_started (a blank-slate schedule) — valid for first submissions, and the certificate notes it for recurring sources where its continued absence becomes suspicious.

## 6. Relationship to the synthetic generator

The generator is this specification's **executable twin**:
- Emits only IDS-conformant submissions (manifest included); generator-output conformance is a standing test.
- Its anomaly catalog is this spec's violation catalog: each seeded defect ↔ one gate check ↔ one expected finding, listed in the generated `truth_manifest.json` with expected schedule properties.
- Scale, anomaly mix, and scenario flavor are parameters. Reality remains the only submitter permitted to surprise us.

## 7. Versioning and governance

`ids_version` in every manifest. Additive ⇒ minor bump; breaking ⇒ major bump with one prior major supported during migration. Changes follow living-document rules: reviewed, recorded in docs/04, never silently repurposed. Thresholds (Appendix A) are versioned policy; per-submission overrides by documented waiver only.

## 8. Extension and pipeline proof

**Growth rule:** each Constraint Catalog (docs/05) concept, when activated, receives an optional dataset + manifest semantics via minor version. A doorway is added when **a capability needs pipeline proof or a submission needs expression — whichever comes first.**

**Pipeline-proof rule:** a capability is *pipeline-proven* only when the complete chain exists — intake doorway (here), gate check (§4), adapter translation, generator scenario with truth manifest, and a schedule-level assertion. Anything less is *model-proven*: real, but weaker, and tracked as such in the Constraint Catalog's test-status column (model-proven / pipeline-proven / unimplemented). Capabilities ship with their doorways or they are not done.

Deferred doorways (each one minor version away, by design): tooling, materials/inventory, labor & skills, min/max lags, alternate routes, preferences.

## Appendix A — Default thresholds (v0.2)
- Order→product / order→route resolution: <60% reject · 60–97% conditional · ≥97% accepted-with-flags
- Duration computability: same bands
- Duplicate order_id > 0 ⇒ conditional (first-wins-with-finding, or block)
- priority_multipliers coverage of used classes <100% ⇒ conditional
- Due dates < reference_date − 365d ⇒ stale-backlog flag (informational)
- Due/requested dates > reference_date + 3y ⇒ placeholder flag (informational)
