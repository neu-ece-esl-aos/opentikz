"""Adapter enforcement checks (ADR-0005 D2/D3), wired into ``tools/validate.py``
so they run in the verify loop and in CI without any ``.github/workflows/``
edit (see README-ESL.md "CI logic convention" — folding into ``validate.py``
rides the existing, unedited ``ci.yml`` invocation).

Scope: only templates carrying the ``esl-architecture`` domain tag are
adapter-governed (ADR-0005 Phase 2b builds the ESL figure-authoring contract's
backend #2 — it does not retrofit every template this fork inherited from
upstream opentikz). Five checks run for each ESL-contract template that ships
an ``edit_contract``:

1. **Re-derivability** — the checked-in ``edit_contract`` must equal what the
   adapter derives right now from the contract + the template's intent
   record (``node_naming``/``styles``/``parameters``/``invariants``;
   ``operations`` is hand-authored and excluded from the comparison).
2. **§1 extensibility rule** — every intent-record entity naming a
   ``component`` must be a real contract §1 vocabulary id.
3. **Master-header <-> sidecar match** — the ``template.tex`` header comment
   block's subject/thesis/provenance must match the sidecar intent record.
4. **Placement-grammar** (WP-7, ADR-0005 D3 §3b row) — every family
   ``placement_grammar`` rule that ``placement_grammar.py`` can prove
   statically must hold; only a proven ``FAIL`` blocks here — a rule this
   fork can't check from source alone (``NEEDS_RENDER``) is intentionally
   NOT a validate.py failure (see ``tools/adapter/cli.py grammar`` /
   ``tools/ci/placement-grammar-report.sh`` for the full per-rule verdict
   breakdown, including what's routed to WP-8's rendered-PNG gate).
5. **circuitikz bipole node identity** (WP-11, cp-4925; circuit-schematic
   family only) — every ``to[...]`` bipole must carry a ``name=<id>`` key
   (settled-decisions/circuit-schematic.yaml ``circuitikz-bipole-node-identity``),
   so it has PGF node identity and is visible to
   ``render_selfcheck.detect_node_node_collisions`` — see
   ``bipole_naming_problems``.
"""
from __future__ import annotations

import re
from pathlib import Path

from .contract_loader import Contract
from .derive import derive_edit_contract, load_settled_decisions, strip_tex_comments
from .intent import (
    IntentRecordError,
    extract_master_header,
    intent_sidecar_path,
    load_intent_record,
    master_header_matches_intent,
)
from .placement_grammar import placement_grammar_problems

# circuitikz bipole invocation: \draw (a) to[<options>] (b); -- <options> is a
# comma-separated key/value list with no nested `[`/`]` in this library's
# templates (see circuitikz-bipole-node-identity below), so a non-greedy scan
# to the next `]` is sufficient.
_BIPOLE_RE = re.compile(r"\bto\s*\[([^\[\]]*)\]")
_BIPOLE_NAME_KEY_RE = re.compile(r"(?:^|,)\s*name\s*=")


def bipole_naming_problems(tex_text: str, tex: Path) -> list[str]:
    """WP-11 (cp-4925), settled-decisions/circuit-schematic.yaml
    ``circuitikz-bipole-node-identity``: every circuitikz ``to[...]`` bipole
    must carry a ``name=<id>`` key. Without one, the bipole is a raw drawing
    path with no PGF/TikZ node identity -- invisible to
    ``render_selfcheck.detect_node_node_collisions`` (see
    docs/VISUAL_SELFCHECK.md). This is a source-level, syntactic check (it
    looks for the literal ``name=`` key, not an expanded value), so it also
    covers a \\foreach-generated bipole whose name is itself a macro
    (e.g. ``name=\\devname``) -- the macro still has to be threaded through
    the foreach list at the source level for this to pass.
    """
    text = strip_tex_comments(tex_text)
    problems: list[str] = []
    for m in _BIPOLE_RE.finditer(text):
        opts = m.group(1)
        if not _BIPOLE_NAME_KEY_RE.search(opts):
            line = text.count("\n", 0, m.start()) + 1
            problems.append(
                f"{tex}:{line}: circuitikz bipole 'to[{opts.strip()}]' has no "
                "name=<id> key -- every to[...] bipole in the circuit-schematic "
                "family must carry one (settled-decisions/circuit-schematic.yaml "
                "circuitikz-bipole-node-identity) so it has PGF node identity and "
                "is visible to render_selfcheck.detect_node_node_collisions"
            )
    return problems

_DERIVED_FIELDS = ("node_naming", "styles", "parameters", "invariants")

# Scope marker: the backend-adapter (ADR-0005 Phase 2b) governs the ESL
# figure-authoring contract's templates, not every generic template this fork
# inherited from upstream opentikz. A template opts into adapter enforcement
# by carrying this domain tag (both cp-4856 fixtures already do) — templates
# without it keep their hand-authored edit_contract, un-checked by the adapter.
ESL_DOMAIN_TAG = "esl-architecture"


def _sorted_by_name(items: list) -> list:
    return sorted(items, key=lambda d: d.get("name", ""))


def adapter_problems(meta: dict, tex: Path, template_dir: Path, contract: Contract) -> list[str]:
    """Run every adapter check for one template. Returns problem strings
    (empty means the template is contract-conformant and drift-free).
    Only applies to templates that ship an ``edit_contract``; callers should
    only invoke this for ``meta.get("type") == "template"`` items.
    """
    edit_contract = meta.get("edit_contract")
    if edit_contract is None:
        return []
    if ESL_DOMAIN_TAG not in (meta.get("domain") or []):
        return []

    problems: list[str] = []

    sidecar_path = intent_sidecar_path(template_dir)
    try:
        intent = load_intent_record(sidecar_path)
    except IntentRecordError as exc:
        return [str(exc)]

    if intent.family not in ("flow", "architecture", "circuit-schematic"):
        problems.append(
            f"{sidecar_path}: intent record family {intent.family!r} is not one of "
            "the contract's three families (flow | architecture | circuit-schematic)"
        )

    # --- check 2: §1 extensibility rule -------------------------------- #
    for entity in intent.entities_with_component():
        component = entity["component"]
        if not contract.has_component(component):
            problems.append(
                f"{sidecar_path}: entity {entity.get('name', '?')!r} names semantic "
                f"component {component!r}, which the contract's §1 vocabulary does not "
                "define (extensibility rule: add to the contract's §1 first, or this is "
                "a contract gap — record it in contract/CONTRACT-GAPS.md)"
            )

    # --- check 1: re-derivability / drift ------------------------------- #
    tex_text = tex.read_text(encoding="utf-8")
    settled_decisions = load_settled_decisions(intent.family)
    derived = derive_edit_contract(tex_text, contract, intent, settled_decisions)

    for field_name in _DERIVED_FIELDS:
        checked_in = edit_contract.get(field_name)
        expected = derived.get(field_name)
        if field_name == "parameters":
            checked_in_cmp = _sorted_by_name(checked_in or [])
            expected_cmp = _sorted_by_name(expected or [])
        elif field_name in ("styles", "invariants"):
            checked_in_cmp = sorted(checked_in or [])
            expected_cmp = sorted(expected or [])
        else:
            checked_in_cmp, expected_cmp = checked_in, expected
        if checked_in_cmp != expected_cmp:
            problems.append(
                f"edit_contract.{field_name} has drifted from the adapter-derived view "
                f"(derived from contract + {sidecar_path.name}); "
                f"checked-in={checked_in!r} derived={expected!r}. "
                "Regenerate with tools/adapter/cli.py derive --write."
            )

    # --- check 3: master-header <-> sidecar match ----------------------- #
    header = extract_master_header(tex_text)
    problems.extend(f"{tex}: {p}" for p in master_header_matches_intent(header, intent))

    # --- check 4: placement-grammar (WP-7) ------------------------------ #
    problems.extend(placement_grammar_problems(tex_text, intent, settled_decisions, tex_path=tex))

    # --- check 5: circuitikz bipole node identity (WP-11) --------------- #
    if intent.family == "circuit-schematic":
        problems.extend(bipole_naming_problems(tex_text, tex))

    return problems
