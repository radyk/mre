# Manufacturing Reasoning Engine — Founding Documents

Orientation for anyone — human or session — opening this repository.

Each document below carries its own status line and version. **Versions are
deliberately not repeated here**: duplicating them is how this file went stale.

| Doc | Contents | Answers |
|---|---|---|
| **01 — Canonical Manufacturing Model** | Three-model architecture, canonicity rules, snapshot semantics, all entities (spine + supporting), PrecedenceEdge, provenance sidecar, design invariants, deferred stubs | *What does the system know, and how is it represented?* |
| **02 — Evidence Contract** | Four-layer reporter architecture, record types (Decision/Finding/Metric/Event/Artifact/RunContext), driver & finding vocabularies, the eight reporter verbs, sink/consolidation rules, boundary rules | *How does every module account for what it did, and how does the AI consume it?* |
| **03 — PoC Plan** | Module inventory M0–M10, original build phases, solver scope cuts, demonstration script, stub list, risk table. **Historical** — superseded for planning by 07 | *What did we build first, and how did we know it worked?* |
| **04 — Design History** | The append-only decision log: alternatives considered and rejected, arguments, governance rulings (R-xx), and the dated Amendment log | *Why is it this way, and what changed when?* |
| **05 — Constraint Catalog** | The census of scheduling constraints: locked rulings, verdict/plane/status per item, input contracts, test triads, acceptance gates | *What can it handle — and what can't it, honestly?* |
| **06 — Incoming Data Specification (IDS)** | Submission schema, manifest declared semantics, the conformance gate's rule registry, the C0–C3 costing-completeness grade, doorways | *How does data get in, and what happens when it's wrong?* |
| **07 — Product Roadmap** | Vision, phases, workstreams, open rulings queue. **Authoritative for what comes next** | *What are we building, and in what order?* |
| **08 — Security Posture** | Encryption, secrets, and tenancy posture as shipped; the named tenant-#2 trigger | *What is the security stance, and where does it stop?* |

`CLAUDE.md` at repo root carries the hard rules, repository layout, working
style, and current roadmap position. It is deliberately short and has a **40k
character ceiling checked at every phase exit** — session history belongs in 04
and 07, never there.

## The system in one paragraph

ERP data enters through an adapter (the only ERP-aware code) and becomes a
versioned snapshot of canonical entities — Demand, WorkPackage, Fulfillment,
Operation, Resource, and friends — each attribute carrying provenance (observed /
derived / defaulted / synthesized). A conformance gate grades the submission
before anything is scheduled; a planner turns Demands into WorkPackages (batching
and splitting as recorded Decisions); a solver builder translates to CP-SAT and
back, so the resulting Schedule lives in canonical language and the math is
disposable. Every module writes Decisions, Findings, and Metrics into one
evidence store through one reporter contract. The AI layer reads only the
canonical model and the evidence — and can therefore explain any schedule, trace
any number, and monitor data quality, in the planner's own vocabulary, without
inventing a single motive.

---

# Thread ledger

Parallel design conversations cannot see each other. This section is the shared
map: paste it into any thread at its start so every thread knows what the others
own and what is open elsewhere.

**Routing rule:** a thread's output passes through the working thread before it
becomes a build prompt or touches the repo. Nothing goes design thread → repo
directly.

**Maintenance rule:** update the date below whenever a thread's open items
change. If this section is more than a phase old, treat it as unverified and
reconcile it against docs/07 before relying on it.

*Last updated: 2026-07-25*

## Live threads

**Working thread — solver/backend track.** Owns session close-out review, prompt
authoring, design rulings. Recent: 4B.2 → 4A.3c. Rulings landed: R-SC3 (earliness
as zero-cost lexicographic tiebreak plus declared coefficient, all solve paths),
R-T2 (two-beat Tier-2 — feasibility ghost shows no money, priced layered delta
card second, contradiction shown not reconciled), R-AI3 (register ladder), R-AI4
(two-axis evaluation). Repo moved OneDrive → `C:\dev\mre`; **the MAX_PATH
short-path workaround is retired.**

**Design thread — co-design and prompt authoring.** Owns this ledger and
context-engineering posture. Delivered Session CE1 (CLAUDE.md extraction:
189.8k → 10,703 bytes, 8 orphan facts preserved to docs/04 first, commit
`5709e10`). Open: whether "design interfaces, not examples" changes the 4A.3
register ladder and exam harness — an expressive route taxonomy may beat a larger
worked-example corpus on this model generation. Design question, not a build
prompt.

**GTM / marketing.** Owns website (same repo as cockpit), pricing bands, funnel,
naming. **Naming is unresolved** — MRE is unsuitable as a brand (military
rations; in-category ERP module collision); ProveOut was the cleanest survivor,
not confirmed. A rename touches the CLAUDE.md title line and this file's heading.
Open: Session W3.1 prompt drafted (capability-answer service off the docs/05
catalog, four honesty registers, market-miss ledger) — not yet run.

**Gatehouse / RCCP.** Owns the pre-solve screen: data load, gate findings, AI
visibility, capacity graph, solver params, Solve button. RCCP is
submission-level, not schedule-level — supersession does not invalidate it. Three
recon questions still open: (1) does the gate evidence store have a
submission-scoped home for pre-solve findings; (2) does
`python -m mre --submission <dataset> --skip-schedule` render a human-readable
certificate or only raw JSONL; (3) is the gate callable over HTTP or CLI only.
Adds repo surface → a later CLAUDE.md layout entry.

**Certificate design.** Open, small: two quarantined catalog notes
(`ids.decision_relevant_attributes_populated`,
`ids.optional_columns_are_not_sparse`) carry `fix_looks_like` with no resolvable
IDS §-cite. Fix is a prose edit plus a `note_version` bump — design-thread-owned.
A guard pins the uncited set to exactly these two, so a later fix trips it. May
be a docs/06 gap rather than a note gap: if no natural section exists to cite,
the spec is missing a sentence.

## Parked

**MES integration** — partnership path deferred until the ticketing pilot
produces a live case study, then target mid-tier vendors lacking APS modules. No
repo impact.

## Closed, folded into docs

Constraint catalog blueprint (05) · multi-machine schema encoding (06) · AI data
logging and evidence tracking · testing with custom datasets · Phase 2 session
2.2 completion.

## Standing cross-thread facts

- **Repo** `C:\dev\mre`, private GitHub `radyk/mre`. Commit to `master`
  directly, push after every commit. No branches, no PRs.
- **All data enters through the IDS submission format** (manifest.json + eight
  required CSVs). Bypassing the gate for test data is forbidden. Pin
  `reference_date`; use `PYTHONHASHSEED=0 --solver-workers 1 --solver-seed 42`
  for any regression baseline.
- **Deterministic mode is mandatory** for any "identical schedule" claim —
  CP-SAT parallel search is not reproducible.
- **Pipeline-proof rule (06 §8):** a new fact class needs IDS doorway → gate
  check → adapter translation → authored remediation note before evidence about
  it can be emitted. Material receipts and supplier reliability have none.
- **Conversational-claim audits run against the pinned run's persisted
  document, never a re-solve.** Listening sessions pin the run id at the start.
- **Feel and visual decisions belong to Daryn at the tuning panel**, never to a
  prompt.
- **Phase exits are audited by a fresh session in audit mode.**
