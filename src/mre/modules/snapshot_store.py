"""M2 — Snapshot Store.

Directory-per-snapshot of JSON files with provenance sidecar alongside.
Write contract is structural: write_entity accepts entity + provenance together.
No code path sets a value without a corresponding ProvenanceSidecar.

Directory layout:
    <base_dir>/
        <snapshot_id>/
            manifest.json
            entities_<type>.jsonl   (one JSONL file per entity type)
            provenance.jsonl        (all ProvenanceSidecar records)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from pydantic import BaseModel

from mre.contracts.provenance import ProvenanceSidecar

if TYPE_CHECKING:
    from mre.modules.identity_map import IdentityMap

# Fields that are universal conventions (docs/01 §4) — no provenance required.
_UNIVERSAL_FIELDS = frozenset({"id", "snapshot_id", "external_refs"})

UTC = timezone.utc


class WriteContractError(Exception):
    """Raised when write_entity is called without full provenance coverage."""


class SnapshotWriter:
    def __init__(self, snapshot_dir: Path, snapshot_id: str, extend: bool = False) -> None:
        self._dir = snapshot_dir
        self._snapshot_id = snapshot_id
        self._extend = extend  # if True: append entities, skip manifest overwrite
        self._dir.mkdir(parents=True, exist_ok=True)
        # Per-type entity buffers; keyed by entity_type string
        self._entity_buffers: dict[str, list[dict]] = {}
        self._provenance: list[dict] = []

    def write_entity(self, entity: BaseModel, provenance: list[ProvenanceSidecar]) -> None:
        """Write entity and its provenance atomically.

        Every non-universal attribute must have a matching ProvenanceSidecar.
        Raises WriteContractError if any attribute is missing provenance.
        """
        covered = {p.attribute_name for p in provenance}
        required = {
            name for name in type(entity).model_fields
            if name not in _UNIVERSAL_FIELDS
        }
        missing = required - covered
        if missing:
            raise WriteContractError(
                f"Entity {entity.__class__.__name__} id={getattr(entity, 'id', '?')} "
                f"is missing provenance for: {sorted(missing)}"
            )

        entity_type = entity.__class__.__name__.lower()
        entity_dict = json.loads(entity.model_dump_json())
        entity_dict["_entity_type"] = entity_type
        self._entity_buffers.setdefault(entity_type, []).append(entity_dict)

        for p in provenance:
            self._provenance.append(json.loads(p.model_dump_json()))

    def write_identity_map(self, identity_map: "IdentityMap") -> None:
        """Persist the identity map as identity_map.json alongside the snapshot."""
        path = self._dir / "identity_map.json"
        path.write_text(
            json.dumps(identity_map.to_json_dict(), indent=2), encoding="utf-8"
        )

    def finalize(self) -> None:
        """Flush all buffered records to disk and (if not extending) write the manifest."""
        mode = "a" if self._extend else "w"
        for entity_type, records in self._entity_buffers.items():
            path = self._dir / f"entities_{entity_type}.jsonl"
            with open(path, mode, encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec) + "\n")

        prov_path = self._dir / "provenance.jsonl"
        with open(prov_path, mode, encoding="utf-8") as f:
            for p in self._provenance:
                f.write(json.dumps(p) + "\n")

        if not self._extend:
            manifest = {
                "snapshot_id": self._snapshot_id,
                "created_at": datetime.now(UTC).isoformat(),
                "entity_counts": {t: len(recs) for t, recs in self._entity_buffers.items()},
                "provenance_count": len(self._provenance),
            }
            (self._dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )


class SnapshotReader:
    """Read-only access to a finalized snapshot.

    Two views:
    - get_entity / iter_entities: plain-value dicts (no provenance). For M5.
    - get_provenance / iter_provenance_for_entity: narrow trust interface. For M3/M4.
    """

    def __init__(self, snapshot_dir: Path, snapshot_id: str) -> None:
        self._dir = snapshot_dir
        self._snapshot_id = snapshot_id
        self._entities: dict[str, dict] = {}          # entity_id → dict
        self._entities_by_type: dict[str, list[dict]] = {}
        self._provenance_index: dict[str, dict[str, dict]] = {}  # entity_id → attr → record
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        # Load entities
        for path in self._dir.glob("entities_*.jsonl"):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    entity_type = rec.get("_entity_type", path.stem.removeprefix("entities_"))
                    clean = {k: v for k, v in rec.items() if k != "_entity_type"}
                    self._entities[clean["id"]] = clean
                    self._entities_by_type.setdefault(entity_type, []).append(clean)
        # Load provenance
        prov_path = self._dir / "provenance.jsonl"
        if prov_path.exists():
            with open(prov_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    p = json.loads(line)
                    eid = p["entity_id"]
                    attr = p["attribute_name"]
                    self._provenance_index.setdefault(eid, {})[attr] = p
        self._loaded = True

    def get_entity(self, entity_id: str) -> dict | None:
        """Plain-value view — no provenance keys."""
        self._load()
        return self._entities.get(entity_id)

    def iter_entities(self, entity_type: str) -> Iterator[dict]:
        self._load()
        yield from self._entities_by_type.get(entity_type, [])

    def get_provenance(self, entity_id: str, attribute_name: str) -> dict | None:
        """Narrow trust interface: one provenance record by (entity, attribute)."""
        self._load()
        return self._provenance_index.get(entity_id, {}).get(attribute_name)

    def iter_provenance_for_entity(self, entity_id: str) -> Iterator[dict]:
        """All provenance records for an entity. Used by the PROVENANCE_GAP sweep."""
        self._load()
        yield from self._provenance_index.get(entity_id, {}).values()

    def iter_all_provenance(self) -> Iterator[dict]:
        self._load()
        for attr_map in self._provenance_index.values():
            yield from attr_map.values()

    def read_identity_map(self) -> "IdentityMap | None":
        """Load the persisted identity map, or None if not present in this snapshot."""
        path = self._dir / "identity_map.json"
        if not path.exists():
            return None
        from mre.modules.identity_map import IdentityMap
        return IdentityMap.from_json_dict(json.loads(path.read_text(encoding="utf-8")))


class SnapshotStore:
    """Root store. Manages one directory per snapshot."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def begin_snapshot(self, snapshot_id: str) -> SnapshotWriter:
        snap_dir = self._base / snapshot_id
        return SnapshotWriter(snap_dir, snapshot_id)

    def load_snapshot(self, snapshot_id: str) -> SnapshotReader:
        snap_dir = self._base / snapshot_id
        if not snap_dir.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found at {snap_dir}")
        return SnapshotReader(snap_dir, snapshot_id)

    def extend_snapshot(self, snapshot_id: str) -> SnapshotWriter:
        """Return a writer that appends new entity types to an existing snapshot.

        Entity JSONL files are opened in append mode; the manifest is NOT rewritten.
        Use this when the adapter snapshot already exists and a downstream module
        (planner, extractor) needs to add derived entities to the same snapshot.
        """
        snap_dir = self._base / snapshot_id
        if not snap_dir.exists():
            raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found at {snap_dir}")
        return SnapshotWriter(snap_dir, snapshot_id, extend=True)

    def list_snapshots(self) -> list[str]:
        return [d.name for d in self._base.iterdir() if d.is_dir()]
