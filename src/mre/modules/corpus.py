"""THE DOCUMENT CORPUS, IN TIERS (Session 4B.15 Item 1).

THE MEASURED FAILURE THIS EXISTS FOR. Asked live on the pinned board, "can two
machines share one operator" came back a confident YES describing ALTERNATES —
one operation eligible on several machines, which is a different thing entirely.
In the same session, on the same board, the blocker analysis correctly listed
"B3/B5 secondary and cumulative resources (tools, operator pools)" among the
families it does NOT weigh. docs/05 states the position plainly: operators are
calendar-bearing capacity POOLS, the roles doorway is a demand-driven §8 doorway
that does not exist, and individual operator rostering is a global exclusion.

Synthesis was not failing at intelligence. It was failing at RETRIEVAL: it had a
nine-entry capability registry and no way to reach the constraint catalog.

THE TIERS, AND WHY EACH BOUNDARY IS LOAD-BEARING
------------------------------------------------
CURRENT (docs/01, docs/05, docs/06) — what the system IS. Free rein.

HISTORICAL (docs/04) — EXCLUDED BY DEFAULT. It is append-only and it carries
    SUPERSEDED rulings as first-class text, indistinguishable in shape from live
    ones. R-SC3(2) priced earliness at 0.05/min: present as a landed ruling AND
    as a retired one. Past-due exclusion is present as designed behaviour AND as
    a removed defect. A retriever pulling the first match states a RETIRED
    MECHANISM AS CURRENT, with a citation to our own history — which is worse
    than not knowing, because the citation is real. Reachable ONLY for
    ``Purpose.DESIGN_RATIONALE``, and every passage is DATED and rendered as
    history. A passage whose heading carries no date is DROPPED AT INDEX TIME
    (fail-closed): the rule is that every historical claim is dated, so an
    undatable one is unservable rather than served bare. That costs the 15
    undated ``D-nn`` founding-decision sections, named in ``dropped_undated``.

INTENT (docs/07) — the roadmap. It describes what we INTEND to build, which to a
    retriever is indistinguishable from what we DID build. No purpose reaches it.
    The boundary is enforced here in code, not asked for in a prompt:
    ``TIERS_FOR_PURPOSE`` simply does not list it, and a test asserts no purpose
    can.

INTERNAL — close-outs, CLAUDE.md, recon and errand reports, measured defect
    lists. NEVER INDEXED AT ALL. Named in ``EXCLUDED_INTERNAL`` with a reason
    each, so the decision to include any of them is Daryn's, made once and
    deliberately, rather than mine made silently. See ``excluded_report()``.

CURRENCY — THE CORPUS SHIPS WITH THE BUILD
-------------------------------------------
A doc claiming behaviour the code does not have is the declared-but-never-
consumed bug class one level up, so this cannot be a directory read at runtime.
It is not: ``docs/`` is deliberately NOT in the runtime image (the Dockerfile
says so in as many words — it copies ``docs`` only into the TEST stage). A
corpus that read ``docs/`` at runtime would be EMPTY in production, not stale.

So the index is PACKAGE DATA, built by ``tools/build_corpus_index.py`` and
committed at ``src/mre/corpus_index.json``. It carries a sha256 per source
document, and ``tests/test_corpus.py`` re-fingerprints the live ``docs/`` and
fails if any differ. Editing a spec without rebuilding the index is a RED TEST,
not a silently stale answer. That is the whole enforcement, and it is a
build-time check rather than a promise.

WHAT THIS MODULE IS NOT. It is a retriever. It selects passages and states where
they came from. It never composes an answer, never grades a claim, and never
routes — the same jurisdiction line ``predicate_coverage`` and ``claim_verifier``
sit on. The structured catalog rows a capability answer is actually built from
live in ``constraint_catalog``; this module serves the surrounding PROSE.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

#: Where the committed index lives, relative to this package.
INDEX_PATH = Path(__file__).resolve().parent.parent / "corpus_index.json"

#: The repo's ``docs/`` directory when it is present (dev + test). Absent in the
#: runtime image, which is exactly why the index is package data.
DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"


class CorpusTier(str, Enum):
    """What KIND of truth a document carries. Add, never repurpose."""

    CURRENT = "current"
    HISTORICAL = "historical"
    INTENT = "intent"


class Purpose(str, Enum):
    """Why a retrieval is being made. The purpose picks the tiers; a caller never
    names a tier directly, so there is one place to audit."""

    #: "can it handle X" / "how do I enable X" / "does it model Y". CURRENT only.
    CAPABILITY = "capability"
    #: "why was it designed this way". CURRENT plus dated HISTORICAL.
    DESIGN_RATIONALE = "design-rationale"


#: THE BOUNDARY, in code. ``INTENT`` appears in no tuple, so no purpose reaches
#: docs/07 — that is the "no capability claim is grounded in the roadmap" rule,
#: enforced rather than requested.
TIERS_FOR_PURPOSE: dict[Purpose, tuple[CorpusTier, ...]] = {
    Purpose.CAPABILITY: (CorpusTier.CURRENT,),
    Purpose.DESIGN_RATIONALE: (CorpusTier.CURRENT, CorpusTier.HISTORICAL),
}

#: Tiers indexed but reachable by nothing. Asserted by the corpus tests.
UNREACHABLE_TIERS: tuple[CorpusTier, ...] = (CorpusTier.INTENT,)


@dataclass(frozen=True)
class CorpusDoc:
    """One indexed source document."""

    doc_id: str            # "docs/05"
    filename: str          # "05-constraint-catalog.md"
    tier: CorpusTier
    title: str
    note: str = ""         # why it sits in that tier, in one line


MANIFEST: tuple[CorpusDoc, ...] = (
    CorpusDoc("docs/01", "01-canonical-model-spec.md", CorpusTier.CURRENT,
              "Canonical Model Specification",
              "the entities and their attributes as they are today"),
    CorpusDoc("docs/05", "05-constraint-catalog.md", CorpusTier.CURRENT,
              "Constraint Catalog",
              "what the system models, what it excludes, and the proof each "
              "capability carries"),
    CorpusDoc("docs/06", "06-incoming-data-spec.md", CorpusTier.CURRENT,
              "Incoming Data Specification",
              "every submission field, its meaning, and how to declare it"),
    CorpusDoc("docs/04", "04-design-history.md", CorpusTier.HISTORICAL,
              "Design History (append-only)",
              "carries SUPERSEDED rulings as first-class text; dated, and only "
              "ever quoted as history"),
    CorpusDoc("docs/07", "07-roadmap.md", CorpusTier.INTENT,
              "Roadmap",
              "what we INTEND to build; never evidence for what the system does"),
)

#: INTERNAL content, deliberately never indexed. Each entry names WHAT and WHY,
#: so the decision to admit any of it is a ruling someone makes on purpose.
EXCLUDED_INTERNAL: tuple[tuple[str, str], ...] = (
    ("docs/closeouts/*.md",
     "session narratives. They state what ONE session found, in that session's "
     "present tense, and are never revised when a later session supersedes "
     "them — the docs/04 hazard without docs/04's dating discipline."),
    ("CLAUDE.md",
     "the working agreement plus a live status section that names unfixed "
     "defects, carry-forwards and internal judgements. A planner-facing answer "
     "grounded in it would quote our own backlog at a customer."),
    ("docs/00-README.md, docs/02, docs/03, docs/08",
     "orientation, the evidence contract, the historical PoC plan and the "
     "security posture. None is wrong; none is a source a capability answer "
     "needs, and every indexed document is surface that must be kept current."),
    ("docs/handoffs/*, docs/promotions/*",
     "in-flight design artifacts and promotion dossiers — proposals under "
     "review, which read as decisions."),
    ("RECON_*.txt, SESSION_*.md, *_scratch/, tools/spikes/**",
     "recon reports, scratch measurement output and spike results. Findings "
     "held at a point in time, with no currency mechanism at all."),
)


@dataclass(frozen=True)
class Passage:
    """One retrievable chunk: a heading path and its body, with its tier."""

    doc_id: str
    tier: CorpusTier
    heading: str           # the heading path, e.g. "2. The catalog > Category B"
    text: str
    dated: Optional[str] = None    # ISO date; REQUIRED on HISTORICAL

    @property
    def citation(self) -> str:
        """How this passage is named in an answer. A historical passage says so
        and says when, every time — never as an unqualified statement of
        behaviour."""
        if self.tier is CorpusTier.HISTORICAL:
            return (f"{self.doc_id} § {self.heading} "
                    f"[history, {self.dated} — may be superseded]")
        return f"{self.doc_id} § {self.heading}"

    def render(self, limit: int = 1200) -> str:
        body = self.text if len(self.text) <= limit else self.text[:limit] + " ..."
        return f"{self.citation}\n{body}"


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)$")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
#: A section longer than this is split at paragraph boundaries, so one huge
#: section cannot crowd out every other passage in a retrieval.
_MAX_CHUNK = 3500


def _split_long(text: str) -> list[str]:
    if len(text) <= _MAX_CHUNK:
        return [text]
    out, buf = [], ""
    for para in text.split("\n\n"):
        if buf and len(buf) + len(para) + 2 > _MAX_CHUNK:
            out.append(buf.strip())
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf.strip():
        out.append(buf.strip())
    return out


def _chunk(doc: CorpusDoc, body: str) -> tuple[list[dict], int]:
    """Split one document into heading-scoped passages.

    Returns the passages and the count DROPPED for want of a date, which is
    non-zero only on the HISTORICAL tier and is reported rather than swallowed.
    """
    lines = body.splitlines()
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, Optional[str], list[str]]] = []
    cur_head, cur_date, cur_lines = doc.title, None, []
    for line in lines:
        m = _HEADING_RE.match(line)
        if not m:
            cur_lines.append(line)
            continue
        sections.append((cur_head, cur_date, cur_lines))
        depth, text = len(m.group(1)), m.group(2).strip()
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, text))
        cur_head = " > ".join(h for _d, h in stack)
        found = _DATE_RE.search(cur_head)
        cur_date = found.group(1) if found else None
        cur_lines = []
    sections.append((cur_head, cur_date, cur_lines))

    out: list[dict] = []
    dropped = 0
    for head, date, chunk_lines in sections:
        text = "\n".join(chunk_lines).strip()
        if not text:
            continue
        # FAIL CLOSED. Every historical claim is dated; an undatable section is
        # unservable, not servable bare.
        if doc.tier is CorpusTier.HISTORICAL and not date:
            dropped += 1
            continue
        for piece in _split_long(text):
            out.append({"doc_id": doc.doc_id, "tier": doc.tier.value,
                        "heading": head, "text": piece, "dated": date})
    return out, dropped


def fingerprint(text: str) -> str:
    """The content hash the currency gate compares. Newlines normalized so a
    checkout's line endings never register as a spec edit."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def build_index(docs_dir: Path = DOCS_DIR) -> dict:
    """Build the whole index from a ``docs/`` directory. Used by the build tool
    and by the currency test; never by a runtime answer path."""
    docs, passages, dropped = [], [], {}
    for doc in MANIFEST:
        raw = (docs_dir / doc.filename).read_text(encoding="utf-8")
        chunks, n_dropped = _chunk(doc, raw)
        passages.extend(chunks)
        if n_dropped:
            dropped[doc.doc_id] = n_dropped
        docs.append({"doc_id": doc.doc_id, "filename": doc.filename,
                     "tier": doc.tier.value, "title": doc.title,
                     "note": doc.note, "sha256": fingerprint(raw)})
    return {"index_version": 1, "docs": docs, "passages": passages,
            "dropped_undated": dropped}


# ---------------------------------------------------------------------------
# The loaded corpus
# ---------------------------------------------------------------------------

_STOP = frozenset("""
a an the and or of to in on for is are be can could would with without at by
it its this that these those do does did how what when where why which who
my our your their there here not no yes if then than as from into over under
i we you they me us them he she him her one two some any all more most
""".split())

_WORD_RE = re.compile(r"[a-z_][a-z0-9_]*")


def _terms(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall((text or "").lower())
            if w not in _STOP and len(w) > 2]


class Corpus:
    """The loaded, tiered corpus. Construct once; it is immutable."""

    def __init__(self, payload: dict) -> None:
        self._docs = {d["doc_id"]: d for d in payload.get("docs", [])}
        self._dropped = dict(payload.get("dropped_undated", {}))
        self._passages: list[Passage] = []
        for row in payload.get("passages", []):
            self._passages.append(Passage(
                doc_id=row["doc_id"], tier=CorpusTier(row["tier"]),
                heading=row["heading"], text=row["text"],
                dated=row.get("dated")))
        # A cheap document-frequency table, so "operator" outweighs "resource".
        self._df: dict[str, int] = {}
        self._toks: list[frozenset[str]] = []
        for p in self._passages:
            toks = frozenset(_terms(f"{p.heading} {p.text}"))
            self._toks.append(toks)
            for t in toks:
                self._df[t] = self._df.get(t, 0) + 1

    # -- introspection the tests and the report read ----------------------

    @property
    def passages(self) -> tuple[Passage, ...]:
        return tuple(self._passages)

    @property
    def dropped_undated(self) -> dict[str, int]:
        """Sections dropped for want of a date, per document. Reported, never
        swallowed: on docs/04 it is the undated ``D-nn`` founding decisions."""
        return dict(self._dropped)

    def doc_fingerprints(self) -> dict[str, str]:
        return {k: v["sha256"] for k, v in self._docs.items()}

    def tier_of(self, doc_id: str) -> Optional[CorpusTier]:
        row = self._docs.get(doc_id)
        return CorpusTier(row["tier"]) if row else None

    # -- retrieval --------------------------------------------------------

    def retrieve(self, query: str, purpose: Purpose,
                 limit: int = 5) -> list[Passage]:
        """The passages most relevant to ``query``, restricted to the tiers the
        PURPOSE admits. A purpose that admits no tier returns nothing; there is
        no "fall back to everything" path, by design."""
        allowed = {t for t in TIERS_FOR_PURPOSE.get(purpose, ())}
        q = set(_terms(query))
        if not q or not allowed:
            return []
        n = max(len(self._passages), 1)
        scored: list[tuple[float, int]] = []
        for i, p in enumerate(self._passages):
            if p.tier not in allowed:
                continue
            toks = self._toks[i]
            hit = q & toks
            if not hit:
                continue
            import math
            score = sum(math.log(n / (1 + self._df.get(t, 0))) for t in hit)
            # A short, precise section beats a long one that merely contains
            # the words. Mild, so it cannot outrank a genuine match.
            score *= 1.0 + (400.0 / (400.0 + len(p.text)))
            scored.append((score, i))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [self._passages[i] for _s, i in scored[:limit]]

    def passages_in(self, doc_id: str,
                    heading_contains: str = "") -> list[Passage]:
        """Every passage from one document, optionally filtered by heading. The
        catalog reader uses this; retrieval scoring is not involved."""
        return [p for p in self._passages
                if p.doc_id == doc_id
                and heading_contains.lower() in p.heading.lower()]


_CORPUS: Optional[Corpus] = None
_LOAD_ERROR: str = ""


def load_corpus() -> Optional[Corpus]:
    """The process-wide corpus, or None when the index is missing or malformed.

    None is an honest state, not a crash: an answer path that cannot reach the
    corpus must say it could not ground the claim, never invent one. See
    ``load_error()`` for why."""
    global _CORPUS, _LOAD_ERROR
    if _CORPUS is not None:
        return _CORPUS
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — a missing corpus is a state
        _LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        return None
    try:
        _CORPUS = Corpus(payload)
    except Exception as exc:  # noqa: BLE001
        _LOAD_ERROR = f"malformed index: {type(exc).__name__}: {exc}"
        return None
    _LOAD_ERROR = ""
    return _CORPUS


def load_error() -> str:
    return _LOAD_ERROR


def excluded_report() -> list[dict]:
    """What was deliberately kept OUT of the corpus, and why — the report Item 1
    owes so the decision to admit any of it is made once and on purpose."""
    return [{"what": what, "why": why} for what, why in EXCLUDED_INTERNAL]
