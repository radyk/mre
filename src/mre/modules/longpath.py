"""Windows long-path (``\\\\?\\`` extended-length) support for the snapshot/run store.

Session 4.0d. The canonical model is a directory-per-snapshot tree under the data
root; a chained-edit workflow nests run dirs deep, and on Windows the classic
MAX_PATH (260) limit made a deep accept fail at the copy seam with
``FileNotFoundError [WinError 3]`` (Sessions 4.0c → 4.0d). The correct fix on
modern Windows is to opt each filesystem call into the extended-length namespace by
prefixing the fully-qualified absolute path with ``\\\\?\\``, which lifts the
260-char limit (paths up to ~32767). This module is that single seam: everything
that writes or reads the snapshot/run tree routes its ``os``/``shutil`` calls
through here, so no snapshot path can ever hit MAX_PATH again — regardless of how
deep the data root or the edit chain is.

Why not pathlib: ``Path.mkdir(parents=True)`` walks up to ``\\\\?\\C:`` (a
syntactically invalid extended path — no trailing separator) and raises
``WinError 123``. So the seam uses ``os.makedirs`` / ``open`` / ``shutil.*`` on the
extended STRING instead, and returns plain :class:`Path` objects (prefix stripped)
so callers can do string operations (``.name``/``.stem``) naturally and re-enter
the seam for the next syscall.

On every non-Windows platform every function is a thin pass-through to the stdlib
(no prefix), so behaviour is identical off Windows.
"""
from __future__ import annotations

import glob as _glob
import os
import shutil
from pathlib import Path
from typing import IO

_ON_WINDOWS = os.name == "nt"
_PREFIX = "\\\\?\\"


def extended(path: Path | str) -> str:
    """The OS path string for ``path``, extended-length-prefixed on Windows.

    Idempotent (an already-prefixed path passes through unchanged) and correct for
    UNC paths (``\\\\server\\share`` → ``\\\\?\\UNC\\server\\share``). The path is
    made absolute + normalized first because the ``\\\\?\\`` namespace disables the
    normalization the OS would otherwise apply (no ``.``/``..``, backslashes only)."""
    s = str(path)
    if not _ON_WINDOWS:
        return s
    if s.startswith(_PREFIX):
        return s
    s = os.path.abspath(s)
    if s.startswith("\\\\"):  # UNC path: \\server\share\...
        return _PREFIX + "UNC\\" + s[2:]
    return _PREFIX + s


def makedirs(path: Path | str, exist_ok: bool = True) -> None:
    os.makedirs(extended(path), exist_ok=exist_ok)


def open_(path: Path | str, mode: str = "r", encoding: str | None = "utf-8") -> IO:
    # Binary modes take no encoding; text modes default to utf-8 (the store's
    # convention).
    if "b" in mode:
        return open(extended(path), mode)
    return open(extended(path), mode, encoding=encoding)


def write_text(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    with open(extended(path), "w", encoding=encoding) as f:
        f.write(text)


def read_text(path: Path | str, encoding: str = "utf-8") -> str:
    with open(extended(path), "r", encoding=encoding) as f:
        return f.read()


def exists(path: Path | str) -> bool:
    return os.path.exists(extended(path))


def copy2(src: Path | str, dst: Path | str) -> None:
    shutil.copy2(extended(src), extended(dst))


def copytree(src: Path | str, dst: Path | str) -> None:
    shutil.copytree(extended(src), extended(dst))


def rmtree(path: Path | str) -> None:
    shutil.rmtree(extended(path), ignore_errors=True)


def glob(dir_path: Path | str, pattern: str) -> list[Path]:
    """Match ``pattern`` inside ``dir_path`` through the extended seam, returning
    plain :class:`Path` objects (prefix stripped) so the caller can do string ops
    and re-enter the seam via :func:`open_`/:func:`read_text` for the next read."""
    matches = _glob.glob(extended(Path(dir_path) / pattern))
    return [Path(_strip(m)) for m in matches]


def child_dir_names(path: Path | str) -> list[str]:
    """Names of the immediate subdirectories of ``path`` (for snapshot listing)."""
    base = extended(path)
    if not os.path.isdir(base):
        return []
    return [name for name in os.listdir(base)
            if os.path.isdir(os.path.join(base, name))]


def _strip(s: str) -> str:
    if s.startswith(_PREFIX + "UNC\\"):
        return "\\\\" + s[len(_PREFIX) + 4:]
    if s.startswith(_PREFIX):
        return s[len(_PREFIX):]
    return s


# ---------------------------------------------------------------------------
# Path-budget check (Session 4.0d, fix 3) — a boot-time / /health tripwire so a
# path-length problem is never again discovered only at accept time.
# ---------------------------------------------------------------------------

# The classic Windows MAX_PATH the ANSI/Unicode APIs enforce without the \\?\
# opt-in. POSIX has no comparable per-path ceiling for our depths.
CLASSIC_MAX_PATH = 260

# The deepest leaf the store writes under a run dir, as a template measured from
# the data root: runs/<uuid>/snapshots/<snapshot-id>/<longest entity file>.
_UUID_LEN = 36
_MAX_SNAPSHOT_ID_LEN = 32  # bound guaranteed by planner_edit._edit_snapshot_id
_LONGEST_LEAF = "entities_serviceoutcome.jsonl"


def path_budget(data_root: Path | str) -> dict:
    """Worst-case snapshot path length under ``data_root`` and whether it is safe.

    ``status`` is ``at_risk`` when the worst-case snapshot path would exceed the
    classic Windows limit — i.e. the data root is deep enough that the run store
    would fail WITHOUT long-path support. ``long_path_mitigation`` reports whether
    the store's seam actually lifts that limit (always, on Windows). So an
    ``at_risk`` root with mitigation ``True`` still works today, but is flagged
    loudly at boot and in /health so the depth is never a silent surprise —
    shortening the data root is the durable fix. POSIX has no comparable per-path
    ceiling for these depths, so it is always ``ok``.
    """
    root = os.path.abspath(str(data_root))
    tail = os.path.join("runs", "u" * _UUID_LEN, "snapshots",
                        "s" * _MAX_SNAPSHOT_ID_LEN, _LONGEST_LEAF)
    worst_case = len(root) + 1 + len(tail)
    limit = CLASSIC_MAX_PATH if _ON_WINDOWS else None
    exceeds_classic = bool(_ON_WINDOWS and worst_case > CLASSIC_MAX_PATH)
    return {
        "data_root_len": len(root),
        "worst_case_path_len": worst_case,
        "classic_max_path": limit,
        "exceeds_classic_limit": exceeds_classic,
        "long_path_mitigation": _ON_WINDOWS,
        "status": "at_risk" if exceeds_classic else "ok",
    }
