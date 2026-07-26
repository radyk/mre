"""The real-doors reverse-guard + invitation semantics (Session 4A.3b, CU4).

R-AI4(3)(c): every authored invitation offers a door into a LIVE route. A door into
a wall is a defect this fast test forbids.

Session 4A.5a re-points the guard. It used to run the deterministic classifier over
each probe; that classifier is retired (R-AI5(2)), and the parse layer that replaced
it needs a model call, which a fast offline test must not make. So the guard is
proven from both sides instead:

  * HERE (offline, every run): the route each invitation DOCUMENTS is a live member
    of the closed intent vocabulary, and dispatching it does not fall through to the
    unsupported assembler. A route rename or deletion breaks the build.
  * IN THE SWEEP (live, per re-baseline): the sidecar parses every offered follow-up
    with the REAL parse layer — what a planner clicking it would hit — and a probe
    that parses to no intent is a `dead-door` finding.
"""
from __future__ import annotations

import pytest

from mre.contracts.parse import Intent
from mre.modules.ask_fallback_copy import (
    INVITATIONS, Invitation, invitation_line, invitation_probe,
)
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import ROUTE_TAXONOMY, Explainer


class _FakeStore:
    """A snapshot store that always misses — puts the Explainer in certificate-only
    mode so we can inject a synthetic vocabulary without a solve."""

    def load_snapshot(self, snapshot_id):  # noqa: ANN001
        raise FileNotFoundError(snapshot_id)


@pytest.fixture(scope="module")
def world():
    ex = Explainer(_FakeStore(), EvidenceIndex(), snapshot_id="x")
    ex._order_refs = {f"ORD-{i:02d}": f"ORD-{i:02d}" for i in range(1, 16)}
    ex._machine_refs = {m: m for m in
                        ("CUT-01", "PRESS-FAST", "PRESS-SLOW", "PAINT-01", "HEAT-01")}
    ex._order_shape_patterns = ex._build_order_shapes()
    ex._order_fuzzy = ex._build_order_fuzzy()
    return ex


_FACTS = {"order": "ORD-05", "machine": "CUT-01"}


class TestRealDoors:
    @pytest.mark.parametrize("key", list(INVITATIONS))
    def test_every_probe_documents_a_live_route(self, world, key):
        inv = INVITATIONS[key]
        probe = invitation_probe(key, **_FACTS)
        assert probe, f"{key}: probe did not fill its slots"
        # the documented destination is a member of the closed intent vocabulary
        assert inv.expect_route in ROUTE_TAXONOMY, (
            f"invitation {key!r} documents {inv.expect_route!r}, not a live route")
        assert inv.expect_route in {i.value for i in Intent}, (
            f"invitation {key!r} documents a route no parse can name")

    @pytest.mark.parametrize("key", list(INVITATIONS))
    def test_every_documented_route_has_an_assembler(self, world, key):
        """A door into a wall shows up as `route()` falling through to the
        unsupported assembler. This fixture's world is deliberately empty (no
        solve), so an assembler that RAISES on empty evidence is fine — that is a
        missing fixture, not a missing door; only the fall-through is the defect."""
        inv = INVITATIONS[key]
        try:
            bundle = world.route(inv.expect_route,
                                 {"question": invitation_probe(key, **_FACTS),
                                  **_FACTS})
        except Exception:  # noqa: BLE001 — an empty world, not a missing door
            return
        assert bundle.subject_type != "unsupported", (
            f"invitation {key!r} offers a door into a wall: "
            f"{inv.expect_route!r} dispatches to the unsupported assembler")

    def test_an_unknown_route_id_does_fall_through(self, world):
        """The guard above is only meaningful because the fall-through exists."""
        assert world.route("not-a-route", {"question": "q"}).subject_type == \
            "unsupported"

    def test_registry_entries_are_well_formed(self):
        for key, inv in INVITATIONS.items():
            assert isinstance(inv, Invitation)
            assert inv.key == key
            assert inv.pattern and inv.probe and inv.expect_route
            # every slot named in the pattern is declared (so a fact is required)
            for slot in ("order", "machine"):
                if "{" + slot + "}" in inv.pattern:
                    assert slot in inv.slots, f"{key}: pattern uses {slot}, not declared"


class TestInvitationSemantics:
    def test_missing_slot_yields_no_offer(self):
        # A half-filled invitation is never emitted (never "queues behind None").
        assert invitation_line("why-late") is None
        assert invitation_line("why-late", machine="") is None
        assert invitation_line("late-orders", order=None) is None

    def test_filled_slot_produces_the_line(self):
        line = invitation_line("why-late", machine="CUT-01")
        assert line and "CUT-01" in line and "Want " in line
        assert invitation_line("data-problems") == INVITATIONS["data-problems"].pattern

    def test_unknown_key_is_silent(self):
        assert invitation_line("order-attributes") is None
        assert invitation_line("inventory") is None
