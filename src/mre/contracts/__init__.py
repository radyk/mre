"""L1 — The contracts package.

The single home for every shared shape in the system. Nothing defines record
shapes outside this package. All modules import from here.

Four modules:
  vocabularies   All enums and controlled vocabularies
  entities       Canonical entity types (spine + supporting)
  provenance     Provenance sidecar structures (four classes)
  records        Evidence record types (RunContext, Decision, Finding,
                 Metric, Event, Artifact) and the common envelope
"""
from mre.contracts.vocabularies import (
    CalendarExceptionReason,
    CalendarExceptionType,
    CommitmentClass,
    ConstraintHardness,
    ConstraintProvenance,
    ConstraintType,
    DecisionBasis,
    DecisionType,
    DemandStatus,
    DriverCode,
    FindingCode,
    FindingDisposition,
    FindingSeverity,
    LimitReason,
    ModuleCode,
    ProcessStatus,
    ProvenanceClass,
    RecordTier,
    ResourceRequirementMode,
    ResourceType,
    RunStatus,
    ScheduleStatus,
    WorkPackageState,
)
from mre.contracts.entities import (
    Assignment,
    Calendar,
    CalendarException,
    Capability,
    Constraint,
    CostModel,
    Demand,
    EntityRef,
    ExternalRef,
    Fulfillment,
    Operation,
    OperationSpec,
    PhaseWindows,
    Process,
    Product,
    Quantity,
    Resource,
    ResourceAssignment,
    ResourcePool,
    ResourceRequirement,
    Schedule,
    ServiceOutcome,
    SetupCostBasis,
    TardinessWeights,
    TimeWindow,
    WorkPackage,
)
from mre.contracts.provenance import (
    DefaultedProvenance,
    DerivedProvenance,
    InputRef,
    ObservedProvenance,
    ProvenancePayload,
    ProvenanceSidecar,
    SynthesizedProvenance,
)
from mre.contracts.records import (
    Artifact,
    Decision,
    DecisionAlternative,
    Event,
    Finding,
    InputManifestEntry,
    Metric,
    OutputManifestEntry,
    RunContextClose,
    RunContextOpen,
)

__all__ = [
    # vocabularies
    "CalendarExceptionReason", "CalendarExceptionType", "CommitmentClass",
    "ConstraintHardness", "ConstraintProvenance", "ConstraintType",
    "DecisionBasis", "DecisionType", "DemandStatus", "DriverCode",
    "FindingCode", "FindingDisposition", "FindingSeverity", "LimitReason",
    "ModuleCode", "ProcessStatus", "ProvenanceClass", "RecordTier",
    "ResourceRequirementMode", "ResourceType", "RunStatus", "ScheduleStatus",
    "WorkPackageState",
    # entities
    "Assignment", "Calendar", "CalendarException", "Capability", "Constraint",
    "CostModel", "Demand", "EntityRef", "ExternalRef", "Fulfillment",
    "Operation", "OperationSpec", "PhaseWindows", "Process", "Product",
    "Quantity", "Resource", "ResourceAssignment", "ResourcePool",
    "ResourceRequirement", "Schedule", "ServiceOutcome", "SetupCostBasis",
    "TardinessWeights", "TimeWindow", "WorkPackage",
    # provenance
    "DefaultedProvenance", "DerivedProvenance", "InputRef", "ObservedProvenance",
    "ProvenancePayload", "ProvenanceSidecar", "SynthesizedProvenance",
    # records
    "Artifact", "Decision", "DecisionAlternative", "Event", "Finding",
    "InputManifestEntry", "Metric", "OutputManifestEntry",
    "RunContextClose", "RunContextOpen",
]
