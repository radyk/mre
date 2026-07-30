"""THE OPENER — what on this board should I be looking at? (Session 4B.16 Item 2.)

The first question a planner asks of a board they have just opened, and until
now the only answer was the morning briefing: late orders ranked by lateness x
priority, one data-quality line. True, useful, and a fraction of what the
persisted document already knows. A board can be provably optimal, carry a
maintenance day that pauses eleven operations, run one machine at 88% while two
eligible ones sit empty, and hold fourteen orders beyond the horizon — and none
of that reached the answer.

WHAT THIS IS
------------
Every candidate item the document supports, each carrying its own number,
RANKED BY CONSEQUENCE. Entirely contracted testimony: no synthesis on the
primary path. Synthesis may still elaborate on any single item when the planner
asks about it — that is what the pointers are for.

THE RANKING RULE, stated because a ranking nobody can check is an opinion
---------------------------------------------------------------------------
Items sort by BAND first, then by the money at stake within it.

  band 1  MONEY AT STAKE IN THIS WINDOW. Two members, and they are comparable
          because both are currency: controllable tardiness (what this schedule
          added, R-PD1 clause 4 — never the floor, which no placement can
          recover) and the unproved optimality gap priced against the ledger
          (`total x gap`, the most a cheaper schedule could save).
  band 2  WORK THAT WILL SLIP. At-risk orders, unplaced work, closures ahead.
          None of these has a price without a re-solve, so they rank by count.
  band 3  STRUCTURE AND PROVENANCE. Concentration, the certificate, a capacity
          margin nobody declared. Real, and none of it is on fire today.
  band 4  CLEAN. An item that is REASSURANCE rather than a worry — a proved
          optimum, an empty late list. It is reported, last, and it is why
          "three things, and none of them are on fire" is a reachable answer
          rather than a silence.

Where two items in a band both carry money, the larger leads. Where one carries
money and the other does not, the priced one leads — not because it matters more
in principle, but because it is the only one of the two whose size is known.

WHAT THE DOCUMENT DOES NOT SUPPORT IS REPORTED, NOT OMITTED
-----------------------------------------------------------
``Opener.unavailable`` carries one entry per candidate that could not be
computed and why: no rolling block, so nothing is known about work beyond the
horizon; eligibility unreadable, so a busy machine cannot be called a
concentration. An opener that silently drops a category reads as a clean bill of
health for it, which is the failure mode this whole session is about.

PURE: facts in, ranked items out. No I/O, no reader, no model. The Explainer
extracts (it is the layer that knows the snapshot and the document); this module
decides what is worth saying, in what order, and in what words.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from mre.modules.planner_language import elapsed_minutes

#: Utilization at or above which a machine is worth naming, and at or below
#: which an eligible alternative counts as idle. Authored thresholds, stated
#: here rather than buried: a "concentration" is only a finding when the work
#: COULD have gone somewhere else, and both halves need a line drawn.
SATURATED = 0.85
IDLE = 0.15

BAND_MONEY = 1
BAND_SLIP = 2
BAND_STRUCTURE = 3
BAND_CLEAN = 4


@dataclass(frozen=True)
class OpenerItem:
    """One thing worth knowing about this board."""

    key: str
    band: int
    #: The money at stake, in the ledger's currency — or None when this item's
    #: size is honestly not expressible as money (which is most of them).
    amount: Optional[float]
    headline: str
    detail: tuple[str, ...] = ()
    #: The question that opens this item up — the seam where the second tier,
    #: or a contracted route, can elaborate on one line of the opener.
    pointer: str = ""
    #: True when this item is reassurance rather than a worry.
    clean: bool = False
    figures: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Opener:
    items: tuple[OpenerItem, ...] = ()
    #: (what could not be computed, why) — never a silent omission.
    unavailable: tuple[tuple[str, str], ...] = ()
    #: Scope: reference date, window, counts. Every figure below is about THIS.
    scope: dict = field(default_factory=dict)

    @property
    def worries(self) -> tuple[OpenerItem, ...]:
        return tuple(i for i in self.items if not i.clean)

    @property
    def clean(self) -> bool:
        """No worries at all — the answer a good board deserves and rarely gets
        said to it."""
        return not self.worries


def _money(x: Optional[float]) -> str:
    return f"{x:,.2f}" if x is not None else "?"


#: Session 4B.21 Item 5(b) — this body moved to ``planner_language`` so the
#: schedule listing can share it. The opener's output is byte-unchanged.
_elapsed = elapsed_minutes


def _work(m: Optional[float]) -> str:
    """WORKING minutes — hours, never days. Same rule as the job card's
    ``_dur_min``: "1d 1h" of work invites the reader to ask a day of what,
    calendar or shift, and the answer is neither."""
    if m is None:
        return "?"
    m = int(round(float(m)))
    if m < 60:
        return f"{m}m"
    h, r = divmod(m, 60)
    return f"{h}h" if not r else f"{h}h{r:02d}m"


def build(*, proof: Any = None, cost: Optional[dict] = None,
          late: Optional[list[dict]] = None,
          at_risk: Optional[list[dict]] = None,
          concentration: Optional[list[dict]] = None,
          closures: Optional[list[dict]] = None,
          unplaced: Optional[dict] = None,
          derate: Optional[dict] = None,
          certificate: Optional[dict] = None,
          scope: Optional[dict] = None,
          unavailable: Optional[list[tuple[str, str]]] = None) -> Opener:
    """Assemble and rank the opener. Every argument is already-extracted fact;
    see the module docstring for what each band means."""
    items: list[OpenerItem] = []
    cost = cost or {}
    unavail = list(unavailable or [])

    items += _proof_items(proof, cost)
    items += _late_items(late or [], cost)
    items += _at_risk_items(at_risk or [])
    items += _unplaced_items(unplaced)
    items += _closure_items(closures or [])
    items += _concentration_items(concentration)
    items += _certificate_items(certificate)
    items += _derate_items(derate)

    # BAND, then money (priced first, larger first), then key — the last only so
    # the order is stable across runs rather than incidental to dict iteration.
    items.sort(key=lambda i: (i.band, 0 if i.amount is not None else 1,
                              -(i.amount or 0.0), i.key))
    return Opener(items=tuple(items), unavailable=tuple(unavail),
                  scope=scope or {})


# ---------------------------------------------------------------------------
# The candidates
# ---------------------------------------------------------------------------

def _proof_items(proof: Any, cost: dict) -> list[OpenerItem]:
    """PROOF STATUS — and it leads when it is unproved and the gap is priced.

    4B.12 measured 13% of the ledger swinging on the seed alone at real density,
    which is why an open gap is a first-class item and not a footnote. Proved is
    the other side of the same coin: reassurance no competitor can offer, so it
    is REPORTED (band 4) rather than left silent.

    AN UNREADABLE PROOF IS ITSELF AN ITEM (Session 4B.18). It was not, and that
    is how this route silently dropped its most consequential member: a
    schema-1 evidence index yielded ``no_solve``, the guard below returned [],
    and a board carrying a 56.9% gap worth up to 29,390.52 against a 51,637.18
    ledger opened with three items and no mention of it — not even under "Not
    covered by this read". The route's contract is that it does not drop a
    category quietly, so the one thing it must never do is stay silent about a
    category it cannot see."""
    if proof is None:
        return []
    if getattr(proof, "unreadable", False):
        return [OpenerItem(
            key="proof", band=BAND_STRUCTURE, amount=None,
            headline="Whether the cost optimum was proved CANNOT BE READ for "
                     "this board — its solver report was not saved with its "
                     "evidence.",
            detail=("This is a gap in what we stored, not a finding about the "
                    "schedule. Re-running the solve records it; the board's own "
                    "strip still shows what the solver reported at the time.",),
            pointer="Ask \"is this schedule optimal?\" for the same caveat in "
                    "full.",
            figures={"unavailable_reason":
                     getattr(proof, "unavailable_reason", None)})]
    if getattr(proof, "no_solve", False):
        return []
    if getattr(proof, "proved", False):
        return [OpenerItem(
            key="proof", band=BAND_CLEAN, amount=None, clean=True,
            headline="The cost optimum is PROVED: no cheaper schedule exists "
                     "for this window under the declared cost model.",
            pointer="Ask \"is this schedule optimal?\" for the full proof.",
            figures={"status": getattr(proof, "status", None)})]
    if not getattr(proof, "unproved", False):
        return []
    gap_txt = proof.gap_text() if hasattr(proof, "gap_text") else ""
    total = cost.get("total")
    gap = getattr(proof, "gap", None)
    at_stake = (float(total) * float(gap)
                if total is not None and gap is not None else None)
    head = ("The cost optimum is NOT proved" +
            (f" — the solver stopped with a gap of {gap_txt} still open"
             if gap_txt else
             " — the solver stopped before closing the bound and reported no "
             "gap, so the distance to the cheapest schedule is unknown") + ".")
    detail: list[str] = []
    if at_stake is not None:
        detail.append(f"Against a ledger of {_money(total)}, that bound leaves "
                      f"up to {_money(at_stake)} on the table — an upper limit "
                      f"on what a cheaper schedule could save, not a saving "
                      f"anyone has found.")
    return [OpenerItem(
        key="proof", band=BAND_MONEY, amount=at_stake, headline=head,
        detail=tuple(detail),
        pointer="Ask \"is this schedule optimal?\" for what the solver did and "
                "did not prove.",
        figures={"status": getattr(proof, "status", None), "gap": gap,
                 "at_stake": at_stake})]


def _late_items(late: list[dict], cost: dict) -> list[OpenerItem]:
    """LATE ORDERS, priced by the part this schedule is answerable for.

    R-PD1 clause (4): the floor — lateness already accrued before the window
    opened — is stated BESIDE the controllable part and never summed into it.
    Ranking on the fused number would put a board at the top of the list for
    work that was already late when it arrived, which no placement can fix."""
    if not late:
        return [OpenerItem(
            key="late", band=BAND_CLEAN, amount=None, clean=True,
            headline="Nothing in this window is late.",
            pointer="Ask \"which orders are late?\" if you want the check.")]
    controllable = cost.get("tardiness_controllable")
    floor = cost.get("tardiness_floor")
    total_cost = cost.get("tardiness")
    amount = controllable if controllable is not None else total_cost
    worst = sorted(late, key=lambda o: -(o.get("lateness_min") or 0))[:3]
    detail = [
        f"{o.get('order')} — {_elapsed(o.get('lateness_min'))} late"
        + (f", of which {_elapsed(o.get('floor_min'))} was already on the clock "
           f"before this window opened" if o.get("floor_min") else "")
        for o in worst]
    if len(late) > len(worst):
        detail.append(f"…and {len(late) - len(worst)} more.")
    head = f"{len(late)} order(s) finish late in this window"
    if amount is not None:
        head += f", costing {_money(amount)}"
        if floor:
            head += (f" that this schedule is answerable for "
                     f"({_money(floor)} more was already accrued and no "
                     f"placement can recover it)")
    return [OpenerItem(
        key="late", band=BAND_MONEY, amount=amount, headline=head + ".",
        detail=tuple(detail),
        pointer="Ask \"why are so many orders late?\" for the cause mix, or "
                "\"why is <order> late?\" for one chain.",
        figures={"count": len(late), "controllable_cost": controllable,
                 "floor_cost": floor})]


def _at_risk_items(at_risk: list[dict]) -> list[OpenerItem]:
    """AT RISK — on time, with less slack than one of its own operations takes.

    "On time with 40 minutes of slack" is a warning, not comfort: any of the
    plant's ordinary disturbances consumes it. The threshold is not arbitrary —
    it is the order's OWN largest operation, so the sentence a planner reads is
    "one hiccup on the longest step and this is late".

    The comparison is CONSERVATIVE by construction, and deliberately so: slack
    is calendar minutes and the step is WORKING minutes, which are never more
    than the calendar time the step occupies. So every order flagged here really
    does have less room than one of its own operations needs, and the ones this
    misses are the ones it was right to be quiet about."""
    if not at_risk:
        return []
    worst = sorted(at_risk, key=lambda o: (o.get("slack_min") or 0))[:3]
    detail = [f"{o.get('order')} — {_elapsed(o.get('slack_min'))} of slack "
              f"against a longest step of {_work(o.get('longest_op_min'))} of work"
              for o in worst]
    if len(at_risk) > len(worst):
        detail.append(f"…and {len(at_risk) - len(worst)} more.")
    return [OpenerItem(
        key="at_risk", band=BAND_SLIP, amount=None,
        headline=f"{len(at_risk)} order(s) finish on time with less slack than "
                 f"one of their own operations takes.",
        detail=tuple(detail),
        pointer="Ask \"when does <order> finish?\" for the timeline, or \"what "
                "would have to change for <order> to start earlier?\".",
        figures={"count": len(at_risk)})]


def _unplaced_items(unplaced: Optional[dict]) -> list[OpenerItem]:
    """UNPLACED WORK — the tray, and anything the coarse zone says will not fit.

    A tray order is never "not in this schedule" (4A.5c CU4). It is known work
    with no placement yet, and the opener says how much of it there is and when
    the first of it is due."""
    if not unplaced:
        return []
    count = int(unplaced.get("count") or 0)
    if not count:
        return []
    detail: list[str] = []
    if unplaced.get("earliest_due"):
        detail.append(f"The earliest of them is due {unplaced['earliest_due']}.")
    if unplaced.get("unmodelable_count"):
        detail.append(
            f"{unplaced['unmodelable_count']} of them could not be placed even "
            f"coarsely, so their load is NOT counted in any figure above.")
    if unplaced.get("infeasibility_proven"):
        detail.append("The coarse proof run returned INFEASIBLE for this book: "
                      "it does not fit as declared. (A coarse refutation is a "
                      "proof; a coarse placement never is.)")
    return [OpenerItem(
        key="unplaced", band=BAND_SLIP, amount=None,
        headline=f"{count} known order(s) sit beyond the planning horizon with "
                 f"no placement yet.",
        detail=tuple(detail),
        pointer="Ask \"what's beyond the horizon?\" for the list, or \"will it "
                "fit?\" for the capacity read.",
        figures={"count": count})]


def _closure_items(closures: list[dict]) -> list[OpenerItem]:
    """CLOSURES AHEAD — declared non-working time inside the window, and what
    it pauses. Never inferred from a gap in a calendar: a night and a shutdown
    look identical in a window list and only one of them was decided."""
    if not closures:
        return []
    first = closures[0]
    machines = first.get("machines") or []
    who = (f"all {len(machines)} of them" if first.get("plant_wide")
           else ", ".join(machines[:4])
           + (f" and {len(machines) - 4} more" if len(machines) > 4 else ""))
    detail = []
    if first.get("spans"):
        detail.append(f"{first['spans']} operation(s) run across it, pausing "
                      f"when the machine closes and resuming when it reopens.")
    for c in closures[1:3]:
        detail.append(f"Also {c.get('reason', 'closure')} on "
                      f"{c.get('date')} ({len(c.get('machines') or [])} "
                      f"machine(s)).")
    if len(closures) > 3:
        detail.append(f"…and {len(closures) - 3} more closures in the window.")
    return [OpenerItem(
        key="closures", band=BAND_SLIP, amount=None,
        headline=f"{first.get('reason', 'closure')} on {first.get('date')} "
                 f"takes out {who}.",
        detail=tuple(detail),
        pointer="Ask \"is any maintenance scheduled?\" for the calendar.",
        figures={"count": len(closures)})]


def _concentration_items(
        concentration: Optional[list[dict]]) -> list[OpenerItem]:
    """CONCENTRATION — a machine near saturation while ELIGIBLE alternatives
    sit idle.

    Eligibility is what makes this a finding and not an observation. CUT-01 at
    88% beside two empty machines is a fact about the plant only if those
    machines could have taken the work; if they could not, the same picture is
    just what a specialised cell looks like."""
    if not concentration:
        return []
    hot = [c for c in concentration
           if (c.get("utilization") or 0) >= SATURATED
           and any((a.get("utilization") or 0) <= IDLE
                   for a in c.get("alternatives") or [])]
    if not hot:
        return []
    hot.sort(key=lambda c: -(c.get("utilization") or 0))
    top = hot[0]
    idle = [a for a in top.get("alternatives") or []
            if (a.get("utilization") or 0) <= IDLE]
    names = ", ".join(f"{a['machine']} at {a['utilization']:.0%}" for a in idle)
    detail = [f"{a['machine']} at {a['utilization']:.0%} of its open hours"
              for a in hot[1:3]]
    return [OpenerItem(
        key="concentration", band=BAND_STRUCTURE, amount=None,
        headline=f"{top['machine']} is at {top['utilization']:.0%} of its open "
                 f"hours while {names} — machines eligible for the same work — "
                 f"are near empty.",
        detail=tuple(detail),
        pointer=f"Ask \"why is {idle[0]['machine']} idle?\", or \"why is "
                f"<order> on {top['machine']}?\" for one placement's reason.",
        figures={"machine": top["machine"],
                 "utilization": top["utilization"],
                 "idle": [a["machine"] for a in idle]})]


def _certificate_items(certificate: Optional[dict]) -> list[OpenerItem]:
    """THE CERTIFICATE — the grade, and any finding the gate PROCEEDED PAST.

    A proceeded-flagged finding is the interesting half: the submission was
    admitted with a disclosed defect, and that disclosure is exactly the thing
    that gets forgotten between the upload and the board."""
    if not certificate:
        return []
    grade = certificate.get("grade")
    count = int(certificate.get("count") or 0)
    proceeded = int(certificate.get("proceeded") or 0)
    if not count and not grade:
        return []
    if not count:
        return [OpenerItem(
            key="certificate", band=BAND_CLEAN, amount=None, clean=True,
            headline=f"The submission graded {grade} with no findings raised.",
            pointer="Ask \"what data problems exist?\" if you want the check.",
            figures={"grade": grade, "count": 0})]
    head = f"{count} data-quality finding(s) stand against this submission"
    head += f" (graded {grade})" if grade else ""
    detail: list[str] = []
    if proceeded:
        detail.append(f"{proceeded} of them were PROCEEDED PAST — the plan was "
                      f"built anyway, with the defect disclosed rather than "
                      f"fixed.")
    if certificate.get("top"):
        detail.append(str(certificate["top"]))
    return [OpenerItem(
        key="certificate", band=BAND_STRUCTURE, amount=None,
        headline=head + ".", detail=tuple(detail),
        pointer="Ask \"what should I fix first?\" for the triage.",
        figures={"grade": grade, "count": count, "proceeded": proceeded})]


def _derate_items(derate: Optional[dict]) -> list[OpenerItem]:
    """DECLARED-BUT-ABSENT — a capacity margin nobody declared.

    docs/06 §5.9's coefficient defaults to 1.0, a no-op derate: an undeclared
    plant is never given an invented margin. The consequence travels with the
    figures — every load number on this board assumes every open minute is a
    usable minute — and saying so is a remediation note, not a gate rule."""
    if not derate or derate.get("provenance") != "defaulted":
        return []
    return [OpenerItem(
        key="undeclared_derate", band=BAND_STRUCTURE, amount=None,
        headline="No capacity margin is declared for this plant, so every "
                 "capacity figure here assumes 100% of open time is usable.",
        detail=("Declare `refinements.coarse_horizon.capacity_derate` in "
                "cost_model.json (docs/06 §5.9) and the coarse figures derate "
                "with it.",),
        pointer="Ask \"how do I declare a capacity margin?\".",
        figures={"capacity_derate": derate.get("value"),
                 "provenance": "defaulted"})]
