"""THE CALIBRATION CEREMONY — python -m mre.calibrate (Session 4B.29, R-CAL1).

4B.26 measured one board's knee and the temptation was to ship its numbers as
product defaults. That is the seed-44 mistake at the configuration level: 10.0
deterministic units is ONE BOARD's calibration, not a law. What generalizes is
the PROCEDURE, and this is the procedure — run per plant, at onboarding, its
output offered to a human and then declared on every certificate.

    python -m mre.calibrate <submission_dir> [--out DIR] [--windows 10 14]
                            [--budgets 3 6 10 15] [--seeds 42 43 44 45 46]
                            [--reference-date 2026-01-05] [--frozen-days 1]
                            [--tolerance-pct 1.0] [--no-resume] [--save]

    python -m mre.calibrate --show <plant_key> [--data-root DIR]
    python -m mre.calibrate --install <profile.json> [--data-root DIR]
    python -m mre.calibrate --accept <plant_key> --by "Daryn Radke"

WHAT IT COSTS IS PRINTED BEFORE IT SPENDS ANYTHING, and the profile records
the actual beside the projection. Resumable: re-run the same command after an
interruption and every cell already on disk is re-used, named as such.

NOTHING IS AUTO-APPLIED. The run ends with an OFFER; `--accept` is the
signature (rule 2), and only an accepted profile reaches a solve.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _utf8_stdout() -> None:
    """A Windows console defaults to cp1252 and this report contains em dashes.
    A ceremony that dies on its own punctuation is not a ceremony."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — a stream that cannot be reconfigured
            pass


def _parse_ref(raw):
    if not raw:
        return None
    d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _emit(ev: dict) -> None:
    k = ev.get("kind")
    if k == "plan":
        reused = ev["cells_reused"]
        print(f"grid: {ev['cells_total']} cells "
              f"({reused} already measured, {ev['cells_pending']} to run)")
        secs = ev["projected_wall_s"]
        print(f"PROJECTED WALL: {secs:.0f}s = {secs / 60.0:.1f} min "
              f"(forecast from 55 s/deterministic unit; the profile records "
              f"the actual)")
        if reused:
            print(f"  {reused} cell(s) re-used from an earlier run of this "
                  f"ceremony — solver output, never authored (rule 1)")
    elif k == "plant":
        print(f"plant prepared in {ev['prepare_s']:.1f}s: {ev['demands']} "
              f"demands, {ev['operations']} operations, {ev['resources']} "
              f"resources")
    elif k == "cell_start":
        print(f"  [{ev['i']}/{ev['n']}] w{ev['window_days']} "
              f"{ev['det_total']:g}u seed {ev['seed']} ... ", end="", flush=True)
    elif k == "cell":
        got = (f"${ev['ledger_total']:,.2f}" if ev["publishable"]
               else f"{ev['status'] or 'EMPTY'} (no board)")
        print(f"{got}  [{ev['wall_s']:.0f}s]", flush=True)


def cmd_show(plant_key: str, data_root: Path) -> int:
    from mre.modules.calibration import ProfileStore, render_profile

    prof = ProfileStore(data_root).load(plant_key)
    if prof is None:
        print(f"no calibration profile for {plant_key} under {data_root}")
        return 1
    print(render_profile(prof))
    if not prof.digest_ok():
        print("\nREFUSED: this profile does not match the digest of its own "
              "grid — it was edited after it was measured (R-CAL1 rule 1).")
        return 2
    return 0


def cmd_install(profile_path: Path, data_root: Path) -> int:
    """Place an ALREADY-MEASURED profile where a solve can find it.

    `--save` is reachable only from inside a measuring run, so a profile that
    was measured elsewhere and committed (docs/calibration/) had no way into a
    data root but a hand-written script — which is precisely the shape rule (1)
    exists to refuse. This is that path, and it verifies the seal on the way in:
    an edited grid is refused HERE as well as at read and at accept.

    Installing is NOT accepting. The profile lands inert, exactly as `--save`
    leaves it, and `--accept` remains the only signature (rule 2).
    """
    from mre.contracts.calibration import CalibrationProfile
    from mre.modules.calibration import ProfileStore, render_profile

    if not profile_path.exists():
        print(f"no such profile: {profile_path}")
        return 1
    try:
        prof = CalibrationProfile.model_validate_json(
            profile_path.read_text("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: {profile_path} is not a readable calibration profile "
              f"({type(exc).__name__}: {exc})")
        return 2
    if not prof.digest_ok():
        print("REFUSED: this profile does not match the digest of its own grid "
              "— it was edited after it was measured (R-CAL1 rule 1).")
        return 2
    # An accepted profile arriving from a file would carry a signature nobody
    # gave in THIS data root. Strip it: installing is a copy, never a consent.
    inert = prof.model_copy(update={
        "accepted": False, "accepted_by": "", "accepted_at": None})
    p = ProfileStore(data_root).save(inert)
    print(render_profile(inert))
    print(f"\ninstalled at {p}")
    print("THIS IS AN OFFER, NOT A SETTING (R-CAL1 rule 2). To apply it:")
    print(f'  python -m mre.calibrate --accept "{prof.plant_key}" '
          f'--by "<your name>"')
    return 0


def cmd_accept(plant_key: str, data_root: Path, by: str) -> int:
    from mre.modules.calibration import ProfileStore, render_profile

    try:
        live = ProfileStore(data_root).accept(plant_key, by=by)
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: {exc}")
        return 2
    print(render_profile(live))
    print(f"\nACCEPTED by {by}. Every solve of this plant now declares these "
          f"coefficients on its certificate (rule 3).")
    return 0


def cmd_run(args) -> int:
    from mre.modules.calibration import (
        DEFAULT_BUDGETS, DEFAULT_SEEDS, MultiFacilitySubmission, ProfileStore,
        build_profile, load_cells, plant_key_for, render_profile, run_grid,
    )

    submission = Path(args.submission).resolve()
    if not (submission / "manifest.json").exists():
        print(f"not a submission directory (no manifest.json): {submission}")
        return 1
    try:
        key, facility = plant_key_for(submission)
    except MultiFacilitySubmission as exc:
        print(f"REFUSED: {exc}")
        return 2

    out = Path(args.out).resolve() if args.out else (
        Path("_calibration") / key.replace("::", "_"))
    windows = args.windows or [args.window or 10]
    budgets = args.budgets or list(DEFAULT_BUDGETS)
    seeds = args.seeds or list(DEFAULT_SEEDS)
    ref = _parse_ref(args.reference_date)

    print(f"CALIBRATING {key}  (facility {facility})")
    print(f"  submission {submission}")
    print(f"  out        {out}")
    print(f"  windows    {windows}   budgets {budgets}   seeds {seeds}")
    print(f"  frozen     {args.frozen_days}   reference {ref or '(manifest)'}")
    print()

    # COST HONESTY, and the projection has to be the SAME SET as the actual or
    # the pair is decoration: a run that re-used twenty cells and measured five
    # must not print a forecast for twenty-five beside a wall for five.
    plan_seen: dict = {}

    def _tap(ev):
        if ev.get("kind") == "plan":
            plan_seen.update(ev)
        _emit(ev)

    t0 = time.monotonic()
    cells = run_grid(submission, out, windows=windows, budgets=budgets,
                     seeds=seeds, frozen_days=args.frozen_days,
                     reference_date=ref, resume=not args.no_resume,
                     on_event=_tap)
    actual = round(time.monotonic() - t0, 1)
    projected = plan_seen.get("projected_wall_s", 0.0)
    reused = plan_seen.get("cells_reused", 0)
    prefer = args.prefer_window if args.prefer_window else min(windows)
    # projected/actual are DERIVED from the grid (the cells this ceremony
    # measured), so a profile rebuilt from its own cells reports the same pair.
    prof = build_profile(submission, cells, seeds=seeds, prefer_window=prefer,
                         reference_date=ref, tolerance_pct=args.tolerance_pct,
                         notes=args.notes or "")
    print()
    print(render_profile(prof))
    print()
    print(f"WALL: projected {projected:.0f}s for the {plan_seen.get('cells_pending', 0)} "
          f"cell(s) this run had to measure, actually spent {actual:.0f}s "
          f"({reused} cell(s) re-used; {len(load_cells(out))} on disk now)")

    written = out / "profile.json"
    written.write_text(prof.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nprofile written to {written}")
    if args.save:
        p = ProfileStore(args.data_root).save(prof)
        print(f"stored at {p}")
        print(f"THIS IS AN OFFER, NOT A SETTING (R-CAL1 rule 2). To apply it:")
        print(f'  python -m mre.calibrate --accept "{key}" --by "<your name>"')
    else:
        print("NOT stored. Re-run with --save to place it where a solve can "
              "find it; it is still inert until --accept (rule 2).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m mre.calibrate",
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("submission", nargs="?", help="an IDS submission directory")
    ap.add_argument("--out", help="where cells.jsonl and profile.json go")
    ap.add_argument("--data-root", default="./_data",
                    help="the data root whose calibration/ store is used")
    ap.add_argument("--windows", nargs="+", type=int)
    ap.add_argument("--window", type=int, help="shorthand for a single window")
    ap.add_argument("--prefer-window", type=int,
                    help="the plant's own declared window; the recommendation "
                         "prefers it and names it if it is unreachable")
    ap.add_argument("--budgets", nargs="+", type=float)
    ap.add_argument("--seeds", nargs="+", type=int)
    ap.add_argument("--frozen-days", type=int, default=1)
    ap.add_argument("--reference-date")
    ap.add_argument("--tolerance-pct", type=float, default=1.0)
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--save", action="store_true",
                    help="store the profile where solves look for it "
                         "(still inert until --accept)")
    ap.add_argument("--notes", default="")
    ap.add_argument("--show", metavar="PLANT_KEY")
    ap.add_argument("--install", metavar="PROFILE_JSON",
                    help="place an already-measured profile.json into the data "
                         "root's store (inert until --accept)")
    ap.add_argument("--accept", metavar="PLANT_KEY")
    ap.add_argument("--by", default="", help="who is accepting (rule 2)")
    a = ap.parse_args(argv)
    _utf8_stdout()

    root = Path(a.data_root)
    if a.show:
        return cmd_show(a.show, root)
    if a.install:
        return cmd_install(Path(a.install), root)
    if a.accept:
        if not a.by.strip():
            print("--accept needs --by: rule (2) is a signature, not a flag")
            return 2
        return cmd_accept(a.accept, root, a.by)
    if not a.submission:
        ap.print_help()
        return 1
    return cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())
