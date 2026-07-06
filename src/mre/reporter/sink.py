"""Append-only per-run JSONL stream (L3 sink).

Crash-safe: every record is flushed to disk immediately after write.
The file is readable at any point during the run — even after a crash.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class JsonlSink:
    def __init__(self, run_id: str, directory: Path) -> None:
        self.run_id = run_id
        self.path = Path(directory) / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "a", encoding="utf-8")

    def write(self, record: BaseModel) -> None:
        line = record.model_dump_json()
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def read_all(self) -> list[dict]:
        """Read all records from the JSONL file. Flushes first."""
        self._file.flush()
        records: list[dict] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
