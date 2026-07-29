"""CAPABILITY ANSWERS, GROUNDED IN docs/05 (Session 4B.15 Item 5).

THE MEASURED FAILURE. "can two machines share one operator" came back a
confident YES describing ALTERNATES, carrying the label
``[synthesis — my reading, no record states this]``. The provenance machinery
worked exactly as designed and the falsehood shipped anyway.

LABELING IS NOT SUFFICIENT WHERE THE CLAIM IS WHAT THE PRODUCT CAN DO. Every
other synthesis claim is a reading of THIS BOARD, and a planner who distrusts it
can look at the board. A capability claim is different in kind: the planner acts
on it by authoring data — declaring an operator pool that no adapter reads, no
gate checks and no solver weighs — and the schedule comes back with the
constraint silently absent. There is no board to check that against.

So: a capability claim GROUNDS IN docs/05 OR IS REFUSED. That is a DOCUMENT
LOOKUP, not a judgment call, and this module is the lookup. Everything ABOVE the
lookup — inference, interpretation, what it means on this board, whether it is
worth doing — runs free in the second tier and gets labeled as always. The floor
applies only where the answer is written down.

THE VERB IS THE ANSWER (4B.14's rule, applied here). ``LEAD`` is authored copy
keyed by the derived register, and the words are chosen so a planner learns the
DISPOSITION from the first clause and the detail only sharpens it. A reword that
softens "not today" into "not currently supported out of the box" is the failure
this exists to end.

WHAT IS AUTHORED AND WHAT IS READ
----------------------------------
Authored here: the LEAD per register, the sentence frames, and the topic map in
``constraint_catalog`` (which authors WHICH RECORDS to read, never a claim).
Read from docs/05: the verdict, the plane, the proof status verbatim, the IDS
doorway, the locked rulings, the exclusions and their approximation guidance.
Nothing composes a capability fact that the catalog does not state.

AGREEMENT WITH THE BLOCKER ANALYSIS IS ASSERTED, NOT HOPED FOR. 4B.14's
``UNCOMPUTED_FAMILIES`` names B3/B5, B7/B8, C4 and F3 as families it cannot
weigh. When a capability answer is about one of those, it says so in the same
words — and ``tests/test_capability_answer.py`` asserts the two surfaces cannot
drift apart. That is the specific contradiction that shipped in one session: the
blocker analysis saying "operator pools: not weighed" while synthesis said yes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mre.modules.blocker_analysis import UNCOMPUTED_FAMILIES
from mre.modules.capabilities import CapabilityNote, note_for_concept
from mre.modules.constraint_catalog import (
    CatalogItem, Grounding, Register, REGISTER_MEANING, ground,
)

#: THE LEAD, per register. The first clause carries the disposition.
LEAD: dict[Register, str] = {
    Register.PROVEN:
        "Yes — the system models this today, and it has been proven end to end.",
    Register.PARTIAL:
        "Partly, and the part matters — one case of this goes end to end today "
        "and the rest is designed but not built. The catalog's status line "
        "below says which is which.",
    Register.MODELED_UNPROVEN:
        "Not today. The model carries the shape, but nothing in the pipeline "
        "does — you cannot declare it and the scheduler does not weigh it.",
    Register.NOT_BUILT:
        "No, not yet. The shape is designed and reserved; nothing is built, so "
        "there is nothing to declare and nothing that would read it.",
    Register.EXCLUDED:
        "No — this is deliberately outside what the system models.",
    Register.UNKNOWN:
        "I can't answer that from the constraint catalog.",
}

#: The families 4B.14's blocker analysis reports it cannot weigh, keyed by the
#: catalog ids they cover. Derived from ``UNCOMPUTED_FAMILIES`` so the two
#: surfaces cannot state different things about the same item.
_UNCOMPUTED_BY_ITEM: dict[str, str] = {}
for _fam, _why in UNCOMPUTED_FAMILIES:
    for _part in _fam.split("/"):
        _UNCOMPUTED_BY_ITEM[_part.strip().upper()] = _why
# ``B3/B5`` names two catalog ids; ``B7/B8`` is ONE id spelled with a slash.
_UNCOMPUTED_BY_ITEM["B7/B8"] = dict(UNCOMPUTED_FAMILIES)["B7/B8"]


@dataclass(frozen=True)
class CapabilityAnswer:
    """One grounded capability answer. Every string here is either authored copy
    or a value read from docs/05 — never a composed capability fact."""

    question: str
    register: Register
    lead: str
    #: One sentence per catalog record consulted, each quoting the row.
    catalog_lines: tuple[str, ...] = ()
    #: The locked rulings that govern the mechanism, quoted.
    ruling_lines: tuple[str, ...] = ()
    #: Exclusions with their approximation-and-limits guidance, quoted.
    exclusion_lines: tuple[str, ...] = ()
    #: What the scheduler does NOT weigh, in the blocker analysis's own words.
    not_weighed: tuple[str, ...] = ()
    #: The how-to, present ONLY when the catalog says it is declarable today.
    how: str = ""
    how_ref: str = ""
    citations: tuple[str, ...] = ()
    #: The topic key that bound, for the ledger and the tests.
    topic: str = ""

    @property
    def grounded(self) -> bool:
        return self.register is not Register.UNKNOWN


def _catalog_line(item: CatalogItem) -> str:
    """One catalog row as a sentence. The STATUS is quoted verbatim — a mixed
    status like ``PP (single-attr) / UI (multi-attr)`` must reach the planner
    with its qualification intact, not flattened to a token."""
    real = item.real_doorways
    door = item.doorway.strip()
    if real:
        door_txt = "declared at docs/06 " + "/".join(real)
        if "§8" in door:
            door_txt += " for that case; the rest has no doorway yet"
    elif "§8" in door:
        # docs/06 §8 is the DEMAND-DRIVEN doorway process: a doorway that does
        # not exist until a submission needs it. Saying "§8" to a planner would
        # read as a section they could go and fill in.
        door_txt = (f"no doorway exists yet ({door} — docs/06 §8 is the process "
                    "for adding one when a plant demands it)")
    else:
        door_txt = "no submission doorway"
    status_txt = (f"proof status {item.status_raw}, "
                  if item.status_raw and item.status_raw not in {"—", "-", ""}
                  else "")
    line = (f"{item.item_id} {item.name}: verdict {item.verdict.value}, "
            f"{status_txt}{door_txt}.")
    if item.approximation:
        line += f" What we offer instead — {item.approximation}"
    return line


def _how_from_note(note: Optional[CapabilityNote]) -> tuple[str, str]:
    if note is None:
        return "", ""
    return note.how, note.ids_ref


def answer(question: str, concept: Optional[str] = None) -> Optional[CapabilityAnswer]:
    """The grounded capability answer for a question, or None.

    None means the catalog names nothing that fits — and per Item 5 the caller
    must then REFUSE rather than reason its way to a capability claim. It is the
    honest floor, not a failure."""
    g = ground(question)
    if g is None:
        return None

    register = g.register
    catalog_lines = tuple(_catalog_line(i) for i in g.items)
    ruling_lines = tuple(
        f"{r.ruling_id} — {r.title}. {_first_sentence(r.text)}"
        for r in g.rulings)
    exclusion_lines = tuple(
        f"{e.name}: {e.text}" for e in g.exclusions)
    # Deduped by the REASON, not the item id: B3 and B5 are two catalog rows of
    # one blocker-analysis family and printing its sentence twice reads as two
    # separate gaps.
    seen_why: set[str] = set()
    weighed: list[str] = []
    for i in g.items:
        why = _UNCOMPUTED_BY_ITEM.get(i.item_id.upper())
        if why and why not in seen_why:
            seen_why.add(why)
            weighed.append(f"{i.item_id} — {why}")
    not_weighed = tuple(weighed)

    # The HOW-TO rides along ONLY when the catalog says the capability is
    # declarable today. Coaching a planner to fill in a column for something
    # that is model-proven-only is exactly how they author data that is
    # silently ignored — the harm this module exists to prevent.
    how, how_ref = "", ""
    if g.declarable:
        how, how_ref = _how_from_note(note_for_concept(concept))

    return CapabilityAnswer(
        question=question, register=register, lead=LEAD[register],
        catalog_lines=catalog_lines, ruling_lines=ruling_lines,
        exclusion_lines=exclusion_lines, not_weighed=not_weighed,
        how=how, how_ref=how_ref,
        citations=tuple(g.citations()), topic=g.topic.key)


def _first_sentence(text: str) -> str:
    """The opening sentence of a quoted ruling — enough to carry the mechanism,
    short enough to belong in an answer. Quoted, never paraphrased."""
    # docs/05 is markdown; a quoted ruling must arrive as prose, not as source.
    flat = " ".join(text.split())
    flat = flat.replace("**", "").replace("`", "").lstrip("- ").strip()
    for stop in (". ", "; "):
        if stop in flat:
            head = flat.split(stop)[0]
            if len(head) > 40:
                return head + "."
    return flat[:300] + ("..." if len(flat) > 300 else "")


def render(ans: CapabilityAnswer) -> str:
    """The planner-facing rendering. Deterministic and authored: no model sees
    this text before the planner does, which is what makes the floor a floor."""
    lines = [ans.lead, ""]
    if ans.catalog_lines:
        lines.append("What the constraint catalog says:")
        lines += [f"  - {ln}" for ln in ans.catalog_lines]
        lines.append("")
    if ans.ruling_lines:
        for ln in ans.ruling_lines:
            lines.append(ln)
        lines.append("")
    if ans.exclusion_lines:
        lines.append("Excluded by ruling, with the approximation we do offer:")
        lines += [f"  - {ln}" for ln in ans.exclusion_lines]
        lines.append("")
    if ans.not_weighed:
        lines.append("And when I explain why an operation sits where it does, "
                     "this is one of the things I do not weigh:")
        lines += [f"  - {ln}" for ln in ans.not_weighed]
        lines.append("")
    if ans.register not in (Register.PROVEN, Register.PARTIAL) and not ans.how:
        meaning = REGISTER_MEANING[ans.register]
        lines.append(meaning[:1].upper() + meaning[1:] + ".")
        lines.append("")
    if ans.how:
        lines.append(f"To declare it: {ans.how}. See the incoming-data spec "
                     f"{ans.how_ref}.")
        lines.append("")
    lines.append("Sources: " + "; ".join(ans.citations))
    return "\n".join(lines).strip()
