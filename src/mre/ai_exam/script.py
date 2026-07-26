"""Question-script parsing (Session 4A.3b, CU1).

A question file is a CONVERSATION SCRIPT, not a flat list — its sequence is the
test. The format is deliberately spartan (the founder pastes plain text):

  * a blank line                     -> ignored
  * a line beginning ``#``           -> a comment (echoed into the transcript so a
                                        bank reads like prose)
  * ``SELECT order=ORD-05 machine=CUT-01``
                                     -> simulate a board selection feeding the
                                        selection channel the panel sends. Either
                                        slot may be omitted. Selecting an op sets
                                        BOTH (the panel derives work_orders[0] +
                                        resource_name from one bar).
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
  * anything else                    -> a question line

Directives are case-insensitive on the keyword; entity ids are preserved verbatim
(so typos in a regression bank survive). Parsing never raises on a malformed
directive line — a ``SELECT``/``RESET`` we cannot parse is reported as a parse
finding by the runner, never silently dropped.
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


ScriptItem = Union[Question, Select, Card, Reset, Comment, Expect]


_SELECT_KV = re.compile(r"(order|machine|op)\s*=\s*(\S+)", re.IGNORECASE)

# The graded-expectation keys (Session 4A.5a CU3). A closed set: an unknown key is
# a parse finding, never a silently ignored expectation.
EXPECT_KEYS = ("intent", "route", "order", "machine", "concept", "followup",
               "polarity", "clarify")
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
        if head == "EXPECT":
            rest = stripped[len("EXPECT"):].strip()
            fields, bad = {}, []
            for m in _EXPECT_KV.finditer(rest):
                key, val = m.group(1).lower(), m.group(2)
                if key in EXPECT_KEYS:
                    fields[key] = val
                else:
                    bad.append(key)
            if bad or not fields:
                out.parse_errors.append(
                    (i, raw, f"EXPECT with unknown key(s) {bad}" if bad
                     else "EXPECT with no recognized key"))
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
            found = False
            for m in _SELECT_KV.finditer(rest):
                found = True
                key, val = m.group(1).lower(), m.group(2)
                if key == "order":
                    order = val
                elif key == "machine":
                    machine = val
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
                    (i, raw, "SELECT with no order=/machine=/op= key"))
                continue
            out.items.append(Select(order=order, machine=machine, clear=False, lineno=i))
            continue
        # A plain question line.
        out.items.append(Question(text=stripped, lineno=i))
    return out
