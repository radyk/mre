# Incoming Data Specification (IDS)

**Document 6** · Status: Draft v0.4 (living document) · Companions: *01 Canonical Model*, *02 Evidence Contract*, *03 PoC Plan*, *04 Design History*, *05 Constraint Catalog (in progress)*

**v0.2 changes:** cost model REQUIRED with a minimal core (§5.9); customer and priority doorways (§5.10, §3); setup transitions (§5.11); locks (§5.12); overtime expression (§5.6, §5.9); extension & pipeline-proof clause (§8); costing-completeness grade on the certificate (§4).

**v0.3 changes:** `wip_status.csv` doorway for in-flight work / soft-start rescheduling (§5.13); `wip_progress_basis` manifest declaration (§3); WIP gate checks (§4 Tier 2); the reschedule-from-a-point invariant amendment (§5.13).

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

### 4.1 The Rule Registry (v0.2 of the registry; IDS v0.4)

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
docs/05's MP/PP column. All 32 read *implemented*; the column is permanent: the
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
| ids.order_dates_internally_consistent | TEMPORAL_IMPOSSIBILITY | §5.1 | implemented |
| ids.facility_references_consistent | ORPHAN_ENTITY | §3, §5.5 | implemented |
| ids.orders_use_active_routes | LOW_CONFIDENCE_INPUT | §5.2 | implemented |
| ids.priority_classes_priced | UNMAPPABLE_VALUE | §5.9, App A | implemented |
| ids.setup_families_have_transition_matrix | AMBIGUOUS_SOURCE | §5.11 | implemented |
| ids.transition_matrix_references_declared_families | AMBIGUOUS_SOURCE | §5.11 | implemented |
| ids.customer_references_have_master | AMBIGUOUS_SOURCE | §5.10 | implemented |
| ids.locks_reference_known_entities | ORPHAN_ENTITY | §5.12 | implemented |
| ids.wip_references_known_entities | ORPHAN_ENTITY | §5.13 | implemented |
| ids.wip_progression_respects_sequence | LOW_CONFIDENCE_INPUT | §5.13 | implemented |
| ids.wip_in_progress_rows_carry_progress | MALFORMED_FIELD | §5.13 | implemented |
| ids.wip_actual_starts_are_at_or_before_reference_date | VALUE_OUT_OF_RANGE | §5.13 | implemented |
| ids.wip_completion_is_internally_consistent | VALUE_OUT_OF_RANGE | §5.13 | implemented |

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
    "inventory_carrying": null
  }
}
```

`core` is Tier-1 required in full. `priority_multipliers` keys must cover every priority/commitment class used in orders/customers (Tier-2 check otherwise). Customer priority **is a cost coefficient**: there is a priced cost to failing high-priority customers, and it enters the objective as the per-demand tardiness weight.

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
