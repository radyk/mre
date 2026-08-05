"""The mechanical pre-triage sidecar (Session 4A.3b, CU3).

Everything checkable about an answer WITHOUT judgment. The sidecar seeds Claude's
triage (RUBRIC.md); it never grades conversation (R-AI4(2)). Each check is a pure
function over a finished ``TurnRecord`` plus a ``Vocab`` view of the pinned world,
and returns zero or more ``Finding``s.

The six mechanical signals (verbatim from the session brief):
  1. the ask path itself raised / timed out               (kind ``exception``)
  2. an empty answer body                                   (kind ``empty``)
  3. an LLM testimony that failed validation                (kind ``validator``)
  4. an interpreted-as entity absent from the document      (kind ``absent-entity``)
  5. a route citing zero records where its shape needs them (kind ``dark-evidence``)
  6. an invitation proposing a question that parses to no intent (``dead-door``)

Signals 1-3 are truth-floor tripwires (R-AI4(1)); 4-6 are shape checks that a human
still reads. None of them is a verdict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Finding:
    kind: str
    lineno: int
    question: str
    detail: str


# Routes whose ANSWER shape is testimony over evidence — it should light at least
# one bar/lane (a non-empty ``cited_refs``). A dark evidence channel here is the
# regression the founder would see as "the answer doesn't point at anything". This
# is a heuristic SEED for triage, not a grade: header-only routes (findings,
# briefing, swap_move, gap_between, machine_idle, coaching, …) compose their whole
# answer in prose and are deliberately excluded.
EVIDENCE_ROUTES = frozenset({
    "late-order", "why-on-machine", "order-schedule", "machine-schedule",
    "start-reason",
})


class Vocab:
    """A read-only view of the pinned world for the sidecar's shape checks — the
    valid entity vocabulary + the door check for the real-doors reverse-guard.

    Built from a throwaway Explainer over the same snapshot the answers run
    against, so 'present in the document' means exactly what the ask path means.

    Session 4A.5a: the reverse-guard used to run the deterministic classifier over
    each offered follow-up. That classifier is retired (R-AI5(2)), so the check now
    runs the REAL parse layer over the probe — which is the honest test, since the
    parse is what the planner's click would actually hit. It costs one model call
    per DISTINCT offered question (memoized across the sweep). With no parser the
    check is SKIPPED, and the runner reports it as skipped rather than as clean."""

    def __init__(self, explainer: Any, parser: Any = None) -> None:
        self._ex = explainer
        self._parser = parser
        self._door_cache: dict[str, str] = {}
        self.order_refs = set((explainer._order_refs or {}).values())
        self.machine_refs = set((explainer._machine_refs or {}).values())
        self.excluded = set(getattr(explainer, "_excluded_labels", set()) or set())
        self._order_shapes = list(getattr(explainer, "_order_shape_patterns", []) or [])
        # A loaded snapshot yields a non-empty entity vocabulary. An EMPTY one means
        # the snapshot did not load (a wiped/missing run dir), and the Explainer has
        # fallen to certificate-only mode — every entity question then silently
        # misroutes. The runner reads this to refuse to run against a dead target
        # rather than emit a transcript full of garbage.
        self.healthy = bool(self.order_refs or self.machine_refs)

    @property
    def door_check_available(self) -> bool:
        return self._parser is not None and getattr(self._parser, "available", False)

    def door_intent(self, question: str) -> Optional[str]:
        """The intent an OFFERED follow-up parses to, or None when the door check
        is unavailable (no parser). Memoized: an invitation pattern repeats across
        a sweep, and a door is a property of the text, not of the turn."""
        if not self.door_check_available:
            return None
        key = question.strip().lower()
        if key in self._door_cache:
            return self._door_cache[key]
        try:
            parsed = self._parser.parse(question, explainer=self._ex, context=None)
            intent = "unmatched" if parsed is None else parsed.intent.value
        except Exception:  # noqa: BLE001 — a parse raise is itself a finding
            intent = "unmatched"
        self._door_cache[key] = intent
        return intent

    def absent_order_tokens(self, text: str) -> list[str]:
        """Order-SHAPED tokens in ``text`` that resolve to no scheduled demand and
        are not a known excluded label — a resolution to an order that isn't here.

        An excluded order (a real order the gate dropped) is NOT flagged: answering
        about it is legitimate (the excluded-orders route). We flag only tokens that
        look like this dataset's orders yet name nothing in it."""
        out: list[str] = []
        for tok in re.findall(r"[A-Za-z][\w./-]*\d[\w./-]*|[A-Za-z]+-\d[\w-]*", text or ""):
            u = tok.upper().strip(".,?!")
            if u in self.order_refs or u in self.machine_refs or u in self.excluded:
                continue
            if any(p.match(u) for p in self._order_shapes) and u not in out:
                out.append(u)
        return out


# An offered follow-up in an invitation / near-miss is phrased  Ask "<question>".
_OFFERED_QUESTION = re.compile(r'Ask\s+"([^"]+)"')


def offered_questions(answer: str) -> list[str]:
    """Every follow-up question an answer offers the planner (the invitation /
    near-miss surface). The real-doors guard classifies each one."""
    return [m.group(1).strip() for m in _OFFERED_QUESTION.finditer(answer or "")]


def answer_body(answer: str) -> str:
    """The answer with its ``[rendered by: … | register: …]`` footer stripped.

    Used by the empty-body check AND, since R-EX2, as the input to the body
    fingerprint — the same body both times, so "this answer is empty" and "these
    two answers are the same" can never disagree about what the answer is."""
    lines = [ln for ln in (answer or "").splitlines()
             if not ln.strip().startswith("[rendered by:")
             and not ln.strip().startswith("[LLM validation failed")]
    return "\n".join(lines).strip()


#: Kept as a private alias: this module's older callers and tests name it.
_answer_body = answer_body


def _subject_ref(parse: dict, kind: str) -> Optional[str]:
    for s in parse.get("subjects", []) or []:
        if s.get("kind") == kind and s.get("ref"):
            return str(s["ref"])
    return None


#: Every R-EX2 key `check_expectation` must NOT try to read off a single turn.
_RELATIONAL_KEYS = frozenset(
    {"body_same_as", "body_differs_from", "records_from", "records"})


def check_expectation(turn: Any) -> list[Finding]:
    """Compare a turn against the EXPECT line that preceded it, if any.

    The ONLY machine-graded axis in a bank, and deliberately a narrow one: which
    intent the parse named, which typed subjects it bound, how it read the follow-up
    linkage, and where the dispatch sent it. Conversation quality stays Claude's and
    the founder's (R-AI4(2))."""
    expect = getattr(turn, "expect", None) or {}
    if not expect:
        return []
    parse = getattr(turn, "parse", None) or {}
    actual = {
        "intent": parse.get("intent"),
        "route": turn.route,
        "order": _subject_ref(parse, "order"),
        "machine": _subject_ref(parse, "machine"),
        "concept": _subject_ref(parse, "concept"),
        "followup": parse.get("followup_of"),
        "polarity": parse.get("polarity"),
        "clarify": parse.get("clarify"),
    }
    misses = []
    for key, want in expect.items():
        # R-EX2's relational keys reference an EARLIER TURN and are checked by
        # `check_relational`, which has the conversation in hand. Falling through
        # to `actual.get(key)` here would compare them against None and report a
        # miss on every relational expectation ever written.
        if key in _RELATIONAL_KEYS:
            continue
        got = actual.get(key)
        # "a|b" means either is acceptable; "-" means the field must be absent.
        options = [w.strip() for w in str(want).split("|")]
        ok = (got in (None, "", "none") if options == ["-"]
              else (str(got) in options))
        if not ok:
            misses.append(f"{key}: expected {want!r}, got {got!r}")
    if not misses:
        return []
    return [Finding("expect-miss", turn.lineno, turn.question, "; ".join(misses))]


#: R-EX2's relational keys, split by what they compare. Held here rather than
#: imported from `script` so this module stays a pure checker over finished
#: records; `script.TURN_REF_KEYS` is the PARSE-side copy and the two are pinned
#: to each other by a test.
_BODY_KEYS = ("body_same_as", "body_differs_from")


def check_relational(turn: Any, prior: list) -> list[Finding]:
    """R-EX2's relational expectations — the ones that reference an EARLIER TURN.

    Session 4A teaching-graft (d.2). Three measured inputs asked for these and no
    bank format could carry them: (d.1) §8, the shared-body census micro-session
    (5/5 passing on a product that rendered one body for two different questions),
    and (e) §8(f).

    ``prior`` is the CURRENT conversation's finished turns, oldest first; an index
    is 1-based into it. A reference the bank cannot resolve — a forward reference,
    an index past the conversation's length, an index into a turn that errored —
    is an ``expect-miss``, NOT a skip. A bank that grades nothing must never read
    like a bank that passed, and that is the failure mode this whole format was
    built because of.
    """
    expect = getattr(turn, "expect", None) or {}
    if not expect:
        return []
    misses: list[str] = []

    def _ref(key: str) -> Optional[Any]:
        """The referenced turn, or None with a miss recorded."""
        n = expect[key]
        if not isinstance(n, int) or n < 1:
            misses.append(f"{key}: {n!r} is not a 1-based turn index")
            return None
        if n > len(prior):
            misses.append(
                f"{key}: refers to turn {n}, but only {len(prior)} turn(s) "
                "precede this one in this conversation")
            return None
        ref = prior[n - 1]
        if getattr(ref, "error", None):
            misses.append(f"{key}: turn {n} failed, so it has nothing to compare")
            return None
        return ref

    for key in _BODY_KEYS:
        if key not in expect:
            continue
        ref = _ref(key)
        if ref is None:
            continue
        # AN EMPTY BODY HAS NO FINGERPRINT, and a relational claim about one is
        # UNEVALUABLE rather than true or false — the third-state discipline
        # this codebase has now applied at seven seams. Failing SAFE in BOTH
        # directions is the point: two empty answers are two defects, and
        # reading them as "the same answer" would let a pair of blank turns
        # satisfy the assertion that pins `deaf`'s premise.
        if not turn.body_sha or not ref.body_sha:
            which = "this turn" if not turn.body_sha else f"turn {expect[key]}"
            misses.append(
                f"{key}: {which} has an EMPTY body, so there is nothing to "
                "compare — an empty answer is a defect, not an answer")
            continue
        same = turn.body_sha == ref.body_sha
        want_same = key == "body_same_as"
        if same is not want_same:
            misses.append(
                f"{key}: turn {expect[key]} body {ref.body_sha[:12]}, this body "
                f"{turn.body_sha[:12]} — "
                + ("they differ" if want_same else "they are IDENTICAL"))

    if "records_from" in expect:
        ref = _ref("records_from")
        if ref is not None:
            mine, theirs = set(turn.record_ids or []), set(ref.record_ids or [])
            if not mine:
                # An empty set is a subset of everything. Grounding nothing is
                # not grounding correctly, and this is the exact hole R-EX2's
                # own note about RECORDS=0 names.
                misses.append(
                    f"records_from: this turn served NO records, so it did not "
                    f"come from turn {expect['records_from']}")
            elif not mine <= theirs:
                stray = sorted(mine - theirs)
                misses.append(
                    f"records_from: {len(stray)} of {len(mine)} record(s) are not "
                    f"in turn {expect['records_from']}'s answer "
                    f"(e.g. {stray[0][:12]})")

    if "records" in expect:
        want = expect["records"]
        if turn.record_count != want:
            misses.append(f"records: expected {want}, got {turn.record_count}")

    if not misses:
        return []
    return [Finding("expect-miss", turn.lineno, turn.question, "; ".join(misses))]


def check_synthesis(turn: Any) -> list[Finding]:
    """The second tier's mechanical tripwires (Session 4A.5b).

    ``failed-claim-rendered`` — a claim the verifier CUT appearing in the answer
    surface. By construction it cannot; this is the guard on that construction, and
    it is a truth-floor tripwire, not a quality read.
    ``ungrounded-load-bearing`` — the answer's own reasoning rested on something
    that could not be grounded. The answer is required to SAY so; the count is what
    a human reads, because a rising one means the tier is reaching past its
    evidence."""
    s = getattr(turn, "synthesis", None) or {}
    if not s:
        return []
    out: list[Finding] = []
    rendered = [c for c in (s.get("claims_detail") or [])
                if c.get("status") == "failed"]
    if rendered:
        out.append(Finding("failed-claim-rendered", turn.lineno, turn.question,
                           f"{len(rendered)} verifier-FAILED claim(s) reached the "
                           "answer surface"))
    n = int(s.get("ungrounded_load_bearing") or 0)
    if n:
        out.append(Finding("ungrounded-load-bearing", turn.lineno, turn.question,
                           f"{n} load-bearing claim(s) could not be grounded and "
                           "were cut"))
    return out


def check_shadow(turn: Any) -> list[Finding]:
    """The PROBATION signal (Session 4A.5c CU2c, R-AI5(7)).

    ``shadow-divergence`` — a promoted route's pre-computed fact CONTRADICTS a
    VERIFIED claim the synthesis tier made about the same evidence. This is the
    loud one: R-AI5(7) makes demotion automatic on divergence, so a finding of
    this kind is not a note to triage, it is the trigger. The flag flip itself is
    a committed edit to ``PROMOTIONS`` — a vocabulary that rewrote itself at
    runtime would be the router rewriting its own routing.

    ``shadow-unchecked`` — the shadow could not run (no synthesizer). Reported so
    a probation sweep with no key reads as UNCHECKED rather than as a clean
    window served."""
    s = getattr(turn, "shadow", None) or {}
    if not s:
        return []
    if s.get("unchecked"):
        return [Finding("shadow-unchecked", turn.lineno, turn.question,
                        "probation shadow did not run; this sweep does not "
                        "count toward the probation window")]
    contradicted = s.get("contradicted") or []
    if contradicted:
        return [Finding(
            "shadow-divergence", turn.lineno, turn.question,
            f"promoted route '{s.get('intent')}' contradicts the synthesis "
            f"shadow on {', '.join(contradicted)} — R-AI5(7): DEMOTE")]
    return []


def check_turn(turn: Any, vocab: Vocab,
               prior: Optional[list] = None) -> list[Finding]:
    """All mechanical findings for one finished turn.

    ``prior`` is the CURRENT conversation's earlier turns (oldest first), which
    R-EX2's relational expectations index into. Omitted, the relational checks
    simply have nothing to resolve against and every relational expectation
    misses — which is the honest reading: a caller with no conversation in hand
    cannot grade a claim about one."""
    findings: list[Finding] = []
    q = turn.question

    # 1 — the ask path itself failed.
    if turn.error:
        findings.append(Finding("exception", turn.lineno, q, turn.error))
        return findings  # nothing else is meaningful on a crashed turn

    # 2 — an empty answer body (the footer alone is not an answer).
    if not _answer_body(turn.answer):
        findings.append(Finding("empty", turn.lineno, q, "answer body is empty"))

    # 3 — an LLM testimony that failed validation and fell back / warned.
    # Session 4B.21 Item 5(a): the planner-visible verdict string is gone (it
    # was developer output on the answer surface) and the rendered-by tag was
    # renamed — "template (LLM validated)" read as though the model had
    # validated the answer when it meant the opposite. The old forms are kept
    # here so archived sweeps still parse; the live signal is the new tag.
    if ("LLM validation failed" in (turn.answer or "")
            or turn.renderer.startswith("template (model draft rejected)")
            or turn.renderer.startswith("template (LLM validated)")):
        findings.append(Finding(
            "validator", turn.lineno, q,
            "LLM testimony failed validation; fell back to template"))

    # 4 — an interpreted-as entity absent from the pinned document.
    for tok in vocab.absent_order_tokens(turn.resolved_question):
        findings.append(Finding(
            "absent-entity", turn.lineno, q,
            f"interpreted-as names '{tok}', absent from the pinned document"))

    # 5 — an evidence-shaped route that cited nothing (a dark lit-bars channel).
    if turn.route in EVIDENCE_ROUTES and turn.lit_bars == 0 and turn.record_count == 0:
        findings.append(Finding(
            "dark-evidence", turn.lineno, q,
            f"route '{turn.route}' cited 0 records and lit 0 bars"))

    # 7 — the bank's own graded expectation (Session 4A.5a CU3). ROUTING only: what
    # intent the parse named, what subjects it bound, where it dispatched. It never
    # grades prose (R-AI4(2)).
    findings.extend(check_expectation(turn))

    # 7b — R-EX2's relational expectations (Session 4A teaching-graft (d.2)):
    # body identity/distinctness by fingerprint, record-set provenance, and
    # record count. Still ROUTING-and-RELATIONS only; still never prose.
    findings.extend(check_relational(turn, prior or []))

    # 8 — the synthesis tier's own tripwires (Session 4A.5b CU5). Both are
    # truth-floor checks, not quality reads: a FAILED claim must never reach the
    # planner, and a cut claim that the answer's reasoning RESTED on must be said
    # out loud rather than papered over.
    findings.extend(check_synthesis(turn))

    # 9 — the PROBATION shadow (Session 4A.5c CU2c). A divergence here is the
    # demotion trigger, not a triage note.
    findings.extend(check_shadow(turn))

    # 6 — an invitation offering a door into a wall. Skipped (not passed) when no
    # parser is available: the honest state is "unchecked", never "clean".
    if vocab.door_check_available:
        for offered in offered_questions(turn.answer):
            if vocab.door_intent(offered) in ("unmatched", None):
                findings.append(Finding(
                    "dead-door", turn.lineno, q,
                    f'offered follow-up "{offered}" parses to no intent'))

    return findings
