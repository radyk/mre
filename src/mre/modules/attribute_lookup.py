"""ATTRIBUTE LOOKUP — ANY DECLARED FIELD, VERBATIM, WITH ITS SOURCE
(Session 4B.15 Item 3).

THE MEASURED FAILURE, and it is the flat one. Asked live on the pinned board:

    "is ORD-000013 op20 splittable"   -> capability documentation, with a scold
    "how long does op20 take"         -> the order card

Both are fully specified. Neither is ambiguous. And in the very next exchange
the blocker analysis quoted BOTH answers — ``splittable=False`` and 431 working
minutes — because it reads the same snapshot. The facts were loaded. There was
simply no route that reads a declared field off an entity and states it.

THE RULE, deliberately broad and NOT an enumeration:

    ANY DECLARED FIELD ON ANY ENTITY IN THE PERSISTED RUN IS ASKABLE AND
    ANSWERABLE, VERBATIM, WITH ITS SOURCE.

So the field vocabulary is built by REFLECTION over the canonical entity models
in ``mre.contracts.entities`` — every field every entity declares, automatically,
including ones added after this module was written. What is authored is the
ALIAS map: the planner's words for those fields ("how long", "due", "which
machines can run it"). A field with no alias is still reachable by its own name.

WITH ITS SOURCE MEANS THE WHOLE CHAIN
--------------------------------------
An ``Operation`` is an INSTANCE of an ``OperationSpec`` (docs/04 D-10), so its
``splittable`` carries ``derived`` provenance with no source field — the
observed value lives on the spec, citing ``routing_lines.csv``. Reporting the
operation's bare ``derived`` would be true and useless. This module walks to the
template when the instance is derived and cites where the value ENTERED THE
SYSTEM, saying that it did so.

Reading the provenance sidecar here is explicitly permitted: the Solver Builder
never reads it, validation and planning read it through a narrow trust
interface, and the AI layer reads everything (CLAUDE.md hard rules).

DECLARED AND DERIVED ARE LABELLED DIFFERENTLY, ALWAYS
------------------------------------------------------
"How long does op20 take" has three honest answers and they are different
numbers: the declared run duration, the total working minutes (setup + run,
ARITHMETIC THIS MODULE DID), and the elapsed span on the board (a placement
fact, not a declaration). 4B.14 made the run/span distinction a contract field
precisely because conflating them is a confusion the product used to create. So
all three are stated, each labelled with what it is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

#: Entity types whose fields are askable, in RESOLUTION ORDER for an
#: operation-scoped question: the instance first, then its template.
_OP_CHAIN = ("operation", "operationspec")


def _entity_models() -> dict[str, Any]:
    """The canonical entity models, by lower-cased type name. Reflection, so a
    field added to an entity is askable the day it lands."""
    from mre.contracts import entities as E
    from pydantic import BaseModel
    out: dict[str, Any] = {}
    for name in dir(E):
        obj = getattr(E, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
            out[name.lower()] = obj
    return out


def declared_fields(entity_type: str) -> tuple[str, ...]:
    """Every field the model declares, minus the universal plumbing (docs/01 §4)
    a planner never means."""
    model = _entity_models().get(entity_type.lower())
    if model is None:
        return ()
    skip = {"id", "snapshot_id", "external_refs"}
    return tuple(f for f in model.model_fields if f not in skip)


@dataclass(frozen=True)
class Alias:
    """The planner's words for a field. Authored — the only authored thing here,
    and it authors WHICH FIELD to read, never a value."""

    field_name: str
    entity_types: tuple[str, ...]
    phrases: tuple[str, ...]
    label: str = ""            # planner-facing name, defaults to field_name


#: Most-specific first, so "minimum chunk" binds before a bare "chunk".
ALIASES: tuple[Alias, ...] = (
    Alias("min_chunk", _OP_CHAIN,
          ("min chunk", "min_chunk", "minimum chunk", "min chunk minutes",
           "min_chunk_minutes", "minimum piece", "smallest piece",
           "minimum piece size"), "minimum chunk"),
    Alias("splittable", _OP_CHAIN,
          ("splittable", "split", "splitable", "can it be split",
           "can be split", "resumable", "interruptible", "chunkable"),
          "splittable"),
    Alias("setup_family", _OP_CHAIN,
          ("setup family", "setup_family", "changeover family", "colour family",
           "color family"), "setup family"),
    # Deliberately NOT a bare "setup": "what is the setup family on op20" would
    # then fire the duration alias too and answer two questions, one unasked.
    Alias("setup_duration", ("operation",),
          ("setup time", "setup duration", "setup minutes", "how long is setup",
           "how much setup"), "setup time"),
    Alias("base_setup", ("operationspec",),
          ("base setup", "base_setup"), "base setup"),
    Alias("run_duration", ("operation",),
          ("run time", "run duration", "run minutes", "processing time",
           "how long does", "how long is", "how long will", "duration",
           "how much time"), "run time"),
    Alias("run_rate", ("operationspec",), ("run rate", "run_rate",
                                            "rate per unit"), "run rate"),
    Alias("yield_factor", ("operationspec",),
          ("yield", "yield factor", "scrap rate"), "yield factor"),
    Alias("resource_requirements", _OP_CHAIN,
          ("eligible", "eligibility", "which machines", "what machines can",
           "can run it", "alternatives", "eligible machines", "routing line"),
          "eligible resources"),
    Alias("sequence", _OP_CHAIN, ("sequence", "step number", "op number"),
          "sequence"),
    Alias("wip_status", ("operation",),
          ("wip", "work in progress", "already started", "shop floor status"),
          "WIP status"),
    # -- demand (order) ---------------------------------------------------
    Alias("due", ("demand",), ("due", "due date", "when is it due",
                               "deadline"), "due date"),
    Alias("earliest_start", ("demand", "workpackage"),
          ("release", "release date", "earliest start", "when can it start",
           "material ready"), "release / earliest start"),
    Alias("quantity", ("demand", "workpackage"),
          ("quantity", "qty", "how many units", "order quantity"), "quantity"),
    Alias("commitment_class", ("demand",),
          ("commitment", "commitment class", "firm", "is it firm"),
          "commitment class"),
    Alias("customer_weight", ("demand",),
          ("customer weight", "priority weight", "customer priority"),
          "customer weight"),
    Alias("customer_ref", ("demand",), ("customer", "which customer",
                                         "whose order"), "customer"),
    Alias("product_ref", ("demand", "workpackage"),
          ("product", "what product", "part number", "item"), "product"),
    Alias("status", ("demand",), ("status", "order status"), "status"),
    # -- resource ---------------------------------------------------------
    Alias("capabilities", ("resource",),
          ("capability", "capabilities", "what can it do", "skills"),
          "capabilities"),
    Alias("capacity", ("resource",), ("capacity", "parallel units",
                                       "how many at once"), "capacity"),
    Alias("cost_rate", ("resource",), ("cost rate", "hourly rate",
                                        "what does it cost per hour"),
          "cost rate"),
    Alias("resource_type", ("resource",), ("resource type", "machine type"),
          "resource type"),
    Alias("calendar_ref", ("resource",), ("calendar", "which calendar"),
          "calendar"),
)


@dataclass(frozen=True)
class AttributeFact:
    """One declared field, its value, and where the value came from."""

    entity_type: str
    entity_label: str          # "ORD-000013 op20"
    field_name: str
    label: str                 # the planner-facing field name
    rendered: str              # the value, planner-readable
    declared: bool             # True when a submission stated it
    provenance_class: str      # observed / derived / defaulted / synthesized
    source: str = ""           # "routing_lines.csv (splittable)"
    ids_ref: str = ""          # the docs/06 § where it is declared
    note: str = ""             # e.g. "derived from the routing template"

    #: True when the entity carries no value at all. An EMPTY declared field and
    #: a declared value are different facts and must not share a sentence: "not
    #: declared — declared in your submission" is the contradiction this exists
    #: to prevent.
    empty: bool = False

    def line(self) -> str:
        head = f"{self.label}: {self.rendered}"
        if self.empty:
            where = f", {self.source}" if self.source else ""
            return (f"{head} — this operation leaves it empty{where}"
                    if where else f"{head} — nothing was submitted for it")
        if self.source:
            return f"{head} — declared in your submission, {self.source}."
        if self.provenance_class == "defaulted":
            return f"{head} — not declared; this is the default."
        if self.note:
            return f"{head} — {self.note}."
        return f"{head} ({self.provenance_class})."


@dataclass(frozen=True)
class AttributeAnswer:
    """The result of one attribute lookup."""

    subject: str                              # "ORD-000013 op20"
    facts: tuple[AttributeFact, ...] = ()
    #: Fields the planner named that this run does not carry. Named, never
    #: silently dropped — an absent field and an absent answer are different.
    unknown_fields: tuple[str, ...] = ()
    #: Placement figures, which are NOT declarations. Labelled separately.
    placement: tuple[str, ...] = ()
    #: True when the FIELD came from the previous turn rather than this one (a
    #: correction). Said out loud, so the planner can see what was carried over
    #: and correct it again if the carry-over was the wrong guess.
    inherited_field: bool = False

    @property
    def answered(self) -> bool:
        return bool(self.facts or self.placement)


# ---------------------------------------------------------------------------
# Field selection
# ---------------------------------------------------------------------------

_SEQ_RE = re.compile(r"\bop(?:eration)?\s*[-_ ]?(\d{1,3})\b", re.IGNORECASE)


def op_seq_in(question: str) -> Optional[int]:
    """The operation the question names ("op20", "operation 30"), or None."""
    m = _SEQ_RE.search(question or "")
    return int(m.group(1)) if m else None


def fields_named(question: str,
                 entity_types: Iterable[str] = ()) -> list[Alias]:
    """Every field alias the question names, most-specific first.

    A bare field NAME always works even with no alias — that is what keeps the
    rule broad rather than an enumeration."""
    ql = f" {(question or '').lower()} "
    allowed = {e.lower() for e in entity_types} if entity_types else None
    hits: list[Alias] = []
    seen: set[str] = set()
    for alias in ALIASES:
        if allowed and not (set(alias.entity_types) & allowed):
            continue
        if any(p in ql for p in alias.phrases):
            if alias.field_name not in seen:
                seen.add(alias.field_name)
                hits.append(alias)
    # Bare declared field names, for anything the alias map has not learned.
    for etype in (entity_types or ("operation", "operationspec", "demand",
                                   "workpackage", "resource", "product")):
        for fname in declared_fields(etype):
            if fname in seen:
                continue
            if re.search(rf"(?<![a-z]){re.escape(fname)}(?![a-z])", ql):
                seen.add(fname)
                hits.append(Alias(fname, (etype,), (fname,), fname))
    return hits


# ---------------------------------------------------------------------------
# Value rendering
# ---------------------------------------------------------------------------

_ISO_DUR = re.compile(
    r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?)?$")


def iso_minutes(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    m = _ISO_DUR.match(value.strip())
    if not m:
        return None
    d, h, mi, s = (float(g or 0) for g in m.groups())
    return d * 1440 + h * 60 + mi + s / 60.0


def human_minutes(mins: float) -> str:
    total = int(round(mins))
    h, m = divmod(total, 60)
    if h and m:
        return f"{h}h {m}m ({total:,} minutes)"
    if h:
        return f"{h}h ({total:,} minutes)"
    return f"{m} minutes"


def render_value(value: Any) -> str:
    """A canonical value as the planner would say it. ``None`` is rendered as
    NOT DECLARED rather than as "null" or "0" — an undeclared floor and a floor
    of zero are different facts."""
    if value is None:
        return "not declared"
    if isinstance(value, bool):
        return "yes" if value else "no"
    mins = iso_minutes(value)
    if mins is not None:
        return human_minutes(mins)
    if isinstance(value, (int, float)):
        return f"{value:,}" if isinstance(value, int) else f"{value:g}"
    if isinstance(value, dict):
        if "value" in value:                          # Quantity {value, uom}
            unit = value.get("uom") or value.get("unit") or ""
            return f"{value['value']:g} {unit}".strip()
        return "; ".join(f"{k}={v}" for k, v in value.items()) or "not declared"
    if isinstance(value, list):
        if not value:
            return "none"
        return f"{len(value)} entr" + ("y" if len(value) == 1 else "ies")
    text = str(value)
    if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
        from mre.modules.explainer import _fmt_ts
        try:
            return _fmt_ts(text)
        except Exception:  # noqa: BLE001 — a bad timestamp prints as itself
            return text
    return text if text.strip() else "not declared"


#: docs/06 § per canonical field, borrowed from the same source the capability
#: registry borrows its citations from. Absent is fine — the answer simply does
#: not cite a §, and never invents one.
IDS_REFS: dict[str, str] = {
    "splittable": "§5.3", "min_chunk": "§5.3", "setup_family": "§5.3",
    "run_rate": "§5.3", "base_setup": "§5.3", "resource_requirements": "§5.3",
    "sequence": "§5.3", "due": "§5.1", "earliest_start": "§5.1",
    "quantity": "§5.1", "commitment_class": "§5.1", "customer_ref": "§5.10",
    "customer_weight": "§5.10", "capabilities": "§5.5", "capacity": "§5.5",
    "cost_rate": "§5.5", "resource_type": "§5.5", "calendar_ref": "§5.6",
    "wip_status": "§5.13", "yield_factor": "§5.3",
}


# ---------------------------------------------------------------------------
# Reading the run
# ---------------------------------------------------------------------------

def _prov(reader: Any, entity_id: str, attr: str) -> tuple[str, str]:
    """(provenance class, human source) for one attribute, or ("", "")."""
    try:
        rec = reader.get_provenance(entity_id, attr)
    except Exception:  # noqa: BLE001 — an unreadable sidecar is "unknown"
        return "", ""
    if not rec:
        return "", ""
    payload = rec.get("payload") or {}
    field_src = payload.get("source_field") or ""
    system = payload.get("source_system") or ""
    src = ""
    if field_src:
        src = f"{field_src}" if "." in field_src or "(" in field_src \
            else f"the {field_src} column"
        if system:
            src = f"{src} ({system} submission)"
    return rec.get("provenance_class", ""), src


def _fact(reader: Any, entity: dict, entity_type: str, label: str,
          alias: Alias, template: Optional[dict] = None,
          template_type: str = "") -> Optional[AttributeFact]:
    """One field off one entity, with its provenance chain walked.

    THE CHAIN. An Operation is an instance of an OperationSpec, so an instance
    field carries ``derived`` provenance and no source. The observed value lives
    on the template, citing the submission column. Reporting the bare ``derived``
    would be true and useless, so when the instance is derived and the template
    carries the same attribute observed, the answer cites where the value
    ENTERED THE SYSTEM and says that it did."""
    name = alias.field_name
    if name not in entity:
        return None
    value = entity[name]
    pclass, source = _prov(reader, entity["id"], name)
    note = ""
    if pclass == "derived" and template is not None:
        if name in template:
            t_class, t_source = _prov(reader, template["id"], name)
            if t_source:
                source = t_source
                note = (f"carried onto this operation from its {template_type} "
                        "(the routing template)")
                pclass = t_class or pclass
        else:
            # The instance field has no template twin because it is COMPUTED
            # from one: run_duration from run_rate x quantity, setup_duration
            # from base_setup. Cite the template field the value came out of
            # rather than reporting a bare "derived", which is true and useless.
            src_field = _COMPUTED_FROM.get(name, "")
            if src_field and src_field in template:
                _c, t_source = _prov(reader, template["id"], src_field)
                note = (f"computed from the routing template's {src_field} "
                        f"({render_value(template[src_field])}) and this "
                        "order's quantity")
                if t_source:
                    note += f", which is declared in your submission, {t_source}"
    empty = value is None or value == "" or value == []
    return AttributeFact(
        entity_type=entity_type, entity_label=label, field_name=name,
        label=alias.label or name, rendered=render_value(value),
        declared=(pclass == "observed" and not empty),
        provenance_class=pclass or "unknown",
        source=source, ids_ref=IDS_REFS.get(name, ""), note=note, empty=empty)


#: Instance fields the adapter COMPUTES from a template field. The chain is real
#: and citable; the bare "derived" on the instance is neither.
_COMPUTED_FROM: dict[str, str] = {
    "run_duration": "run_rate",
    "setup_duration": "base_setup",
}


def lookup(explainer: Any, question: str, *, order: Optional[str] = None,
           op_seq: Optional[int] = None, machine: Optional[str] = None,
           prior_question: str = "") -> Optional[AttributeAnswer]:
    """Answer an attribute question off the persisted run, or None.

    None means the question named no readable field or no resolvable subject —
    the caller then falls through rather than inventing a value.

    ``prior_question`` carries the previous turn's words, and is read ONLY when
    this question names no field of its own. "no, I mean for ORD-000013
    specifically" is a CORRECTION: it re-binds the subject and inherits the
    predicate, and answering it as though no field were named is how an explicit
    correction got the same wrong answer a second time in the measured
    transcript."""
    reader = getattr(explainer, "_reader", None)
    if reader is None:
        return None

    # -- resolve the subject ------------------------------------------------
    if op_seq is None:
        op_seq = op_seq_in(question)
    rows = []
    try:
        rows = explainer._load_enriched_assignments()
    except Exception:  # noqa: BLE001
        rows = []

    # THE ENTITY IS CHOSEN PER FIELD, NOT UP FRONT. "when is ORD-000013 due"
    # names an order with one placement; resolving to that OPERATION first and
    # then looking for `due` on it finds nothing, and the question is
    # unanswerable for a reason that has nothing to do with the question. A
    # single ask can legitimately name an operation field and an order field at
    # once ("is op20 splittable and when is it due"), so every candidate entity
    # is resolved and each alias binds to the first candidate of a type it
    # declares. Ordered narrowest first.
    candidates: list[dict] = []
    entity_types: tuple[str, ...] = ()
    entity: Optional[dict] = None
    template: Optional[dict] = None
    template_type = ""
    label = ""
    placement: list[str] = []

    if order:
        mine = [r for r in rows
                if order.upper() in [w.upper() for w in r.get("work_orders", [])]]
        mine.sort(key=lambda r: (r.get("op_seq") or 0))
        row = None
        if op_seq is not None:
            row = next((r for r in mine if r.get("op_seq") == op_seq), None)
        elif len(mine) == 1:
            row = mine[0]
        if row is not None:
            entity = reader.get_entity(row["operation_ref"])
            if entity is not None:
                entity_types = _OP_CHAIN
                template = reader.get_entity(entity.get("spec_ref", "")) or None
                template_type = "operation spec"
                label = f"{order} op{row.get('op_seq')}"
                # THREE DIFFERENT NUMBERS, THREE DIFFERENT LABELS (4B.14 Item
                # 4) — and the arithmetic is easy to get wrong. The solver
                # models setup and run as one contiguous block from the
                # operation's start, so ``run_min`` (summed over the chunks)
                # ALREADY INCLUDES the setup phase. Adding setup to it
                # double-counts: op20 is 20m setup + 6h51m run = 431 working
                # minutes, which is exactly what the chunks total, not 451.
                booked = row.get("run_min") or 0.0
                span = row.get("span_min") or 0.0
                setup = iso_minutes(row.get("setup_duration")) or 0.0
                declared_run = iso_minutes(entity.get("run_duration")) or 0.0
                placement = [
                    f"working time: {human_minutes(setup + declared_run)} "
                    f"— setup {human_minutes(setup)} plus run "
                    f"{human_minutes(declared_run)}, the two declared durations "
                    "added (the machine is occupied for both)",
                    f"elapsed span on the board: {human_minutes(span)} "
                    f"on {row.get('machine')} — a placement fact, not a "
                    "declaration"
                    + (", and it is longer than the working time because the "
                       "operation pauses across a closure"
                       if span > booked + 1 else ""),
                ]
        if entity is not None:
            candidates.append({"entity": entity, "type": "operation",
                               "template": template,
                               "template_type": template_type, "label": label})
            if template is not None:
                candidates.append({"entity": template, "type": "operationspec",
                                   "template": None, "template_type": "",
                                   "label": label})
        # The DEMAND is always a candidate for an order-scoped question.
        dem = next((d for d in reader.iter_entities("demand")
                    if any(r.get("value", "").upper() == order.upper()
                           for r in d.get("external_refs", []))), None)
        if dem is not None:
            candidates.append({"entity": dem, "type": "demand",
                               "template": None, "template_type": "",
                               "label": order})
            if entity is None:
                entity, entity_types, label = dem, ("demand",), order
    elif machine:
        ref = explainer.resolve_machine_value(machine) or machine
        res = next((r for r in reader.iter_entities("resource")
                    if any(x.get("value", "").upper() == ref.upper()
                           for x in r.get("external_refs", []))), None)
        if res is not None:
            entity, entity_types, label = res, ("resource",), ref
            candidates.append({"entity": res, "type": "resource",
                               "template": None, "template_type": "",
                               "label": ref})

    if entity is None:
        return None

    searchable = tuple(dict.fromkeys(c["type"] for c in candidates)) \
        or entity_types
    aliases = fields_named(question, searchable)
    inherited = False
    if not aliases and prior_question:
        aliases = fields_named(prior_question, searchable)
        inherited = bool(aliases)
    if not aliases:
        return None

    facts: list[AttributeFact] = []
    unknown: list[str] = []
    for alias in aliases:
        got, matched = None, None
        for cand in candidates:
            if cand["type"] not in alias.entity_types:
                continue
            got = _fact(reader, cand["entity"], cand["type"], cand["label"],
                        alias, cand["template"], cand["template_type"])
            if got is not None:
                matched = cand
                break
        if got is None:
            unknown.append(alias.label or alias.field_name)
            continue
        # "1 entry" is not an answer to "which machines can run it". The
        # eligible SET is the one field whose canonical value is a structure the
        # planner has never seen; resolve it through the same capability
        # resolver the routes use, so the two cannot name different machines.
        if got.field_name == "resource_requirements":
            names = None
            try:
                names = explainer._eligible_machine_names(
                    (matched or {}).get("entity", {}).get("id"))
            except Exception:  # noqa: BLE001 — unreadable eligibility is unknown
                names = None
            rendered = (", ".join(names) if names
                        else "I can't read the eligible set for this operation")
            got = AttributeFact(**{**vars(got), "rendered": rendered})
        facts.append(got)

    # A duration question wants the placement figures; nothing else does.
    wants_duration = any(a.field_name in ("run_duration", "setup_duration",
                                          "run_rate") for a in aliases)
    return AttributeAnswer(subject=label, facts=tuple(facts),
                           unknown_fields=tuple(unknown),
                           placement=tuple(placement) if wants_duration else (),
                           inherited_field=inherited)


def render(ans: AttributeAnswer) -> str:
    """The planner-facing rendering: the value first, its source second, and
    nothing else. A lookup that opens with a paragraph is a lookup that lost."""
    lines: list[str] = []
    if ans.inherited_field and ans.facts:
        lines.append(f"Reading the same field you just asked about, for "
                     f"{ans.subject}:")
    for f in ans.facts:
        # The label is the FACT'S own, not the answer's: one ask can name an
        # operation field and an order field at once, and they live on
        # different entities ("ORD-000013 op20" vs "ORD-000013").
        line = f"{f.entity_label or ans.subject} — {f.line()}"
        if f.ids_ref and (f.source or f.empty):
            line = line.rstrip(".") + f" (incoming-data spec {f.ids_ref})."
        if f.note and f.note not in line:
            line = line.rstrip(".") + f"; {f.note}."
        lines.append(line if line.endswith(".") else line + ".")
    for p in ans.placement:
        lines.append(f"{ans.subject} — {p}.")
    for u in ans.unknown_fields:
        lines.append(f"{ans.subject} carries no {u} in this run — that field is "
                     "not part of what was submitted.")
    return "\n".join(lines)
