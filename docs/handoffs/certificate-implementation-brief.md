# Handoff — Conversational Certificate: catalog, renderer, router, triage

> **STATUS: IMPLEMENTED — 2026-07-10.** All of §1–§7 landed; 985 tests green
> (+145). The frozen catalog now lives authoritatively at
> `src/mre/catalog/remediation-catalog-v1.yaml` (the copy beside this brief is
> the design-thread artifact). Registers: `src/mre/modules/remediation.py`,
> `triage.py`; router in `explainer.py`; models in `src/mre/catalog/`.
> **Errand (a) verdict:** `DEFAULTED` mislabelled an exclusion → corrected to
> `EXCLUDED` (gate + adapter); no progress value is invented. **Errand (b):**
> docs/06 §4 severity reworded to (outcome, category). **Reported, not fixed
> (frozen prose):** two quality notes — `decision_relevant_attributes_populated`,
> `optional_columns_are_not_sparse` — carry a `fix_looks_like` with no resolvable
> IDS §-cite, failing the §2 jurisdiction lint; quarantined + pinned, pending a
> design-thread note_version bump. See docs/04 (2026-07-10 entry).

**Mode: IMPLEMENT. Fresh session.** Companion artifact: `remediation-catalog-v1.yaml`
(FROZEN — authored knowledge, reviewed in the design thread). The catalog's prose
is not yours to edit; if a note proves unrenderable or factually wrong against the
code, stop and report — note edits are design-thread work and bump note_version.
Tests from spec first. No new finding codes. docs/04 append-only.

## 1. Catalog storage and integrity

Land `remediation-catalog-v1.yaml` in the repo (e.g. `src/mre/catalog/`). Load
into typed Pydantic models (validation-at-construction): `RemediationNote` keyed
by `RuleId`, `FallbackNote` keyed by `FindingCode`.

Completeness tests (parametrized over registry/vocabulary data, never hand lists):
- every `RuleId` in `ids_rules.py` has exactly one rule-level note
- every note's rule_id exists in the registry (no orphan notes)
- every `FindingCode` (all 18) has exactly one fallback note
- each note's `outcome_phrasing` keys ⊆ the outcomes its rule's category permits
  (a quality note with a `degraded` phrasing is a construction error)
- banded notes carry `measures`/`thresholds_ref` matching the registry row

## 2. Jurisdiction lint (CI)

For every rule-level `fix_looks_like`: must contain ≥1 IDS citation that
resolves — a §-reference present in docs/06 or a §2 filename. Fallbacks with
`remediation_applies: false` are structurally exempt (no fix_looks_like field at
all — assert that too). The negative half (no ERP nouns / no foreign-system
instruction) is review policy, not regex — do not attempt to automate it.

## 3. Remediation register: renderer + validator

New register alongside testimony/judgment. Rendering a remediation = the note's
authored text instantiated with this finding's evidence values (subjects,
measured value, threshold from thresholds_ref, band phrasing from
outcome_phrasing keyed by the finding's outcome). The LLM's job is assembly and
fluency, never invention.

**Post-render validator — single-source-of-truth rule (the 2026-07-06 lesson):**
derive the allowed-content set from exactly the material placed in the render
prompt (note fields + finding evidence + threshold values), one derivation, and
validate the rendered text against it. Numbers not in the set fail closed.
Register phrasing: remediation output is introduced as authored guidance
(catalog note_version citable as a footnote), never as testimony.

## 4. Certificate question domain (explainer router)

Route certificate-scoped questions to the three registers:
- "why was this rejected?" / "what's wrong with X?" → **testimony**: findings,
  evidence, footnotes (existing machinery; gate findings now carry rule_id and
  IDS-space subjects, so entity questions resolve through the identity map —
  including for REJECTED runs where the IDS ref is the only identity).
- "how do I fix it?" → **remediation register** (§3).
- "what should I fix first?" / "does this matter?" → **judgment**, grounded per §5.
Question resolution must go through the identity map, never id-shape regexes
(Phase-1 exit audit rule). Certificate-domain answers read gate findings from
the evidence store — no re-running the gate to answer a question.

## 5. Grade-distance triage (ruled in the design thread)

Deterministic ordering: all `violated` first; then `degraded` ordered by
proximity to the Appendix A threshold that escapes the band (closest escape
first); then `flagged` with WARNING before INFO; quality flags last. Severity is
already (outcome, category) — reuse, don't re-derive. Expose as a pure function
over a certificate's findings + thresholds so the judgment register and any
future UI consume one ordering. Judgment phrasing names the arithmetic: rule,
measured value, threshold, distance.

Truth manifests: every CONDITIONAL/REJECTED generator scenario gains
expected-remediation assertions — expected fix-first ordering (rule_id list) and,
per finding, that the rendered remediation cites the note's ids_ref. This is the
roadmap's "truth manifests gain expected-remediation assertions" clause landing.

## 6. Riding errands

a. **`wip_in_progress_rows_carry_progress` disposition audit.** The gate emits
   `ERROR / defaulted`. Determine what is actually defaulted. If the gate invents
   a progress value, that violates the docs/06 charter (the gate checks, never
   repairs; semantics are never invented) — change behavior to exclusion or
   proceeded_flagged and record in docs/04. If `defaulted` merely mislabels an
   exclusion, correct the disposition. Either way the catalog note ("we never
   invent a progress value") must end up true.
b. **docs/06 severity wording**: confirm the registry text states severity as a
   function of (outcome, category), not outcome alone; amend if it carries the
   one-argument version.
c. **CLAUDE.md status** updated same-commit: Conversational Certificate landed
   (catalog v1 frozen, renderer/router/triage live), Phase 2 remaining items.

## 7. Regression bar

- Full suite green + one `--runslow` pass (renderer/router touch end-to-end paths).
- Live, not just CI: fresh messy plant at CONDITIONAL → ask "what's wrong?",
  "how do I fix the worst one?", "what should I fix first?" through the REPL;
  eyeball that testimony cites records, remediation cites the note + §-refs,
  judgment names its arithmetic, and no answer invents a number.
- A REJECTED scenario: same three questions work with IDS-space identity only.

Report back: test counts, the errand-(a) verdict, and any note that proved
unrenderable as authored (report, don't edit).
