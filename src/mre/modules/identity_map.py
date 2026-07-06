"""Identity map: bidirectional (system, type, value) ↔ canonical_id.

Standalone so both the adapter (writer) and snapshot store (reader) can
import it without a circular dependency.
"""
from __future__ import annotations

from typing import Optional

from mre.contracts.entities import ExternalRef


class IdentityMap:
    """Bidirectional map: (system, type, value) ↔ canonical_id."""

    def __init__(self) -> None:
        self._to_canonical: dict[tuple[str, str, str], str] = {}
        self._from_canonical: dict[str, list[tuple[str, str, str]]] = {}

    def register(self, canonical_id: str, system: str, ref_type: str, value: str) -> None:
        key = (system, ref_type, value)
        self._to_canonical[key] = canonical_id
        self._from_canonical.setdefault(canonical_id, []).append(key)

    def resolve(self, system: str, ref_type: str, value: str) -> Optional[str]:
        return self._to_canonical.get((system, ref_type, value))

    def external_refs(self, canonical_id: str) -> list[ExternalRef]:
        return [
            ExternalRef(system=s, type=t, value=v)
            for s, t, v in self._from_canonical.get(canonical_id, [])
        ]

    def to_json_dict(self) -> dict:
        return {
            "entries": [
                {"system": s, "type": t, "value": v, "canonical_id": cid}
                for (s, t, v), cid in self._to_canonical.items()
            ]
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "IdentityMap":
        m = cls()
        for entry in data.get("entries", []):
            m.register(entry["canonical_id"], entry["system"], entry["type"], entry["value"])
        return m
