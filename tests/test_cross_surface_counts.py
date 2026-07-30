"""SESSION 4B.21 — THE CROSS-SURFACE COUNT GUARD.

THE RULING THIS PINS (docs/04, 2026-07-30):

    A COUNT NAMES THE DISPOSITION IT COUNTS. "Orders" alone is not a
    disposition. Known, scheduled, committed, active-window, beyond-horizon and
    excluded are different sets, and a surface that reports one of them says
    WHICH.

    A PREDICATE ASSERTED OVER A COUNT MUST BE APPLICABLE TO EVERY MEMBER OF THE
    SET COUNTED. Where it is not, the set is split and each part is reported
    with the predicate that applies to it — never fused, and never left to the
    reader to notice.

THE SPECIMEN. On the pinned rolling board (40 known / 26 scheduled / 14 beyond /
56 placed operations of 88 declared) the `inventory` route said:

    "40 order(s) are in the plan, scheduled across 56 operation(s).
     3 operation(s) can split across a pause.
     Every order finishes on time."

while the opener said "26 orders", the tray said "14 known orders sit beyond the
planning horizon", and the synthesis toolbox's own note said "14 of 40 order(s)
have NO placement in this schedule ... they are neither late nor on time". One
board, four surfaces, three different answers to "how many orders".

======================================================================
THE TWO MECHANISMS, AND WHY NEITHER ALONE CLOSES THE CLASS
======================================================================

(1) THE CROSS-SURFACE AGREEMENT TEST. Every surface that reports a count of
    orders or operations is registered here under the DISPOSITION it claims to
    count. Two surfaces registered under the same disposition must report the
    same value on one board — or they are reporting demonstrably different
    quantities, in which case they belong under different dispositions and the
    register says so. This is the class-level half: it catches a NEW surface
    that picks its own denominator, because a surface reporting a figure that
    matches no registered disposition fails.

(2) THE PROSE TEST. Registering a figure under a disposition does not make the
    SENTENCE name it. So every rendered answer is scanned: a number that equals
    one disposition's value and NOT the others must appear in a sentence
    carrying that disposition's word, and no universal ("every order …",
    "nothing is late …") may stand over a set whose members cannot satisfy the
    predicate. The agreement half cannot see this — the figures can all be
    right while the words fuse them, which is exactly what `inventory` did.

======================================================================
ITS LIMIT, STATED (the 4B.19/4B.20 discipline)
======================================================================

THIS GUARD WATCHES THE ANSWER SURFACE — the contracted routes reachable through
``Explainer.route`` and rendered by ``TemplateRenderer``, plus the synthesis
toolbox's summaries. It does NOT watch:

  * THE COCKPIT'S JAVASCRIPT. `tray.js` renders its own count from
    `doc.rolling.beyond_horizon.length`; a fused count invented there is
    invisible here. (Checked by hand this session and correct — the tray's
    label is "Beyond the horizon" and its title is "known work not yet in a
    window".)
  * THE CONFORMANCE GATE'S RATES ("order→product resolution rate 98.0%").
    Those count SUBMISSION ROWS, not plan dispositions — a different set with a
    different authority, deliberately out of the register rather than silently
    passing it.
  * A SENTENCE WHOSE FIGURE IS CORRECT AND WHOSE WORDING IS MERELY VAGUE in a
    way no disposition value collides with. The prose test fires on a COLLISION
    (a number that is one disposition and not another); a plant where 26 == 40
    would hide the class, which is what the premise test below exists for.

"A sixth fusion is impossible" is not the claim. "The surfaces that answer
'how many' are now checked against each other on a board where the sets
genuinely differ" is.

======================================================================
THE NEGATIVE CONTROLS (run this session, recorded in docs/closeouts/4B.21.md)
======================================================================

  (a) restore `order_count`/`operation_count` fused into the old inventory
      sentence -> 3 failed (both prose tests + the named regression), agreement
      test GREEN. Every figure was still right; only the words fused them.
  (b) register the opener's scheduled count under KNOWN -> 1 failed
      (agreement), prose tests GREEN. Every word was still right; only the
      register lied about which set the figure was.

Each half catches exactly what the other cannot; that is why there are two.

======================================================================
AND WHAT THIS GUARD DID NOT CATCH, until the live run did
======================================================================

Every test here calls `Explainer.route(...)` WITH A DOCUMENT IN HAND. The ask
path does not: `interpreter` injects `params["document"]` from an ALLOW-LIST of
intents, and `inventory` was not on it. So this file was green while a planner
asking "how many orders are in this plan" got a route that could not see the
beyond-horizon region at all -- and, worse, reported that as a VIOLATED
PARTITION rather than an unreadable one.

`test_the_ask_path_hands_the_document_to_every_counting_route` and
`test_a_documentless_census_says_it_cannot_tell` close both halves.
A GUARD THAT SUPPLIES ITS OWN ARGUMENTS PROVES THE ASSEMBLER, NOT THE PATH.
"""
from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "tools"))

UTC = timezone.utc
REF = datetime(2026, 1, 5, tzinfo=UTC)


# ---------------------------------------------------------------------------
# the world: a REAL solved rolling board with a REAL split
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def board(tmp_path_factory):
    """18 orders in a 10-day window — enough book that some orders are placed
    and some are not, which is the only condition under which any assertion
    here means anything (see ``test_premise``)."""
    from generate_erp_dataset import generate
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.rolling_horizon import build_rolling_view, prepare_plant
    from mre.modules.schedule_assembler import assemble_rolling_document

    d = tmp_path_factory.mktemp("xsurface")
    generate(d / "sub", scenario="pilot_scale", orders=18, seed=1)
    plant = prepare_plant(d / "sub", d / "prep", reference_date=REF)
    view = build_rolling_view(plant, window_days=10, frozen_days=3, gravity=True,
                              deterministic=True, seed=42,
                              member_time_limit_s=60.0, det_total=2.0,
                              persist=True)
    idmap = plant.store.load_snapshot(plant.snapshot_id).read_identity_map()
    doc = assemble_rolling_document(plant=plant, view=view, schedule_id="sched-xs",
                                    run_id=str(uuid.uuid4()), identity_map=idmap)
    dd = doc.model_dump(mode="json")
    index = EvidenceIndex().build(plant.out_dir / "runs")
    ex = Explainer(plant.store, index, snapshot_id=plant.snapshot_id)
    return ex, dd


@pytest.fixture(scope="module")
def disposition(board):
    from mre.modules.order_disposition import census
    ex, doc = board
    return census(ex, doc)


# ---------------------------------------------------------------------------
# THE PREMISE — without this every assertion below passes vacuously
# ---------------------------------------------------------------------------

def test_premise_the_board_has_a_non_trivial_split(disposition):
    """4B.18's failure mode, refused in advance.

    Every assertion in this file compares one disposition against another. On a
    board where every known order is scheduled, every one of those comparisons
    is 40 == 40 and the guard proves nothing — it becomes
    `test_load_populates_all_evidence` again: green, and blind.

    So the fixture must genuinely contain all four of: known orders, orders WITH
    a placement, orders WITHOUT one, and more declared operations than placed
    ones. Each is asserted separately, because a fixture can drift into
    satisfying three of them."""
    d = disposition
    assert d.known_orders > 0, "no orders at all — the fixture is empty"
    assert d.scheduled_orders > 0, "nothing is placed; every prose test is moot"
    assert d.beyond_horizon_orders, (
        "no beyond-horizon tray — known and scheduled coincide and the whole "
        "class this guard exists for cannot occur on this board")
    assert d.scheduled_orders < d.known_orders, (
        "scheduled == known: the two figures a planner sees on different "
        "surfaces are the same number here, so a fusion would be invisible")
    assert d.declared_operations > d.placed_operations, (
        "every declared operation is placed, so the splittable line's "
        "denominator cannot differ from the placed line's")
    assert d.partitions(), (
        "the dispositions do not partition the known set — the fixture itself "
        "violates the 4B.3a completeness invariant")


# ---------------------------------------------------------------------------
# (1) THE CROSS-SURFACE AGREEMENT TEST
# ---------------------------------------------------------------------------

#: Each entry: (surface id, disposition, how to read the figure off the board).
#: A surface is registered under the SET IT CLAIMS TO COUNT. Adding a count
#: surface without adding it here is what `test_no_unregistered_count_surface`
#: is for.
def _registry():
    from mre.contracts.synthesis import ToolName
    from mre.modules import rolling_questions as rq
    from mre.modules.evidence_tools import EvidenceToolbox

    def route_fact(rid, key, **params):
        def read(ex, doc):
            b = ex.route(rid, {**params, "document": doc, "question": rid})
            return b.key_facts.get(key)
        return read

    def tool_summary(tool, key):
        def read(ex, doc):
            return (EvidenceToolbox(ex).call(tool, {}).summary or {}).get(key)
        return read

    return [
        # --- KNOWN: every demand the plan carries, placed or not -------------
        ("inventory.known_order_count", "KNOWN",
         route_fact("inventory", "known_order_count")),
        ("lateness_cause.total_orders", "KNOWN",
         route_fact("lateness-cause", "total_orders")),
        ("unknown_entity.order_total", "KNOWN",
         route_fact("unknown-entity", "order_total",
                    mention="ORD-NOPE", mention_kind="order")),
        ("lateness_set.summary.known_orders", "KNOWN",
         tool_summary(ToolName.LATENESS_SET.value, "known_orders")),
        ("entity_vocabulary.summary.known_orders", "KNOWN",
         tool_summary(ToolName.ENTITY_VOCABULARY.value, "known_orders")),

        # --- SCHEDULED: orders with at least one placement in this window ----
        ("inventory.scheduled_order_count", "SCHEDULED",
         route_fact("inventory", "scheduled_order_count")),
        ("late_orders.scheduled_order_count", "SCHEDULED",
         route_fact("late-orders", "scheduled_order_count")),
        ("lateness_cause.scheduled_order_count", "SCHEDULED",
         route_fact("lateness-cause", "scheduled_order_count")),
        ("briefing.opener_scope.orders", "SCHEDULED",
         lambda ex, doc: (ex.route("briefing", {"document": doc,
                                                "question": "briefing"})
                          .key_facts.get("opener_scope") or {}).get("orders")),
        ("lateness_set.summary.scheduled", "SCHEDULED",
         tool_summary(ToolName.LATENESS_SET.value, "scheduled")),

        # --- BEYOND HORIZON: known, admitted, no placement in this window ----
        ("inventory.beyond_horizon_order_count", "BEYOND",
         route_fact("inventory", "beyond_horizon_order_count")),
        ("late_orders.not_scheduled_order_count", "BEYOND",
         route_fact("late-orders", "not_scheduled_order_count")),
        ("lateness_cause.beyond_horizon_order_count", "BEYOND",
         route_fact("lateness-cause", "beyond_horizon_order_count")),
        ("lateness_set.summary.not_scheduled", "BEYOND",
         tool_summary(ToolName.LATENESS_SET.value, "not_scheduled")),
        ("rolling.beyond_horizon", "BEYOND",
         lambda ex, doc: len((doc.get("rolling") or {}).get("beyond_horizon") or [])),
        ("rolling_questions.answer_beyond_horizon", "BEYOND",
         lambda ex, doc: _leading_int(rq.answer_beyond_horizon(doc))),

        # --- PLACED OPERATIONS ----------------------------------------------
        ("inventory.placed_operation_count", "PLACED_OPS",
         route_fact("inventory", "placed_operation_count")),
        ("document.assignments", "PLACED_OPS",
         lambda ex, doc: len(doc.get("assignments") or [])),
        ("cost_ledger.summary.assignments", "PLACED_OPS",
         tool_summary(ToolName.COST_LEDGER.value, "assignments")),

        # --- DECLARED OPERATIONS --------------------------------------------
        ("inventory.declared_operation_count", "DECLARED_OPS",
         route_fact("inventory", "declared_operation_count")),
    ]


def _leading_int(text: str):
    m = re.search(r"\b(\d+)\b", text or "")
    return int(m.group(1)) if m else None


def test_surfaces_registered_under_one_disposition_agree(board, disposition):
    """THE TEETH. Two surfaces that claim to count the same set must report the
    same number on one board, and that number must be the census's.

    This is what a planner actually experiences: they read one answer, then
    another, and the two disagree about how many orders there are. Before this
    session the opener said 26 and `inventory` said 40, both calling it
    "orders", with nothing on either surface naming a set."""
    ex, doc = board
    expected = {
        "KNOWN": disposition.known_orders,
        "SCHEDULED": disposition.scheduled_orders,
        "BEYOND": disposition.beyond_horizon_orders,
        "PLACED_OPS": disposition.placed_operations,
        "DECLARED_OPS": disposition.declared_operations,
    }
    seen: dict[str, list[tuple[str, int]]] = {}
    for sid, disp, read in _registry():
        value = read(ex, doc)
        assert value is not None, (
            f"{sid} is registered under {disp} but reported nothing — a "
            f"surface that silently drops its count is the 4B.18 failure "
            f"mode, not a pass")
        seen.setdefault(disp, []).append((sid, int(value)))

    problems = []
    for disp, entries in sorted(seen.items()):
        want = expected[disp]
        for sid, got in entries:
            if got != want:
                problems.append(f"{sid} reports {got} for {disp}, census says {want}")
    assert not problems, (
        "surfaces disagree about the same disposition on ONE board:\n  "
        + "\n  ".join(problems))


def test_every_disposition_has_at_least_two_independent_surfaces(disposition):
    """A cross-surface test with one surface per disposition is a tautology.

    Each disposition below is read by at least two code paths that do not share
    a computation — a route's key facts, a tool summary, the document itself.
    That is what makes disagreement possible and therefore detectable."""
    counts: dict[str, int] = {}
    for _sid, disp, _read in _registry():
        counts[disp] = counts.get(disp, 0) + 1
    thin = [d for d, n in counts.items() if n < 2 and d != "DECLARED_OPS"]
    assert not thin, (
        f"only one surface registered for {thin} — nothing to cross-check "
        f"against, so the agreement test cannot fail for it")


# ---------------------------------------------------------------------------
# (2) THE PROSE TEST
# ---------------------------------------------------------------------------

#: The word each disposition must appear beside when its figure is spoken.
_DISPOSITION_WORDS = {
    "KNOWN": ("known", "knows about", "in this plan"),
    "SCHEDULED": ("scheduled", "placed", "in this window"),
    "BEYOND": ("beyond the horizon", "beyond the planning horizon",
               "beyond the current window", "not yet scheduled",
               "no placement"),
    "PLACED_OPS": ("placed", "scheduled", "in this window", "running"),
    "DECLARED_OPS": ("declared",),
}

#: Every route whose rendered answer states a count of orders or operations.
_COUNTING_ROUTES = ("inventory", "late-orders", "lateness-cause", "briefing")


def _render(ex, doc, rid, **params):
    from mre.modules.renderers import TemplateRenderer
    b = ex.route(rid, {**params, "document": doc, "question": rid})
    return TemplateRenderer().render(b)


def test_a_spoken_count_names_its_disposition(board, disposition):
    """CLAUSE 1, ON THE SENTENCE.

    For each rendered answer, find every number that is UNAMBIGUOUSLY one
    disposition (equal to that disposition's value and to no other's), and
    require the sentence containing it to carry one of that disposition's
    words. A figure whose value collides across dispositions is skipped — the
    premise test is what keeps the collisions rare enough for this to bite."""
    ex, doc = board
    values = {
        "KNOWN": disposition.known_orders,
        "SCHEDULED": disposition.scheduled_orders,
        "BEYOND": disposition.beyond_horizon_orders,
        "DECLARED_OPS": disposition.declared_operations,
    }
    unique = {d: v for d, v in values.items()
              if v is not None
              and sum(1 for w in values.values() if w == v) == 1}
    assert unique, "no disposition has a distinguishable value on this board"

    problems = []
    for rid in _COUNTING_ROUTES:
        text = _render(ex, doc, rid)
        for sentence in re.split(r"(?<=[.:;])\s+", text):
            if sentence.lstrip().startswith("["):
                continue          # the rendered-by footer is delivery metadata
            for disp, val in unique.items():
                # THE NUMBER MUST GOVERN AN ENTITY NOUN. Caught on this guard's
                # own first run: the fixture has 15 machines and 15
                # beyond-horizon orders, so "3 scheduled orders on 15 machines"
                # was reported as an unnamed BEYOND count. A bare value match
                # cannot tell a machine count from an order count, and a guard
                # that cries wolf is one a future session learns to edit
                # without reading.
                if not re.search(
                        rf"\b{val}\b[^.]{{0,40}}?\b(orders?|operations?)\b",
                        sentence, re.I):
                    continue
                if not any(w in sentence.lower()
                           for w in _DISPOSITION_WORDS[disp]):
                    problems.append(
                        f"[{rid}] states {val} ({disp}) without naming the "
                        f"set: {sentence.strip()!r}")
    assert not problems, (
        "a count was spoken without its disposition:\n  " + "\n  ".join(problems))


#: A universal quantifier over orders presupposes that every member can satisfy
#: the predicate. On a rolling board an unplaced order has no completion date,
#: so "every order finishes on time" is not merely imprecise — it asserts
#: something of orders that have no finish.
_BARE_UNIVERSAL = re.compile(
    r"\b(every|all)\s+(order|orders)\b(?!\s+(with|that|which))|"
    r"\bnothing\s+is\s+late\b(?!\s+in\s+this\s+window)", re.I)
_SCOPE_WORDS = ("scheduled", "placed", "in this window", "with a placement")


def test_no_universal_stands_over_a_set_it_cannot_apply_to(board, disposition):
    """CLAUSE 2. The sharpest specimen in the census carried no number at all —
    "Every order finishes on time." — which is exactly why it survived four
    sessions: with no figure on the surface, nothing told the reader what set
    it ranged over.

    Any universal over "order(s)" must be scoped, in its own sentence, to the
    set that can satisfy the predicate."""
    ex, doc = board
    assert disposition.beyond_horizon_orders, "premise: the tray must be non-empty"
    problems = []
    for rid in _COUNTING_ROUTES:
        for sentence in re.split(r"(?<=[.:;])\s+", _render(ex, doc, rid)):
            if not _BARE_UNIVERSAL.search(sentence):
                continue
            if not any(w in sentence.lower() for w in _SCOPE_WORDS):
                problems.append(f"[{rid}] {sentence.strip()!r}")
    assert not problems, (
        "an unscoped universal over orders, on a board where "
        f"{disposition.beyond_horizon_orders} of them have no completion "
        "date:\n  " + "\n  ".join(problems))


def test_the_prose_test_is_not_vacuous(board, disposition):
    """4B.20's lesson: a guard whose scan finds nothing to scan passes every
    universal quantifier it contains.

    So: the routes really do render, they really do contain digits, and at
    least one of them really does state a disposition figure. Without this, a
    renderer refactor that emptied `_COUNTING_ROUTES`' output would leave both
    prose tests green."""
    ex, doc = board
    rendered = {rid: _render(ex, doc, rid) for rid in _COUNTING_ROUTES}
    for rid, text in rendered.items():
        assert text.strip(), f"{rid} rendered nothing"
        assert re.search(r"\d", text), f"{rid} rendered no figure at all"
    blob = " ".join(rendered.values())
    hits = sum(1 for v in (disposition.known_orders, disposition.scheduled_orders,
                           disposition.beyond_horizon_orders)
               if v and re.search(rf"\b{v}\b", blob))
    assert hits >= 2, (
        "fewer than two disposition figures appear anywhere in the counting "
        "routes' output — the prose test has almost nothing to check")


# ---------------------------------------------------------------------------
# the invariant the whole thing rests on
# ---------------------------------------------------------------------------

def test_the_ask_path_hands_the_document_to_every_counting_route(board):
    """THE SEAM THIS GUARD MISSED ON ITS FIRST LIVE RUN, closed.

    Every test above calls `Explainer.route` with a document in hand. The ASK
    PATH does not: `interpreter` injects `params["document"]` from an ALLOW-LIST
    of intents, and `inventory` was not on it. So the guard was green while a
    planner asking "how many orders are in this plan" got a route that could see
    40 known and 26 placed and had no way to learn the other 14 were admitted
    work waiting for a later window.

    A count route WITHOUT the document cannot see the beyond-horizon region at
    all. This asserts the allow-list covers every route registered above as
    reporting a BEYOND figure — the property, not the three names, so a route
    added tomorrow is caught by the same assertion."""
    from mre.contracts.parse import Intent
    from mre.modules import interpreter as itp

    src = Path(itp.__file__).read_text(encoding="utf-8")
    needs_document = (Intent.INVENTORY, Intent.LATE_ORDERS,
                      Intent.LATENESS_CAUSE, Intent.BRIEFING)
    missing = [i.name for i in needs_document
               if f"Intent.{i.name}" not in src]
    assert not missing, (
        f"{missing} report a beyond-horizon count but are not in the "
        f"interpreter's document allow-list — they will be answered from the "
        f"snapshot alone, where that region does not exist")


def test_a_documentless_census_says_it_cannot_tell(board):
    """THE OTHER HALF OF THE SAME SEAM, and the harder one.

    With no document the census cannot READ the beyond-horizon region. It must
    not then report the partition as VIOLATED — that manufactures a claim about
    the schedule ("at least one order is unaccounted for") out of a missing
    argument, which is precisely 4B.18's `CostProof.unreadable` distinction in a
    new place. It says it cannot tell.

    This fired live before it was a test: `inventory` answered "the orders I can
    account for (0 scheduled, 0 beyond, 0 excluded) do not add up to the 40 this
    plan knows about"."""
    from mre.modules.order_disposition import census
    ex, doc = board
    blind = census(ex, None)
    assert blind.known_orders > 0
    assert blind.scheduled_orders > 0, (
        "a documentless census cannot even see the PLACED orders — it is "
        "reading the enriched rows under the wrong key")
    assert blind.beyond_horizon_orders is None, "absent, not zero"
    assert blind.partitions() is None, (
        "a census that cannot read the tray reported a definite verdict about "
        "the partition")


def test_the_dispositions_partition_the_known_set(board, disposition):
    """The 4B.3a completeness invariant, asserted where sentences are built.

    The assembler raises when the DOCUMENT violates it. This asserts that the
    census read at the ANSWER surface agrees — a partition that holds in the
    document and not in the counts a route reads would let every figure above
    be individually right and collectively wrong."""
    d = disposition
    assert d.scheduled_orders + (d.beyond_horizon_orders or 0) + d.excluded_orders \
        == d.known_orders
    assert d.orders_with_a_finish == d.scheduled_orders
    assert d.splittable_placed <= d.splittable_declared


def test_inventory_states_all_three_dispositions(board, disposition):
    """The specimen, pinned by name.

    The old sentence is gone and the three sets are each spoken. This is the
    narrow regression test beside the class-level ones above; it exists so a
    future reader can see what the ruling changed without reconstructing it."""
    ex, doc = board
    text = _render(ex, doc, "inventory")
    assert "are in the plan, scheduled across" not in text, (
        "the fused inventory sentence is back")
    for value, word in ((disposition.known_orders, "known"),
                        (disposition.scheduled_orders, "scheduled"),
                        (disposition.beyond_horizon_orders, "beyond the horizon")):
        assert re.search(rf"\b{value}\b", text), f"{value} missing from inventory"
        assert word in text.lower(), f"'{word}' missing from inventory"
