# Manufacturing Reasoning Engine

An AI-assisted production scheduling platform: cost-optimized CP-SAT schedules
with full explainability and ERP data-quality monitoring, built on a canonical
manufacturing model and a universal evidence contract.

Start here:
1. `docs/00-README.md` — one-page orientation
2. `CLAUDE.md` — standing rules and repo map
3. `PHASE0_PROMPT.md` — the first Claude Code session

## Getting started

```bash
git init
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -e ".[dev]"
pytest        # (no tests yet — Phase 0 writes them)
```
