"""The question ledger (R-AI1(d), Session 4A.1 CU3).

An append-only JSONL stream of every question asked of the AI layer — its OWN
stream, never the schedule evidence store. Records are ``QuestionLedgerEntry``
(shape defined in ``contracts/``); this module only appends and reads them.

Three consumers:
  1. The ``/ask`` path writes one entry per question (routed or refused).
  2. The dev-panel view (cockpit, DEV-gated) reads ``refusal_clusters()``.
  3. The meta-route "what questions couldn't you answer recently?" reads
     ``recent(...)`` — the ledger answering questions about itself, per R-AI1(d).

Rephrase linkage (the free labeled data): when a routed question follows a
REFUSED one in the same session within ``REPHRASE_WINDOW_S``, the routed entry's
``rephrase_of`` points at that refusal — a (failed phrasing → phrasing that
worked) pair the human-curated improvement loop consumes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mre.contracts.question_ledger import QuestionLedgerEntry

# A rephrase is a refusal followed by a routed question in the SAME session
# within this window. Wide enough to cover a planner re-typing after reading the
# refusal menu; short enough not to link unrelated later asks.
REPHRASE_WINDOW_S = 180.0


class QuestionLedger:
    """Append-only JSONL ledger of asked questions."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        verbatim_question: str,
        resolved_question: str,
        route: str,
        *,
        source: str = "deterministic",
        confidence: Optional[float] = None,
        answer_register: Optional[str] = None,
        schedule_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> QuestionLedgerEntry:
        """Append one entry. When ``route`` is a real taxonomy route (not a
        refusal sentinel) and the same session refused a question inside the
        rephrase window, link this entry to that refusal (free labeled data)."""
        entry = QuestionLedgerEntry(
            entry_id=str(uuid.uuid4()),
            verbatim_question=verbatim_question,
            resolved_question=resolved_question,
            route=route,
            source=source,
            confidence=confidence,
            answer_register=answer_register,
            schedule_id=schedule_id,
            session_id=session_id,
        )
        if not entry.refused and session_id:
            entry.rephrase_of = self._recent_refusal_id(session_id, entry.ts)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")
        return entry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def all_entries(self) -> list[QuestionLedgerEntry]:
        if not self._path.exists():
            return []
        out: list[QuestionLedgerEntry] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(QuestionLedgerEntry.model_validate_json(line))
            except Exception:
                # A malformed line never breaks the read path; the ledger is
                # advisory, not load-bearing.
                continue
        return out

    def recent(self, limit: int = 20) -> list[QuestionLedgerEntry]:
        """The most recent entries, newest first."""
        entries = sorted(self.all_entries(), key=lambda e: e.ts, reverse=True)
        return entries[:limit]

    def recent_refusals(self, limit: int = 20) -> list[QuestionLedgerEntry]:
        """The most recent REFUSED / NEAR_MISS / CLARIFY entries, newest first —
        the meta-route's substance (R-AI1(d))."""
        refused = [e for e in self.all_entries() if e.refused]
        refused.sort(key=lambda e: e.ts, reverse=True)
        return refused[:limit]

    def refusal_clusters(self, limit: int = 20) -> list[dict]:
        """Refusals grouped by a normalized form of the resolved question, ranked
        by frequency — the dev-panel view. Each cluster carries an example
        verbatim question and whether any rephrase in the ledger later succeeded
        for it (a curation signal)."""
        entries = self.all_entries()
        refusals = [e for e in entries if e.refused]
        by_id = {e.entry_id: e for e in entries}
        # entry_ids of refusals that a later routed entry rephrased from.
        rephrased_from = {
            e.rephrase_of for e in entries if e.rephrase_of is not None
        }
        buckets: dict[str, list[QuestionLedgerEntry]] = {}
        for e in refusals:
            key = _normalize(e.resolved_question)
            buckets.setdefault(key, []).append(e)
        clusters = []
        for key, group in buckets.items():
            group.sort(key=lambda e: e.ts, reverse=True)
            clusters.append({
                "normalized": key,
                "count": len(group),
                "example": group[0].verbatim_question,
                "route": group[0].route,
                "last_ts": group[0].ts.isoformat(),
                "any_rephrased": any(g.entry_id in rephrased_from for g in group),
            })
        clusters.sort(key=lambda c: (-c["count"], c["normalized"]))
        return clusters[:limit]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _recent_refusal_id(self, session_id: str, now: datetime) -> Optional[str]:
        """The entry_id of the most recent refusal in ``session_id`` within the
        rephrase window before ``now`` — or None."""
        best: Optional[QuestionLedgerEntry] = None
        for e in self.all_entries():
            if e.session_id != session_id or not e.refused:
                continue
            dt = (now - _aware(e.ts)).total_seconds()
            if 0 <= dt <= REPHRASE_WINDOW_S:
                if best is None or e.ts > best.ts:
                    best = e
        return best.entry_id if best else None


def _normalize(text: str) -> str:
    """Cluster key: lowercased, punctuation-stripped, whitespace-collapsed."""
    keep = [c.lower() if (c.isalnum() or c.isspace()) else " " for c in text]
    return " ".join("".join(keep).split())


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
