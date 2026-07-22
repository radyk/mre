"""IDS Rule Registry (docs/06 §4) — the single source of truth.

The registry data in this module IS what renders docs/06 §4's rule table: the
gate (src/mre/modules/conformance.py) reads rule metadata from here, the typed
gate-finding evidence payload validates its ``rule_id`` against it, and the
end-to-end coverage matrix (tests/test_ids_end_to_end.py) parametrizes over
``RULE_REGISTRY`` directly — so a rule added without an anomaly generator fails
CI by construction.

Governance (docs/06 §4):
- rule_ids are stable identifiers — never renamed for style, retired-never-reused;
  a superseded rule carries ``superseded_by`` and stays resolvable.
- Naming convention (lint-bound): rule ids are positive present-tense conditions
  in IDS domain vocabulary (§2/§5 nouns); no digits, no threshold/band/severity
  words, no implementation words (check/validate/parse).
- Thresholds (Appendix A) are versioned rule *parameters*; a change of *meaning*
  is a new rule_id, never a repurpose.
- The ``status`` field is a permanent honesty column (implemented / unimplemented),
  mirroring docs/05's MP/PP convention: the registry never silently claims a
  check the gate does not have.

Outcome vocabulary (closed enum) and grade (docs/06 §4): a certificate grade is
a pure function of rule outcomes — any ``violated`` → REJECTED; else any
``degraded`` → CONDITIONALLY ACCEPTED; else ACCEPTED (flags disclosed). Boolean
structural rules resolve to satisfied/violated only; quality rules resolve to
satisfied/flagged only and structurally cannot degrade a grade.

Nothing here defines a canonical entity or a record envelope; ``RuleId`` and
``RuleOutcome`` are controlled vocabularies (add, never repurpose) and
``GateFindingEvidence`` is the typed shape of one Finding's ``evidence`` dict —
both properly belong in the contracts package.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator

from mre.contracts.vocabularies import (
    FindingCode, FindingDisposition, FindingSeverity,
)


class RuleId(str, Enum):
    """Stable rule identifiers (docs/06 §4). Add, never repurpose; retire,
    never reuse. Present-tense positive conditions in IDS vocabulary."""

    # --- Boolean structural (satisfied / violated) ---
    SUBMISSION_FILES_PRESENT = "ids.submission_files_present"
    MANIFEST_SCHEMA_VALID = "ids.manifest_schema_valid"
    MANIFEST_SEMANTICS_DECLARED = "ids.manifest_semantics_declared"
    REQUIRED_COLUMNS_PARSE = "ids.required_columns_parse"
    KEY_FIELDS_POPULATED = "ids.key_fields_populated"
    IN_SCOPE_ORDERS_EXIST = "ids.in_scope_orders_exist"
    IN_SCOPE_RESOURCES_EXIST = "ids.in_scope_resources_exist"
    CALENDAR_PATTERNS_EXIST = "ids.calendar_patterns_exist"
    COST_MODEL_CORE_PRESENT = "ids.cost_model_core_present"

    # --- Banded (full outcome range; declared measurement) ---
    ORDERS_RESOLVE_TO_PRODUCTS = "ids.orders_resolve_to_products"
    ORDERS_RESOLVE_TO_ROUTES = "ids.orders_resolve_to_routes"
    ROUTES_RESOLVE_TO_LINES = "ids.routes_resolve_to_lines"
    OPERATION_DURATIONS_COMPUTABLE = "ids.operation_durations_computable"

    # --- Conditional integrity (satisfied / flagged / degraded) ---
    ORDER_IDENTITIES_UNIQUE = "ids.order_identities_unique"
    ORDER_QUANTITIES_ARE_POSITIVE = "ids.order_quantities_are_positive"
    ORDER_DATES_INTERNALLY_CONSISTENT = "ids.order_dates_internally_consistent"
    FACILITY_REFERENCES_CONSISTENT = "ids.facility_references_consistent"
    ORDERS_USE_ACTIVE_ROUTES = "ids.orders_use_active_routes"
    PRIORITY_CLASSES_PRICED = "ids.priority_classes_priced"
    EARLINESS_VALUE_SANE = "ids.earliness_value_sane"
    SETUP_FAMILIES_HAVE_TRANSITION_MATRIX = "ids.setup_families_have_transition_matrix"
    TRANSITION_MATRIX_REFERENCES_DECLARED_FAMILIES = (
        "ids.transition_matrix_references_declared_families")
    CUSTOMER_REFERENCES_HAVE_MASTER = "ids.customer_references_have_master"
    LOCKS_REFERENCE_KNOWN_ENTITIES = "ids.locks_reference_known_entities"
    WIP_REFERENCES_KNOWN_ENTITIES = "ids.wip_references_known_entities"
    WIP_PROGRESSION_RESPECTS_SEQUENCE = "ids.wip_progression_respects_sequence"
    WIP_IN_PROGRESS_ROWS_CARRY_PROGRESS = "ids.wip_in_progress_rows_carry_progress"
    WIP_ACTUAL_STARTS_ARE_AT_OR_BEFORE_REFERENCE_DATE = (
        "ids.wip_actual_starts_are_at_or_before_reference_date")
    WIP_COMPLETION_IS_INTERNALLY_CONSISTENT = "ids.wip_completion_is_internally_consistent"
    ALTERNATIVE_STEP_ATTRIBUTES_AGREE = "ids.alternative_step_attributes_agree"

    # --- Quality (satisfied / flagged; fixed informational consequence) ---
    DURATIONS_WITHIN_PLAUSIBLE_RANGE = "ids.durations_within_plausible_range"
    DUE_DATES_WITHIN_PLANNING_HORIZON = "ids.due_dates_within_planning_horizon"
    BACKLOG_IS_CURRENT = "ids.backlog_is_current"
    DECISION_RELEVANT_ATTRIBUTES_POPULATED = "ids.decision_relevant_attributes_populated"
    OPTIONAL_COLUMNS_ARE_NOT_SPARSE = "ids.optional_columns_are_not_sparse"


class RuleCategory(str, Enum):
    """Determines the permitted outcome range and the grade-consequence class."""
    STRUCTURAL = "structural"        # satisfied / violated
    BANDED = "banded"                # satisfied / flagged / degraded / violated
    CONDITIONAL = "conditional"      # satisfied / flagged / degraded
    QUALITY = "quality"              # satisfied / flagged (cannot degrade a grade)


class RuleOutcome(str, Enum):
    """Closed outcome vocabulary (docs/06 §4). Certificate grade is a pure
    function of the set of rule outcomes."""
    SATISFIED = "satisfied"
    FLAGGED = "flagged"
    DEGRADED = "degraded"
    VIOLATED = "violated"


class RuleStatus(str, Enum):
    IMPLEMENTED = "implemented"
    UNIMPLEMENTED = "unimplemented"


# Which outcomes each category is allowed to produce.
_ALLOWED_OUTCOMES: dict[RuleCategory, frozenset[RuleOutcome]] = {
    RuleCategory.STRUCTURAL: frozenset({RuleOutcome.SATISFIED, RuleOutcome.VIOLATED}),
    RuleCategory.BANDED: frozenset(RuleOutcome),
    RuleCategory.CONDITIONAL: frozenset(
        {RuleOutcome.SATISFIED, RuleOutcome.FLAGGED, RuleOutcome.DEGRADED}),
    RuleCategory.QUALITY: frozenset({RuleOutcome.SATISFIED, RuleOutcome.FLAGGED}),
}


class RuleSpec(BaseModel):
    """One row of the registry."""
    rule_id: RuleId
    category: RuleCategory
    finding_code: FindingCode
    ids_ref: str
    measures: Optional[str] = None      # metric name; banded rules only
    thresholds_ref: Optional[str] = None
    status: RuleStatus = RuleStatus.IMPLEMENTED
    superseded_by: Optional[RuleId] = None
    note: str = ""

    def allows(self, outcome: RuleOutcome) -> bool:
        return outcome in _ALLOWED_OUTCOMES[self.category]


def _spec(rule_id: RuleId, category: RuleCategory, finding_code: FindingCode,
          ids_ref: str, *, measures: Optional[str] = None,
          thresholds_ref: Optional[str] = None, note: str = "") -> RuleSpec:
    return RuleSpec(rule_id=rule_id, category=category, finding_code=finding_code,
                    ids_ref=ids_ref, measures=measures, thresholds_ref=thresholds_ref,
                    note=note)


_S = RuleCategory.STRUCTURAL
_B = RuleCategory.BANDED
_C = RuleCategory.CONDITIONAL
_Q = RuleCategory.QUALITY
_APP_A = "App A"

# The Rule Registry v0.3 (35 rules). Order is documentation order (docs/06 §4).
RULE_REGISTRY: dict[RuleId, RuleSpec] = {
    r.rule_id: r for r in [
        # Boolean structural
        _spec(RuleId.SUBMISSION_FILES_PRESENT, _S, FindingCode.MISSING_REFERENCE, "§2"),
        _spec(RuleId.MANIFEST_SCHEMA_VALID, _S, FindingCode.MALFORMED_FIELD, "§3"),
        _spec(RuleId.MANIFEST_SEMANTICS_DECLARED, _S, FindingCode.AMBIGUOUS_SOURCE, "§3"),
        _spec(RuleId.REQUIRED_COLUMNS_PARSE, _S, FindingCode.MALFORMED_FIELD, "§5"),
        _spec(RuleId.KEY_FIELDS_POPULATED, _S, FindingCode.MALFORMED_FIELD, "§5"),
        _spec(RuleId.IN_SCOPE_ORDERS_EXIST, _S, FindingCode.MISSING_REFERENCE, "§4"),
        _spec(RuleId.IN_SCOPE_RESOURCES_EXIST, _S, FindingCode.MISSING_REFERENCE, "§4"),
        _spec(RuleId.CALENDAR_PATTERNS_EXIST, _S, FindingCode.MISSING_REFERENCE, "§5.6"),
        _spec(RuleId.COST_MODEL_CORE_PRESENT, _S, FindingCode.MISSING_REFERENCE, "§5.9"),
        # Banded
        _spec(RuleId.ORDERS_RESOLVE_TO_PRODUCTS, _B, FindingCode.ORPHAN_ENTITY,
              "§5.1, App A", measures="order_product_resolution_rate", thresholds_ref=_APP_A),
        _spec(RuleId.ORDERS_RESOLVE_TO_ROUTES, _B, FindingCode.ORPHAN_ENTITY,
              "§5.2, App A", measures="order_route_resolution_rate", thresholds_ref=_APP_A),
        _spec(RuleId.ROUTES_RESOLVE_TO_LINES, _B, FindingCode.ORPHAN_ENTITY,
              "§5.3, App A", measures="route_line_resolution_rate", thresholds_ref=_APP_A),
        _spec(RuleId.OPERATION_DURATIONS_COMPUTABLE, _B, FindingCode.VALUE_OUT_OF_RANGE,
              "§5.3, App A", measures="duration_computability_rate", thresholds_ref=_APP_A),
        # Conditional integrity
        _spec(RuleId.ORDER_IDENTITIES_UNIQUE, _C, FindingCode.DUPLICATE_IDENTITY,
              "§5.1, App A", thresholds_ref=_APP_A),
        _spec(RuleId.ORDER_QUANTITIES_ARE_POSITIVE, _C, FindingCode.VALUE_OUT_OF_RANGE,
              "§5.1", note="an order quantity must be > 0; a zero/negative quantity is "
                           "an invalid demand (you cannot make -60 units) — the order is "
                           "excluded downstream and the submission grade degrades. A "
                           "plausible-value class distinct from in_scope_orders_exist "
                           "(which counts whether ANY valid order remains)"),
        _spec(RuleId.ORDER_DATES_INTERNALLY_CONSISTENT, _C,
              FindingCode.TEMPORAL_IMPOSSIBILITY, "§5.1"),
        _spec(RuleId.FACILITY_REFERENCES_CONSISTENT, _C, FindingCode.ORPHAN_ENTITY, "§3, §5.5"),
        _spec(RuleId.ORDERS_USE_ACTIVE_ROUTES, _C, FindingCode.LOW_CONFIDENCE_INPUT, "§5.2"),
        _spec(RuleId.PRIORITY_CLASSES_PRICED, _C, FindingCode.UNMAPPABLE_VALUE,
              "§5.9, App A", thresholds_ref=_APP_A),
        _spec(RuleId.EARLINESS_VALUE_SANE, _C, FindingCode.VALUE_OUT_OF_RANGE,
              "§5.9", note="cost_model refinements.earliness_value (R-SC3) prices "
                           "op-start earliness plant-wide ($/minute). Optional; "
                           "absent => 0. A negative or unparseable value is invalid "
                           "(degraded, defaulted to 0 downstream); a positive value "
                           "dearer than the cheapest resource's per-minute rate is "
                           "almost certainly a unit error (hours vs minutes) and is "
                           "flagged — the gate checks, never repairs"),
        _spec(RuleId.SETUP_FAMILIES_HAVE_TRANSITION_MATRIX, _C,
              FindingCode.AMBIGUOUS_SOURCE, "§5.11"),
        _spec(RuleId.TRANSITION_MATRIX_REFERENCES_DECLARED_FAMILIES, _C,
              FindingCode.AMBIGUOUS_SOURCE, "§5.11"),
        _spec(RuleId.CUSTOMER_REFERENCES_HAVE_MASTER, _C, FindingCode.AMBIGUOUS_SOURCE,
              "§5.10", note="fires only when customer weighting is declared in the "
                            "manifest (priority_precedence); §3-correct silence otherwise"),
        _spec(RuleId.LOCKS_REFERENCE_KNOWN_ENTITIES, _C, FindingCode.ORPHAN_ENTITY, "§5.12"),
        _spec(RuleId.WIP_REFERENCES_KNOWN_ENTITIES, _C, FindingCode.ORPHAN_ENTITY, "§5.13"),
        _spec(RuleId.WIP_PROGRESSION_RESPECTS_SEQUENCE, _C,
              FindingCode.LOW_CONFIDENCE_INPUT, "§5.13"),
        _spec(RuleId.WIP_IN_PROGRESS_ROWS_CARRY_PROGRESS, _C,
              FindingCode.MALFORMED_FIELD, "§5.13"),
        _spec(RuleId.WIP_ACTUAL_STARTS_ARE_AT_OR_BEFORE_REFERENCE_DATE, _C,
              FindingCode.VALUE_OUT_OF_RANGE, "§5.13"),
        _spec(RuleId.WIP_COMPLETION_IS_INTERNALLY_CONSISTENT, _C,
              FindingCode.VALUE_OUT_OF_RANGE, "§5.13"),
        _spec(RuleId.ALTERNATIVE_STEP_ATTRIBUTES_AGREE, _C,
              FindingCode.AMBIGUOUS_SOURCE, "§5.3",
              note="alternative-group rows sharing (route_id, sequence) must agree "
                   "on STEP attributes (setup_family / dwell / splittable / "
                   "min_chunk); disagreement is first-row-wins with this flag"),
        # Quality
        _spec(RuleId.DURATIONS_WITHIN_PLAUSIBLE_RANGE, _Q, FindingCode.STATISTICAL_OUTLIER,
              "§4", note="today measures run-rate outliers vs family median; the rule "
                         "condition is stated broadly and the check may grow into it"),
        _spec(RuleId.DUE_DATES_WITHIN_PLANNING_HORIZON, _Q, FindingCode.VALUE_OUT_OF_RANGE,
              "App A", thresholds_ref=_APP_A),
        _spec(RuleId.BACKLOG_IS_CURRENT, _Q, FindingCode.VALUE_OUT_OF_RANGE,
              "App A", thresholds_ref=_APP_A),
        _spec(RuleId.DECISION_RELEVANT_ATTRIBUTES_POPULATED, _Q,
              FindingCode.LOW_CONFIDENCE_INPUT, "§4"),
        _spec(RuleId.OPTIONAL_COLUMNS_ARE_NOT_SPARSE, _Q,
              FindingCode.LOW_CONFIDENCE_INPUT, "§4"),
    ]
}

assert len(RULE_REGISTRY) == 35, f"registry must hold 35 rules, has {len(RULE_REGISTRY)}"


# Finding severity derives from the DISPOSITION — what the system actually did —
# not from the rule outcome. This is the Session 4.5 cure for "severity means
# nothing": the outcome vocabulary drives the GRADE (grade_from_outcomes); the
# per-entity consequence drives the finding SEVERITY, and the Finding contract
# (records.Finding) enforces that error/blocker severities carry an acting
# disposition. A DEGRADED rule that proceeds flagged therefore emits a WARNING
# finding (the run proceeded) while still degrading the grade to CONDITIONAL via
# its outcome — the two axes no longer contradict each other.
_SEVERITY_BY_DISPOSITION: dict[FindingDisposition, FindingSeverity] = {
    FindingDisposition.BLOCKED: FindingSeverity.BLOCKER,
    FindingDisposition.EXCLUDED: FindingSeverity.ERROR,
    FindingDisposition.PROCEEDED_FLAGGED: FindingSeverity.WARNING,
    FindingDisposition.DEFAULTED: FindingSeverity.WARNING,
    FindingDisposition.AUTO_CORRECTED: FindingSeverity.INFO,
}


def finding_severity(category: RuleCategory,
                     disposition: FindingDisposition) -> FindingSeverity:
    """Finding severity for a non-satisfied gate outcome (docs/06 §4, Session
    4.5). Quality rules carry a *fixed informational* consequence and can never
    degrade a grade, so a quality finding is always INFO; every other rule's
    finding severity is the honest consequence of its disposition (``blocked``→
    BLOCKER, ``excluded``→ERROR, ``proceeded_flagged``/``defaulted``→WARNING,
    ``auto_corrected``→INFO). Severity is decoupled from the outcome so it can
    never again claim a consequence the disposition did not deliver."""
    if category == RuleCategory.QUALITY:
        return FindingSeverity.INFO
    return _SEVERITY_BY_DISPOSITION[disposition]


class ThresholdBand(BaseModel):
    """One Appendix A banded threshold pair (docs/06 Appendix A, v0.2).

    ``reject`` is the floor below which a resolution rate is VIOLATED; the
    [reject, conditional) interval is DEGRADED; ``conditional`` and above is
    SATISFIED. This is the single source the gate bands against and that the
    remediation/judgment registers resolve ``thresholds_ref`` to."""
    reject: float
    conditional: float


# Appendix A default thresholds (v0.2). The four banded resolution rules share
# one band pair; keyed by the ``thresholds_ref`` anchor the remediation catalog
# cites (appendix_a.*), so a note's authored threshold reference resolves to a
# real number here rather than being reinvented at answer time.
_BANDED_RESOLUTION = ThresholdBand(reject=0.60, conditional=0.97)
APPENDIX_A_BANDS: dict[str, ThresholdBand] = {
    "appendix_a.order_product_resolution": _BANDED_RESOLUTION,
    "appendix_a.order_route_resolution": _BANDED_RESOLUTION,
    "appendix_a.route_line_resolution": _BANDED_RESOLUTION,
    "appendix_a.duration_computability": _BANDED_RESOLUTION,
}


def resolve_threshold_band(thresholds_ref: Optional[str]) -> Optional[ThresholdBand]:
    """Resolve a catalog ``thresholds_ref`` anchor to its Appendix A band, or
    None when the ref names no banded threshold (coarse "App A" registry refs
    and non-banded rules resolve to None — they carry no rate band)."""
    if not thresholds_ref:
        return None
    return APPENDIX_A_BANDS.get(thresholds_ref)


def grade_from_outcomes(outcomes: list[RuleOutcome]) -> str:
    """Certificate grade as a pure function of rule outcomes (docs/06 §4).

    Returns the gate's internal grade token (REJECTED / CONDITIONAL / ACCEPTED;
    CONDITIONAL renders as 'CONDITIONALLY ACCEPTED' on the certificate)."""
    if any(o == RuleOutcome.VIOLATED for o in outcomes):
        return "REJECTED"
    if any(o == RuleOutcome.DEGRADED for o in outcomes):
        return "CONDITIONAL"
    return "ACCEPTED"


class Measured(BaseModel):
    """A banded rule's measurement, echoed onto the finding evidence."""
    name: str
    value: float
    unit: str


class GateFindingEvidence(BaseModel):
    """Typed evidence payload for an M0 gate Finding (handoff §B2).

    Validation-at-construction: rule_id must be a registry member, and the
    outcome must be one the rule's category permits. ``check`` is the legacy
    string key kept for one transition (some tests still grep it); ``detail``
    carries check-specific context.
    """
    rule_id: RuleId
    outcome: RuleOutcome
    measured: Optional[Measured] = None
    thresholds_ref: Optional[str] = None
    check: Optional[str] = None
    detail: dict = {}

    @model_validator(mode="after")
    def _outcome_in_range(self) -> "GateFindingEvidence":
        spec = RULE_REGISTRY[self.rule_id]
        if not spec.allows(self.outcome):
            raise ValueError(
                f"rule {self.rule_id.value} ({spec.category.value}) cannot "
                f"produce outcome {self.outcome.value}")
        return self

    def as_evidence(self, **extra) -> dict:
        """Render to the plain dict stored on Finding.evidence, merging any
        check-specific fields (kept flat for the existing test greps)."""
        d = {"rule_id": self.rule_id.value, "outcome": self.outcome.value}
        if self.measured is not None:
            d["measured"] = self.measured.model_dump()
        if self.thresholds_ref is not None:
            d["thresholds_ref"] = self.thresholds_ref
        if self.check is not None:
            d["check"] = self.check
        d.update(self.detail)
        d.update(extra)
        return d
