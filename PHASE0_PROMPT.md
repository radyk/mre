# Opening prompt for the first Claude Code session

Paste (or paraphrase) this to start:

---

Read CLAUDE.md and the specs in docs/ (01 and 02 fully; 03 section 3 Phase 0).

Implement Phase 0:

1. `src/mre/contracts/` — entities (Demand, WorkPackage, Fulfillment, Product,
   Process, OperationSpec, Operation, ResourceRequirement, Resource, ResourcePool,
   Capability, Calendar, Constraint, CostModel, Schedule, Assignment,
   ServiceOutcome), the provenance sidecar structures (four classes with
   class-specific payloads), the evidence records (RunContext, Decision, Finding,
   Metric, Event, Artifact) and all enums/vocabularies exactly as specified in
   docs/02 (12 driver codes, 16 finding codes, severities, dispositions, basis,
   tiers).

2. `src/mre/reporter/` — the Reporter with the eight verbs from docs/02 §6,
   schema validation at the verb call, ambient capture (run id, seq, timestamps,
   config hash, exception capture via context manager), JSONL streaming sink,
   and the consolidator with the decomposability check and tier filter
   (docs/02 §7).

3. The Phase 0 deliverable: a toy module under src/mre/modules/ that begins a
   run, emits one of each record type, ends, and produces a valid consolidated
   run document.

Write the tests FIRST, derived from the spec text (contract shapes, vocabulary
membership, write-contract enforcement, decomposability pass/fail, tier
filtering, crash-safety of the JSONL stream). Then implement until green.

Do not start Phase 1. Do not import anything from legacy/.
