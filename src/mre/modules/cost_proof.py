"""THE COST PROOF, IN ONE PLACE (Session 4B.11 CU1 — docs/07 §5a.23).

Contract 1.10 (Session 4B.8 CU3) separated two claims a solve makes:

  ``solver.status``           THE COST PROOF   — "no cheaper schedule exists"
  ``solver.tiebreak_status``  THE TIEBREAK     — "no equally-cheap schedule
                                                  starts earlier"

and **nothing rendered either**. Before 4B.10 that looked like a withheld boast.
It is not. On the real plant's real shape (§5a.27) five runs of one instance
differing ONLY in the solver's random seed split 4 OPTIMAL / 1 FEASIBLE, and the
unproved run's ledger is **13.056% more expensive** than the optimum the other
four prove to the cent. Every pre-solve quantity across those five runs is
identical, so **no rule computable before solving can distinguish them** — the
honest mechanism is REPORTING, not prediction, and ``solver.status`` is the only
thing that distinguishes a truthful board from a misleading one.

This module is that report's SINGLE DEFINITION. Two surfaces consume it:

  * the cockpit's top strip, via ``chip()`` — served on the API's schedule
    payload so the JS renders a label it never composes itself;
  * the answer surface, via ``rider()`` — appended by the ONE delivery seam
    (``TemplateRenderer.render``) to any answer that states money.

Three rules the wording obeys, and they are the whole point:

  (1) AN UNPROVEN TIEBREAK NEVER DOWNGRADES A PROVEN COST. The two claims are
      stated separately or not at all; they are never fused into one verdict.
      (Contract 1.10's ruling, restated as language.)
  (2) AN UNPROVED BOARD STATES ITS GAP. "Not proved" alone is the fact without
      its magnitude, and the magnitude is what 4B.10 measured at 13.056%.
      A gap the solver did not report is said to be unreported — never 0.
  (3) A TIEBREAK THAT NEVER RAN IS DISTINGUISHABLE FROM ONE THAT RAN AND WON
      NOTHING. ``tiebreak_skipped_reason`` is voiced, not swallowed.

Three consumers since Session 4B.13 — the third closes the loop:

  * the ASK path, via ``from_evidence()`` — the ``solve-optimality`` route
    (``Explainer._explain_optimality``) answers "is this schedule optimal?" from
    this module and nothing else.

That route is new in 4B.13 (docs/07 §5a.29, discharged). Until then the note
here read that there was deliberately NO such route, because a new intent is a
vocabulary-class change (CLAUDE.md) and 4B.11's brief said to NAME the debt
rather than bolt on a route. 4B.13 paid it properly: `Intent`,
`INTENT_MEANINGS`, `ROUTE_TAXONOMY`, `ROUTE_OFFERS`, the assembler, the authored
copy and parse prompt v10, in one commit. The proof is now rendered, voiced AND
askable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Statuses that constitute a PROOF of the cost optimum. Exactly one, and it is
# CP-SAT's own word for it: the search closed the bound.
_PROVED = ("OPTIMAL",)

# The status a run carries when nothing was admitted at all — there was no solve,
# so there is neither a proof nor a failure to prove. Reporting "not proved" here
# would be a false negative about a solve that never happened.
_NO_SOLVE = ("NO_ADMISSION", "", None)


@dataclass(frozen=True)
class CostProof:
    """What this schedule can and cannot claim about its own cost.

    ``gap`` is CP-SAT's relative gap as ``solve_runner`` records it — a FRACTION,
    ``0.1147`` for 11.47% — or None when the solve reported none. None and 0.0
    are different facts and are never conflated.
    """
    status: Optional[str]
    gap: Optional[float] = None
    objective: Optional[float] = None
    tiebreak_status: Optional[str] = None
    tiebreak_skipped_reason: Optional[str] = None
    # WHY the proof could not be read, when that is the reason there is none —
    # as opposed to a solve that genuinely never happened. Session 4B.18: a
    # schema-1 evidence index dropped the M6 ``solve_complete`` event on save, so
    # every consumer saw ``no_solve`` and said "nothing was admitted" about a
    # board whose own document stated a 56.9% gap.
    unavailable_reason: Optional[str] = None

    # -- verdicts -----------------------------------------------------------
    @property
    def unreadable(self) -> bool:
        """The proof could not be READ. This is a fourth state, not a flavour of
        the other three: the run may have proved its optimum, may have failed to,
        may not have solved at all, and this object cannot tell you which. It
        takes priority over all three so that no surface can accidentally make a
        claim about the plant out of a fact about our storage."""
        return self.unavailable_reason is not None

    @property
    def no_solve(self) -> bool:
        return not self.unreadable and (self.status or None) in _NO_SOLVE

    @property
    def proved(self) -> bool:
        return (self.status or "").upper() in _PROVED

    @property
    def unproved(self) -> bool:
        """A solve ran and did NOT close the bound. Note this is not simply
        ``not proved``: a run with no solve at all is neither, and neither is a
        run whose proof we failed to persist."""
        return not self.unreadable and not self.no_solve and not self.proved

    @property
    def gap_pct(self) -> Optional[float]:
        if self.gap is None:
            return None
        try:
            return float(self.gap) * 100.0
        except (TypeError, ValueError):
            return None

    def gap_text(self) -> str:
        """"11.5%" — one decimal, the same figure the strip chip shows. Empty
        when the solver reported no gap (never "0.0%", which would assert a
        proof the solve did not make)."""
        pct = self.gap_pct
        return "" if pct is None else f"{pct:.1f}%"

    # -- the cockpit strip --------------------------------------------------
    def chip(self) -> dict:
        """The strip chip's payload: a short label, a tone, and the long-form
        title. The JS renders these; it never composes the wording itself, so
        the two surfaces cannot state different things."""
        # Session 4B.13 Item 5(a). Every label here is rendered UNDER the strip's
        # "cost" tag (`<span class="lbl">cost</span> {label}`, main.js), exactly
        # as the certificate chip renders its grade under "certificate". The
        # proved label carried its own "cost" and the strip read
        # "cost cost optimum proved". Fixed on this side rather than by dropping
        # the tag, so all three states read as one sentence with it:
        #   cost | proof not attempted
        #   cost | optimum proved
        #   cost | optimum not proved · gap 11.5%
        if self.unreadable:
            return {"state": "unreadable", "label": "proof not readable",
                    "title": "This schedule's solver report was not saved with "
                             "its evidence, so whether the cost optimum was "
                             "proved cannot be read here. That is a gap in what "
                             "we stored, not a statement about the schedule. "
                             f"({self.unavailable_reason})"}
        if self.no_solve:
            return {"state": "none", "label": "proof not attempted",
                    "title": "Nothing was admitted to this window, so no cost "
                             "proof was attempted."}
        if self.proved:
            label = "optimum proved"
            title = ("No cheaper schedule exists for this window under the "
                     "declared cost model — the solver closed the bound.")
            return {"state": "proved", "label": label,
                    "title": title + self._tiebreak_clause()}
        g = self.gap_text()
        return {
            "state": "unproved",
            "label": f"optimum not proved · gap {g}" if g else "optimum not proved",
            "title": (
                "The solver ran out of budget before it could prove this is the "
                "cheapest schedule."
                + (f" Its own bound leaves a gap of {g}: a cheaper schedule may "
                   f"exist and could be up to that much cheaper."
                   if g else
                   " It reported no gap, so the distance to the optimum is "
                   "unknown.")
                + self._tiebreak_clause()),
        }

    def _tiebreak_clause(self) -> str:
        """Clause (1)/(3): the tiebreak is stated BESIDE the cost proof, never
        folded into it, and a tiebreak that never ran says so."""
        if self.tiebreak_skipped_reason:
            return (f" The earliest-start tiebreak did not run "
                    f"({self.tiebreak_skipped_reason}).")
        if not self.tiebreak_status:
            return ""
        if self.tiebreak_status.upper() in _PROVED:
            return (" The earliest-start tiebreak also proved out: no equally "
                    "cheap schedule starts earlier.")
        return (" The earliest-start tiebreak did not prove out, which does not "
                "affect the cost claim above.")

    # -- the answer surface -------------------------------------------------
    def rider(self) -> Optional[str]:
        """The unprompted qualifier a money claim carries on an UNPROVED board,
        or None when there is nothing to qualify.

        Deliberately silent when the cost optimum IS proved: a rider on every
        answer is noise, and the strip already states the proof. The asymmetry is
        the point — the surface volunteers the thing that WEAKENS its own number.

        AND THEREFORE IT CANNOT BE SILENT WHEN THE PROOF IS UNREADABLE (Session
        4B.18). Silence here is not neutral: on this surface it MEANS "proved",
        because proved is the only other state that says nothing. A board whose
        proof we failed to persist would state money under the same silence a
        proved board does. So an unreadable proof gets its own rider — which
        claims no gap, because we do not have one.
        """
        if self.unreadable:
            return ("Note: I can't tell you whether these cost figures are "
                    "proven optimal — this schedule's solver report was not "
                    "saved with its evidence. Read that as unknown, not as "
                    "proved.")
        if not self.unproved:
            return None
        g = self.gap_text()
        if g:
            return (f"Note: the cost figures above are not proven optimal — the "
                    f"solver ran out of budget with a gap of {g} still open, so a "
                    f"cheaper schedule may exist and could be up to that much "
                    f"cheaper.")
        return ("Note: the cost figures above are not proven optimal — the solver "
                "ran out of budget before it could close the bound, and reported "
                "no gap, so the distance to the cheapest schedule is unknown.")


def from_solver_block(block: Any) -> CostProof:
    """Read a contract-1.10 ``solver`` block (a SolverBlock or its dict)."""
    if block is None:
        return CostProof(status=None)
    get = (block.get if isinstance(block, dict)
           else lambda k, d=None: getattr(block, k, d))
    return CostProof(
        status=get("status"),
        gap=get("gap"),
        objective=get("objective"),
        tiebreak_status=get("tiebreak_status"),
        tiebreak_skipped_reason=get("tiebreak_skipped_reason"),
    )


def from_evidence(index: Any) -> CostProof:
    """Read the cost proof from an EvidenceIndex — the Explainer's own source.

    The M6 ``solve_complete`` event is where both paths record it (the monolithic
    solve via ``solve_runner``, the rolling window-0 solve via
    ``rolling_horizon.build_rolling_view``), which is the same record the
    assembler builds ``SolverBlock`` from. Reading it here rather than taking the
    document keeps the answer surface evidence-first: the answer and the board
    agree because they read one record, not because they were kept in step.

    Never raises — an index without a solve event yields an honest ``unknown``.

    Session 4B.18: when the event is absent AND the index declares itself
    incomplete (a schema-1 artifact, which dropped every subject-less record on
    save), the result is ``unreadable`` rather than ``no_solve``. The difference
    is the whole point — ``no_solve`` is a claim about the plant ("nothing was
    admitted"), and making it out of a storage gap is how the opener came to
    drop a band-1 money item on every monolithic board the API served.
    """
    payload = None
    try:
        # The LATEST M6 run, exactly as `_solver_block` picks it — a run dir can
        # hold several solves (a re-solve, a pool member) and the board shows the
        # last one, so the answer must speak about the same solve.
        m6 = sorted((r for r in index.runs() if r.get("module") == "M6"),
                    key=lambda r: r.get("timestamp_open") or "")
        run_id = m6[-1].get("run_id") if m6 else None
        for rec in index.events():
            if (rec.get("status_text") == "solve_complete"
                    and (run_id is None or rec.get("run_id") == run_id)):
                payload = rec.get("payload") or {}
    except Exception:  # noqa: BLE001 — a missing proof never breaks an answer
        payload = None
    if payload is None:
        incomplete = tuple(getattr(index, "incomplete", ()) or ())
        if incomplete:
            return CostProof(
                status=None,
                unavailable_reason=(
                    "this run's evidence index was saved in an older format "
                    "that did not persist run-level records; missing classes: "
                    + ", ".join(incomplete)))
        return CostProof(status=None)
    return CostProof(
        status=payload.get("status"),
        gap=payload.get("gap"),
        objective=payload.get("objective"),
        tiebreak_status=payload.get("tiebreak_status"),
        tiebreak_skipped_reason=payload.get("tiebreak_skipped_reason"),
    )
