"""M3 — what does R-TG6 (ii)'s floor read COST at demo density?

Session 4A teaching-graft (e2). (e) §8(d) names this as unmeasured: the mobility
check calls `Explainer.order_mobility_verdicts` once per named order (capped at
3), and each verdict is a blocker analysis. On the fenced world that is
milliseconds; on a 386-bar board nobody had looked.

This measures it on both worlds, three repetitions each, and reports the spread.
It changes nothing regardless of the number — the brief's rule is that M3
MEASURES and the docket decides.

    python tools/spikes/teaching_graft_e2/m3_floor_read_cost.py

Nothing is minted: both worlds are opened read-only.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from mre.ai_exam.runner import RunTarget  # noqa: E402

DEMO = "rolling-c32a6140-b6b"
FENCED = ROOT / "_ai_exam_scratch" / "mobility_pinned"
REPS = 3
#: R-TG6 (ii) reads at most three named orders per claim (`orders[:3]`), so the
#: capped worst case is three reads, not an unbounded one.
CAP = 3


def _explainer(target) -> object:
    """The same Explainer the ask path builds over this run — constructed the
    way `RunTarget.build_vocab` does, so the object being timed is the object a
    live turn would call."""
    from mre.modules.evidence_index import EvidenceIndex
    from mre.modules.explainer import Explainer
    from mre.modules.snapshot_store import SnapshotStore
    ip = target.out_dir / "evidence_index.json"
    index = (EvidenceIndex.load(ip) if ip.exists()
             else EvidenceIndex().build(target.out_dir / target.runs_subdir))
    store = SnapshotStore(target.out_dir / "snapshots")
    return Explainer(store, index, snapshot_id=target.snapshot_id,
                     out_dir=target.out_dir, runs_subdir=target.runs_subdir)


def _time(fn, *args) -> tuple[float, object]:
    t0 = time.perf_counter()
    out = fn(*args)
    return (time.perf_counter() - t0) * 1000.0, out


def _measure(label: str, target, orders: list[str]) -> None:
    ex = None
    # The explainer build is NOT part of the cost being measured — every ask
    # already pays it. Build once, outside the timed region.
    try:
        ex = _explainer(target)
    except Exception as exc:  # noqa: BLE001
        print(f"  {label}: could not build an explainer ({exc})")
        return
    reader = getattr(ex, "order_mobility_verdicts", None)
    if reader is None:
        print(f"  {label}: no order_mobility_verdicts on this explainer")
        return

    print(f"\n=== {label} ===")
    print(f"  orders probed: {orders}")

    singles: list[float] = []
    for rep in range(REPS):
        for ref in orders[:1]:
            ms, verdicts = _time(reader, ref)
            singles.append(ms)
            if rep == 0:
                print(f"  single order {ref}: {len(verdicts or [])} operation "
                      f"verdict(s)")
    worst: list[float] = []
    for _rep in range(REPS):
        t0 = time.perf_counter()
        for ref in orders[:CAP]:
            reader(ref)
        worst.append((time.perf_counter() - t0) * 1000.0)

    def _stat(name: str, xs: list[float]) -> None:
        print(f"  {name:<26} min {min(xs):8.1f} ms   median "
              f"{statistics.median(xs):8.1f} ms   max {max(xs):8.1f} ms"
              f"   spread {max(xs) - min(xs):.1f} ms")

    _stat("single order (typical)", singles)
    _stat(f"capped worst case (x{CAP})", worst)


def main() -> int:
    print(__doc__.splitlines()[0])

    # The fenced world first — the cheap side, and the one (e) reasoned from.
    try:
        fenced = RunTarget.from_out_dir(FENCED, snapshot_id="snap-mobility")
        _measure("FENCED WORLD  datasets/mobility_box (9 orders, 3 machines)",
                 fenced, ["ORD-BOX", "ORD-EARLY", "ORD-PACK"])
    except Exception as exc:  # noqa: BLE001
        print(f"  fenced world unavailable: {exc}")

    try:
        demo = RunTarget.from_schedule(ROOT / "_data", DEMO)
        _measure(f"DEMO BOARD    {DEMO} (386 bars)", demo,
                 ["ORD-000128", "ORD-000112", "ORD-000252"])
    except Exception as exc:  # noqa: BLE001
        print(f"  demo board unavailable: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
