# Legacy codebase — REFERENCE ONLY

This is the previous-generation scheduler. It is kept as the reference
implementation for hard-won solver logic that will be ported in Phase 2:

- `ProFunctv2_8.py` — CP-SAT model: chunked processing around downtime,
  hybrid workcenter capacity constraints, sequence-dependent setup with
  scrap matrices, dwell phases, tool capacity, objective definition.
- `Formatnewjobs.py` — the ERP joins (workorders/routing/routinglines/product)
  that inform the M1 adapter's source shapes.
- `batchsep.py`, `generate_capacity.py` — preprocessing references.
- `intdash.py` / `Plotly3.py` — Dash Gantt, to be re-pointed at the canonical
  Schedule shape in Phase 3.
- Remaining files — old web wrapper; superseded by the evidence architecture.

RULES:
- Nothing in src/ may import from legacy/.
- Port logic, never shapes. Positional task tuples, epoch-minute due dates,
  integer machine indices, and stdout-as-interface are exactly what the new
  architecture replaces.
