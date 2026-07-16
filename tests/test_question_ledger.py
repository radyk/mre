"""The question ledger (Session 4A.1 CU3, R-AI1(d)).

Every ask is a logged fact. Unanswerable ones are the labeled data the
improvement loop consumes: a refusal followed by a successful rephrase in the
same session is linked, and refusals cluster by frequency for the dev-panel view.
The ledger is its OWN stream — never the schedule evidence store.
"""
from __future__ import annotations

import time

from mre.contracts.question_ledger import QuestionLedgerEntry
from mre.modules.question_ledger import QuestionLedger


def _ledger(tmp_path):
    return QuestionLedger(tmp_path / "ledger" / "questions.jsonl")


def test_record_and_read_roundtrip(tmp_path):
    led = _ledger(tmp_path)
    led.record("why is WO-2001 late?", "why is WO-2001 late?", "late-order")
    entries = led.all_entries()
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, QuestionLedgerEntry)
    assert e.route == "late-order"
    assert e.refused is False


def test_refusal_is_flagged(tmp_path):
    led = _ledger(tmp_path)
    led.record("what's the vibe", "what's the vibe", "REFUSED", source="none")
    e = led.all_entries()[0]
    assert e.refused is True


def test_rephrase_links_refusal_to_later_success(tmp_path):
    led = _ledger(tmp_path)
    refusal = led.record("what's cooking on the big press", "what's cooking on the big press",
                         "REFUSED", source="none", session_id="s1")
    routed = led.record("what's running on M-GEAR-01?", "what's running on M-GEAR-01?",
                        "machine-schedule", source="deterministic", session_id="s1")
    assert routed.rephrase_of == refusal.entry_id


def test_rephrase_does_not_cross_sessions(tmp_path):
    led = _ledger(tmp_path)
    led.record("mystery q", "mystery q", "REFUSED", source="none", session_id="s1")
    routed = led.record("what's running on M-GEAR-01?", "what's running on M-GEAR-01?",
                        "machine-schedule", session_id="s2")
    assert routed.rephrase_of is None


def test_refusal_clusters_rank_by_frequency(tmp_path):
    led = _ledger(tmp_path)
    for _ in range(3):
        led.record("what's the ETA on castings?", "what's the ETA on castings?", "REFUSED")
    led.record("is batching worth it?", "is batching worth it?", "REFUSED")
    led.record("why is WO-2001 late?", "why is WO-2001 late?", "late-order")  # routed
    clusters = led.refusal_clusters()
    assert clusters[0]["count"] == 3
    assert "eta" in clusters[0]["normalized"]
    # the routed question is not a refusal → not a cluster
    assert all("wo 2001" not in c["normalized"] for c in clusters)


def test_cluster_marks_rephrased(tmp_path):
    led = _ledger(tmp_path)
    ref = led.record("what's cooking on the big press", "what's cooking on the big press",
                     "REFUSED", session_id="s1")
    led.record("what's running on M-GEAR-01?", "what's running on M-GEAR-01?",
               "machine-schedule", session_id="s1")
    clusters = led.refusal_clusters()
    target = [c for c in clusters if "big press" in c["normalized"]][0]
    assert target["any_rephrased"] is True


def test_recent_refusals_newest_first(tmp_path):
    led = _ledger(tmp_path)
    led.record("first", "first", "REFUSED")
    time.sleep(0.01)
    led.record("second", "second", "REFUSED")
    recent = led.recent_refusals()
    assert recent[0].verbatim_question == "second"


def test_malformed_line_is_skipped_not_fatal(tmp_path):
    led = _ledger(tmp_path)
    led.record("ok", "ok", "late-orders")
    with led._path.open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
    # the read path tolerates the junk line
    assert len(led.all_entries()) == 1
