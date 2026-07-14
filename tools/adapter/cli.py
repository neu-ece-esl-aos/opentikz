#!/usr/bin/env python3
"""Backend-adapter CLI: derive/inspect a template's ``edit_contract``.

    python3 tools/adapter/cli.py derive <template-dir> [--write]
    python3 tools/adapter/cli.py check  <template-dir>

``derive`` prints the adapter-derived ``edit_contract`` fields (or, with
``--write``, merges them into the template's ``template.meta.json`` in place,
preserving the hand-authored ``operations`` list). ``check`` runs the same
enforcement checks ``tools/validate.py`` runs in CI, for one template.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import load_json, repo_root  # noqa: E402

from adapter.checks import adapter_problems  # noqa: E402
from adapter.contract_loader import load_contract  # noqa: E402
from adapter.derive import derive_edit_contract, load_settled_decisions  # noqa: E402
from adapter.intent import intent_sidecar_path, load_intent_record  # noqa: E402


def _template_paths(template_dir: Path) -> tuple[Path, Path]:
    meta_path = template_dir / "template.meta.json"
    tex_path = template_dir / "template.tex"
    return meta_path, tex_path


def _find_matching_brace(text: str, open_idx: int) -> int:
    """Return the index of the ``}`` matching the ``{`` at ``open_idx``,
    respecting JSON string literals (so a ``{``/``}`` inside a quoted value
    doesn't throw off the depth count)."""
    depth = 0
    in_string = False
    escape = False
    i = open_idx
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("no matching closing brace found")


def _render_edit_contract_value(ec: dict, key_indent: str) -> str:
    """Render just the ``{...}`` value for the ``"edit_contract"`` key, in the
    file's existing hand-formatting convention (compact single-line objects
    inside arrays; one array item per line) — so regenerating only touches
    the edit_contract span, not the whole file's formatting.
    """
    child = key_indent + "  "
    item = child + "  "

    def _array_of(name: str, items: list, render_item) -> list[str]:
        lines = [f'{child}"{name}": [']
        for i, it in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            lines.append(f"{item}{render_item(it)}{comma}")
        lines.append(f"{child}],")
        return lines

    lines = ["{"]
    lines += _array_of("parameters", ec["parameters"], lambda p: json.dumps(p, ensure_ascii=False))
    lines.append(f'{child}"node_naming": {json.dumps(ec["node_naming"], ensure_ascii=False)},')
    lines.append(f'{child}"styles": {json.dumps(ec["styles"], ensure_ascii=False)},')
    lines += _array_of("operations", ec["operations"], lambda o: json.dumps(o, ensure_ascii=False))
    inv_lines = _array_of("invariants", ec["invariants"], lambda s: json.dumps(s, ensure_ascii=False))
    inv_lines[-1] = inv_lines[-1].rstrip(",")  # last field in the object: no trailing comma
    lines += inv_lines
    lines.append(f"{key_indent}}}")
    return "\n".join(lines)


def cmd_derive(args: argparse.Namespace) -> int:
    root = repo_root()
    template_dir = Path(args.template_dir).resolve()
    meta_path, tex_path = _template_paths(template_dir)
    meta = load_json(meta_path)
    contract = load_contract()
    intent = load_intent_record(intent_sidecar_path(template_dir))
    settled_decisions = load_settled_decisions(intent.family)
    derived = derive_edit_contract(tex_path.read_text(encoding="utf-8"), contract, intent, settled_decisions)

    if args.write:
        existing = meta.get("edit_contract", {})
        operations = existing.get("operations")
        if operations is None:
            print("error: template.meta.json has no edit_contract.operations to preserve; "
                  "author it by hand first (operations is not adapter-derived)", file=sys.stderr)
            return 1
        new_ec = {
            "parameters": derived["parameters"],
            "node_naming": derived["node_naming"],
            "styles": derived["styles"],
            "operations": operations,
            "invariants": derived["invariants"],
        }

        raw = meta_path.read_text(encoding="utf-8")
        m = re.search(r'"edit_contract"\s*:\s*', raw)
        if not m:
            print(f"error: {meta_path}: no edit_contract key found", file=sys.stderr)
            return 1
        brace_start = raw.index("{", m.end())
        brace_end = _find_matching_brace(raw, brace_start)
        line_start = raw.rfind("\n", 0, m.start()) + 1
        key_indent = raw[line_start : m.start()]
        rendered = _render_edit_contract_value(new_ec, key_indent)
        new_raw = raw[:brace_start] + rendered + raw[brace_end + 1 :]
        json.loads(new_raw)  # sanity: still valid JSON before touching disk
        meta_path.write_text(new_raw, encoding="utf-8")
        print(f"wrote derived edit_contract to {meta_path.relative_to(root)}")
    else:
        print(json.dumps(derived, indent=2, ensure_ascii=False))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    template_dir = Path(args.template_dir).resolve()
    meta_path, tex_path = _template_paths(template_dir)
    meta = load_json(meta_path)
    contract = load_contract()
    problems = adapter_problems(meta, tex_path, template_dir, contract)
    if problems:
        for p in problems:
            print(f"FAIL  {p}")
        return 1
    print(f"PASS  {template_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_derive = sub.add_parser("derive", help="derive edit_contract for a template")
    p_derive.add_argument("template_dir")
    p_derive.add_argument("--write", action="store_true", help="merge into template.meta.json in place")
    p_derive.set_defaults(func=cmd_derive)

    p_check = sub.add_parser("check", help="run adapter enforcement checks for a template")
    p_check.add_argument("template_dir")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
