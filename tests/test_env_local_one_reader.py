"""ONE READER for .env.local — Errand 4B.16a Item 1.

The repo held FOUR independent implementations of "populate the environment from
`.env.local`" (dev_api.ps1 in PowerShell, tools/run_ai_exam_sweep.py since 4A.5b,
tests/conftest.py copied in 4B.8, and a spike copy that had already DRIFTED to
`os.environ.setdefault`). Two entry points that need the key -- `python -m mre.ask`
and `python -m mre.ai_exam` -- had none at all, so from a bare shell they built an
unavailable parser and answered on the honest could-not-interpret floor. That is
indistinguishable from a missing key, and it is one of the readings that kept
docs/07 5a.7's "the sweep is key-blocked" alive for three sessions after it stopped
being true.

These tests pin the semantics AND pin the count. A second Python loader is the
failure mode, so it is what goes red.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from mre.env_local import env_local_path, load_env_local

REPO = Path(__file__).resolve().parents[1]
THE_READER = REPO / "src" / "mre" / "env_local.py"


# -- the count ---------------------------------------------------------------

def test_exactly_one_python_loader_exists():
    """No .py file besides the one reader both NAMES `.env.local` and WRITES to
    `os.environ`. Naming it in a docstring is fine -- being a second loader is not.

    The PowerShell loader in `src/cockpit/dev_api.ps1` is deliberately exempt: it
    runs BEFORE any Python exists, to populate uvicorn's environment. It is the
    shell, not a second reader in this language.
    """
    # A second loader necessarily does two things: it names `.env.local` as a
    # WHOLE string literal (a path to read) and it WRITES to os.environ. Prose
    # about `.env.local` is not a loader, and neither is an `os.environ.get`.
    literal = re.compile(r"""['"]\.env\.local['"]""")
    writes = re.compile(r"os\.environ\s*\[\s*\S+\s*\]\s*=|os\.environ\.setdefault"
                        r"|os\.environ\.update")
    offenders = []
    for path in REPO.rglob("*.py"):
        rel = path.relative_to(REPO)
        parts = set(rel.parts)
        if parts & {".venv", "venv", "legacy", "node_modules", "__pycache__",
                    "build", "dist"}:
            continue
        if path in (THE_READER, Path(__file__).resolve()):
            continue  # the reader itself, and this guard, must name the pattern
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        code = "\n".join(line for line in text.splitlines()
                         if not line.lstrip().startswith("#"))
        if literal.search(code) and writes.search(code):
            offenders.append(str(rel))
    assert offenders == [], (
        "a SECOND .env.local loader has appeared -- import "
        f"mre.env_local.load_env_local instead: {offenders}")


def test_the_one_reader_is_importable_from_every_caller():
    """Each populate site calls the shared function rather than defining one."""
    for rel in ("tests/conftest.py",
                "tools/run_ai_exam_sweep.py",
                "tools/spikes/density_4b10/pastdue_visibility.py",
                "src/mre/ask.py",
                "src/mre/demo.py",
                "src/mre/ai_exam/__main__.py"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "from mre.env_local import load_env_local" in text, rel


def test_library_modules_never_load_on_import():
    """`mre.env_local` mutates nothing until it is CALLED. A package that writes
    to the environment on import is a surprise the API server does not need -- in
    a container the key comes from the platform secret store and there is no file.
    """
    src = THE_READER.read_text(encoding="utf-8")
    body = "\n".join(line for line in src.splitlines()
                     if line and not line.startswith((" ", "\t", "#", '"""', "'''")))
    assert "load_env_local()" not in body, (
        "the one reader must not call itself at import time")


# -- the semantics -----------------------------------------------------------

def test_anchored_to_repo_root_not_cwd(tmp_path, monkeypatch):
    """The anchor is THIS FILE's repo root. A CWD-relative path loads when a tool
    is run from the repo root and silently does not from `tools/` or a spike dir --
    which is the shape of every "it works for me" in this class.
    """
    monkeypatch.chdir(tmp_path)
    assert env_local_path() == REPO / ".env.local"


def test_already_set_variable_always_wins(tmp_path, monkeypatch):
    f = tmp_path / ".env.local"
    f.write_text("MRE_TEST_ONE_READER=from-file\n", encoding="utf-8")
    monkeypatch.setenv("MRE_TEST_ONE_READER", "from-shell")
    assert load_env_local(f) is True
    assert os.environ["MRE_TEST_ONE_READER"] == "from-shell"


def test_empty_value_is_not_a_value(tmp_path, monkeypatch):
    """The drifted spike copy used `setdefault`, which writes an EMPTY value. A
    commented-out or blanked key must not shadow a real one from the environment.
    """
    f = tmp_path / ".env.local"
    f.write_text("MRE_TEST_BLANK=\nMRE_TEST_QUOTED=\"kept\"\n", encoding="utf-8")
    monkeypatch.delenv("MRE_TEST_BLANK", raising=False)
    monkeypatch.delenv("MRE_TEST_QUOTED", raising=False)
    load_env_local(f)
    assert "MRE_TEST_BLANK" not in os.environ
    assert os.environ["MRE_TEST_QUOTED"] == "kept"
    monkeypatch.delenv("MRE_TEST_QUOTED", raising=False)


def test_comments_and_blank_lines_ignored(tmp_path, monkeypatch):
    f = tmp_path / ".env.local"
    f.write_text("# a comment=not a var\n\n  \nMRE_TEST_REAL=yes\n", encoding="utf-8")
    monkeypatch.delenv("MRE_TEST_REAL", raising=False)
    load_env_local(f)
    assert os.environ["MRE_TEST_REAL"] == "yes"
    assert "# a comment" not in os.environ
    monkeypatch.delenv("MRE_TEST_REAL", raising=False)


def test_missing_file_is_a_noop_returning_false(tmp_path):
    """The runtime image has no `.env.local` (docs/08) and must not care."""
    assert load_env_local(tmp_path / "nope.env") is False


def test_values_are_never_printed(tmp_path, capsys, monkeypatch):
    f = tmp_path / ".env.local"
    f.write_text("MRE_TEST_SECRET=sk-ant-do-not-print\n", encoding="utf-8")
    monkeypatch.delenv("MRE_TEST_SECRET", raising=False)
    load_env_local(f)
    out = capsys.readouterr()
    assert "sk-ant-do-not-print" not in (out.out + out.err)
    monkeypatch.delenv("MRE_TEST_SECRET", raising=False)


@pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY"])
def test_conftest_actually_populated_this_process(name):
    """Not an assertion that a key EXISTS -- a dev checkout without `.env.local` is
    legitimate. It asserts the two states agree, so "the parser is unavailable"
    can never again mean "some entry point forgot to populate".
    """
    on_disk = env_local_path().exists() and any(
        line.strip().startswith(name + "=") and line.strip().partition("=")[2].strip()
        for line in env_local_path().read_text(encoding="utf-8").splitlines())
    if on_disk:
        assert os.environ.get(name), (
            f"{name} is on disk but absent from this process -- conftest's "
            "populate step did not run")
