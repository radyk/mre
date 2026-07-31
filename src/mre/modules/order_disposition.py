"""THE DISPOSITION CENSUS — one definition of how many orders there are and
which set each figure counts (Session 4B.21, docs/04 2026-07-30 ruling).

WHY THIS EXISTS. On the pinned rolling board the `inventory` route said

    "40 order(s) are in the plan, scheduled across 56 operation(s).
     3 operation(s) can split across a pause.
     Every order finishes on time."

Four claims, four DIFFERENT sets, nothing on the surface naming any of them:

    40  the KNOWN demands in the snapshot
    56  the PLACED operations — of 88 declared, belonging to 26 of the 40 orders
     3  the SPLITTABLE operations of the 88, one of which has no placement
    40  the set the universal ranged over; 26 of them have a finish at all

Each number was true of its own set. The sentence was false of every set it
could be read against, and three OTHER surfaces on the SAME board contradicted
it — the opener ("26 orders on 15 machines"), the tray ("14 known orders sit
beyond the planning horizon"), and the synthesis toolbox's own lateness note
("14 of 40 order(s) have NO placement in this schedule").

THE RULE THIS MODULE ENFORCES BY CONSTRUCTION. A count names the disposition it
counts. "Orders" alone is not a disposition. So every count surface reads its
figures from HERE, where each one carries its set in its own field name, and no
surface is free to invent a denominator of its own.

THE PARTITION IS THE 4B.3a COMPLETENESS INVARIANT, read at the answer surface
instead of at document build: every Demand appears exactly once as committed /
active-window / beyond-horizon / certificate-visible exclusion. The assembler
raises when the document violates it; :meth:`OrderDisposition.partitions` is the
same statement, checked where a sentence is about to be built from it.

WHAT THIS MODULE DOES NOT DO. It counts; it does not phrase. The wording lives
in the renderers and in ``ask_fallback_copy`` (R-AI1(c): planner-facing prose is
authored by a human). And it is a READ — no solve, no re-derivation of anything
the persisted document already states.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

__all__ = ["OrderDisposition", "census"]


@dataclass(frozen=True)
class OrderDisposition:
    """How many orders and operations there are, per DISPOSITION.

    Every field name states the set. Two fields are Optional and are ``None``
    rather than 0 when the board cannot support them — an absent figure and a
    zero figure are different claims, and a monolithic board has no horizon to
    sit beyond.
    """

    #: Demands in the snapshot — every order this plan knows about, whatever
    #: became of it. The union of the three dispositions below.
    known_orders: int
    #: Orders with at least one placed operation in this window.
    scheduled_orders: int
    #: Orders admitted but with no placement in this window: they enter a later
    #: one as the schedule rolls. ``None`` on a monolithic run (no horizon).
    beyond_horizon_orders: Optional[int]
    #: Orders removed by the conformance gate — certificate-visible, never
    #: silent (R-PD1 clause 2: exclusion is a DATA-DEFECT category only).
    excluded_orders: int

    #: Operations declared in the snapshot, across ALL known orders.
    declared_operations: int
    #: Operations with a placement in this window. Never equal to
    #: ``declared_operations`` when anything sits beyond the horizon.
    placed_operations: int
    #: Declared operations flagged splittable, and how many of those were
    #: placed. The pair exists because the two differ on a rolling board and
    #: the difference is exactly the kind a single number hides.
    splittable_declared: int
    splittable_placed: int

    #: True when the document carries a rolling block. A monolithic board has
    #: no beyond-horizon region, so ``scheduled_orders`` there really does
    #: cover every admitted order and a plan-wide universal is honest.
    rolling: bool

    #: HOW THE PLACEMENT FALLS **WITHIN** AN ORDER (Session 4B.22 Item B3).
    #: ``scheduled_orders`` says an order has AT LEAST ONE placed operation. It
    #: does not say whether it has ALL of them, and "are orders all-in or all-out"
    #: is a different question from "how many are in" — the one 4B.21 answered
    #: truly and about something else. ALL THREE ARE ``None`` TOGETHER when the
    #: demand -> fulfillment -> work-package -> operation chain could not be
    #: walked: unreadable is not zero, and "no order is partly placed" is a claim
    #: about the plant that must never be manufactured out of a failed read.
    fully_placed_orders: Optional[int] = None
    partly_placed_orders: Optional[int] = None
    unplaced_orders: Optional[int] = None

    #: True when a schedule document reached this call at all. WITHOUT ONE THE
    #: BEYOND-HORIZON REGION IS UNREADABLE, and unreadable is not the same as
    #: empty: ``rolling`` is itself read off the document, so a documentless
    #: call cannot even tell whether there is a tray it is missing. Every
    #: surface that would state a TOTAL checks this before speaking.
    document_read: bool = True

    # ------------------------------------------------------------------
    @property
    def orders_with_a_finish(self) -> int:
        """The only set a "finishes on time" predicate may range over.

        An order with no placement has no projected completion, so it is
        NEITHER late nor on time — the distinction 4B.13 put into
        ``lateness_set`` and that every universal in the product must respect.
        """
        return self.scheduled_orders

    @property
    def unscheduled_orders(self) -> int:
        """Known, not excluded, and not placed in this window."""
        return max(0, self.known_orders - self.scheduled_orders
                   - self.excluded_orders)

    @property
    def placement_is_all_or_nothing(self) -> Optional[bool]:
        """Does every order on THIS board have all of its declared operations
        placed, or none of them? ``None`` when the per-order chain is unreadable.

        THIS IS A MEASUREMENT, NOT AN INVARIANT, and every surface that speaks it
        must say so. The rolling admission unit is the WORK PACKAGE
        (``rolling_horizon._derive_maps`` keeps exactly one per demand, last
        fulfillment wins), and every operation of an admitted package enters the
        window model as a mandatory interval — so on a board where each order has
        one work package, all-or-nothing falls out. An order fulfilled by TWO work
        packages has no such guarantee: only one of them is reachable through that
        map, and the other's operations would be declared and never admitted. No
        code enforces the one-package case. So "no order is partly placed" is true
        of this schedule and is not a rule of the product, and a surface that
        states the second when it measured the first is making 4B.21's mistake
        one level down.
        """
        if self.partly_placed_orders is None:
            return None
        return self.partly_placed_orders == 0

    def partitions(self) -> Optional[bool]:
        """The completeness invariant, restated where sentences are built.

        Scheduled + beyond-horizon + excluded == known. False means some order
        is in no bucket, which is the silent exclusion the assembler raises on;
        a surface that finds it false must say so rather than pick a number.

        TRI-STATE, AND THE THIRD STATE IS THE POINT. ``None`` means the
        invariant COULD NOT BE EVALUATED — the beyond-horizon region is
        unreadable because no document reached this call. That is a fact about
        our reach, not about the plant, and reporting it as a violated
        partition would manufacture a claim about the schedule out of a missing
        argument. (The same distinction 4B.18 drew for ``CostProof`` between
        `unreadable` and `no solve`, and the same one that made this method
        wrong on its first live run: without a document it declared every
        rolling board broken.)
        """
        if not self.document_read:
            return None
        beyond = self.beyond_horizon_orders or 0
        return self.scheduled_orders + beyond + self.excluded_orders == \
            self.known_orders


def census(explainer: Any, document: Any = None) -> OrderDisposition:
    """Read the disposition census off the snapshot and the persisted document.

    ``document`` is optional: without it the beyond-horizon region cannot be
    read, and ``beyond_horizon_orders`` is ``None`` (absent), never 0.
    """
    reader = getattr(explainer, "_reader", None)

    def _entities(kind: str) -> list:
        if reader is None:
            return []
        try:
            return list(reader.iter_entities(kind))
        except Exception:  # noqa: BLE001 — a failed read never invents a count
            return []

    demands = _entities("demand")
    operations = _entities("operation")

    rows: list[dict] = []
    try:
        rows = explainer._load_enriched_assignments() or []
    except Exception:  # noqa: BLE001
        rows = []

    doc = {}
    if document is not None:
        try:
            doc = explainer._doc(document)
        except Exception:  # noqa: BLE001
            doc = {}
    rolling = bool(doc.get("rolling"))

    # PLACED ORDERS AND OPERATIONS. The document's assignments are authoritative
    # when there is one (they are what the board draws); the enriched rows are
    # the same set read through the explainer, and are the fallback when a route
    # was reached without a document.
    assignments = doc.get("assignments") or []
    if assignments:
        placed_orders = {str(wo) for a in assignments
                         for wo in (a.get("work_orders") or []) if wo}
        placed_ops = {str(a.get("operation_ref")) for a in assignments
                      if a.get("operation_ref")}
        placed_operations = len(assignments)
    else:
        # The enriched row's order refs live under `work_orders` (a LIST — an
        # operation can serve several demands through batching). Reading a
        # `order` key that does not exist returned an empty set, and with the
        # document absent the whole census then reported 0 scheduled against 40
        # known — a partition failure invented by the reader. Caught on the LIVE
        # ask path, where the document was not being threaded to this route,
        # while the guard (which passes one explicitly) stayed green.
        placed_orders = {str(wo) for r in rows
                         for wo in (r.get("work_orders") or []) if wo}
        placed_ops = {str(r.get("operation_ref")) for r in rows
                      if r.get("operation_ref")}
        placed_operations = len(rows)

    beyond: Optional[int] = None
    if rolling:
        tray = {str(i.get("work_order")) for i in
                ((doc.get("rolling") or {}).get("beyond_horizon") or [])
                if i.get("work_order")}
        beyond = len(tray - placed_orders)

    excluded = len(getattr(explainer, "_excluded_order_labels", None) or [])

    splittable = {str(o.get("id")) for o in operations if o.get("splittable")}

    full, part, none_ = _placement_completeness(
        _entities("fulfillment"), demands, operations, placed_ops)

    return OrderDisposition(
        known_orders=len(demands),
        scheduled_orders=len(placed_orders),
        beyond_horizon_orders=beyond,
        excluded_orders=excluded,
        declared_operations=len(operations),
        placed_operations=placed_operations,
        splittable_declared=len(splittable),
        splittable_placed=len(splittable & placed_ops),
        rolling=rolling,
        fully_placed_orders=full,
        partly_placed_orders=part,
        unplaced_orders=none_,
        document_read=document is not None,
    )


def _placement_completeness(fulfillments: list, demands: list, operations: list,
                            placed_ops: set) -> tuple:
    """Split the known orders into FULLY / PARTLY / NOT placed (4B.22 Item B3).

    The chain is Demand -> Fulfillment -> WorkPackage -> Operation, which is the
    canonical one (docs/01 §5): a Demand carries no operations, its Fulfillments
    name the WorkPackages that serve it, and Operations belong to a WorkPackage.
    Every Fulfillment of a demand contributes — deliberately NOT the solver's
    ``wp_of_demand`` map, which keeps one package per demand and would therefore
    make a genuinely partial order look complete by discarding the half it never
    admitted.

    Returns ``(None, None, None)`` when the chain cannot be walked at all: three
    absent figures, never three zeros, because "no order is partly placed" read
    off an empty fulfillment list is a claim about the plant manufactured from a
    failed read.
    """
    if not fulfillments or not demands or not operations:
        return None, None, None
    ops_by_wp: dict = {}
    for o in operations:
        wp = o.get("workpackage_ref")
        if wp:
            ops_by_wp.setdefault(str(wp), []).append(str(o.get("id")))
    declared: dict = {}
    for f in fulfillments:
        did, wp = f.get("demand_ref"), f.get("workpackage_ref")
        if not did or not wp:
            continue
        declared.setdefault(str(did), set()).update(ops_by_wp.get(str(wp), []))
    if not declared:
        return None, None, None

    full = part = none_ = 0
    for d in demands:
        mine = declared.get(str(d.get("id")))
        if not mine:
            # A demand with no reachable operations at all is not an order that
            # is "not placed" — it is an order we could not read. Counting it as
            # unplaced would understate the split and overstate our reach.
            continue
        placed = len(mine & placed_ops)
        if placed == 0:
            none_ += 1
        elif placed == len(mine):
            full += 1
        else:
            part += 1
    return full, part, none_
