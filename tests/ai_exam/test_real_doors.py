"""The real-doors reverse-guard + invitation semantics (Session 4A.3b, CU4).

R-AI4(3)(c): every authored invitation offers a door into a LIVE route — its probe
(the proposed follow-up in isolation) must classify to a supported route. A door
into a wall is a defect this fast test forbids. Fast: a lightweight Explainer with
an injected glass_box vocabulary, no solve.
"""
from __future__ import annotations

import pytest

from mre.modules.ask_fallback_copy import (
    INVITATIONS, Invitation, invitation_line, invitation_probe,
)
from mre.modules.evidence_index import EvidenceIndex
from mre.modules.explainer import Explainer


class _FakeStore:
    """A snapshot store that always misses — puts the Explainer in certificate-only
    mode so we can inject a synthetic vocabulary without a solve."""

    def load_snapshot(self, snapshot_id):  # noqa: ANN001
        raise FileNotFoundError(snapshot_id)


@pytest.fixture(scope="module")
def classifier():
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
    def test_every_probe_opens_a_live_route(self, classifier, key):
        inv = INVITATIONS[key]
        probe = invitation_probe(key, **_FACTS)
        assert probe, f"{key}: probe did not fill its slots"
        route, _ = classifier.classify(probe)
        assert route != "unsupported", (
            f"invitation {key!r} offers a door into a wall: "
            f"probe {probe!r} classifies to no route")
        # And it opens the door it DOCUMENTS (the taxonomy naming is pinned so a
        # future route rename cannot silently redirect an invitation).
        assert route == inv.expect_route, (
            f"{key}: probe {probe!r} -> {route}, documented {inv.expect_route}")

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
