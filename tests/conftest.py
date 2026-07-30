"""Shared pytest configuration.

--runslow opts in to tests marked @pytest.mark.slow (e.g. the clean_large IDS
scenario, which generates and solves a 3000-order dataset).

It also loads the gitignored ``.env.local`` (Session 4B.8 pre-flight). Before
that, ``tools/run_ai_exam_sweep.py`` carried the ONLY loader in the repo, so a
key that was present on disk was invisible to the test process: four committed
slow tests landed on the honest no-parser floor and read as failures for a
reason unrelated to whatever was under test.

Errand 4B.16a: the loader was COPIED here in 4B.8 and the repo then held four
copies, one already drifted. It now calls ``mre.env_local`` — the one reader —
whose docstring records why the library itself never loads a file. Semantics are
unchanged: repo-root anchoring, an already-set variable (or a monkeypatch) always
wins, nothing printed.
"""
import pytest

from mre.env_local import load_env_local

load_env_local()


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
