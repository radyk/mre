"""The capability/coaching registry (Session 4A.3-pre, CU4).

A planner asks "how do I enable X / what can be done to allow Y / I want Z, how /
does MRE support W". The answer is RETRIEVED from this authored, structured
registry — never generated, never read from prose — and carries a doc §-citation.

Per R-AI1(c): intelligence accrues in a reviewable artifact (this file); a human
edits these strings, a model never writes them. Add, never repurpose.

Why a NEW registry rather than the remediation catalog or RULE_REGISTRY: both of
those are FINDINGS-keyed ("your data is wrong about X; here's the fix") and need a
certificate finding as input. A coaching question needs no finding — it answers
"here is the knob and where it's specified". The § citations here are borrowed
verbatim from the `ids_ref` strings the gate's `RULE_REGISTRY` already carries
(docs/06 §4), so a lint can assert every citation resolves.

Jurisdiction rule (docs/07): coach the IDS REQUIREMENT — the submission field and
its spec § — never ERP-specific surgery.

NAMED DEBT (docs/04): docs/05 (the constraint catalog) is PROSE with no structured
backing, so the fuller "why can't it do X / what constraints exist" coaching
surface is prose-locked and NOT built — this registry covers only the submission
DOORWAY / refinement capabilities whose fields and § citations are structured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CapabilityNote:
    """One authored capability answer: what it enables, how to declare it (the
    submission field), and the spec § that governs it. `rationale` cites the
    docs/05 ruling behind the mechanism when one exists (prose, cross-reference
    only — never retrieved from)."""
    concept: str
    enables: str            # one planner-facing sentence: what turning this on does
    how: str                # the concrete declaration (field + file), authored
    ids_ref: str            # the docs/06 § citation (borrowed from RULE_REGISTRY)
    rationale: str = ""     # optional docs/05 cross-reference (prose)
    triggers: tuple[str, ...] = field(default_factory=tuple)


# The authored registry. `triggers` are the planner phrasings that name the
# concept (matched as substrings, lower-cased). Ordered most-specific first so a
# question naming two concepts binds to the more specific (span-downtime before a
# bare "split").
CAPABILITIES: tuple[CapabilityNote, ...] = (
    CapabilityNote(
        concept="splittable",
        enables="an operation to pause at a shift end or closure and resume the "
                "next working period, so a long job can span downtime instead of "
                "waiting for a gap big enough to hold it whole",
        how="set splittable=true and a min_chunk_minutes on that operation's "
            "routing line in routing_lines.csv (the run phase becomes resumable; "
            "chunk boundaries fall on calendar boundaries, and nothing is billed "
            "to the pause)",
        ids_ref="§5.3",
        rationale="docs/05 R-C3 (interruptibility) is the semantic spec: a "
                  "resumable op spans calendar breaks while occupying its resource",
        triggers=("span downtime", "span a closure", "span the closure",
                  "span a break", "span overnight", "across a pause",
                  "across the pause", "across downtime", "across a closure",
                  "over the closure", "over downtime", "over a pause",
                  "pause overnight", "resume", "resumable", "splittable", "split",
                  "chunk", "span a shift", "spanning downtime"),
    ),
    CapabilityNote(
        concept="earliness_value",
        enables="the schedule to pay a little more to start eligible work sooner "
                "(banking slack), as a declared, priced preference rather than the "
                "free zero-cost tiebreak that already prefers earlier starts",
        how="set earliness_value (currency per minute of op-start earliness, "
            "plant-wide, >= 0) under refinements in cost_model.json",
        ids_ref="§5.9",
        rationale="R-SC3: earliness is a zero-cost tiebreak by default; a positive "
                  "earliness_value makes paid earliness declared and traceable",
        triggers=("earliness", "start earlier on purpose", "prefer earlier",
                  "pay to start", "bank slack", "earliness value"),
    ),
    CapabilityNote(
        concept="setup_family",
        enables="sequence-dependent changeovers between job families (e.g. a "
                "colour change on a paint line) to be modeled and their time "
                "amortized by grouping like work",
        how="tag each operation with a setup_family on its routing line "
            "(routing_lines.csv, §5.3) and declare the changeover times between "
            "families in setup_transitions.csv",
        ids_ref="§5.11",
        rationale="docs/05 R-B7/B8 (setup families + transition matrix)",
        triggers=("setup family", "setup families", "changeover", "colour change",
                  "color change", "sequence dependent", "sequence-dependent",
                  "setup transition", "family setup"),
    ),
    CapabilityNote(
        concept="alternates",
        enables="one operation to be eligible on more than one machine, so the "
                "solver can route it to whichever is cheapest or free — with an "
                "honest per-machine rate for each",
        how="add one routing_lines.csv row per eligible machine sharing the same "
            "(route_id, sequence); give each its own run_minutes_per_unit / "
            "setup_minutes where the rates differ",
        ids_ref="§5.3",
        rationale="docs/05 B2 (capability-routed eligible sets)",
        triggers=("alternate", "alternative machine", "alternative resource",
                  "eligible set", "more than one machine", "multiple machines",
                  "run on either", "either machine", "either press", "route it to"),
    ),
    CapabilityNote(
        concept="customers",
        enables="customer-weighted priority, so tardiness on a high-priority "
                "customer's orders is ranked ahead of the rest",
        how="declare each order's customer and priority in customers.csv "
            "(customer_id, name, priority_class → a priority multiplier)",
        ids_ref="§5.10",
        rationale="the customers doorway (customer-weighted tardiness)",
        triggers=("customer priority", "customer weight", "priority customer",
                  "weight my customers", "customers file", "customer master",
                  "declare customers", "rank by customer"),
    ),
    CapabilityNote(
        concept="locks",
        enables="a human scheduling decision about future work to be honored — an "
                "operation frozen in place, pinned to a machine, or pinned to a "
                "start — so the solver plans around it",
        how="declare it in locks.csv (frozen / pinned_resource / pinned_start, "
            "with the deciding authority and provenance)",
        ids_ref="§5.12",
        rationale="the locks doorway (human commitments about future work)",
        triggers=("lock an order", "lock a job", "freeze an order", "freeze a job",
                  "pin an order", "pin a job", "pin to a machine", "pin the start",
                  "locks file", "pinned resource", "pinned start"),
    ),
    CapabilityNote(
        concept="wip",
        enables="the plant to reschedule from its actual shop-floor position — "
                "work already complete or in progress — instead of planning from a "
                "blank slate",
        how="declare observed status in wip_status.csv (complete / in_progress / "
            "not_started, with progress for in-flight work)",
        ids_ref="§5.13",
        rationale="the wip_status doorway (soft starts / reschedule-from-a-point)",
        triggers=("work in progress", "wip", "already started", "already running",
                  "in progress", "reschedule from", "shop floor state",
                  "soft start"),
    ),
)


_CAP_BY_CONCEPT = {c.concept: c for c in CAPABILITIES}

# Explicit capability-question shapes: a planner asking HOW to turn something on /
# whether the product supports it, independent of naming a concept. Used so an
# unrecognized capability question still reaches coaching (an honest not-yet that
# names what CAN be coached) rather than an entity-lookup miss.
_CAPABILITY_SHAPE_RE = re.compile(
    r"(?:how (?:do|can|would) (?:i|we|you)\s+(?:enable|allow|turn on|switch on|"
    r"configure|set up|set-up|let|permit)"
    r"|how can this be done|how is this done|how do i do this|how would i do this"
    r"|is it possible to|is there a way to"
    r"|can i (?:configure|enable|allow|set up|turn on)"
    r"|does (?:this|mre|it|the (?:system|product|tool)) support"
    r"|do you support|can the (?:system|product|solver|tool)"
    r"|what (?:do i|would i|can i) (?:set|declare|configure|add|change) to)",
    re.IGNORECASE)

# A "want/wish" shape ("i want X", "i'd like Y") is a capability question ONLY when
# it also names a known concept — otherwise "i want to know why ORD-05 is late" or
# "i want to see the schedule" would wrongly read as coaching.
_WANT_RE = re.compile(
    r"\b(?:i want|i'd like|i would like|i need|i wish|i'm trying to|"
    r"i am trying to|we want|we'd like|we need)\b", re.IGNORECASE)


def wants_capability(question: str, concept: Optional[str]) -> bool:
    """True for a want/wish phrasing that names a known capability concept."""
    return bool(concept) and bool(_WANT_RE.search(question or ""))


def coaching_concept(question: str) -> Optional[str]:
    """The capability concept a question names (by trigger substring), or None.
    Most-specific first (registry order), so 'span downtime' binds to splittable
    before a bare 'split' would."""
    ql = (question or "").lower()
    for note in CAPABILITIES:
        if any(t in ql for t in note.triggers):
            return note.concept
    return None


def is_capability_question(question: str) -> bool:
    """True when the question has an explicit HOW-TO-ENABLE / does-it-support
    shape — a coaching question even if it names no known concept."""
    return bool(_CAPABILITY_SHAPE_RE.search(question or ""))


def note_for_concept(concept: Optional[str]) -> Optional[CapabilityNote]:
    return _CAP_BY_CONCEPT.get(concept) if concept else None
