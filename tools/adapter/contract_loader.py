"""Load the vendored frozen backend contract as structured, queryable data.

Parses ``contract/backend-contract-v1.2.0.md`` directly (the contract must be
buildable *from the document alone*, ADR-0005 D3 conformance obligation) —
never TikZ internals (``figstyle.tex`` / ``tikzsemantics.tex``). Exposes:

- section 1 (§1a/§1b): the semantic component/macro vocabulary (name + role,
  both families)
- section 2 (§2): style/color tokens (token -> role, default hue, neutral hex)
- section 3a: the 6-primitive generic placement-semantics core
- section 3b: the per-family settled-decisions record schema (field sketch)
- section 4: the intent-record format (field sketch)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import repo_root  # noqa: E402

CONTRACT_RELPATH = "contract/backend-contract-v1.2.0.md"

# Families named by the contract's schemas (§3/§4 `family:` field).
FAMILIES = ("flow", "architecture", "circuit-schematic")

# Which §1 vocabulary subsection each family's components live in. Both
# `architecture` and `flow` draw on the combined §1b table.
_FAMILY_TO_VOCAB_SECTION = {
    "circuit-schematic": "1a",
    "architecture": "1b",
    "flow": "1b",
}


@dataclass(frozen=True)
class Component:
    name: str            # contract name, e.g. "crossbar-cell"
    role: str            # role in the figure
    tikz_realization: str
    section: str          # "1a" | "1b"


@dataclass(frozen=True)
class StyleToken:
    token: str
    role: str
    default_hue: str
    neutral_hex: str


@dataclass(frozen=True)
class PlacementPrimitive:
    id: str
    meaning: str
    circuit_realization: str
    architecture_realization: str
    flow_realization: str


@dataclass(frozen=True)
class Contract:
    version: str
    path: Path
    text: str
    components: dict           # name -> Component
    style_tokens: dict         # token -> StyleToken
    placement_primitives: dict  # id -> PlacementPrimitive
    settled_decisions_schema: dict  # field sketch, see _sketch_yaml_schema
    intent_record_schema: dict      # field sketch, see _sketch_yaml_schema

    # --- §1 queries -------------------------------------------------- #
    def component_names(self, family: str | None = None) -> list[str]:
        if family is None:
            return sorted(self.components)
        section = _FAMILY_TO_VOCAB_SECTION[family]
        return sorted(c.name for c in self.components.values() if c.section == section)

    def has_component(self, name: str) -> bool:
        return name in self.components

    # --- §2 queries -------------------------------------------------- #
    def has_style_token(self, token: str) -> bool:
        return token in self.style_tokens

    # --- §3a queries ------------------------------------------------- #
    def has_primitive(self, primitive_id: str) -> bool:
        return primitive_id in self.placement_primitives


def _strip_md_comments(text: str) -> str:
    # Drop blockquote "changelog" callouts (`> ...`) so they don't pollute
    # section slicing; they never contain table/schema content we parse.
    return "\n".join(line for line in text.splitlines() if not line.startswith(">"))


def _section(text: str, start: str, end: str | None) -> str:
    """Return the text between a `start` heading (inclusive) and the next
    `end` heading (exclusive); to end-of-document if `end` is None."""
    start_idx = text.index(start)
    if end is None:
        return text[start_idx:]
    end_idx = text.index(end, start_idx + len(start))
    return text[start_idx:end_idx]


def _parse_md_table(block: str) -> list[list[str]]:
    """Parse a GFM pipe-table's data rows (skips the header + separator row)."""
    lines = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def _unbacktick(cell: str) -> str:
    return cell.strip().strip("*").strip().strip("`").strip()


def _split_names(cell: str) -> list[str]:
    """Split a cell like "`a` / `b` / `c`" into ["a", "b", "c"]."""
    return [_unbacktick(part) for part in cell.split("/") if part.strip()]


def _parse_components(block: str, section_id: str) -> list[Component]:
    out: list[Component] = []
    for row in _parse_md_table(block):
        if len(row) < 3:
            continue
        names = _split_names(row[0])
        role, realization = row[1], row[2]
        for name in names:
            out.append(Component(name=name, role=role, tikz_realization=realization, section=section_id))
    return out


def _parse_style_tokens(block: str) -> list[StyleToken]:
    out: list[StyleToken] = []
    for row in _parse_md_table(block):
        if len(row) < 4:
            continue
        token, role, hue, hexv = row
        out.append(StyleToken(token=_unbacktick(token), role=role, default_hue=hue, neutral_hex=_unbacktick(hexv)))
    return out


def _parse_placement_primitives(block: str) -> list[PlacementPrimitive]:
    out: list[PlacementPrimitive] = []
    for row in _parse_md_table(block):
        if len(row) < 6:
            continue
        _num, pid, meaning, circuit, arch, flow = row[:6]
        out.append(
            PlacementPrimitive(
                id=_unbacktick(pid),
                meaning=meaning,
                circuit_realization=circuit,
                architecture_realization=arch,
                flow_realization=flow,
            )
        )
    return out


_TOP_FIELD_RE = re.compile(r"^([a-zA-Z_][\w]*):\s*(.*)$")
_INDENTED_FIELD_RE = re.compile(r"^\s+-?\s*([a-zA-Z_][\w]*):\s*(.*)$")


def _sketch_yaml_schema(block: str) -> dict:
    """Lightly parse a YAML-*shaped* schema block (values are placeholders,
    e.g. ``<flow | architecture | circuit-schematic>``, not real YAML values,
    so this is a structural field-name sketch, not a full YAML parse).

    Returns ``{top_field: {"placeholder": str, "item_fields": [str, ...]}}``;
    ``item_fields`` is populated for list-valued fields from their first
    ``- id: ...`` style item template.
    """
    fields: dict = {}
    current_top: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.split("  #", 1)[0].rstrip()
        if not line.strip():
            continue
        m_top = _TOP_FIELD_RE.match(line)
        if m_top:
            current_top = m_top.group(1)
            fields[current_top] = {"placeholder": m_top.group(2).strip(), "item_fields": []}
            continue
        m_indented = _INDENTED_FIELD_RE.match(line)
        if m_indented and current_top:
            fname = m_indented.group(1)
            if fname not in fields[current_top]["item_fields"]:
                fields[current_top]["item_fields"].append(fname)
    return fields


def _first_fenced_block(text: str, lang: str = "yaml") -> str:
    marker = f"```{lang}"
    start = text.index(marker) + len(marker)
    end = text.index("```", start)
    return text[start:end]


def load_contract(path: Path | None = None) -> Contract:
    root = repo_root()
    contract_path = path or (root / CONTRACT_RELPATH)
    raw_text = contract_path.read_text(encoding="utf-8")
    text = _strip_md_comments(raw_text)

    m = re.search(r"\*\*Contract version:\*\*\s*`([^`]+)`", text)
    version = m.group(1) if m else "unknown"

    # --- §1 vocabulary ------------------------------------------------ #
    sec1 = _section(text, "## 1. Semantic component", "## 2. Style / color tokens")
    sec1a = _section(sec1, "### 1a. Circuit / schematic family", "### 1b. Architecture / flow family")
    sec1b = _section(sec1, "### 1b. Architecture / flow family", None)
    if "**Extensibility rule.**" in sec1b:
        sec1b = sec1b[: sec1b.index("**Extensibility rule.**")]
    components = _parse_components(sec1a, "1a") + _parse_components(sec1b, "1b")

    # --- §2 style/color tokens ----------------------------------------- #
    sec2 = _section(text, "## 2. Style / color tokens", "## 3. Settled-decisions record schema")
    style_tokens = _parse_style_tokens(sec2)

    # --- §3 settled-decisions schema (incl. §3a primitives, §3b schema) #
    sec3 = _section(text, "## 3. Settled-decisions record schema", "## 4. Intent-record format")
    sec3a = _section(sec3, "### 3a. Generic placement-primitive core", "### 3b. Per-family record schema")
    primitives = _parse_placement_primitives(sec3a)
    sec3b = _section(sec3, "### 3b. Per-family record schema", None)
    settled_decisions_schema = _sketch_yaml_schema(_first_fenced_block(sec3b, "yaml"))

    # --- §4 intent-record format --------------------------------------- #
    sec4 = _section(text, "## 4. Intent-record format", "## 5. What is NOT in the contract")
    intent_record_schema = _sketch_yaml_schema(_first_fenced_block(sec4, "yaml"))

    return Contract(
        version=version,
        path=contract_path,
        text=raw_text,
        components={c.name: c for c in components},
        style_tokens={t.token: t for t in style_tokens},
        placement_primitives={p.id: p for p in primitives},
        settled_decisions_schema=settled_decisions_schema,
        intent_record_schema=intent_record_schema,
    )
