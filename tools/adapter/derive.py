"""Derive a template's ``edit_contract`` from the contract + its intent record.

ADR-0005 D2: ``edit_contract`` is a **derived, mechanical view** — never a
second place semantic decisions live. This module is the one place that
mechanical view is produced:

  - ``node_naming``  <- projected from the §1 component names the intent
                        record's entities bind to concrete ``.tex`` node
                        names (a 1:1 correspondence, cp-4856)
  - ``styles``       <- every ``<name>/.style`` binding actually defined in
                        the ``.tex`` (mechanical scan; cp-4856 found this is
                        1:1 with tikzset names)
  - ``parameters``   <- copied from the intent record's "what varies"
                        (contract §4 row, D3)
  - ``invariants``   <- the adapter-baseline invariants (extensibility rule +
                        token-binding rule) plus, once WP-7 lands a family
                        settled-decisions record, that record's applicable
                        slice (the seam: ``load_settled_decisions``)

``operations`` is intentionally **not** derived — it is prose describing
safe, contract-sanctioned edit recipes that has no contract-element source
(D3's mapping table has no row for it); it stays hand-authored and is passed
through unchanged by the drift check.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .contract_loader import Contract
from .intent import IntentRecord

STYLE_DEF_RE = re.compile(r"([A-Za-z][\w ]*?)\s*/\.style\s*=")

BASELINE_INVARIANTS = [
    "a template must not name a semantic component the contract's §1 vocabulary "
    "does not define (§1 extensibility rule)",
    "style/color bindings carry their contract §2 token role; a role's color is "
    "never swapped for decoration",
]


def strip_tex_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        buf = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                buf.append(line[i : i + 2])
                i += 2
                continue
            if ch == "%":
                break
            buf.append(ch)
            i += 1
        out.append("".join(buf))
    return "\n".join(out)


def derive_node_naming(intent: IntentRecord, contract: Contract) -> str:
    """Project §1 component names -> concrete node names, per entity.

    Only entities carrying the adapter-extension ``component`` (+ ``nodes``)
    fields participate — those are checked against the contract's §1
    vocabulary elsewhere (``checks.py``). Entities without a ``component``
    are free-text per contract §4 and are not part of this mechanical view
    (e.g. a structural node with no §1 vocabulary counterpart — record that
    as a contract gap, don't invent a mapping).
    """
    parts = []
    for entity in intent.entities_with_component():
        component = entity["component"]
        nodes = entity.get("nodes") or []
        parts.append(f"{component}: (" + ", ".join(nodes) + ")")
    return "; ".join(parts)


def derive_styles(tex_text: str) -> list[str]:
    text = strip_tex_comments(tex_text)
    seen: list[str] = []
    for match in STYLE_DEF_RE.finditer(text):
        name = match.group(1).strip()
        if name not in seen:
            seen.append(name)
    return seen


def derive_parameters(intent: IntentRecord) -> list[dict]:
    # Straight passthrough of the intent record's "what varies" list — the
    # contract-mandated derivation source (D3 §4 row); no independent
    # authoring at the edit_contract layer.
    return [dict(p) for p in intent.parameters]


def load_settled_decisions(family: str, root: Path | None = None) -> dict | None:
    """WP-7 seam: load the family-level settled-decisions record, if it has
    landed. Returns ``None`` until WP-7 ships ``settled-decisions/<family>.yaml``
    (this WP does not author that record — see ADR-0005 D3 §3 row) so
    ``derive_invariants`` can fall back to the adapter baseline.
    """
    base = root or (Path(__file__).resolve().parent / "settled-decisions")
    path = base / f"{family}.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def derive_invariants(family: str, settled_decisions: dict | None) -> list[str]:
    invariants = list(BASELINE_INVARIANTS)
    if settled_decisions is None:
        invariants.append(
            f"(seam: no WP-7 family settled-decisions record yet for family {family!r}; "
            "family-specific placement/style/semantic invariants project here once it lands)"
        )
        return invariants
    for entry in settled_decisions.get("placement_grammar", []) or []:
        invariants.append(f"{entry['id']}: {entry['rule']}")
    for entry in settled_decisions.get("style_decisions", []) or []:
        invariants.append(f"{entry['id']}: {entry['decision']}")
    for entry in settled_decisions.get("semantic_decisions", []) or []:
        invariants.append(f"{entry['id']}: {entry['decision']}")
    return invariants


def derive_edit_contract(
    tex_text: str,
    contract: Contract,
    intent: IntentRecord,
    settled_decisions: dict | None = None,
) -> dict:
    """The mechanical view: everything D2/D3 say must be *derived*, not
    hand-authored. ``operations`` is deliberately absent — callers merge in
    the template's hand-authored ``operations`` unchanged.
    """
    return {
        "parameters": derive_parameters(intent),
        "node_naming": derive_node_naming(intent, contract),
        "styles": derive_styles(tex_text),
        "invariants": derive_invariants(intent.family, settled_decisions),
    }
