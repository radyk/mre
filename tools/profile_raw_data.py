#!/usr/bin/env python3
"""Profile every CSV in raw_data/ and write raw_data_profile.md.

Streams each file; never loads the whole file into memory.
Run from the project root:

    python tools/profile_raw_data.py
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "raw_data"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "raw_data_profile.md"

LOW_CARD_LIMIT = 50    # stop tracking distinct values above this per column
SAMPLE_ROWS = 5
TRUNC = 40             # character limit for sample cell values

_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}|^\d{1,2}/\d{1,2}/\d{4}")
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}")
# Column-name suffixes that suggest a join key
_KEY_SUFFIXES = ("no", "code", "id", "ref", "key", "wono")
# Minimum fraction of A's values found in B to report as a join candidate
_OVERLAP_THRESHOLD = 0.05


# ---------------------------------------------------------------------------
# File-level helpers
# ---------------------------------------------------------------------------

def _detect_meta(path: Path) -> tuple[str, str]:
    """Return (encoding, delimiter)."""
    with open(path, "rb") as fh:
        bom = fh.read(3)
    enc = "utf-8-sig" if bom == b"\xef\xbb\xbf" else "utf-8"
    with open(path, encoding=enc) as fh:
        first = fh.readline()
    delim = "," if first.count(",") >= first.count(";") else ";"
    return enc, delim


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _is_date(s: str) -> bool:
    return bool(_DATE_RE.match(s))


def _is_time(s: str) -> bool:
    return bool(_TIME_RE.match(s)) and not _is_date(s)


def _looks_like_key(col: str) -> bool:
    low = col.lower()
    return any(low.endswith(sfx) for sfx in _KEY_SUFFIXES) or low in _KEY_SUFFIXES


def _md_cell(s: str) -> str:
    s = str(s).replace("|", r"\|").replace("\n", " ").replace("\r", "")
    return s[:TRUNC] + "…" if len(s) > TRUNC else s


# ---------------------------------------------------------------------------
# Per-column statistics (streaming)
# ---------------------------------------------------------------------------

class ColStats:
    __slots__ = (
        "name", "total", "blank",
        "numeric_n", "date_n", "time_n",
        "num_min", "num_max", "num_sum", "num_count",
        "date_min", "date_max", "date_examples",
        "distinct",   # dict[str,int] | None (None = exceeded LOW_CARD_LIMIT)
        "value_set",  # set[str] | None — only for key-like columns
    )

    def __init__(self, name: str) -> None:
        self.name = name
        self.total = 0
        self.blank = 0
        self.numeric_n = 0
        self.date_n = 0
        self.time_n = 0
        self.num_min = float("inf")
        self.num_max = float("-inf")
        self.num_sum = 0.0
        self.num_count = 0
        self.date_min: str | None = None
        self.date_max: str | None = None
        self.date_examples: list[str] = []
        self.distinct: dict[str, int] | None = {}
        self.value_set: set[str] | None = set() if _looks_like_key(name) else None

    def observe(self, raw: str) -> None:
        self.total += 1
        if not raw.strip():
            self.blank += 1
            return

        # Distinct-value tracking (stops at LOW_CARD_LIMIT+1)
        if self.distinct is not None:
            self.distinct[raw] = self.distinct.get(raw, 0) + 1
            if len(self.distinct) > LOW_CARD_LIMIT:
                self.distinct = None

        # Unlimited set for key-like columns (used for cross-file join analysis)
        if self.value_set is not None:
            self.value_set.add(raw)

        if _is_numeric(raw):
            self.numeric_n += 1
            v = float(raw)
            self.num_count += 1
            if v < self.num_min:
                self.num_min = v
            if v > self.num_max:
                self.num_max = v
            self.num_sum += v
        elif _is_date(raw):
            self.date_n += 1
            if self.date_min is None or raw < self.date_min:
                self.date_min = raw
            if self.date_max is None or raw > self.date_max:
                self.date_max = raw
            if len(self.date_examples) < 3:
                self.date_examples.append(raw)
        elif _is_time(raw):
            self.time_n += 1

    @property
    def non_blank(self) -> int:
        return self.total - self.blank

    def inferred_type(self) -> str:
        nb = self.non_blank
        if nb == 0:
            return "empty"
        if self.numeric_n / nb > 0.9:
            return "numeric"
        if self.date_n / nb > 0.9:
            return "datetime"
        if self.time_n / nb > 0.9:
            return "time"
        return "string"

    def null_rate(self) -> float:
        return self.blank / self.total if self.total else 0.0

    def num_mean(self) -> float | None:
        return self.num_sum / self.num_count if self.num_count else None

    def effective_value_set(self) -> set[str] | None:
        """Return the best available value set for join analysis.

        Key-named columns (value_set != None) are always included.
        For other low-cardinality columns: only include string-typed ones.
        Numeric low-cardinality columns (0/1 flags, small integers) produce
        accidental overlaps with unrelated numeric data and are excluded.
        """
        if self.value_set is not None:
            return self.value_set
        if (
            self.distinct is not None
            and len(self.distinct) > 1
            and self.inferred_type() == "string"
        ):
            return set(self.distinct.keys())
        return None


# ---------------------------------------------------------------------------
# File profiler
# ---------------------------------------------------------------------------

def profile_file(path: Path) -> dict:
    enc, delim = _detect_meta(path)

    col_stats: list[ColStats] = []
    sample: list[list[str]] = []
    row_count = 0

    with open(path, encoding=enc, newline="") as fh:
        reader = csv.reader(fh, delimiter=delim)
        raw_headers = next(reader)
        headers = [h.lstrip("﻿").strip() for h in raw_headers]
        col_stats = [ColStats(h) for h in headers]

        for row in reader:
            row_count += 1
            # Pad short rows defensively
            while len(row) < len(headers):
                row.append("")
            for i, val in enumerate(row[: len(headers)]):
                col_stats[i].observe(val)
            if len(sample) < SAMPLE_ROWS:
                sample.append([_md_cell(v) for v in row[: len(headers)]])

    return {
        "path": path,
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "row_count": row_count,
        "encoding": enc,
        "delimiter": repr(delim),
        "headers": headers,
        "col_stats": col_stats,
        "sample": sample,
    }


# ---------------------------------------------------------------------------
# Cross-file join candidates
# ---------------------------------------------------------------------------

def cross_file_analysis(profiles: list[dict]) -> list[dict]:
    """Find column pairs across files with high value overlap."""
    # Gather (file, col, value_set) for every column that has a usable set
    candidates = []
    for p in profiles:
        for cs in p["col_stats"]:
            vs = cs.effective_value_set()
            if vs:
                candidates.append({
                    "file": p["name"],
                    "col": cs.name,
                    "values": vs,
                    "non_blank": cs.non_blank,
                })

    results = []
    n = len(candidates)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = candidates[i], candidates[j]
            if a["file"] == b["file"]:
                continue
            overlap = len(a["values"] & b["values"])
            if overlap == 0:
                continue
            rate_a = overlap / len(a["values"]) if a["values"] else 0.0
            rate_b = overlap / len(b["values"]) if b["values"] else 0.0
            if rate_a < _OVERLAP_THRESHOLD and rate_b < _OVERLAP_THRESHOLD:
                continue
            results.append({
                "file_a": a["file"],
                "col_a": a["col"],
                "cnt_a": len(a["values"]),
                "file_b": b["file"],
                "col_b": b["col"],
                "cnt_b": len(b["values"]),
                "overlap": overlap,
                "pct_a_in_b": rate_a,
                "pct_b_in_a": rate_b,
            })

    results.sort(key=lambda r: -(r["pct_a_in_b"] + r["pct_b_in_a"]))
    return results


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.2f} MB"


def render_markdown(profiles: list[dict], cross_refs: list[dict]) -> str:
    out: list[str] = []

    out.append("# Raw Data Profile\n")
    out.append("Generated by `tools/profile_raw_data.py`.  Data directory: `raw_data/`.\n")

    # Summary table
    out.append("## Files at a glance\n")
    out.append("| File | Size | Rows | Cols | Encoding | Delimiter |")
    out.append("|------|------|------|------|----------|-----------|")
    for p in profiles:
        out.append(
            f"| {p['name']} | {_fmt_size(p['size_bytes'])} | {p['row_count']:,} |"
            f" {len(p['headers'])} | {p['encoding']} | {p['delimiter']} |"
        )
    out.append("")

    # -----------------------------------------------------------------------
    # Per-file sections
    # -----------------------------------------------------------------------
    for p in profiles:
        out.append(f"---\n\n## {p['name']}\n")
        out.append(f"**{_fmt_size(p['size_bytes'])}  ·  {p['row_count']:,} rows  ·"
                   f"  {len(p['headers'])} columns  ·  {p['encoding']}  ·  delimiter {p['delimiter']}**\n")

        # Column table
        out.append("### Columns\n")
        out.append("| # | Column | Type | Null % | Stats |")
        out.append("|---|--------|------|--------|-------|")
        for idx, cs in enumerate(p["col_stats"], 1):
            t = cs.inferred_type()
            null_pct = f"{cs.null_rate() * 100:.1f}%"
            notes: list[str] = []
            if t == "numeric" and cs.num_count > 0:
                mean = cs.num_mean()
                notes.append(
                    f"min={cs.num_min:g}  max={cs.num_max:g}  mean={mean:.1f}"
                )
            elif t == "datetime":
                notes.append(f"min=`{cs.date_min}`  max=`{cs.date_max}`")
            if cs.distinct is not None:
                notes.append(f"{len(cs.distinct)} distinct")
            out.append(
                f"| {idx} | `{cs.name}` | {t} | {null_pct} | {'; '.join(notes)} |"
            )
        out.append("")

        # Sample rows
        out.append("### Sample rows (first 5)\n")
        header_row = "| " + " | ".join(p["headers"]) + " |"
        sep_row = "| " + " | ".join(["---"] * len(p["headers"])) + " |"
        out.append(header_row)
        out.append(sep_row)
        for row in p["sample"]:
            out.append("| " + " | ".join(row) + " |")
        out.append("")

        # Low-cardinality columns
        low_card = [
            cs for cs in p["col_stats"]
            if cs.distinct is not None and 1 < len(cs.distinct) <= LOW_CARD_LIMIT
        ]
        if low_card:
            out.append("### Low-cardinality columns\n")
            for cs in low_card:
                sorted_vals = sorted(cs.distinct.items(), key=lambda x: -x[1])
                out.append(f"**`{cs.name}`** — {len(cs.distinct)} distinct values:\n")
                val_parts = [f"`{_md_cell(k)}` ({v:,})" for k, v in sorted_vals]
                out.append(",  ".join(val_parts))
                out.append("")

        # Date columns
        date_cols = [cs for cs in p["col_stats"] if cs.inferred_type() == "datetime"]
        if date_cols:
            out.append("### Date / datetime columns\n")
            out.append("| Column | Min (raw) | Max (raw) | Sample raw values |")
            out.append("|--------|-----------|-----------|-------------------|")
            for cs in date_cols:
                examples = "  ·  ".join(f"`{e}`" for e in cs.date_examples)
                out.append(
                    f"| `{cs.name}` | `{cs.date_min}` | `{cs.date_max}` | {examples} |"
                )
            out.append("")

    # -----------------------------------------------------------------------
    # Cross-file join candidates
    # -----------------------------------------------------------------------
    out.append("---\n\n## Cross-file join candidates\n")
    out.append(
        f"Columns whose name ends in a key suffix (`{'`, `'.join(_KEY_SUFFIXES)}`) "
        f"or that stayed under {LOW_CARD_LIMIT} distinct values.  "
        f"Threshold: ≥{int(_OVERLAP_THRESHOLD * 100)}% of one side's distinct values "
        f"appear in the other.\n"
    )
    if cross_refs:
        out.append(
            "| File A | Column A | Distinct A | File B | Column B | Distinct B |"
            " A→B % | B→A % | Overlap |"
        )
        out.append(
            "|--------|----------|-----------|--------|----------|-----------|"
            "-------|-------|---------|"
        )
        for r in cross_refs:
            out.append(
                f"| {r['file_a']} | `{r['col_a']}` | {r['cnt_a']:,} |"
                f" {r['file_b']} | `{r['col_b']}` | {r['cnt_b']:,} |"
                f" {r['pct_a_in_b']*100:.0f}% | {r['pct_b_in_a']*100:.0f}% |"
                f" {r['overlap']:,} |"
            )
        out.append("")
        out.append("### Interpretation notes\n")
        # Emit a brief note for the highest-overlap pairs
        seen: set[tuple] = set()
        for r in cross_refs[:10]:
            key = tuple(sorted([(r["file_a"], r["col_a"]), (r["file_b"], r["col_b"])]))
            if key in seen:
                continue
            seen.add(key)
            if r["pct_a_in_b"] >= 0.95 and r["pct_b_in_a"] >= 0.95:
                out.append(
                    f"- **`{r['col_a']}`** ({r['file_a']}) ↔ **`{r['col_b']}`**"
                    f" ({r['file_b']}): near-complete bidirectional match —"
                    f" likely the same entity viewed from two tables."
                )
            elif r["pct_a_in_b"] >= 0.90:
                out.append(
                    f"- **`{r['col_a']}`** in {r['file_a']} → **`{r['col_b']}`**"
                    f" in {r['file_b']}: {r['pct_a_in_b']*100:.0f}% of A resolves in B —"
                    f" strong FK candidate."
                )
            elif r["pct_b_in_a"] >= 0.90:
                out.append(
                    f"- **`{r['col_b']}`** in {r['file_b']} → **`{r['col_a']}`**"
                    f" in {r['file_a']}: {r['pct_b_in_a']*100:.0f}% of B resolves in A —"
                    f" strong FK candidate."
                )
            else:
                out.append(
                    f"- **`{r['col_a']}`** ({r['file_a']}) / **`{r['col_b']}`**"
                    f" ({r['file_b']}): partial overlap"
                    f" (A→B {r['pct_a_in_b']*100:.0f}%, B→A {r['pct_b_in_a']*100:.0f}%)."
                )
        out.append("")
    else:
        out.append("No candidates found above the overlap threshold.\n")

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not RAW_DATA_DIR.is_dir():
        print(f"ERROR: {RAW_DATA_DIR} not found.  Run from the project root.")
        return

    csv_files = sorted(RAW_DATA_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {RAW_DATA_DIR}")
        return

    print(f"Profiling {len(csv_files)} file(s) in {RAW_DATA_DIR} …")
    profiles = []
    for path in csv_files:
        print(f"  {path.name} ({_fmt_size(path.stat().st_size)}) …", end="  ", flush=True)
        p = profile_file(path)
        profiles.append(p)
        print(f"{p['row_count']:,} rows, {len(p['headers'])} columns")

    print("Computing cross-file join candidates …")
    cross_refs = cross_file_analysis(profiles)
    print(f"  {len(cross_refs)} candidate pair(s) above {int(_OVERLAP_THRESHOLD*100)}% threshold")

    print(f"Writing {OUTPUT_PATH} …")
    md = render_markdown(profiles, cross_refs)
    OUTPUT_PATH.write_text(md, encoding="utf-8")
    size = OUTPUT_PATH.stat().st_size
    print(f"Done — {_fmt_size(size)} written.")


if __name__ == "__main__":
    main()
