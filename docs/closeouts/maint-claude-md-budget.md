# Maintenance errand — CLAUDE.md back under budget

**2026-08-05** · **R-CM1 ruled and BUILT** (docs/04, same date) · docs/07 **v2.97**,
§5a.203 · contract unchanged **1.15**, no docs/06 doorway owed · **both governed
prompts unchanged** — parse **v18**, synthesis **v9**. This errand touched no
prompt, no `src/mre/` module, no solver, no dataset and no `_data`.

---

## 1. The number, and the method

**190,354 → 33,453 characters. 17.6% of what it was.**

The method is part of the ruling. Characters are counted **as the file is read
from disk**: decoded UTF-8, line endings intact, so a CRLF counts as two. That is
the strictest of the available methods — the LF-normalised count of the same file
is 187,779, some 2,575 lower — and it is the method the 190.4k figure in the brief
was taken with. Counting the looser way would have handed back headroom the budget
did not grant.

The target was ≤130k. The file landed at **33,453**, which is also under the
**40,000-character phase-exit ceiling CLAUDE.md names for itself** — a ceiling it
has been over since 4B.14 and has not met in twenty-one sessions.

## 2. The census

Section by section, as it stood at HEAD (characters, on-disk method):

| section | chars | % | class |
| --- | ---: | ---: | --- |
| `## Current status` | 177,722 | 93.4% | mixed — see below |
| `## Dev API quick reference` | 4,496 | 2.4% | (O) |
| `## Hard rules` | 3,409 | 1.8% | (L) |
| `## Authoritative documents` | 1,915 | 1.0% | (O) |
| `## Repository layout` | 1,251 | 0.7% | (O) |
| `## Working style` | 1,191 | 0.6% | (O) |
| `## What this repository is` | 324 | 0.2% | (O) |
| title | 48 | — | (O) |

Inside `## Current status`:

| block | chars | % of file | class | disposition |
| --- | ---: | ---: | --- | --- |
| session changelog (4B.11 → (e2)) | 67,947 | 35.7% | (H) | **(a)** → docs/04 verbatim |
| ruling + discovery narratives | 78,144 | 41.0% | (H) / (L) | **(a)** → docs/04 verbatim; (L) residue condensed to one line each |
| small carry-forwards | 22,866 | 12.0% | (S) / (D) | **(a)** verbatim + **(b)** pointer table |
| pinned worlds | 5,424 | 2.8% | (O) | **(c)** condensed in place |
| carried qualifications | 2,544 | 1.3% | (S) | **(c)** condensed in place |
| maintenance rule | 776 | 0.4% | (L) | **(c)** rewritten around the test |

**Top five contributors: 67,947 / 78,144 / 22,866 / 5,424 / 4,496.** The first
three are **88.7% of the whole file** between them, and they are all **one growth
pattern**: a session finishes, writes its narrative into the top of the status
section, and never removes the one below it. The file grew by roughly one
close-out per session and shrank never.

That pattern — not the size — is the finding, and it is why R-CM1 clause (2)
governs where prose is **born** rather than asking sessions to tidy up afterwards.

## 3. What moved, and how

**Nothing was deleted.**

- **(a) moved to docs/04**, verbatim, under *2026-08-05 — CLAUDE.md STATUS
  SECTION CONSOLIDATION*: the session changelog, the ruling and discovery
  narratives, and the small carry-forwards — **168,280 characters**, reproduced
  unedited **before a byte of the original was condensed**, so every relocation is
  provable by diff rather than by assurance.
- **(b) deduplicated to pointers**: the per-session carry-forwards became a
  fifteen-row table naming, for each session, the two items a session should take
  next plus its docs/07 §5a range and close-out file. Sampled and confirmed present
  in docs/07 / the close-outs before the move.
- **(c) condensed in place**: the pinned worlds, the carried qualifications, the
  standing law (forty-odd ruling codes at one line each — **the code is the
  pointer**), and the maintenance rule.

## 4. Stale content corrected in the move

Named rather than silently fixed:

1. **Two RETIRED-LOST board ids carried paragraphs written as if current.**
   `rolling-db5395dc-2ae` and `rolling-c362baa4-1b0` now appear once, as
   retired-lost, with their successors named.
2. **The over-the-ceiling running tally is retired** — a fourteen-entry list
   tracking the file's own growth from 47k to 170k, which described the problem
   and did nothing about it. The test replaces it.
3. **docs/07's own Status line read v2.95 while a v2.96 entry stood above it** —
   (e2) added the entry and did not bump the header. Caught here, corrected to
   v2.97.

## 5. The guard

`tests/test_claude_md_budget.py`, **four tests**:

- the budget itself (**150,000** characters, on-disk method);
- an assertion that the constant **is** 150,000, so a session quietly raising the
  bar has to delete a test that says why;
- the counting method pinned **both ways** (CRLF = 2, LF = 1);
- the negative control.

**The control goes through the shipped comparison.** `check_budget` is the only
place the comparison happens; the control asserts an unpadded copy passes it
first, then that a padded copy raises. Written the obvious way it would have
re-asserted a *copy* of the assertion and stayed green against a broken guard —
**4B.28 §5a.123's species**, at the seam where it is cheapest to commit. It was
written that way first and rewritten.

**Live control, out of band:** the real CLAUDE.md padded 33,453 → 243,453
characters, the guard run, **RED**; restored and **byte-identical by sha256**
(`df02b1237545e8f8…`), green again 4/4.

## 6. The write rule

**R-CM1**, in docs/04 in full and one bullet in CLAUDE.md's Hard rules: sessions
append **only pointer-form lines** — a ruling code, an id, a one-sentence
discipline. Prose, rationale, measurements and changelog content are **born in
docs/04 or docs/07** and referenced. A session whose CLAUDE.md diff adds more than
**~15 lines** is presumptively doing it wrong and **says so in its close-out**.

Clause (1) and the ~15-line heuristic are **not testable** and the test file says
so in its docstring. Clause (3) is the test. **Clause (2) is the one that does the
work, and it is enforced by nothing but being read** — which is exactly what
failed last time. Stated, not glossed.

## 7. Verification that orientation survived

- **Ruling codes in the last five close-outs** — 15 distinct, **14 resolve** in
  CLAUDE.md pointer-form and/or docs/04. The fifteenth, **R-EX2, resolves
  nowhere and did not resolve at HEAD either** (0 occurrences in both files before
  this errand): (e) and (e2) cite it as the ladder session's *proposed* relational
  expectations work, never ruled. **Pre-existing dangling reference, not something
  this errand broke.**
- **Standing disciplines named by the errand and recent prompts** — 16 checked,
  16 present: R-PW1 custody, deterministic mode and the determinism triple, the
  never-junction-`_data` rule, docs/04 append-only, the close-out path convention,
  "a defect class fixed at one seam is not fixed", negative controls with
  byte-identical restores, "a guard that supplies its own arguments proves the
  assembler", line endings per file, add-never-repurpose, provenance-with-every-
  write, contracts-only record shapes, `external_refs`, `rollup_of`, M10's absent
  write path.
- **The facts a fresh session cannot function without** — 11 checked, 11 present
  and correct: the three rolling board ids, the fenced world, the retired-lost
  law, the data-root law, the off-tree capsule command, roadmap position, and the
  three governed-artifact versions.
- **Final character count: 33,453.**

## 8. Suites

Corpus index rebuilt after the doc moves and **before** the suite (849 passages;
the 15 undated `D-nn` decisions still dropped, unchanged).

| | passed | skipped | failed | collected |
| --- | ---: | ---: | ---: | ---: |
| baseline (clean HEAD) | 2767 | 305 | **1** | 3073 |
| after | **2772** | 305 | **0** | **3077** |

Both sides sum exactly to their own collection count. **No residual.**
**Collection +4 exactly, and the new guard file collects exactly 4** — confirmed
independently of the pass counts. Passed +5 = the 4 new tests **plus one
pre-existing failure going green** (below).

**Both runs are chunked** — eight alphabetical slices per side, summing to each
side's collection. This was not a choice: **three consecutive background runs
were killed by the environment** (one full run at 65%, one four-slice run at
slice 0). (d.1) recorded the same behaviour and the shared-body micro-session
recorded the opposite; the tally is now **two sessions for, one against**, and
foreground slices are what actually completed here.

**`test_corpus::TestCurrency` was RED AT HEAD** — pre-existing, not caused by this
errand and not a flake. The working tree matched HEAD byte for byte while the
**committed** `src/mre/corpus_index.json` recorded a stale hash for docs/07: (e2)
rebuilt the index, ran green, then edited docs/07 again before committing. **This
is the fourth occurrence of the class** (4B.33, (c2), the shared-body
micro-session, now (e2)). This errand's own rebuild fixes it as a side effect,
which is why the passed delta is +5 against a collection delta of +4.

**Line endings, every edited file checked and stated:** CLAUDE.md, docs/04,
docs/07 and the new test are each **uniformly CRLF in the working tree with zero
bare LF**; docs/04 and docs/07 are LF in the blob, which is the repo's normal
`autocrlf` behaviour and shows as a clean diff (docs/04: insertions only). This
close-out is **LF**, matching every other file in `docs/closeouts/`.

**Minted nothing.** `_data` untouched — 8 runs before and after. Both pinned
boards unread. Cockpit untouched, not re-run.

## 9. What a summary would undersell

**The 2026-07-25 maintenance rule was not ignored.** It was in the file and it was
read: **eleven close-outs quote it**, and the growth tally it asked for was
diligently updated by session after session — 47k, 53k, 57k, 62k, 65k, 70k, 74k,
78k, 81k, 85k, 88k, 92k, 96k, 102k, 110k, 142k, 155k, 160k, 170k. **Nineteen
sessions measured the problem correctly and not one of them fixed it.**

That is the lesson, and it is not "CLAUDE.md got big". The rule asked for
restraint at the exact moment a session is least able to supply it: the close-out,
at the end, when the narrative is already written and the only remaining question
is where to paste it. **A rule that asks a tired agent to do the more expensive
thing loses to a rule that makes the cheaper thing correct.** R-CM1 clause (2)
moves the decision earlier — prose is *born* elsewhere, so pasting it into
CLAUDE.md is never the path of least resistance — and clause (3) puts a failing
test under it so the drift shows up in one run instead of nineteen.

**The errand's own rules caught three of my mistakes, and that is worth recording
because none of them would have been visible in the result.** (i) "Docs never
touched while a suite runs" caught a baseline I had contaminated by editing docs
mid-run; discarded and re-measured from a stashed clean HEAD rather than reported.
(ii) I wrote a final character count of **33,352 into docs/07 before measuring
it** — the measured figure is 33,453; corrected before commit, and it is exactly
the defect class this repo keeps ruling on, committed by the session writing the
ruling. (iii) My inserted docs/07 text left **32 bare-LF lines** in a uniformly
CRLF file — **(e2) §6's lesson, one session later, in the same file**.

## 10. Reported, not fixed

- **The 150k budget is inherited and has never been derived.** Nobody has measured
  what a 150k CLAUDE.md actually costs a session in context. If that measurement is
  taken the number should move to what it says; until then the test enforces a
  figure chosen on 2026-07-25 for reasons no longer recorded.
- **The test enforces the floor of sanity, not the 40k phase-exit target.**
  Encoding 40k would fail ordinary pointer-form appends. The gap between 33,453 and
  150,000 is headroom by design and will be spent.
- **Clause (1) is uncheckable.** No test can tell a pointer from prose; the
  ~15-line heuristic is a close-out obligation and will be honoured or not.
- **The negative control's green-first step is coupled to the real file.** When
  CLAUDE.md is over budget, *two* tests fail rather than one, because the control
  asserts an unpadded copy passes before padding it. Informative rather than
  wrong, but it is a coupling and it is named.
- **R-EX2 is cited by two close-outs and defined nowhere** (pre-existing).
- **The docs/04 consolidation entry is 168,280 characters of archive** in an
  already-1.1MB append-only file, now 1.27MB, indexed by nothing beyond its
  headings. That is the right place for it and it is also a cost.
- **`RECON_GATEHOUSE.txt` remains untracked at the repo root**, pre-existing and
  outside this errand's scope.
