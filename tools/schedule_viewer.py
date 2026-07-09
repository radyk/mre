"""schedule_viewer.py — standalone schedule Gantt chart.

Usage:
    python tools/schedule_viewer.py schedule.csv [options]

Options:
    --out PATH          output HTML file (default: schedule.html next to input)
    --snapshot PATH     snapshot directory to join lateness coloring
    --title TEXT        chart title
    --reference-date    ISO date string to draw a vertical reference line
                        (inferred from snapshot run context if not given)
    --color-by          'facility' (default) or 'lateness'

Output: a single self-contained HTML file (CDN plotly.js, no server needed).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _load_schedule(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_lateness(snapshot_dir: Path) -> dict[str, str]:
    """Return work_order → lateness_class ('late'|'on_time'|'early')."""
    so_path = snapshot_dir / "entities_serviceoutcome.jsonl"
    dem_path = snapshot_dir / "entities_demand.jsonl"
    if not so_path.exists() or not dem_path.exists():
        return {}

    # demand_id → work_orders (may be multiple WOs per demand)
    dem_wos: dict[str, list[str]] = {}
    with open(dem_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            wos = d.get("external_refs", {}).get("work_orders", [])
            if isinstance(wos, str):
                wos = [wos]
            dem_wos[d["id"]] = wos

    # demand_id → lateness class from service outcomes
    wo_class: dict[str, str] = {}
    with open(so_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                so = json.loads(line)
            except json.JSONDecodeError:
                continue
            lat = so.get("lateness_minutes", 0)
            if lat is None:
                lat = 0
            cls = "late" if lat > 0 else ("early" if lat < 0 else "on_time")
            for dem_id in [so.get("demand_ref", "")]:
                for wo in dem_wos.get(dem_id, []):
                    wo_class[wo] = cls

    return wo_class


def _infer_reference_date(snapshot_dir: Path) -> str | None:
    """Try to read reference_date from a run context record in the snapshot dir."""
    runs_dir = snapshot_dir.parent / "runs"
    if not runs_dir.exists():
        return None
    for jsonl in sorted(runs_dir.glob("*.jsonl"), reverse=True):
        try:
            with open(jsonl, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("record_type") == "run_context":
                        ref = rec.get("config", {}).get("reference_date")
                        if ref:
                            return ref
        except OSError:
            continue
    return None


def build_figure(
    rows: list[dict],
    color_by: str,
    wo_lateness: dict[str, str],
    reference_date_str: str | None,
    title: str,
):
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd

    # ------------------------------------------------------------------ parse
    records = []
    for r in rows:
        machine = r.get("machine", "unknown")
        facility = machine.split("/")[0] if "/" in machine else machine
        resource = machine.split("/")[1] if "/" in machine else machine

        # lateness: use the first WO in the work_orders field
        wos_str = r.get("work_orders", "")
        first_wo = wos_str.split(",")[0].strip()
        lat_class = wo_lateness.get(first_wo, "unknown")

        try:
            start = _parse_dt(r["start"])
            end = _parse_dt(r["end"])
        except (KeyError, ValueError):
            continue

        dur = int(r.get("duration_min", 0))
        chunk_seq = r.get("chunk_seq", "")
        op_label = r.get("op_seq", "")
        if chunk_seq:
            op_label = f"{op_label} (chunk {chunk_seq})"
        records.append({
            "machine": machine,
            "facility": facility,
            "resource": resource,
            "start": start,
            "end": end,
            "work_orders": wos_str,
            "op_seq": op_label,
            "duration_min": dur,
            "lateness_class": lat_class,
            "color_key": facility if color_by == "facility" else lat_class,
        })

    if not records:
        print("No valid rows to plot.", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(records)

    # Sort: facility first, then resource name, so machines cluster visually
    df = df.sort_values(["facility", "resource"])

    # ----------------------------------------------------------------- colors
    if color_by == "facility":
        facilities = sorted(df["facility"].unique())
        palette = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel
        color_map = {f: palette[i % len(palette)] for i, f in enumerate(facilities)}
    else:
        color_map = {
            "late":     "#e74c3c",
            "on_time":  "#2ecc71",
            "early":    "#3498db",
            "unknown":  "#bdc3c7",
        }

    df["color"] = df["color_key"].map(color_map).fillna("#bdc3c7")

    # ----------------------------------------------------------------- figure
    # Build as a scatter plot on a Gantt-like layout for WebGL performance.
    # px.timeline works well up to ~15K bars; no per-bar text annotations.
    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="machine",
        color="color_key",
        color_discrete_map=color_map,
        hover_data={
            "work_orders": True,
            "op_seq": True,
            "duration_min": True,
            "facility": True,
            "start": False,
            "end": False,
            "color_key": False,
        },
        title=title,
        labels={"color_key": "Facility" if color_by == "facility" else "Status"},
    )

    fig.update_layout(
        height=max(600, 20 * df["machine"].nunique()),
        plot_bgcolor="#1e1e2e",
        paper_bgcolor="#12121c",
        font_color="#cdd6f4",
        legend=dict(
            bgcolor="#1e1e2e",
            bordercolor="#45475a",
            borderwidth=1,
        ),
        xaxis=dict(
            gridcolor="#313244",
            showgrid=True,
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            gridcolor="#313244",
            tickfont=dict(size=9),
            autorange="reversed",
        ),
        title_font_size=15,
    )

    # ---- reference-date vertical line
    if reference_date_str:
        try:
            ref_dt = _parse_dt(reference_date_str)
            fig.add_vline(
                x=ref_dt.timestamp() * 1000,  # plotly timeline uses ms epoch
                line_color="#f5c2e7",
                line_dash="dash",
                line_width=2,
                annotation_text="ref date",
                annotation_font_color="#f5c2e7",
                annotation_font_size=10,
            )
        except ValueError:
            print(f"Warning: cannot parse reference-date '{reference_date_str}'",
                  file=sys.stderr)

    # ---- color-by toggle buttons
    if color_by == "facility" and wo_lateness:
        # Build alternative lateness-colored traces
        lat_colors = {
            "late": "#e74c3c", "on_time": "#2ecc71",
            "early": "#3498db", "unknown": "#bdc3c7",
        }
        alt_colors = [lat_colors.get(df["lateness_class"].iloc[i], "#bdc3c7")
                      for i in range(len(df))]
        # Use updatemenus button to swap marker colors
        fig.update_layout(
            updatemenus=[dict(
                type="buttons",
                direction="left",
                x=0.0, y=1.08, xanchor="left",
                showactive=True,
                bgcolor="#313244",
                font=dict(color="#cdd6f4"),
                buttons=[
                    dict(label="Color: Facility",
                         method="restyle",
                         args=[{"marker.color": [df["color"].tolist()]}]),
                    dict(label="Color: Late/Early",
                         method="restyle",
                         args=[{"marker.color": [alt_colors]}]),
                ],
            )]
        )

    return fig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render schedule.csv as a self-contained Gantt HTML."
    )
    parser.add_argument("csv", help="Path to schedule.csv")
    parser.add_argument("--out", help="Output HTML path (default: <csv>.html)")
    parser.add_argument("--snapshot", help="Snapshot directory for lateness join")
    parser.add_argument("--title", default="Production Schedule", help="Chart title")
    parser.add_argument("--reference-date", dest="reference_date",
                        help="ISO date for reference line (e.g. 2025-03-22)")
    parser.add_argument("--color-by", dest="color_by",
                        choices=["facility", "lateness"], default="facility",
                        help="Bar color scheme")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else csv_path.with_suffix(".html")

    rows = _load_schedule(csv_path)
    print(f"Loaded {len(rows)} rows from {csv_path}")

    wo_lateness: dict[str, str] = {}
    reference_date_str = args.reference_date
    if args.snapshot:
        snap_dir = Path(args.snapshot)
        wo_lateness = _load_lateness(snap_dir)
        if wo_lateness:
            print(f"Joined lateness for {len(wo_lateness)} work orders")
        if not reference_date_str:
            reference_date_str = _infer_reference_date(snap_dir)

    color_by = args.color_by
    if color_by == "lateness" and not wo_lateness:
        print("Warning: --color-by lateness requested but no snapshot loaded; "
              "defaulting to facility coloring.", file=sys.stderr)
        color_by = "facility"

    fig = build_figure(rows, color_by, wo_lateness, reference_date_str, args.title)

    fig.write_html(
        str(out_path),
        include_plotlyjs="cdn",
        full_html=True,
    )
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
