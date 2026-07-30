SWEEP 2026-07-30 -- regression_founder_r5, GRADED FOR THE FIRST TIME
Session 4B.17. Plain ASCII.

WHAT THIS IS. Six runs of the recalibrated `regression_founder_r5` bank against
the pinned world `rolling-c362baa4-1b0`, three on the shipped model defaults
(parse Haiku 4.5 / synthesis Sonnet 5) and three on Haiku-everywhere
(MRE_SYNTHESIS_MODEL=claude-haiku-4-5-20251001). 33 questions each, 198 answers.
PYTHONHASHSEED=0. No solve; every read is from the persisted run (R-AI4).

The target is `_ai_exam_scratch/rolling_pinned` via its TARGET.json, verified
this session to be byte-identical to
`_data/runs/c362baa4-1b03-4f6c-b3a4-d092c341dbdf/schedule_document.json` apart
from `schedule_id`, `run_id` and the `interaction` block.

NOT PRODUCED BY tools/run_ai_exam_sweep.py. That tool writes one transcript per
BANK per sweep and reports no token usage, and this session needed N runs of ONE
bank with measured cost. `run_r5.py` below drives the same `ExamRunner` through
the same `_answer_question` entry point; nothing is mocked.

FILES

  transcript-{shipped,haiku}-{1,2,3}.txt
      the standard exam transcript, one per run
  sidecar-{shipped,haiku}-{1,2,3}.json
      the standard mechanical findings sidecar, one per run. Identical in all
      six: {'dark-evidence': 2, 'expect-miss': 5, 'validator': 1}, graded 27/32.
  runs-shipped.json / runs-haiku.json
      the per-question row set this session's triage was read from: intent,
      confidence, route, register, renderer, records, lit bars, latency, the
      parse and synthesis blocks, the EXPECT verdict, the findings, and the
      ANSWER VERBATIM. This is the primary evidence for docs/closeouts/4B.17.md.

  run_r5.py    the driver. One fresh parser and synthesizer per run so
               run-to-run variance is not fused into one stats object. Token
               usage is MEASURED off each response's own `usage` and attributed
               by the model the call named -- the same discipline
               tools/model_tier_bench.py uses.
  grade_r5.py  deterministic tripwires over the answers. THESE ARE NOT THE GRADE
               (R-AI4(2) makes the grade a read). They only decide what a read
               must look at, and every check is derived from the pinned world's
               document or from the bank's own written expectation -- never from
               an observed answer. Also prints the stable-vs-flipped verdict.
  cols.py      Item 4's two quality columns: did the answer reach the ASKED
               QUANTITY, and did the declared multi-hop questions get answered.
               Both sets are declared in the file with their hops named.

REPRODUCE

  cd C:\dev\mre
  PYTHONHASHSEED=0 python tests/ai_exam/sweeps/2026-07-30-r5-graded/run_r5.py \
      --label shipped --runs 3 --out <dir>
  MRE_SYNTHESIS_MODEL=claude-haiku-4-5-20251001 PYTHONHASHSEED=0 \
    python tests/ai_exam/sweeps/2026-07-30-r5-graded/run_r5.py \
      --label haiku --runs 3 --out <dir>
  python tests/ai_exam/sweeps/2026-07-30-r5-graded/grade_r5.py <dir>/runs-*.json
  python tests/ai_exam/sweeps/2026-07-30-r5-graded/cols.py    <dir>/runs-*.json

`run_r5.py` hardcodes the repo root and the bank path, because it is a record of
one measurement rather than a tool. A future session wanting a general N-run
harness should promote it into tools/ rather than edit it in place -- editing it
would make these transcripts unreproducible.

TWO WARNINGS FOR ANYONE READING THESE TRANSCRIPTS

1. THE TARGET CANNOT STATE ITS OWN COST PROOF. `EvidenceIndex.save()` persists
   only entity-keyed records, so the M6 `solve_complete` Event does not survive
   the round-trip and `cost_proof.from_evidence` returns `no_solve` on the
   loaded index. Every cost-proof-dependent answer in these transcripts is
   therefore wrong in the same direction -- most visibly, the opener's CLEAN
   band shows one item where 4B.16's close-out documents two. docs/07 section
   5a.55. NOT FIXED in 4B.17.

2. `dark-evidence` FIRES TWICE PER RUN AS A FALSE POSITIVE. L221 and L231 are
   the premise CORRECTIONS: `why-on-machine` is an evidence-shaped route and a
   correction cites zero records because there is nothing to cite. The sidecar
   signal predates 4B.13's premise guard.
