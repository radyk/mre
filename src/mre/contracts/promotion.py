"""L1 — The promotion contract (R-AI5(7), Session 4A.5c).

R-AI5(7), verbatim: *"The promotion loop runs autonomously through analysis,
drafting from verified-synthesis exemplars, and harness validation; promotion into
the contracted vocabulary is a reviewed change carrying a machine-produced dossier;
promoted routes run shadowed for a probation window; demotion to synthesis on
divergence is automatic. The system proposes its own healing; the proven register
is entered only by review."*

Four asymmetries are the whole design, and every one of them lives here as a shape:

  1. **Proposing is autonomous, entering is not.** ``tools/promotion_dossier.py``
     writes a ``PromotionDossier`` without asking anyone. Nothing in this package
     can put an intent into dispatch: that takes a session editing ``Intent``,
     ``INTENT_MEANINGS``, ``ROUTE_TAXONOMY`` and the parse prompt, with the dossier
     cited as the authority. The dossier is the APPLICATION; the working thread's
     review is the SIGNATURE.
  2. **Promotion is never automatic; demotion always is.** A ``Promotion`` in
     ``PROMOTIONS`` whose probation fires a divergence flips to ``DEMOTED`` — one
     field — and the intent leaves ``model_selectable_intents()``, so the parse can
     no longer name it and the shape falls back to the second tier. No re-review is
     required to make a wrong promotion stop hurting.
  3. **Probation is measured, not waited out.** A promoted route runs SHADOWED:
     the sweep asks the shape under both paths and diffs their facts. The window
     closes on evidence (``sweeps_observed``), never on a clock.
  4. **Interpretive residue is not backlog** (R-AI5(6)). A shape whose answers are
     takes and aggregate reads is marked NOT-PROMOTABLE-BY-DESIGN by the
     provenance report and never becomes a dossier. Protecting it is a feature.

Nothing here reads or writes the canonical model or the evidence store (M10 has no
write path). ``PROMOTIONS`` is a REVIEWED VOCABULARY on the ``INTENT_MEANINGS``
discipline: add, never repurpose, and a change ships with its doc update.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from mre.contracts.parse import Intent


# ---------------------------------------------------------------------------
# Probation
# ---------------------------------------------------------------------------

class ProbationStatus(str, Enum):
    """Where a promoted route stands. Closed.

    PROBATION — promoted and live, but every question of its shape is ALSO
                answered by the synthesis shadow and the two are diffed. This is
                the only state in which a demotion can fire.
    SETTLED   — the probation window closed with no divergence. The route is an
                ordinary contracted route; the shadow stops running.
    DEMOTED   — a divergence fired (or a reviewer pulled it). The intent leaves
                ``model_selectable_intents()``, the parse can no longer name it,
                and the shape returns to the second tier. A mechanical flag flip.
    """

    PROBATION = "probation"
    SETTLED = "settled"
    DEMOTED = "demoted"


#: How many sweeps a promoted route must run shadowed and clean before it may be
#: SETTLED. Stated in the contract rather than chosen per promotion: a probation
#: length nobody can find is not a probation.
PROBATION_SWEEPS = 2


class Promotion(BaseModel):
    """One promoted shape, with the paperwork that authorized it.

    ``promoted_from`` is the provenance report's cluster id, ``dossier`` the path
    of the committed dossier that argued for it. Both are required: a promotion
    with no dossier is exactly what R-AI5(7) forbids, and the model_validator
    below refuses to construct one."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    #: The cluster id from the provenance report (``ShapeCluster.cluster_id``).
    promoted_from: str
    #: Repo-relative path of the committed dossier that argued for this promotion.
    dossier: str
    #: ISO date (YYYY-MM-DD) the working thread signed it.
    promoted_on: str
    status: ProbationStatus = ProbationStatus.PROBATION
    #: Sweeps this route has run shadowed. Probation closes on evidence, not time.
    sweeps_observed: int = 0
    #: Set when the status is DEMOTED — why, in one line, for the next reader.
    demotion_reason: str = ""
    #: The questions the shadow asks. Drawn from the cluster's exemplars by the
    #: dossier generator, so the probation asks the shape that was promoted rather
    #: than whatever the next sweep happens to contain.
    shadow_questions: list[str] = Field(default_factory=list)

    @property
    def shadowed(self) -> bool:
        """True while this route must be asked under BOTH paths."""
        return self.status is ProbationStatus.PROBATION

    def demote(self, reason: str) -> "Promotion":
        """The mechanical flag flip (R-AI5(7): demotion is automatic). Returns a
        DEMOTED copy — the registry is a vocabulary, so a demotion that outlives
        the process is a committed edit, and this is what the sweep signals."""
        return self.model_copy(update={
            "status": ProbationStatus.DEMOTED,
            "demotion_reason": (reason or "unstated")[:300],
        })


# ---------------------------------------------------------------------------
# The registry — a REVIEWED VOCABULARY (add, never repurpose)
# ---------------------------------------------------------------------------

#: Every promoted shape. Session 4A.5c promotes exactly ONE, as the proof cycle the
#: working thread pre-authorized: the aggregate-lateness shape ("why so many late
#: orders" and kin), the oldest debt in the AI ledger. Its dossier is the authority
#: and is cited here by path.
#:
#: Adding an entry is a VOCABULARY-CLASS CHANGE: it ships with the Intent, the
#: INTENT_MEANING, the ROUTE_TAXONOMY entry, the parse-prompt bump and the doc
#: update in ONE reviewed commit. Nothing generates this dict.
PROMOTIONS: dict[Intent, Promotion] = {
    Intent.LATENESS_CAUSE: Promotion(
        intent=Intent.LATENESS_CAUSE,
        # The provenance report's cluster id, verbatim. The MACHINE names the
        # cluster (adjacency | subject kinds | dominant tool); the human names the
        # SHAPE, and the shape's name is the dossier's filename.
        promoted_from="late-orders|no-subject|lateness_set",
        dossier="docs/promotions/aggregate-lateness-2026-07-26.md",
        promoted_on="2026-07-26",
        status=ProbationStatus.PROBATION,
        # The cluster's own exemplars, plus the phrasing the working thread named
        # when it reviewed the dossier. The probation asks the shape that was
        # promoted, not whatever the next sweep happens to contain.
        shadow_questions=[
            "why so many late orders",
            "whats actually driving the lateness in this plan",
            "why are so many orders late",
        ],
    ),
}


def demoted_intents() -> frozenset[Intent]:
    """The intents a demotion has taken back out of the parse vocabulary.

    ``contracts.parse.model_selectable_intents()`` subtracts this set, which is how
    a demotion actually reaches the planner: the prompt stops offering the id, so
    the parse cannot name it, so the shape goes to the second tier again."""
    return frozenset(i for i, p in PROMOTIONS.items()
                     if p.status is ProbationStatus.DEMOTED)


def shadowed_intents() -> frozenset[Intent]:
    """The intents currently on probation — asked under BOTH paths by the sweep."""
    return frozenset(i for i, p in PROMOTIONS.items() if p.shadowed)


def promotion_for(intent: Intent) -> Optional[Promotion]:
    return PROMOTIONS.get(intent)


# ---------------------------------------------------------------------------
# The shadow diff
# ---------------------------------------------------------------------------

class ShadowDiff(BaseModel):
    """One probation comparison: the promoted route's answer against the synthesis
    shadow's, diffed for FACT AGREEMENT.

    What is compared, stated plainly because the honesty of the demotion trigger
    depends on it: only figures that BOTH sides state about the SAME labelled
    quantity. A figure only one side mentions is not a disagreement — the route
    answers in its own authored shape and the shadow reasons in its own, and
    demanding they say the same words would fire on every turn and teach everyone
    to ignore the signal. A CONTRADICTION on a shared quantity is the signal.

    ``provenance_strengthened`` is the other half of the promotion's claim: the
    route should PROVE what synthesis could only read. It is reported, never a
    trigger — a promotion that fails to strengthen provenance is a review question,
    not an automatic demotion."""

    model_config = ConfigDict(extra="forbid")

    question: str = ""
    intent: str = ""
    #: Quantities both sides spoke to, and agreed on.
    agreed: list[str] = Field(default_factory=list)
    #: Quantities both sides spoke to and CONTRADICTED each other on. Non-empty
    #: here is what fires the demotion signal.
    contradicted: list[str] = Field(default_factory=list)
    #: Verified claims the shadow produced that the route's answer does not speak
    #: to at all. Reported for the reviewer; never a trigger.
    shadow_only: list[str] = Field(default_factory=list)
    #: True when the route cited records for what the shadow could only label
    #: interpretive — the promotion's whole point.
    provenance_strengthened: bool = False
    #: The shadow could not be run (no synthesizer available). Reported as
    #: UNCHECKED, never as clean — the 4A.5a door-check discipline.
    unchecked: bool = False
    #: How long the shadow itself took. Reported so the harness can SUBTRACT it
    #: from the turn's measured latency: the shadow is our own quality control and
    #: runs only in the sweep, so counting it as time a planner waited would make
    #: the promoted route look ~10x slower than it is — the exact opposite of what
    #: the promotion bought.
    latency_ms: Optional[float] = None

    @property
    def diverged(self) -> bool:
        """The demotion trigger. Only a contradiction on a shared quantity."""
        return bool(self.contradicted)
