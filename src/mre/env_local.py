"""THE ONE READER for the gitignored ``.env.local`` (Errand 4B.16a Item 1).

``ANTHROPIC_API_KEY`` lives in ``.env.local`` at the repo root. Nothing in the
library ever loads it: ``question_parser.py``, ``renderers.py``, ``synthesizer.py``
and ``api/app.py`` all read a BARE ``os.environ``, which is correct — in a
container the key arrives from the platform secret store and there is no file.

So every ENTRY POINT has to populate the environment itself, and until this
module there were FOUR independent implementations of that step, which is how
docs/07 §5a.7 came to name a blocker nobody had tested:

    src/cockpit/dev_api.ps1        PowerShell, before uvicorn starts
    tools/run_ai_exam_sweep.py     Python, since 4A.5b  (worked all along)
    tests/conftest.py              Python, copied in 4B.8
    tools/spikes/.../pastdue_visibility.py   Python, and already DRIFTED
                                   (``os.environ.setdefault`` sets an EMPTY
                                   value where the other three skip it)

and TWO entry points had none at all — ``python -m mre.ask`` and
``python -m mre.ai_exam``, the harness's own module front door. From a bare
shell those built an UNAVAILABLE parser and answered on the honest
could-not-interpret floor, which reads exactly like a key that is missing.

Rules this reader keeps, because the three surviving copies kept them:

* the path is anchored to THIS FILE's repo root, NEVER to the CWD — the tools
  are run from the repo root, from ``tools/``, and from spike directories, and a
  CWD-relative path loads in some of those and silently not in others;
* an already-set variable ALWAYS wins, so a shell export or a pytest
  monkeypatch still overrides the file;
* an EMPTY value is not a value — it is skipped, so a commented-out key cannot
  shadow a real one from the environment;
* nothing from the file is ever printed;
* a missing file is a no-op returning False, never a raise. The runtime image
  has no ``.env.local`` and must not care.

``python-dotenv`` is deliberately not a dependency of this project; this is a
dozen lines and carries no import cost on the production path.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

#: The repo root as seen from ``src/mre/env_local.py``. Meaningful for an
#: editable install (every dev checkout); harmless otherwise, because the file
#: simply will not be there.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def env_local_path() -> Path:
    """Where the reader looks. Exposed so a guard test can assert the anchor."""
    return _REPO_ROOT / ".env.local"


def load_env_local(path: Optional[Path] = None) -> bool:
    """Load ``.env.local`` into ``os.environ``. Return True iff the file existed.

    Call this from an ENTRY POINT (a ``main()``, a tool, ``conftest``), never at
    import time from a library module: a package that mutates the environment on
    import is a surprise the API server does not need.
    """
    target = Path(path) if path is not None else env_local_path()
    if not target.exists():
        return False
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value
    return True
