"""THE CONSTRAINT CATALOG, AS RECORDS (Session 4B.15 Item 5).

docs/05 §0 says it in as many words: "**Form:** structured records first; prose
is rendered from them (assembly-then-render, the house principle)." The records
were never built, so the catalog shipped as its own rendering and CLAUDE.md has
carried "the docs/05 structured-constraint surface (prose-locked, retrieval must
never read prose)" as a named AI-track debt ever since.

This module reads the catalog's own MARKDOWN TABLES back into records. That is
not "retrieval reading prose" — a table is structure, and every column docs/05
declares (verdict, plane, coverage, input contract, test triad, status, IDS
doorway) becomes a field. The surrounding PROSE (the locked rulings, the
approximation-and-limits notes, the global exclusions) is carried VERBATIM and
quoted, never parsed for meaning.

WHY THIS IS THE GROUND FOR A CAPABILITY CLAIM
----------------------------------------------
"can two machines share one operator" was answered YES, describing ALTERNATES
(B2: one operation eligible on several machines) — a different mechanism, on a
board where the blocker analysis was simultaneously and correctly reporting
"B3/B5 secondary and cumulative resources (tools, operator pools)" as a family
it does not weigh. Both sentences shipped in one session.

The catalog answers it exactly, and the answer needs THREE of its columns, not
one:

    B3  multi-resource set-with-roles   verdict core   status MP   doorway §8
    B5  cumulative secondary resources  verdict core   status MP   doorway §5.5
    R-B3 (locked ruling)  operators are calendar-bearing POOLS, never individuals
    Global exclusion      individual operator rostering is OUT

So: the MODEL carries it, it is NOT pipeline-proven, the roles doorway is a §8
doorway that does not exist yet, and named individuals are excluded by ruling.
A YES is wrong, a flat NO is wrong, and the true answer is only expressible if
the VERDICT and the STATUS are separate fields — which is precisely what a
nine-entry authored registry could never carry.

THE HONESTY REGISTER IS DERIVED, NOT AUTHORED TWICE
----------------------------------------------------
``Register`` is a pure function of (verdict, status). Nobody writes "this one is
aspirational" beside a catalog row; the row already says so and the register
reads it. When someone moves a status column from MP to PP in docs/05 and
rebuilds the index, every answer about that item changes with it.

Where a status is MIXED — B7/B8 is literally ``PP (single-attr) / UI
(multi-attr)`` — the register takes the WEAKEST token present and the answer
QUOTES THE RAW STRING. Understating a capability is the safe direction to be
wrong in; overstating one is how a planner authors data that is silently
ignored.

STATUS HONESTY IS THE CATALOG'S OWN ACCEPTANCE GATE (docs/05 §3.5): "PP only
with the full docs/06 §8 chain; MP and UI are respectable, tracked states — the
column exists so nothing hides between 'the model supports it' and 'the system
has ever done it.'" This module is what makes that column reach a planner.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mre.modules.corpus import Corpus, CorpusTier, load_corpus


class Verdict(str, Enum):
    """docs/05's own three verdicts."""

    CORE = "in-core"                 # the catalog's ✔core
    SLOT = "in-later-modular-slot"   # ◐slot
    OUT = "out"                      # ✘out
    UNKNOWN = "unknown"


class Status(str, Enum):
    """docs/05's proof ladder. PP is the only one that means the system has ever
    actually done it end to end."""

    PIPELINE_PROVEN = "PP"
    MODEL_PROVEN = "MP"
    UNIMPLEMENTED = "UI"
    UNKNOWN = "?"


#: Weakest first. A mixed status resolves to the weakest token present.
_STATUS_ORDER = (Status.UNIMPLEMENTED, Status.MODEL_PROVEN,
                 Status.PIPELINE_PROVEN)


class Register(str, Enum):
    """The honesty register an answer speaks in. Derived from (verdict, status);
    never authored per item."""

    #: Modeled and proven through the full docs/06 §8 chain.
    PROVEN = "proven"
    #: SOME CASE of it is pipeline-proven and the rest is not. B7/B8 is the live
    #: specimen: ``PP (single-attr) / UI (multi-attr)`` — single-attribute setup
    #: families go end to end through `setup_transitions.csv`, the generalized
    #: multi-attribute table is unbuilt. Collapsing that to either token is a
    #: lie in one direction or the other, so it gets its own register and the
    #: answer quotes the qualification.
    PARTIAL = "partly-proven"
    #: The model carries it; NOT proven through the pipeline. Often no doorway.
    MODELED_UNPROVEN = "modeled-unproven"
    #: Shape blessed, nothing built.
    NOT_BUILT = "not-built"
    #: Deliberately excluded, with approximation guidance.
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


#: What each register MEANS to a planner, in one sentence. Authored copy, keyed
#: by a derived value — the same discipline ``ask_fallback_copy`` uses.
REGISTER_MEANING: dict[Register, str] = {
    Register.PROVEN:
        "modeled and proven end to end — declared in a submission, honored by "
        "the solver, and asserted by a test on generated data",
    Register.PARTIAL:
        "one case of it is proven end to end and the rest is not; the catalog's "
        "own status line says which, and that distinction is the answer",
    Register.MODELED_UNPROVEN:
        "the model carries it, but it has NOT been proven through the pipeline: "
        "no submission has ever declared it and no schedule has ever been "
        "asserted against it. Treat it as unavailable until it is",
    Register.NOT_BUILT:
        "the shape is designed and reserved, and nothing is built. It cannot be "
        "declared and the solver would not read it",
    Register.EXCLUDED:
        "deliberately NOT modeled — an exclusion, with documented approximation "
        "guidance rather than a gap",
    Register.UNKNOWN:
        "the catalog carries no readable verdict for this item",
}


@dataclass(frozen=True)
class CatalogItem:
    """One row of the docs/05 catalog, as a record."""

    item_id: str                  # "B3"
    category: str                 # "Category B — Resources & requirements"
    name: str                     # "Multi-resource set-with-roles"
    verdict: Verdict
    plane: str                    # "S" | "D" | "O" | ""
    verdict_raw: str
    coverage: str
    input_contract: str
    test_triad: str
    status: Status
    status_raw: str               # quoted verbatim; "PP (single-attr) / UI (multi-attr)"
    doorway: str
    #: Every proof token the cell carries. More than one ⇒ a MIXED status.
    status_tokens: frozenset = field(default_factory=frozenset)
    #: The item's "approximation & limits" paragraph, verbatim, where docs/05
    #: writes one. Exclusions are product statements, not gaps — the guidance is
    #: the substance of the answer and must travel with the No.
    approximation: str = ""

    @property
    def mixed_status(self) -> bool:
        return len(self.status_tokens) > 1

    @property
    def register(self) -> Register:
        if self.verdict is Verdict.OUT:
            return Register.EXCLUDED
        if self.verdict is Verdict.UNKNOWN:
            return Register.UNKNOWN
        if self.mixed_status and Status.PIPELINE_PROVEN in self.status_tokens:
            return Register.PARTIAL
        return {Status.PIPELINE_PROVEN: Register.PROVEN,
                Status.MODEL_PROVEN: Register.MODELED_UNPROVEN,
                Status.UNIMPLEMENTED: Register.NOT_BUILT,
                Status.UNKNOWN: Register.UNKNOWN}[self.status]

    @property
    def real_doorways(self) -> list[str]:
        """The § doorways that EXIST. ``§8`` is docs/06's name for a
        demand-driven doorway that does not exist until a plant asks for one, so
        it is never a place a planner can go and declare something."""
        return [seg.strip() for seg in re.split(r"[;/]", self.doorway or "")
                if "§" in seg and "§8" not in seg]

    @property
    def declarable(self) -> bool:
        """Can a planner declare this in a submission TODAY? A proven (or
        partly-proven) item with at least one doorway that actually exists."""
        return (self.register in (Register.PROVEN, Register.PARTIAL)
                and bool(self.real_doorways))

    def cite(self) -> str:
        return f"docs/05 catalog {self.item_id} ({self.name})"


@dataclass(frozen=True)
class Ruling:
    """A locked ruling from docs/05 §1, carried verbatim."""

    ruling_id: str      # "R-B3"
    title: str
    text: str

    def cite(self) -> str:
        return f"docs/05 §1 {self.ruling_id}"


@dataclass(frozen=True)
class Exclusion:
    """A global exclusion from docs/05, carried verbatim with its approximation
    and limits — which is the product statement, not a gap."""

    name: str
    text: str

    def cite(self) -> str:
        return "docs/05 Global exclusions"


@dataclass(frozen=True)
class CatalogView:
    """The parsed catalog. Immutable; built once from the corpus index."""

    items: tuple[CatalogItem, ...] = ()
    rulings: tuple[Ruling, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()
    notes: tuple[str, ...] = ()      # the approximation & limits paragraphs

    def by_id(self, item_id: str) -> Optional[CatalogItem]:
        key = item_id.strip().upper()
        return next((i for i in self.items if i.item_id.upper() == key), None)

    def ruling(self, ruling_id: str) -> Optional[Ruling]:
        key = ruling_id.strip().upper()
        return next((r for r in self.rulings if r.ruling_id.upper() == key), None)


# ---------------------------------------------------------------------------
# Parsing the catalog tables
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_ITEM_ID_RE = re.compile(r"^[A-H]\d+(?:/[A-H]?\d+)?$")
#: ``### R-B3 — ...`` and ``### R-Dwell (corollary) — ...``. Matched on the
#: heading alone: no other ``###`` in docs/05 begins with ``R-``, so this needs
#: no section tracking — and section tracking is exactly what broke here, since
#: ``## 1. Locked rulings`` carries no body text and therefore emits no passage.
_RULING_RE = re.compile(
    r"^(R-[A-Za-z0-9/]+)\s*(?:\([^)]*\))?\s*[—–-]\s*(.*)$")

_VERDICT_MARKS = ((("✔", "core"), Verdict.CORE),
                  (("◐", "slot"), Verdict.SLOT),
                  (("✘", "out"), Verdict.OUT))


def _parse_verdict(cell: str) -> tuple[Verdict, str]:
    low = cell.lower()
    for marks, verdict in _VERDICT_MARKS:
        if any(m in cell or m in low for m in marks):
            return verdict, cell
    return Verdict.UNKNOWN, cell


def _parse_plane(cell: str) -> str:
    m = re.search(r"\*\*([SDO])\*\*|(?<![A-Za-z])([SDO])(?![A-Za-z])", cell)
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").upper()


def _parse_status(cell: str) -> tuple[Status, str, frozenset]:
    """The WEAKEST proof token present, the raw cell, and EVERY token found.

    Weakest-wins because understating a capability is the safe direction to be
    wrong in. But the full token set travels too: a cell reading ``PP
    (single-attr) / UI (multi-attr)`` is not honestly summarized by either
    token, and flattening it to UI would tell a planner that setup families are
    unbuilt when `setup_transitions.csv` is pipeline-proven."""
    found = frozenset(Status(t) for t in ("PP", "MP", "UI")
                      if re.search(rf"(?<![A-Za-z]){t}(?![A-Za-z])", cell))
    if not found:
        return Status.UNKNOWN, cell.strip(), found
    for s in _STATUS_ORDER:
        if s in found:
            return s, cell.strip(), found
    return Status.UNKNOWN, cell.strip(), found


def _cells(line: str) -> Optional[list[str]]:
    m = _ROW_RE.match(line.strip())
    if not m:
        return None
    return [c.strip() for c in m.group(1).split("|")]


def parse_catalog(text: str) -> CatalogView:
    """docs/05's full text → records. Pure; no I/O."""
    items: list[CatalogItem] = []
    rulings: list[Ruling] = []
    exclusions: list[Exclusion] = []
    notes: list[str] = []

    category = ""
    section = ""
    ruling_head: Optional[tuple[str, str]] = None
    ruling_buf: list[str] = []
    in_exclusions = False

    def _flush_ruling() -> None:
        if ruling_head and ruling_buf:
            rulings.append(Ruling(ruling_head[0], ruling_head[1],
                                  "\n".join(ruling_buf).strip()))

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            _flush_ruling()
            ruling_head, ruling_buf = None, []
            section = stripped[3:].strip()
            in_exclusions = section.lower().startswith("global exclusions")
            continue
        if stripped.startswith("### "):
            _flush_ruling()
            ruling_head, ruling_buf = None, []
            head = stripped[4:].strip()
            in_exclusions = head.lower().startswith("global exclusions")
            m = _RULING_RE.match(head)
            if m:
                ruling_head = (m.group(1), m.group(2).strip())
            elif head.lower().startswith("category"):
                category = head
            continue

        if ruling_head is not None:
            ruling_buf.append(line)
            continue

        # The global-exclusion bullets, verbatim.
        if in_exclusions and stripped.startswith("- **"):
            m = re.match(r"^-\s+\*\*(.+?)\*\*\s*[—-]?\s*(.*)$", stripped)
            if m:
                exclusions.append(Exclusion(m.group(1).strip(), m.group(2).strip()))
            continue

        # The approximation & limits paragraphs, verbatim. docs/05 writes them
        # as "**B9 approximation & limits:** ..." — the leading id is what binds
        # the guidance to its row, so an exclusion's No arrives with the thing
        # we DO offer instead.
        if stripped.startswith("**") and "approximation & limits" in stripped.lower():
            notes.append(stripped)
            continue

        cells = _cells(line)
        if not cells or len(cells) < 8:
            continue
        if not _ITEM_ID_RE.match(cells[0]):
            continue          # header row, separator row, or a legend
        verdict, verdict_raw = _parse_verdict(cells[2])
        status, status_raw, tokens = _parse_status(cells[6])
        items.append(CatalogItem(
            item_id=cells[0], category=category, name=cells[1],
            verdict=verdict, plane=_parse_plane(cells[2]),
            verdict_raw=verdict_raw, coverage=cells[3],
            input_contract=cells[4], test_triad=cells[5],
            status=status, status_raw=status_raw, doorway=cells[7],
            status_tokens=tokens))

    _flush_ruling()
    # Bind each "**<id> approximation & limits:** ..." paragraph to its row.
    notes_by_id: dict[str, str] = {}
    for note in notes:
        m = re.match(r"^\*\*([A-H]\d+(?:/[A-H]?\d+)?)\s+approximation", note)
        if m:
            notes_by_id[m.group(1).upper()] = re.sub(r"^\*\*.*?:\*\*\s*", "",
                                                     note).strip()
    if notes_by_id:
        items = [
            CatalogItem(**{**vars(i),
                           "approximation": notes_by_id.get(i.item_id.upper(), "")})
            if i.item_id.upper() in notes_by_id else i
            for i in items
        ]
    return CatalogView(tuple(items), tuple(rulings), tuple(exclusions),
                       tuple(notes))


# ---------------------------------------------------------------------------
# Loading, and the topic map
# ---------------------------------------------------------------------------

_VIEW: Optional[CatalogView] = None


def load_catalog(corpus: Optional[Corpus] = None) -> CatalogView:
    """The catalog, reassembled from the corpus index's docs/05 passages.

    Returns an EMPTY view when the corpus is unavailable — the caller then says
    it could not ground the claim, which is the only honest move. It never falls
    back to an authored guess."""
    global _VIEW
    if _VIEW is not None and corpus is None:
        return _VIEW
    corp = corpus or load_corpus()
    if corp is None:
        return CatalogView()
    if corp.tier_of("docs/05") is not CorpusTier.CURRENT:
        # A tiering change that demoted docs/05 must not silently keep serving
        # capability claims from it.
        return CatalogView()
    text = "\n".join(
        f"{'#' * (p.heading.count('>') + 2)} {p.heading.split('>')[-1].strip()}\n{p.text}"
        for p in corp.passages_in("docs/05"))
    view = parse_catalog(text)
    if corpus is None:
        _VIEW = view
    return view


@dataclass(frozen=True)
class Topic:
    """A planner-facing subject and the catalog records that govern it.

    The trigger words are the PLANNER'S vocabulary; the ids are the catalog's.
    This map is the only authored thing in the module, and it authors no CLAIM —
    it authors which records to read. That distinction is the whole point: get
    the mapping wrong and the answer is about the wrong item, but it is still
    the catalog's own words about that item, never an invented capability."""

    key: str
    triggers: tuple[str, ...]
    item_ids: tuple[str, ...] = ()
    ruling_ids: tuple[str, ...] = ()
    exclusion_terms: tuple[str, ...] = ()


#: Add, never repurpose. A topic enters when a question has been MEASURED to
#: need it — the same discipline ``predicate_coverage`` states for its own
#: vocabulary. Ordered most-specific first.
TOPICS: tuple[Topic, ...] = (
    # THE SPECIMEN (Session 4B.15 Item 5): "can two machines share one operator".
    Topic("operators",
          ("operator", "operators", "labour", "labor", "staff", "crew",
           "manning", "manned", "share one operator", "same operator",
           "one person", "headcount", "shift worker", "technician"),
          item_ids=("B3", "B5"), ruling_ids=("R-B3",),
          exclusion_terms=("operator rostering",)),
    Topic("tooling",
          ("tool", "tools", "tooling", "fixture", "fixtures", "die", "dies",
           "mould", "mold", "jig"),
          item_ids=("B5", "B3"), ruling_ids=("R-B3",)),
    Topic("batching",
          ("batch", "co-load", "coload", "oven", "furnace", "tank",
           "shared cycle", "cure together", "bake together"),
          item_ids=("B9",)),
    Topic("buffers",
          ("buffer", "buffers", "blocking", "wip limit", "queue limit",
           "floor space", "starve", "starved"),
          item_ids=("B10",)),
    Topic("transfer_overlap",
          ("transfer batch", "overlap", "partial quantity", "start on partial",
           "split lot transfer"),
          item_ids=("D2",)),
    Topic("changeover",
          ("changeover", "change over", "setup family", "setup families",
           "sequence dependent", "sequence-dependent", "colour change",
           "color change", "transition matrix", "forbidden sequence"),
          item_ids=("B7/B8",), ruling_ids=("R-B7/B8",)),
    Topic("alternates",
          ("alternate", "alternates", "alternative machine", "eligible set",
           "more than one machine", "multiple machines", "either machine",
           "cross-train", "cross train"),
          item_ids=("B2",)),
    Topic("splitting",
          ("splittable", "split", "chunk", "resumable", "span downtime",
           "span a break", "interrupt", "pause and resume", "min_chunk"),
          item_ids=("C3",), ruling_ids=("R-C3",)),
    # C4 BEFORE C1/C2, and the ordering is load-bearing: "can I restrict an
    # operation to the day shift only" is a TIME-WINDOW RESTRICTION on that
    # operation (C4, model-proven with an §8 doorway that does not exist), not a
    # question about the plant's working calendar (C1/C2, both pipeline-proven).
    # With `calendars` first it answered "Yes, proven end to end" about the
    # wrong catalog item — the exact mis-mapping this module's docstring warns
    # the topic map can produce, caught in the same session that built it.
    Topic("time_windows",
          ("day shift only", "only day shift", "only the day shift",
           "night shift", "time window", "restrict to shift",
           "restrict an operation to", "restrict it to", "only run during",
           "only during the day", "days only", "only on day shift"),
          item_ids=("C4",)),
    Topic("calendars",
          ("calendar", "shift", "shifts", "weekend", "holiday", "downtime",
           "maintenance", "closure", "breakdown"),
          item_ids=("C1", "C2")),
    Topic("lags",
          ("dwell", "lag", "cure time", "cooling time", "max lag", "min lag",
           "wait between", "time between operations"),
          item_ids=("A2", "A3"), ruling_ids=("R-A2/A3", "R-Dwell")),
    Topic("release",
          ("release date", "material ready", "material availability",
           "when can it start", "earliest start"),
          item_ids=("A4",), ruling_ids=("R-A4",)),
    Topic("deadlines",
          ("hard deadline", "firm deadline", "must ship", "commitment class",
           "cannot be late"),
          item_ids=("A6", "A5")),
    Topic("pins",
          ("pin", "pinned", "lock", "locked", "freeze", "frozen",
           "exclude machine", "keep it off", "same machine as"),
          item_ids=("A7", "F1", "F2", "F3")),
    Topic("yield",
          ("yield", "scrap", "scrap rate", "shrinkage", "fallout"),
          item_ids=("D3",)),
    Topic("lot_sizing",
          ("lot size", "lot sizing", "min batch", "max batch", "merge orders",
           "combine orders"),
          item_ids=("D1",)),
    Topic("preferences",
          ("prefer", "preference", "keep on", "soft", "would rather",
           "priority customer", "customer weight"),
          item_ids=("H1",)),
    Topic("materials",
          ("mrp", "material netting", "bom", "bill of materials", "pegging",
           "purchase order", "inventory netting"),
          exclusion_terms=("mrp / material netting", "material netting")),
    Topic("multi_site",
          ("multi site", "multi-site", "another plant", "second facility",
           "transport between", "inter-plant", "interplant"),
          exclusion_terms=("multi-site with transport",)),
    Topic("energy",
          ("energy", "tariff", "electricity price", "power cost",
           "peak demand charge", "curtailment"),
          exclusion_terms=("energy/tariff-aware scheduling",)),
    Topic("preemption",
          ("preempt", "preemption", "bump", "interrupt a running job",
           "kick off the machine"),
          exclusion_terms=("arbitrary-point preemption",)),
)


def topics_for(question: str) -> list[Topic]:
    """Every catalog topic a question names, most-specific first. A question
    naming none returns [] and the caller must NOT invent a capability answer —
    that is the refusal Item 5 requires."""
    ql = f" {(question or '').lower()} "
    hits = []
    for topic in TOPICS:
        if any(t in ql for t in topic.triggers):
            hits.append(topic)
    return hits


@dataclass(frozen=True)
class Grounding:
    """Everything docs/05 says about one topic — the input to an authored
    capability answer, and the thing a test can assert against."""

    topic: Topic
    items: tuple[CatalogItem, ...] = ()
    rulings: tuple[Ruling, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()

    @property
    def register(self) -> Register:
        """The register the ANSWER speaks in: the weakest across the items, or
        EXCLUDED when the topic resolves only to an exclusion."""
        if not self.items:
            return Register.EXCLUDED if self.exclusions else Register.UNKNOWN
        order = [Register.EXCLUDED, Register.NOT_BUILT,
                 Register.MODELED_UNPROVEN, Register.PARTIAL, Register.PROVEN]
        regs = [i.register for i in self.items]
        for r in order:
            if r in regs:
                return r
        return Register.UNKNOWN

    @property
    def declarable(self) -> bool:
        return bool(self.items) and all(i.declarable for i in self.items)

    def citations(self) -> list[str]:
        out = [i.cite() for i in self.items]
        out += [r.cite() for r in self.rulings]
        out += [e.cite() for e in self.exclusions]
        seen, uniq = set(), []
        for c in out:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq


def ground(question: str,
           view: Optional[CatalogView] = None) -> Optional[Grounding]:
    """The docs/05 grounding for a capability question, or None when the catalog
    names nothing that fits. None is the REFUSAL signal: Item 5's rule is that a
    capability claim grounds in docs/05 or is not made."""
    cat = view or load_catalog()
    if not cat.items and not cat.exclusions:
        return None
    hits = topics_for(question)
    if not hits:
        return None
    topic = hits[0]
    items = tuple(i for i in (cat.by_id(t) for t in topic.item_ids) if i)
    rulings = tuple(r for r in (cat.ruling(t) for t in topic.ruling_ids) if r)
    excls = tuple(e for e in cat.exclusions
                  if any(term.lower() in e.name.lower()
                         or term.lower() in e.text.lower()
                         for term in topic.exclusion_terms))
    if not items and not excls:
        return None
    return Grounding(topic, items, rulings, excls)
