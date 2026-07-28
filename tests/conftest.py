"""Shared pytest configuration.

--runslow opts in to tests marked @pytest.mark.slow (e.g. the clean_large IDS
scenario, which generates and solves a 3000-order dataset).

It also loads the gitignored ``.env.local`` (Session 4B.8 pre-flight). Before
that, ``tools/run_ai_exam_sweep.py`` carried the ONLY loader in the repo, so a
key that was present on disk was invisible to the test process: four committed
slow tests landed on the honest no-parser floor and read as failures for a
reason unrelated to whatever was under test. The loader is copied from the exam
harness deliberately — same semantics, same repo-root anchoring — because
``python-dotenv`` is not a dependency of this project.
"""
import os
from pathlib import Path

import pytest


def _load_env_local() -> None:
    """Load the gitignored .env.local into this process's environment, without
    printing anything from it. An already-set variable always wins, so an
    explicit shell export or a monkeypatch still overrides the file.

    The path is anchored to THIS FILE's repo root, never to the CWD — pytest is
    run from the repo root, from tests/, and from tools/ spikes, and a
    CWD-relative path would load in some of those and silently not in others.
    """
    path = Path(__file__).resolve().parents[1] / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


_load_env_local()


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
