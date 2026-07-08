"""Controlled vocabularies for the manufacturing reasoning engine.

All enums are closed sets. Add codes, never repurpose.
Vocabulary changes require review and a corresponding spec update in docs/.
"""
from enum import Enum


class CommitmentClass(str, Enum):
    STANDARD = "standard"
    RUSH = "rush"
    FIRM = "firm"


class DemandStatus(str, Enum):
    OPEN = "open"
    CANCELLED = "cancelled"
    FULFILLED = "fulfilled"


class WorkPackageState(str, Enum):
    PLANNED = "planned"
    FROZEN = "frozen"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class ResourceType(str, Enum):
    MACHINE = "machine"
    TOOL = "tool"
    LABOR = "labor"
    FIXTURE = "fixture"


class ResourceRequirementMode(str, Enum):
    CAPABILITY = "capability"
    EXPLICIT_SET = "explicit_set"


class ProcessStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class ConstraintType(str, Enum):
    SETUP_TRANSITION = "setup_transition"
    FROZEN_ASSIGNMENT = "frozen_assignment"
    PINNED_WINDOW = "pinned_window"
    RESOURCE_EXCLUSION = "resource_exclusion"
    MAX_QUEUE_TIME = "max_queue_time"


class ConstraintHardness(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class ConstraintProvenance(str, Enum):
    PHYSICS = "physics"
    ERP_DATA = "erp_data"
    POLICY = "policy"
    HUMAN_OVERRIDE = "human_override"


class ScheduleStatus(str, Enum):
    PROPOSED = "proposed"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class LimitReason(str, Enum):
    LABOR_PROXY = "labor_proxy"
    UTILITY = "utility"
    SPACE = "space"
    POLICY = "policy"
    UNKNOWN = "unknown"


class CalendarExceptionType(str, Enum):
    CLOSURE = "closure"
    ADDED = "added"


class CalendarExceptionReason(str, Enum):
    PLANNED_MAINTENANCE = "planned_maintenance"
    BREAKDOWN = "breakdown"
    HOLIDAY = "holiday"
    OVERTIME = "overtime"


class ProvenanceClass(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    DEFAULTED = "defaulted"
    SYNTHESIZED = "synthesized"


class DecisionType(str, Enum):
    IDENTITY_RESOLUTION = "identity_resolution"
    INTERPRETATION = "interpretation"
    DEMAND_MERGE = "demand_merge"
    DEMAND_SPLIT = "demand_split"
    MODEL_SIMPLIFICATION = "model_simplification"
    CONSTRAINT_RELAXATION = "constraint_relaxation"
    ASSIGNMENT = "assignment"
    SCENARIO_MODIFICATION = "scenario_modification"


class DriverCode(str, Enum):
    """Primary driver codes for Decisions. Exactly 12 per spec docs/02 §4.2."""
    COST_TRADEOFF = "COST_TRADEOFF"
    DUE_DATE_PRESSURE = "DUE_DATE_PRESSURE"
    CAPACITY_BLOCKED = "CAPACITY_BLOCKED"
    CAPABILITY_LIMITED = "CAPABILITY_LIMITED"
    SETUP_AMORTIZATION = "SETUP_AMORTIZATION"
    SEQUENCE_DEPENDENCY = "SEQUENCE_DEPENDENCY"
    CALENDAR_WINDOW = "CALENDAR_WINDOW"
    FROZEN_COMMITMENT = "FROZEN_COMMITMENT"
    DATA_EXCLUSION = "DATA_EXCLUSION"
    POLICY_RULE = "POLICY_RULE"
    SOLVER_LIMIT = "SOLVER_LIMIT"
    NO_ALTERNATIVE = "NO_ALTERNATIVE"


class FindingCode(str, Enum):
    """Finding codes. 16 total, grouped by pipeline layer of origin per docs/02 §4.3."""
    # Adapter (ERP-shape)
    MISSING_REFERENCE = "MISSING_REFERENCE"
    UNMAPPABLE_VALUE = "UNMAPPABLE_VALUE"
    AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"
    MALFORMED_FIELD = "MALFORMED_FIELD"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    IDENTITY_CHANGED = "IDENTITY_CHANGED"
    # Validation (semantic)
    TEMPORAL_IMPOSSIBILITY = "TEMPORAL_IMPOSSIBILITY"
    NO_CAPABLE_RESOURCE = "NO_CAPABLE_RESOURCE"
    ORPHAN_ENTITY = "ORPHAN_ENTITY"
    VALUE_OUT_OF_RANGE = "VALUE_OUT_OF_RANGE"
    STATISTICAL_OUTLIER = "STATISTICAL_OUTLIER"
    PROVENANCE_GAP = "PROVENANCE_GAP"
    LOW_CONFIDENCE_INPUT = "LOW_CONFIDENCE_INPUT"
    # Planning / Solve
    BATCH_CONFLICT = "BATCH_CONFLICT"
    INFEASIBLE_SUBSET = "INFEASIBLE_SUBSET"
    HORIZON_EXCEEDED = "HORIZON_EXCEEDED"
    SOLVER_NONOPTIMAL = "SOLVER_NONOPTIMAL"


class FindingSeverity(str, Enum):
    BLOCKER = "blocker"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingDisposition(str, Enum):
    BLOCKED = "blocked"
    EXCLUDED = "excluded"
    DEFAULTED = "defaulted"
    PROCEEDED_FLAGGED = "proceeded_flagged"
    AUTO_CORRECTED = "auto_corrected"


class DecisionBasis(str, Enum):
    OBSERVED = "observed"
    RECONSTRUCTED = "reconstructed"
    POLICY_APPLIED = "policy_applied"


class RecordTier(str, Enum):
    HEADLINE = "headline"
    SUPPORTING = "supporting"
    DETAIL = "detail"


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class ModuleCode(str, Enum):
    M0 = "M0"  # IDS conformance gate (pre-adapter intake)
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"
    M6 = "M6"
    M7 = "M7"
    M8 = "M8"
    M9 = "M9"
    M10 = "M10"
