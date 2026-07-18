# Glass Box — the sabotage menu

Ten one-cell edits to the clean submission. Each names the file, the row, the
column, and the value to change; the rule that must catch it; the outcome,
severity, and grade it produces; and what the certificate conversation should say.
**Item 8 is the control — a legal edit that must trip *nothing*.**

Apply an edit, re-run the gate, and read the certificate:

```
python -m mre.gate datasets/glass_box     # (work on a copy so the clean set stays clean)
```

Every row below was verified once, mechanically, in `tests/test_glass_box.py`
(`test_sabotage_menu_item`) — so no menu item is wrong about itself. The gate
**detects; it never repairs** (except where a rule's disposition is "first wins").

| # | Edit (file · row · column → value) | Rule caught | Outcome / severity | Grade | Certificate should say |
|---|-------------------------------------|-------------|--------------------|-------|------------------------|
| 1 | `orders.csv` · ORD-01 · `product_id` → `PROD-NOPE` | `ids.orders_resolve_to_products` | degraded / ERROR (`ORPHAN_ENTITY`) | **CONDITIONAL** | An order points at a product that does not exist; too many unresolved to proceed clean. |
| 2 | `orders.csv` · ORD-01 · `due_date` → `2026-01-01` | `ids.order_dates_internally_consistent` | degraded / ERROR (`TEMPORAL_IMPOSSIBILITY`) | **CONDITIONAL** | An order is due before it was created — no schedulable window. Fix the §5.1 dates at the source. |
| 3 | `routing_lines.csv` · `RT-BRACKET,10,PRESS-SLOW` · `splittable` → `true` | `ids.alternative_step_attributes_agree` | degraded / ERROR (`AMBIGUOUS_SOURCE`) | **CONDITIONAL** | The two rows of one alternative group disagree on a *step* attribute (splittable). Resolved **first-row-wins**, disclosed. |
| 4 | `products.csv` · P-WIDGET · `production_minutes` → `3000` | `ids.durations_within_plausible_range` | flagged / **INFO** (`STATISTICAL_OUTLIER`) | ACCEPTED | A product's run rate is >10× its family median — a plausibility flag, disclosed, still accepted. |
| 5 | `orders.csv` · duplicate the whole `ORD-05` row | `ids.order_identities_unique` | degraded / ERROR (`DUPLICATE_IDENTITY`) | **CONDITIONAL** | Two rows share `order_id` ORD-05; first occurrence wins, the duplicate is disclosed. |
| 6 | `orders.csv` · ORD-07 · `order_id` → *(blank)* | `ids.key_fields_populated` | violated / **BLOCKER** (`MALFORMED_FIELD`) | **REJECTED** | A key field is blank — the row cannot be identified. A hard reject; nothing solves. |
| 7 | `routing_lines.csv` · both `RT-BRACKET,10` rows · `active` → `0` | `ids.routes_resolve_to_lines` | degraded / ERROR (`ORPHAN_ENTITY`) | **CONDITIONAL** | A route step has zero active rows — an unroutable operation. |
| 8 | `orders.csv` · ORD-01 · `quantity` → `55` **(CONTROL)** | *(none)* | — | ACCEPTED | Nothing. A legal quantity change must not raise a single flag. |
| 9 | `orders.csv` · ORD-02 · `facility_id` → `F999` | `ids.facility_references_consistent` | degraded / ERROR (`ORPHAN_ENTITY`) | **CONDITIONAL** | An order names a facility outside the declared scope. |
| 10 | `routings.csv` · RT-WIDGET · `status` → `inactive` | `ids.orders_use_active_routes` | degraded / ERROR (`LOW_CONFIDENCE_INPUT`) | **CONDITIONAL** | A live order is built on a route the ERP marks inactive — a low-confidence input. |

## Two things worth noticing

- **Grade is a pure function of outcomes.** Any `violated` → REJECTED (item 6);
  any `degraded` → CONDITIONAL (items 1,2,3,5,7,9,10); only `flagged`/`satisfied`
  → ACCEPTED (items 4, 8). Severity follows outcome: violated = BLOCKER,
  degraded = ERROR, flagged = WARNING, and quality flags = INFO.
- **The control (item 8) is the real test.** A gate that cries wolf is as useless
  as one that sleeps. Editing a quantity to another legal value changes the plan
  but breaks no rule — the certificate stays clean. If item 8 ever flags, the gate
  has a false-positive and that is the bug, not the data.

## Interrogate the certificate

After a sabotage, once you've solved (CONDITIONAL still solves; REJECTED does
not), ask it in the cockpit ask panel — or the CLI (`python -m mre.ask "…"`):

- `what's wrong?` → the **testimony** register: the findings, verbatim.
- `how do I fix the worst one?` → the **remediation** register: authored guidance
  citing the catalog note and the IDS section to correct.
- `what should I fix first?` → the **judgment** register: the fix-first order,
  violated before degraded before flags.
