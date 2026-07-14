#!/usr/bin/env python3
"""Validate OpenTikZ content items.

For every ``*.meta.json`` under icons/, templates/, examples/:
  1. validate it against meta.schema.json (using the ``jsonschema`` library);
  2. enforce the project's structural rules statically (no LaTeX needed):
       - the sibling ``.tex`` exists and uses ``\\documentclass{standalone}``;
       - ``id`` is globally unique across the library;
       - every id in ``composed_of`` resolves to a real library item;
       - every ``\\usetikzlibrary`` (and ``tikz`` itself) used by the ``.tex`` is
         declared in ``requires`` (so the metadata never drifts from the source);
       - any ``edit_contract`` (templates only) names parameters/styles that
         actually exist in the ``.tex`` (so the skill's contract never drifts);
  3. confirm the ``.tex`` compiles standalone via ``latexmk``.

The static checks (1, 2) always run. The compile step (3) is SKIPped (non-fatal)
when no LaTeX engine is installed, so the script still runs locally without a TeX
distribution. Use ``--strict`` in CI, where the compile is required and a SKIP
becomes a failure.

Exit code is non-zero if any item FAILs.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _common import iter_meta_files, load_json, rel, repo_root, tex_sibling
from render_selfcheck import DEFAULT_DPI, detect_overfull, detect_text_overlaps, render_png

SCHEMA_NAME = "meta.schema.json"
SELFCHECK_PNG_DIR = "_selfcheck-pngs"  # gitignored; CI's PNG-self-check-gate output

# --- .tex static analysis ------------------------------------------------- #
_DOCCLASS_RE = re.compile(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}")
_TIKZLIB_RE = re.compile(r"\\usetikzlibrary\s*\{([^}]*)\}")
_USEPKG_RE = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


def _strip_tex_comments(text: str) -> str:
    """Drop TeX line comments (an unescaped ``%`` to end of line)."""
    out: list[str] = []
    for line in text.splitlines():
        buf: list[str] = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):  # escaped char (incl. \%)
                buf.append(line[i : i + 2])
                i += 2
                continue
            if ch == "%":
                break
            buf.append(ch)
            i += 1
        out.append("".join(buf))
    return "\n".join(out)


def _scan_tex(tex: Path) -> tuple[str | None, set[str], set[str]]:
    """Return (documentclass, tikz libraries, \\usepackage names) used by a .tex."""
    text = _strip_tex_comments(tex.read_text(encoding="utf-8"))
    m = _DOCCLASS_RE.search(text)
    docclass_opts = m.group(1) if m else None
    docclass = m.group(2).strip() if m else None

    def _items(groups: list[str]) -> set[str]:
        names: set[str] = set()
        for grp in groups:
            for name in grp.split(","):
                name = name.strip()
                if name:
                    names.add(name)
        return names

    libs = _items(_TIKZLIB_RE.findall(text))
    pkgs = _items(_USEPKG_RE.findall(text))
    # `\documentclass[tikz]{standalone}` (the circuitikz/standalone idiom) loads
    # tikz via a class option rather than `\usepackage{tikz}` — register it as
    # provided so `requires` doesn't need "tikz" hand-added per template (cp-4856;
    # ADR-0005 D4).
    if docclass_opts:
        pkgs |= _items([docclass_opts])
    return docclass, libs, pkgs


def _structural_problems(
    meta: dict, tex: Path, known_ids: set[str]
) -> list[str]:
    """Project-rule checks on a (schema-valid) item. Returns a list of problems."""
    problems: list[str] = []
    docclass, libs, pkgs = _scan_tex(tex)

    if docclass != "standalone":
        problems.append(
            f"document class must be 'standalone' (found {docclass!r}); "
            "every content .tex must compile standalone"
        )

    requires = set(meta.get("requires", []))
    missing_libs = sorted(libs - requires)
    if missing_libs:
        problems.append(
            "requires is missing TikZ libraries used by the .tex: "
            + ", ".join(missing_libs)
            + " (mirror every \\usetikzlibrary into requires)"
        )
    if (libs or "tikz" in pkgs) and "tikz" not in requires:
        problems.append("requires must list 'tikz' (the .tex draws with TikZ)")

    for cid in meta.get("composed_of", []):
        if cid not in known_ids:
            problems.append(
                f"composed_of references unknown library id '{cid}'"
            )

    problems.extend(_edit_contract_problems(meta, tex))

    return problems


def _edit_contract_problems(meta: dict, tex: Path) -> list[str]:
    """Cross-check an edit_contract against its .tex (existence checks only).

    Every ``parameters[].name`` must appear as a ``\\def`` and every ``styles[]``
    entry as a ``<name>/.style`` in the source, so the contract the
    using-opentikz skill consumes can never drift from the figure.
    """
    contract = meta.get("edit_contract")
    if contract is None:
        return []

    problems: list[str] = []
    if meta.get("type") != "template":
        problems.append("edit_contract is only allowed on templates")

    text = _strip_tex_comments(tex.read_text(encoding="utf-8"))
    for param in contract.get("parameters", []):
        name = param.get("name", "")
        if not re.search(r"\\def\s*" + re.escape(name) + r"\b", text):
            problems.append(
                f"edit_contract parameter '{name}' has no \\def in the .tex"
            )
    for style in contract.get("styles", []):
        if not re.search(re.escape(style) + r"\s*/\.style", text):
            problems.append(
                f"edit_contract style '{style}' has no /.style definition in the .tex"
            )

    return problems


_CONTRACT_SHA256_RE = re.compile(r"```\n([0-9a-f]{64})\n```")


def _contract_checksum_problem(root: Path) -> str | None:
    """Check contract/backend-contract-v1.2.0.md against the sha256 pinned in
    contract/CONTRACT.md (ADR-0005 D2/D3: the frozen backend contract is consumed
    read-only; this is the drift gate for that vendored copy). Returns a problem
    string, or None if it matches -- or if contract/ hasn't been vendored yet
    (this check is a no-op before WP-1 lands it, and for any repo state that never
    carries a vendored contract)."""
    contract_file = root / "contract" / "backend-contract-v1.2.0.md"
    contract_doc = root / "contract" / "CONTRACT.md"
    if not contract_file.exists() or not contract_doc.exists():
        return None
    m = _CONTRACT_SHA256_RE.search(contract_doc.read_text(encoding="utf-8"))
    if not m:
        return "contract/CONTRACT.md has no pinned sha256 fenced code block"
    pin = m.group(1)
    actual = hashlib.sha256(contract_file.read_bytes()).hexdigest()
    if pin != actual:
        return (
            f"contract/backend-contract-v1.2.0.md checksum drift: "
            f"pinned={pin} actual={actual} -- see contract/CONTRACT.md change-control "
            "(never edit the vendored copy in place; re-vendor from the source of truth)"
        )
    return None


def _load_validator(root: Path):
    """Return a jsonschema validator for meta.schema.json, or exit on error."""
    try:
        import jsonschema  # noqa: WPS433 (local import: optional-at-import-time dep)
    except ModuleNotFoundError:
        sys.exit(
            "error: the 'jsonschema' package is required.\n"
            "       install it with:  python3 -m pip install -r requirements.txt"
        )
    schema = load_json(root / SCHEMA_NAME)
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def _latex_available() -> bool:
    return shutil.which("latexmk") is not None


def _compile_tex(
    tex: Path, selfcheck_png: Path | None = None
) -> tuple[bool, str, list[str]]:
    """Compile a standalone .tex with latexmk in a temp dir.

    Returns ``(ok, log, selfcheck_problems)``. When ``selfcheck_png`` is given
    and the compile succeeds, also runs the D6 visual-self-check gate's
    *mechanical* half (ADR-0005 §D6; docs/VISUAL_SELFCHECK.md) against the
    compiled PDF -- overfull/underfull box warnings and cross-label text-bbox
    overlap -- and rasterizes a PNG to ``selfcheck_png`` for the agent (or a
    human) to read, which is the half these mechanical checks CANNOT replace.
    """
    with tempfile.TemporaryDirectory(prefix="opentikz-build-") as tmp:
        proc = subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={tmp}",
                tex.name,
            ],
            cwd=tex.parent,
            capture_output=True,
            text=True,
        )
        log = proc.stdout + proc.stderr
        pdf = Path(tmp) / (tex.stem + ".pdf")
        ok = proc.returncode == 0 and pdf.exists()
        if not ok or selfcheck_png is None:
            return ok, log, []

        problems = detect_overfull(log)
        problems += detect_text_overlaps(pdf)
        selfcheck_png.parent.mkdir(parents=True, exist_ok=True)
        render_png(pdf, selfcheck_png.with_suffix(""), dpi=DEFAULT_DPI)
        return ok, log, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="require LaTeX: turn compile SKIPs into FAILs (use in CI).",
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="only validate metadata; never attempt to compile .tex.",
    )
    parser.add_argument(
        "--no-render-selfcheck",
        action="store_true",
        help=(
            "skip the D6 visual-self-check gate's mechanical half (PNG render + "
            "overfull-box / text-overlap detection). Does NOT skip the compile "
            "check -- only the render+mechanical-check step on top of it. Use "
            "for fast local metadata iteration; omit this flag (the default) "
            "in the authoring loop and whenever CI runs this script."
        ),
    )
    args = parser.parse_args(argv)

    root = repo_root()
    validator = _load_validator(root)

    have_latex = _latex_available()
    do_compile = not args.no_compile
    do_selfcheck = do_compile and not args.no_render_selfcheck
    if do_compile and not have_latex and not args.strict:
        print("note: latexmk not found; .tex compilation will be SKIPPED")
    if do_selfcheck:
        print(
            f"note: D6 visual-self-check PNGs will be written under "
            f"{SELFCHECK_PNG_DIR}/ -- mechanical checks only (overfull boxes, "
            "text-bbox overlap); READ THE PNGS for the semantic half "
            "(docs/VISUAL_SELFCHECK.md)."
        )

    n_pass = n_fail = n_skip = 0
    failures: list[str] = []

    # --- pass 1: load + schema-validate everything, then build the global id set.
    # composed_of references and id-uniqueness are cross-item, so they need the
    # whole library in hand before any per-item structural check runs.
    schema_ok: list[tuple[Path, dict]] = []  # items that passed schema validation
    id_paths: dict[str, list[str]] = {}      # id -> items declaring it (dup detect)
    for meta_path in iter_meta_files(root):
        item = rel(meta_path, root)
        try:
            meta = load_json(meta_path)
        except ValueError as exc:
            print(f"FAIL  {item}: {exc}")
            n_fail += 1
            failures.append(item)
            continue
        errors = sorted(validator.iter_errors(meta), key=lambda e: e.path)
        if errors:
            print(f"FAIL  {item}: schema validation")
            for err in errors:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                print(f"        - {loc}: {err.message}")
            n_fail += 1
            failures.append(item)
            continue
        schema_ok.append((meta_path, meta))
        id_paths.setdefault(meta["id"], []).append(item)

    known_ids = set(id_paths)
    duplicate_ids = {i: paths for i, paths in id_paths.items() if len(paths) > 1}

    # --- pass 2: structural rules + compile, on schema-valid items only.
    for meta_path, meta in schema_ok:
        item = rel(meta_path, root)

        # --- .tex sibling ---
        tex = tex_sibling(meta_path)
        if not tex.exists():
            print(f"FAIL  {item}: missing sibling .tex ({rel(tex, root)})")
            n_fail += 1
            failures.append(item)
            continue

        # --- project structural rules (standalone, requires, composed_of) ---
        problems = _structural_problems(meta, tex, known_ids)
        if meta["id"] in duplicate_ids:
            others = [p for p in duplicate_ids[meta["id"]] if p != item]
            problems.append(
                f"id '{meta['id']}' is not unique; also declared by: "
                + ", ".join(others)
            )
        if problems:
            print(f"FAIL  {item}: structural rules")
            for p in problems:
                print(f"        - {p}")
            n_fail += 1
            failures.append(item)
            continue

        # --- compile ---
        if not do_compile:
            print(f"PASS  {item} (compile disabled)")
            n_pass += 1
            continue
        if not have_latex:
            if args.strict:
                print(f"FAIL  {item}: latexmk not found (--strict)")
                n_fail += 1
                failures.append(item)
            else:
                print(f"SKIP  {item}: latexmk not found")
                n_skip += 1
            continue
        selfcheck_png = (
            (root / SELFCHECK_PNG_DIR / (item.replace("/", "_") + ".png"))
            if do_selfcheck
            else None
        )
        ok, log, selfcheck_problems = _compile_tex(tex, selfcheck_png)
        if not ok:
            print(f"FAIL  {item}: standalone compile failed")
            tail = "\n".join(log.strip().splitlines()[-15:])
            print("        --- latexmk output (tail) ---")
            for line in tail.splitlines():
                print(f"        {line}")
            n_fail += 1
            failures.append(item)
        elif selfcheck_problems:
            print(f"FAIL  {item}: D6 visual-self-check gate (mechanical) — {selfcheck_png and rel(selfcheck_png, root)}")
            for p in selfcheck_problems:
                print(f"        - {p}")
            print(
                "        NOTE: passing this mechanical check is NOT sufficient -- "
                "an agent must still read the PNG against the checklist "
                "(docs/VISUAL_SELFCHECK.md) before delivering."
            )
            n_fail += 1
            failures.append(item)
        else:
            print(f"PASS  {item}")
            n_pass += 1

    # --- vendored contract checksum (not a catalog item; runs once per invocation) ---
    contract_file = root / "contract" / "backend-contract-v1.2.0.md"
    if contract_file.exists():
        item = rel(contract_file, root)
        problem = _contract_checksum_problem(root)
        if problem:
            print(f"FAIL  {item}: {problem}")
            n_fail += 1
            failures.append(item)
        else:
            print(f"PASS  {item} (checksum OK)")
            n_pass += 1

    total = n_pass + n_fail + n_skip
    print(
        f"\n{total} item(s): {n_pass} passed, {n_fail} failed, {n_skip} skipped"
    )
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
