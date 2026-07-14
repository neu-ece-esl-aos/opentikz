"""The per-figure intent layer (ADR-0005 D3 §4 row; contract §4).

Realizes the intent record three ways (net-new — opentikz has no analog):

1. a per-figure **sidecar** YAML file (``templates/<name>/intent.yaml``),
   owned by the adapter, not by opentikz metadata. Its base shape is the
   contract's §4 shape (``slug``/``family``/``subject``/``thesis``/
   ``visual_argument``/``entities``/``relationships``/``check_questions``/
   ``provenance``); the adapter *extends* it with two adapter-owned fields
   the contract does not define: each ``entities[]`` item may carry
   ``component`` (a §1 vocabulary id) plus **one of**:
     - ``nodes``: a literal list of concrete ``.tex`` node names (a small,
       hand-instantiated, fixed-shape figure), or
     - ``node_family``: ``{stem, indices}`` — an indexed-family pattern for a
       `\foreach`-generated array at any scale (the family-wide convention,
       cp-4883 ruling: dash-separated, index-addressable, e.g.
       ``cell-<row>-<col>``, never concatenated digits like ``g11``, which
       becomes ambiguous once an index exceeds 9)
   so ``node_naming`` can be derived mechanically either way (see
   ``derive.py``). A top-level ``parameters`` list — the intent record's
   "what varies" — is the derivation source for ``edit_contract.parameters``.
   None of this widens opentikz's ``edit_contract`` schema (D2); it lives one
   layer above it, in the sidecar the adapter owns.
2. a **master-header** comment block inside ``template.tex`` carrying
   ``subject``/``thesis``/``provenance`` (contract's master-header rule).
3. ``edit_contract.parameters`` derived from this record (``derive.py``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Contract §4's own required fields (the shape a sidecar must carry *at
# minimum*; the adapter extension fields below are additive on top of this).
CONTRACT_REQUIRED_FIELDS = (
    "slug",
    "family",
    "subject",
    "thesis",
    "visual_argument",
    "entities",
    "relationships",
    "check_questions",
    "provenance",
)


@dataclass(frozen=True)
class IntentRecord:
    slug: str
    family: str
    subject: str
    thesis: str
    visual_argument: str
    entities: list        # [{name, role, component?, nodes?}, ...]
    relationships: list   # [{from, to, carries}, ...]
    check_questions: list
    provenance: dict      # {sources: [...], constraints: [...]}
    parameters: list      # ADAPTER EXTENSION (not contract §4): "what varies"
    path: Path

    def entities_with_component(self) -> list:
        """Entities that name a §1 vocabulary component (subject to the
        adapter's extensibility-rule check and projected into node_naming)."""
        return [e for e in self.entities if e.get("component")]


class IntentRecordError(ValueError):
    pass


def load_intent_record(path: Path) -> IntentRecord:
    if not path.exists():
        raise IntentRecordError(
            f"{path}: no sidecar intent record found. Every template that ships an "
            "edit_contract must carry a contract-§4-shaped intent record (see "
            "intent-record-template.md) — the adapter derives edit_contract from it."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    missing = [f for f in CONTRACT_REQUIRED_FIELDS if f not in data]
    if missing:
        raise IntentRecordError(
            f"{path}: missing contract §4 required field(s): {', '.join(missing)}"
        )
    if "parameters" not in data:
        raise IntentRecordError(
            f"{path}: missing adapter-extension field 'parameters' (the intent "
            "record's \"what varies\" — edit_contract.parameters is derived from it)"
        )

    return IntentRecord(
        slug=data["slug"],
        family=data["family"],
        subject=data["subject"],
        thesis=data["thesis"],
        visual_argument=data["visual_argument"],
        entities=data["entities"] or [],
        relationships=data["relationships"] or [],
        check_questions=data["check_questions"] or [],
        provenance=data["provenance"] or {},
        parameters=data["parameters"] or [],
        path=path,
    )


def intent_sidecar_path(template_dir: Path) -> Path:
    return template_dir / "intent.yaml"


# --- master-header (template.tex) ------------------------------------- #

@dataclass(frozen=True)
class MasterHeader:
    subject: str | None
    thesis: str | None
    provenance_text: str    # the raw text of every leading "% ..." line, for loose containment checks


_HEADER_LINE_RE = re.compile(r"^%\s?(.*)$")
_SUBJECT_LINE_RE = re.compile(r"^[\w.-]+\s*[—-]{1,2}\s*(.+)$")
_THESIS_LINE_RE = re.compile(r"^THESIS:\s*(.+)$", re.IGNORECASE)


def extract_master_header(tex_text: str) -> MasterHeader:
    """Parse the leading run of ``%``-comment lines at the top of a
    ``template.tex`` as the contract's master-header block:

        % <slug> — <subject>
        % THESIS: <thesis>
        % <further provenance lines: sources / constraints>
    """
    lines = tex_text.splitlines()
    header_lines: list[str] = []
    for line in lines:
        m = _HEADER_LINE_RE.match(line)
        if m is None:
            break
        header_lines.append(m.group(1).strip())

    subject = None
    thesis = None
    for line in header_lines:
        if subject is None:
            m_subj = _SUBJECT_LINE_RE.match(line)
            if m_subj:
                subject = m_subj.group(1).strip()
                continue
        m_thesis = _THESIS_LINE_RE.match(line)
        if m_thesis:
            thesis = m_thesis.group(1).strip()

    return MasterHeader(subject=subject, thesis=thesis, provenance_text="\n".join(header_lines))


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().rstrip(".").lower()


def master_header_matches_intent(header: MasterHeader, intent: IntentRecord) -> list[str]:
    """Return a list of mismatch descriptions (empty means it matches)."""
    problems: list[str] = []
    if header.subject is None:
        problems.append("template.tex has no master-header subject line ('% <slug> — <subject>')")
    elif _normalize(header.subject) != _normalize(intent.subject):
        problems.append(
            f"master-header subject ({header.subject!r}) does not match "
            f"intent record subject ({intent.subject!r})"
        )

    if header.thesis is None:
        problems.append("template.tex has no master-header '% THESIS: ...' line")
    elif _normalize(header.thesis) != _normalize(intent.thesis):
        problems.append(
            f"master-header thesis ({header.thesis!r}) does not match "
            f"intent record thesis ({intent.thesis!r})"
        )

    provenance_norm = _normalize(header.provenance_text)
    for source in intent.provenance.get("sources", []) or []:
        if _normalize(source) not in provenance_norm:
            problems.append(f"intent record provenance source {source!r} is not carried in the master header")
    for constraint in intent.provenance.get("constraints", []) or []:
        if _normalize(constraint) not in provenance_norm:
            problems.append(f"intent record provenance constraint {constraint!r} is not carried in the master header")

    return problems
