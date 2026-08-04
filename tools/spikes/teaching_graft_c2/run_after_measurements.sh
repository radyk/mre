#!/usr/bin/env bash
# Session 4A teaching-graft (c2) — the after-half of the measurement, in the
# order the close-out reports it. Each step writes into
# tests/ai_exam/sweeps/2026-08-04-teaching-c2/ and prints its own summary.
#
# Run from the repo root. Every step calls a live model; nothing here mints
# anything in _data.
set -u
OUT=tests/ai_exam/sweeps/2026-08-04-teaching-c2

echo "=================================================================="
echo "1/3  sweep_teaching_v3, run 2 (the graded run, final grader)"
echo "=================================================================="
python tools/spikes/teaching_graft_c/grade_c9_sweep.py rolling-db5395dc-2ae "$OUT"

echo
echo "=================================================================="
echo "2/3  sweep_teaching_v2 — session (b)'s depth families, NON-REGRESSION"
echo "=================================================================="
python tools/spikes/teaching_graft_b/grade_depth_sweep.py rolling-db5395dc-2ae "$OUT"

echo
echo "=================================================================="
echo "3/3  NEGATIVE CONTROL — rule 14 excised, restore asserted by sha256"
echo "=================================================================="
python tools/spikes/teaching_graft_c2/rule14_control.py rolling-db5395dc-2ae

echo
echo "ALL AFTER-MEASUREMENTS COMPLETE"
