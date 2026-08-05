"""Question-script parsing (Session 4A.3b, CU1).

A question file is a CONVERSATION SCRIPT, not a flat list — its sequence is the
test. The format is deliberately spartan (the founder pastes plain text):

  * a blank line                     -> ignored
  * a line beginning ``#``           -> a comment (echoed into the transcript so a
                                        bank reads like prose)
  * ``SELECT order=ORD-05 machine=CUT-01 seq=20``
                                     -> simulate a board selection feeding the
                                        selection channel the panel sends. Either
                                        slot may be omitted. Selecting an op sets
                                        BOTH (the panel derives work_orders[0] +
                                        resource_name from one bar). ``seq=`` is
                                        the OPERATION GRAIN the panel has sent
                                        since 4B.14 and this script could not
                                        express until the listening docket —
                                        without it the one channel that supplies
                                        a grain the planner did not type was
                                        unreachable from any exam.
  * ``SELECT clear`` / ``SELECT none``
                                     -> drop the board selection
  * ``CARD order=ORD-38 machine=MILL-01``
                                     -> a PRICED DELTA CARD is open on the board
                                        (Session 4B.5 CU2) — the top of the
                                        resolution ladder. The bank states the
                                        move; the runner synthesizes a plausible
                                        priced payload around it, because what a
                                        card bank grades is ROUTING (does the
                                        question reach `open-card`), never the
                                        figures, which the card itself supplies in
                                        the product.
  * ``CARD clear`` / ``CARD none``   -> the card was dismissed/accepted; the
                                        channel is empty again. A bank that opens
                                        a card and never closes it is testing the
                                        easy half.
  * ``RESET``                        -> clear ALL conversation state (history AND
                                        selection): many conversations per bank
  * ``REBIND rolling-c32a6140-b6b``  -> point the conversation at a DIFFERENT
                                        SCHEDULE mid-sequence (R-EX2, Session 4A
                                        teaching-graft (d.2)). It reproduces
                                        ``main.js::onVersionChange``, which is
                                        what fires after an accepted edit, a
                                        boundary move or a publish: rebind the
                                        schedule, clear the board selection,
                                        TOUCH NOTHING ELSE. History, the
                                        last-answered subject, the open card and
                                        the session id all survive, by design —
                                        which is precisely the shape a
                                        cross-version bank has to be able to
                                        express. Requires the runner to know a
                                        data root; without one the rebind is a
                                        loud finding and the run STOPS, never a
                                        silent continuation against the old
                                        world.
  * ``EXPECT intent=advice order=ORD-13 route=advice``
                                     -> the GRADED EXPECTATION for the NEXT question
                                        (Session 4A.5a CU3). Any subset of
                                        ``intent`` / ``route`` / ``order`` /
                                        ``machine`` / ``concept`` / ``followup`` /
                                        ``polarity`` / ``clarify`` may be given;
                                        each is compared to what the parse and the
                                        dispatch actually produced, and a mismatch
                                        is an ``expect-miss`` finding. This is the
                                        only machine-graded part of a bank — it
                                        grades ROUTING, never conversation
                                        (R-AI4(2)).

                                        R-EX2 adds four RELATIONAL keys, which
                                        reference an EARLIER TURN BY INDEX
                                        (1-based, within the CURRENT
                                        conversation — ``RESET`` restarts the
                                        numbering, because a reference across a
                                        reset would name a turn the bank has
                                        already thrown away):

                                          ``BODY_SAME_AS=2``      this answer's
                                          ``BODY_DIFFERS_FROM=2`` body is / is not
                                              byte-identical to turn 2's, by
                                              fingerprint over the answer body
                                              with its ``[rendered by: …]`` footer
                                              stripped.
                                          ``RECORDS_FROM=1``  this turn's records
                                              came from turn 1's answer: a
                                              NON-EMPTY record set, every id of
                                              which turn 1 also served. Non-empty
                                              is load-bearing — an empty set is a
                                              subset of everything, and "opened
                                              nothing" must never read as
                                              "grounded correctly".
                                          ``RECORDS=0``  this turn served exactly
                                              N records. With a route expectation
                                              beside it this is what separates
                                              "opened nothing" from "opened the
                                              wrong thing".
  * anything else                    -> a question line

**BANKS GRADE ROUTES AND RELATIONS; BODIES BELONG TO TESTS** (R-EX2 clause 3).
There is no way to assert PROSE in this grammar and there will not be one:
``EXPECT_KEYS`` is a closed set and an unrecognised key is a parse finding, so
the division is enforced rather than merely stated. A string assertion against
authored copy in a bank is a weaker duplicate of a unit test that breaks on
every legitimate copy edit — body CONTENT is guard-file territory
(``tests/test_*.py``), body IDENTITY and DISTINCTNESS are a bank's business.

Directives are case-insensitive on the keyword; entity ids are preserved verbatim
(so typos in a regression bank survive). Parsing never raises on a malformed
directive line — a ``SELECT``/``RESET``/``REBIND`` we cannot parse is reported as
a parse finding by the runner, never silently dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class Question:
    """A question line, fired through the ask path with the live state."""
    text: str
    lineno: int


@dataclass
class Select:
    """A simulated board selection. ``order``/``machine`` are external refs (or
    None to leave that slot unchanged is NOT supported — Select always REPLACES the
    selection; an omitted slot is None). ``clear`` drops the selection entirely."""
    order: Optional[str]
    machine: Optional[str]
    clear: bool
    lineno: int
    #: WHICH OPERATION of the order the bar belongs to (the listening docket).
    #: The cockpit's selection has carried `op_seq` since 4B.14 and the bank
    #: could not express it, so the one channel that supplies an operation
    #: grain WITHOUT the planner typing it was unreachable from an exam — which
    #: is why S2's specimen ("why cant this be moved" with a bar selected) had
    #: to be measured by hand against the live API. Written `seq=20`.
    op_seq: Optional[int] = None


@dataclass
class Card:
    """A PRICED DELTA CARD open on the board (Session 4B.5 CU2) — the top of the
    resolution ladder. ``clear`` closes it (dismissed / accepted / returned home);
    a bank that never closes one is testing the easy half."""
    order: Optional[str]
    machine: Optional[str]
    clear: bool
    lineno: int


@dataclass
class Reset:
    """Clear all conversation state — a fresh conversation starts on the next line."""
    lineno: int


@dataclass
class Rebind:
    """Point the conversation at a different SCHEDULE, mid-sequence (R-EX2).

    `main.js::onVersionChange` in one directive: the board changes underneath a
    live conversation and only the SELECTION is cleared. A bank that wants to
    grade what happens across a version boundary has to be able to say this;
    before R-EX2 no bank format could, so no committed bank has ever crossed
    one and the (d.0) recon had to drive the seam by hand."""
    schedule: str
    lineno: int


@dataclass
class Expect:
    """The graded expectation for the NEXT question (Session 4A.5a CU3). Only the
    keys present are checked; everything absent is unconstrained."""
    fields: dict
    lineno: int


@dataclass
class Comment:
    """A ``#`` line, echoed into the transcript so a bank reads as prose."""
    text: str
    lineno: int


ScriptItem = Union[Question, Select, Card, Reset, Rebind, Comment, Expect]


_SELECT_KV = re.compile(r"(order|machine|seq|op)\s*=\s*(\S+)", re.IGNORECASE)

# The graded-expectation keys (Session 4A.5a CU3). A closed set: an unknown key is
# a parse finding, never a silently ignored expectation — and, since R-EX2, the
# thing that makes "no prose assertions in banks" enforced rather than advisory.
EXPECT_KEYS = ("intent", "route", "order", "machine", "concept", "followup",
               "polarity", "clarify",
               # R-EX2's relational forms (Session 4A teaching-graft (d.2)).
               "body_same_as", "body_differs_from", "records_from", "records")

#: The three that name an EARLIER TURN and must therefore be a 1-based index.
TURN_REF_KEYS = ("body_same_as", "body_differs_from", "records_from")
#: The one that names a COUNT — zero is meaningful and must be allowed.
COUNT_KEYS = ("records",)

_EXPECT_KV = re.compile(r"([a-z_]+)\s*=\s*(\S+)", re.IGNORECASE)


@dataclass
class ParsedScript:
    items: list[ScriptItem] = field(default_factory=list)
    # (lineno, raw, reason) for directive lines that did not parse — surfaced by
    # the runner as parse findings, never silently dropped.
    parse_errors: list[tuple[int, str, str]] = field(default_factory=list)


def parse_script(text: str) -> ParsedScript:
    out = ParsedScript()
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            out.items.append(Comment(text=stripped.lstrip("# ").rstrip(), lineno=i))
            continue
        head = stripped.split(None, 1)[0].upper()
        if head == "RESET":
            out.items.append(Reset(lineno=i))
            continue
        if head == "REBIND":
            rest = stripped[len("REBIND"):].strip()
            # One bare token: a schedule id. An empty or multi-token argument is
            # a parse finding — a REBIND we half-understood would grade the
            # wrong world, which is worse than not running.
            if not rest or len(rest.split()) != 1:
                out.parse_errors.append(
                    (i, raw, "REBIND takes exactly one schedule id"))
                continue
            out.items.append(Rebind(schedule=rest, lineno=i))
            continue
        if head == "EXPECT":
            rest = stripped[len("EXPECT"):].strip()
            fields, bad, malformed = {}, [], []
            for m in _EXPECT_KV.finditer(rest):
                key, val = m.group(1).lower(), m.group(2)
                if key not in EXPECT_KEYS:
                    bad.append(key)
                    continue
                # R-EX2: the relational keys are NUMBERS, and an unreadable one
                # is a finding rather than a silently dropped expectation — a
                # bank that thinks it is grading turn 2 and is grading nothing
                # reads exactly like a bank that passed.
                if key in TURN_REF_KEYS or key in COUNT_KEYS:
                    try:
                        n = int(val)
                    except ValueError:
                        malformed.append(f"{key}={val!r} is not a number")
                        continue
                    floor = 1 if key in TURN_REF_KEYS else 0
                    if n < floor:
                        malformed.append(
                            f"{key}={val!r} must be >= {floor}"
                            + (" (turn indexes are 1-based)"
                               if key in TURN_REF_KEYS else ""))
                        continue
                    fields[key] = n
                    continue
                fields[key] = val
            if bad or malformed or not fields:
                reason = (f"EXPECT with unknown key(s) {bad}" if bad
                          else "; ".join(malformed) if malformed
                          else "EXPECT with no recognized key")
                out.parse_errors.append((i, raw, reason))
                continue
            out.items.append(Expect(fields=fields, lineno=i))
            continue
        if head == "CARD":
            rest = stripped[len("CARD"):].strip()
            if rest.lower() in ("clear", "none", "off", "dismissed", "accepted"):
                out.items.append(Card(order=None, machine=None, clear=True, lineno=i))
                continue
            order = machine = None
            found = False
            for m in _SELECT_KV.finditer(rest):
                found = True
                key, val = m.group(1).lower(), m.group(2)
                if key == "order":
                    order = val
                elif key == "machine":
                    machine = val
            if not found:
                out.parse_errors.append(
                    (i, raw, "CARD with no order=/machine= key"))
                continue
            out.items.append(Card(order=order, machine=machine, clear=False, lineno=i))
            continue
        if head == "SELECT":
            rest = stripped[len("SELECT"):].strip()
            if rest.lower() in ("clear", "none", "off"):
                out.items.append(Select(order=None, machine=None, clear=True, lineno=i))
                continue
            order = machine = None
            op_seq: Optional[int] = None
            found = False
            for m in _SELECT_KV.finditer(rest):
                found = True
                key, val = m.group(1).lower(), m.group(2)
                if key == "order":
                    order = val
                elif key == "machine":
                    machine = val
                elif key == "seq":
                    # The OPERATION GRAIN (the listening docket). Unreadable is
                    # None and is reported as a parse error rather than
                    # silently dropped — a bank that thinks it selected op20
                    # and did not would grade the wrong bar.
                    try:
                        op_seq = int(val)
                    except ValueError:
                        out.parse_errors.append(
                            (i, raw, f"SELECT seq= is not a number: {val!r}"))
                elif key == "op":
                    # An op selection sets both slots when written ord@machine;
                    # a bare op= with no '@' sets neither honestly (we cannot
                    # resolve op -> order/machine without the document).
                    if "@" in val:
                        o, _, mm = val.partition("@")
                        order = order or (o or None)
                        machine = machine or (mm or None)
            if not found:
                out.parse_errors.append(
                    (i, raw, "SELECT with no order=/machine=/op=/seq= key"))
                continue
            out.items.append(Select(order=order, machine=machine, clear=False,
                                    lineno=i, op_seq=op_seq))
            continue
        # A plain question line.
        out.items.append(Question(text=stripped, lineno=i))
    return out
