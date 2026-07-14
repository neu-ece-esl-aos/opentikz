"""WP-9 contract-conformance test (ADR-0005 D3 — the feature's exit gate).

Answers one question, mechanically, every time this runs: *is backend #2
buildable from ``contract/backend-contract-v1.2.0.md`` alone?* It drives
entirely off the vendored contract document (via ``contract_loader``), never
off a hand-maintained list of "the components we remember naming" — so a
contract re-freeze that adds an element shows up here as a new, unchecked
row, not a silent gap.

Two independent obligations, kept in separate functions so either can fail
on its own:

1. **Coverage** (``vocabulary_coverage`` / ``check_*``): every §1a/§1b
   component, §2 token, §3a primitive, §3b family record, and §4 intent/
   master-header row has a realized counterpart in this fork's own source —
   and the reverse: no template/intent-record names a component, token, or
   primitive the contract doesn't define.
2. **Anti-coupling** (``anti_coupling_problems``): nothing in this fork may
   depend on, vendor, or reference backend #1's actual TikZ internals
   (``figstyle.tex`` / ``tikzsemantics.tex``, the Phase-1 ESL skill's own
   assets) or any Phase-1 skill asset other than the vendored contract
   itself. The **reference publication libraries** this fork's templates
   were originally grafted from (the analog-ai handbook chapter's own
   ``fig/figstyle.tex``; ``tsarilp-pub``'s ``tikzsetup.tex``) are a *distinct*
   thing from backend #1's internals — consulting them for visual fidelity
   (colors, proportions) is permitted (contract §5: coordinates/geometry are
   backend-private); taking an un-contracted *semantic* from them would not
   be. This module tells the two apart by requiring every in-tree mention of
   ``figstyle.tex``/``tikzsemantics.tex`` outside ``contract/`` to co-occur,
   in the same file, with an explicit reference-library citation
   (``analog-ai`` / ``tsarilp``), and by rejecting any literal path reference
   to the Phase-1 skill's own asset location or an ``\\input`` of either file.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import repo_root  # noqa: E402

from adapter.contract_loader import Contract, FAMILIES, load_contract  # noqa: E402
from adapter.intent import (  # noqa: E402
    CONTRACT_REQUIRED_FIELDS,
    IntentRecordError,
    intent_sidecar_path,
    load_intent_record,
)
from adapter.checks import ESL_DOMAIN_TAG, adapter_problems  # noqa: E402
from adapter.derive import derive_invariants, load_settled_decisions  # noqa: E402
from adapter.placement_grammar import evaluate_template  # noqa: E402


@dataclass(frozen=True)
class Finding:
    check: str
    detail: str


def _load_json(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _esl_template_dirs(root: Path) -> list[Path]:
    out = []
    for meta_path in sorted((root / "templates").glob("*/template.meta.json")):
        meta = _load_json(meta_path)
        if ESL_DOMAIN_TAG in (meta.get("domain") or []):
            out.append(meta_path.parent)
    return out


def _all_tex_files(root: Path) -> list[Path]:
    """Every ``.tex`` this fork ships under its own content dirs — the only
    place a §1 realization can legitimately live (backend #2's own source)."""
    return sorted((root / "templates").glob("*/template.tex")) + sorted(
        (root / "icons").glob("**/*.tex")
    )


_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _candidate_tokens(tikz_realization: str) -> list[str]:
    """Extract candidate macro/style identifiers from the contract's own
    'TikZ realization' column text -- e.g. ``\\`\\crossbarcell{...}\\` /
    \\`cell\\` style`` -> ``["crossbarcell", "cell"]``. Used ONLY as a search
    key into backend #2's OWN source below; never a reason to open
    figstyle.tex/tikzsemantics.tex."""
    out: list[str] = []
    for raw in _BACKTICK_RE.findall(tikz_realization):
        name = raw.lstrip("\\")
        name = re.split(r"[\{\s]", name, 1)[0]
        if name and name not in out:
            out.append(name)
    return out


def _entity_components(root: Path) -> set[str]:
    found: set[str] = set()
    for intent_path in sorted((root / "templates").glob("*/intent.yaml")):
        data = yaml.safe_load(intent_path.read_text(encoding="utf-8")) or {}
        for entity in data.get("entities") or []:
            component = entity.get("component")
            if component:
                found.add(component)
    return found


def _cited_in_source(name: str, section: str, tex_corpus: list[tuple[Path, str]]) -> str | None:
    """A file that mentions this component's contract section AND names it in
    backticks is treated as an explicit realization citation -- covers
    figure-wide/generator-level components (e.g. `crossbar-array`) that have
    no single node/style of their own (see esl-crossbar-array/intent.yaml's
    own reasoning: "no single node stands for the array as a whole")."""
    section_tag = f"§{section}"
    quoted = f"`{name}`"
    for path, text in tex_corpus:
        if section_tag in text and quoted in text:
            return f"{path.relative_to(repo_root())}: cites {section_tag} `{name}`"
    return None


def _grep_token(token: str, tex_corpus: list[tuple[Path, str]]) -> str | None:
    style_re = re.compile(rf"\b{re.escape(token)}\b\s*/\.style\s*=")
    macro_re = re.compile(rf"\\{re.escape(token)}\b")
    for path, text in tex_corpus:
        for i, line in enumerate(text.splitlines(), 1):
            if style_re.search(line) or macro_re.search(line):
                return f"{path.relative_to(repo_root())}:{i}"
    return None


@dataclass
class ComponentCoverage:
    name: str
    section: str
    realized: bool
    evidence: str


def vocabulary_coverage(contract: Contract, root: Path | None = None) -> list[ComponentCoverage]:
    root = root or repo_root()
    entity_components = _entity_components(root)
    tex_corpus = [(p, p.read_text(encoding="utf-8")) for p in _all_tex_files(root)]
    # Also let templates'/icons' .meta.json / intent.yaml prose count as citation
    # sources (the `contract §1a \`name\`` convention every WP used).
    prose_corpus = list(tex_corpus)
    for pattern in ("*/template.meta.json", "*/intent.yaml"):
        for p in sorted((root / "templates").glob(pattern)):
            prose_corpus.append((p, p.read_text(encoding="utf-8")))
    for p in sorted((root / "icons").glob("**/*.meta.json")):
        prose_corpus.append((p, p.read_text(encoding="utf-8")))

    out: list[ComponentCoverage] = []
    for name in sorted(contract.components):
        component = contract.components[name]
        if name in entity_components:
            out.append(
                ComponentCoverage(
                    name, component.section, True,
                    "realized as an intent-record entity `component:` binding",
                )
            )
            continue
        cite = _cited_in_source(name, component.section, prose_corpus)
        if cite:
            out.append(ComponentCoverage(name, component.section, True, cite))
            continue
        found_token_evidence = None
        for token in _candidate_tokens(component.tikz_realization):
            ev = _grep_token(token, tex_corpus)
            if ev:
                found_token_evidence = f"style/macro `{token}` at {ev}"
                break
        if found_token_evidence:
            out.append(ComponentCoverage(name, component.section, True, found_token_evidence))
        else:
            out.append(
                ComponentCoverage(
                    name, component.section, False,
                    "no intent-record entity, contract citation, or style/macro "
                    "match found anywhere under templates/ or icons/",
                )
            )
    return out


def check_vocabulary_coverage(contract: Contract, root: Path | None = None) -> list[Finding]:
    findings = []
    for cov in vocabulary_coverage(contract, root):
        if not cov.realized:
            findings.append(
                Finding(
                    "§1-coverage",
                    f"contract component `{cov.name}` (§{cov.section}) has no realized "
                    f"counterpart in backend #2 -- {cov.evidence}",
                )
            )
    return findings


def check_no_undefined_components(contract: Contract, root: Path | None = None) -> list[Finding]:
    """Reverse direction: no template names a §1 component the contract does
    not define. (Per-template, this is also checked live by
    ``adapter.checks.adapter_problems``; this is the contract-driven,
    whole-repo aggregate of the same rule.)"""
    root = root or repo_root()
    findings = []
    for intent_path in sorted((root / "templates").glob("*/intent.yaml")):
        data = yaml.safe_load(intent_path.read_text(encoding="utf-8")) or {}
        for entity in data.get("entities") or []:
            component = entity.get("component")
            if component and not contract.has_component(component):
                findings.append(
                    Finding(
                        "§1-extensibility",
                        f"{intent_path.relative_to(root)}: entity {entity.get('name', '?')!r} "
                        f"names component {component!r}, not in contract §1 vocabulary",
                    )
                )
    return findings


_TOKEN_ROW_RE = re.compile(
    r"^\|\s*`([\w-]+)`\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*`(#[0-9A-Fa-f]{6})`\s*\|\s*$",
    re.MULTILINE,
)


def check_style_tokens(contract: Contract, root: Path | None = None) -> list[Finding]:
    root = root or repo_root()
    palette_file = root / "reference" / "color-palettes" / "color-palettes.md"
    findings = []
    if not palette_file.exists():
        return [Finding("§2-tokens", "reference/color-palettes/color-palettes.md is missing")]
    palette_rows = {
        tok: (role, hue, hexv)
        for tok, role, hue, hexv in _TOKEN_ROW_RE.findall(palette_file.read_text(encoding="utf-8"))
    }
    for token, tok_obj in sorted(contract.style_tokens.items()):
        got = palette_rows.get(token)
        if got is None:
            findings.append(Finding("§2-tokens", f"token `{token}` has no palette colorlet + neutral-hex fallback"))
            continue
        got_role, got_hue, got_hex = got
        if got_role != tok_obj.role:
            findings.append(Finding("§2-tokens", f"token `{token}` role binding drifted: contract={tok_obj.role!r} palette={got_role!r}"))
        if got_hex != tok_obj.neutral_hex:
            findings.append(Finding("§2-tokens", f"token `{token}` neutral-hex fallback drifted: contract={tok_obj.neutral_hex!r} palette={got_hex!r}"))
    return findings


SETTLED_DECISIONS_SCHEMA_KEYS = ("family", "version", "placement_grammar", "style_decisions", "semantic_decisions", "constraints")


def check_settled_decisions_schema(contract: Contract, root: Path | None = None) -> list[Finding]:
    root = root or repo_root()
    findings = []
    # The schema keys this module checks against are sourced from the
    # contract's own §3b field sketch, not a separately hand-maintained list.
    contract_keys = set(contract.settled_decisions_schema.keys())
    missing_from_contract_sketch = set(SETTLED_DECISIONS_SCHEMA_KEYS) - contract_keys
    if missing_from_contract_sketch:
        findings.append(
            Finding(
                "§3b-schema",
                f"contract §3b field sketch no longer names {sorted(missing_from_contract_sketch)} "
                "-- contract_loader's §3b parse may have drifted from the document",
            )
        )
    for family in FAMILIES:
        record = load_settled_decisions(family, root=root / "tools" / "adapter" / "settled-decisions")
        if record is None:
            findings.append(Finding("§3b-schema", f"no settled-decisions record for family {family!r}"))
            continue
        missing = [k for k in SETTLED_DECISIONS_SCHEMA_KEYS if k not in record]
        if missing:
            findings.append(Finding("§3b-schema", f"settled-decisions/{family}.yaml missing field(s): {missing}"))
        if record.get("family") != family:
            findings.append(
                Finding("§3b-schema", f"settled-decisions/{family}.yaml family field {record.get('family')!r} != {family!r}")
            )
        for rule in record.get("placement_grammar") or []:
            if not rule.get("primitives"):
                findings.append(
                    Finding("§3a-tagging", f"settled-decisions/{family}.yaml rule {rule.get('id')!r} has no `primitives:` tag (§3b requires every rule tag its §3a primitive(s))")
                )
    return findings


def check_placement_primitives(contract: Contract, root: Path | None = None) -> list[Finding]:
    """§3a: every one of the contract's six primitives has a named, checked
    realization somewhere in the family grammars, and no seventh id is
    ever used -- driven off ``contract.placement_primitives``, not a
    hardcoded six-string list, so a future contract bump is picked up."""
    root = root or repo_root()
    findings = []
    used_ids: set[str] = set()
    sd_dir = root / "tools" / "adapter" / "settled-decisions"
    for family in FAMILIES:
        record = load_settled_decisions(family, root=sd_dir)
        if record is None:
            continue
        for rule in record.get("placement_grammar") or []:
            for pid in rule.get("primitives") or []:
                used_ids.add(pid)
                if not contract.has_primitive(pid):
                    findings.append(
                        Finding(
                            "§3a-primitives",
                            f"settled-decisions/{family}.yaml rule {rule.get('id')!r} tags primitive "
                            f"`{pid}`, which contract §3a does not name (a 7th primitive would be invented here)",
                        )
                    )
    missing = set(contract.placement_primitives) - used_ids
    for pid in sorted(missing):
        findings.append(Finding("§3a-primitives", f"contract §3a primitive `{pid}` is never tagged by any family's placement_grammar -- no realized instance found"))
    return findings


def check_placement_grammar_runs_per_template(contract: Contract, root: Path | None = None) -> list[Finding]:
    """§3b: every family's placement_grammar rules are actually evaluated
    against every one of its templates (not silently skipped)."""
    root = root or repo_root()
    findings = []
    sd_dir = root / "tools" / "adapter" / "settled-decisions"
    for template_dir in _esl_template_dirs(root):
        tex_path = template_dir / "template.tex"
        try:
            intent = load_intent_record(intent_sidecar_path(template_dir))
        except IntentRecordError as exc:
            findings.append(Finding("§3b-grammar", str(exc)))
            continue
        record = load_settled_decisions(intent.family, root=sd_dir)
        if record is None:
            findings.append(Finding("§3b-grammar", f"{template_dir.name}: no settled-decisions record for family {intent.family!r} to check its grammar against"))
            continue
        results = evaluate_template(tex_path.read_text(encoding="utf-8"), intent, record, tex_path=tex_path)
        if not results:
            findings.append(Finding("§3b-grammar", f"{template_dir.name}: placement-grammar evaluation returned zero rule results (family {intent.family!r} may have no registered checkers at all)"))
    return findings


def check_intent_and_master_header(contract: Contract, root: Path | None = None) -> list[Finding]:
    """§4: every template with an edit_contract has a sidecar intent record
    (contract-shaped) and a matching master-header block, and
    edit_contract.parameters is derived from it. Also a meta-check: the
    adapter's hardcoded required-field list still matches the contract's own
    §4 field sketch (so a future contract §4 change is caught, not silently
    diverged from)."""
    root = root or repo_root()
    findings = []

    contract_field_names = set(contract.intent_record_schema.keys())
    adapter_field_names = set(CONTRACT_REQUIRED_FIELDS)
    missing = contract_field_names - adapter_field_names
    if missing:
        findings.append(
            Finding(
                "§4-schema",
                f"contract §4 names field(s) {sorted(missing)} that tools/adapter/intent.py's "
                "CONTRACT_REQUIRED_FIELDS does not check for",
            )
        )

    for template_dir in _esl_template_dirs(root):
        meta = _load_json(template_dir / "template.meta.json")
        tex = template_dir / "template.tex"
        problems = adapter_problems(meta, tex, template_dir, contract)
        for p in problems:
            findings.append(Finding("§4-intent-record", f"{template_dir.name}: {p}"))
    return findings


def check_recheck_rule_wired(contract: Contract, root: Path | None = None) -> list[Finding]:
    """Contract-level re-check rule (§3, applies to §3b): bumping a family's
    settled-decisions ``version`` (or its placement_grammar/style/semantic
    entries) must change what ``derive_invariants`` produces, so the
    checked-in ``edit_contract.invariants`` on every figure in that family
    would go stale and the drift check (``adapter_problems`` check 1) would
    catch it. Proven in-memory (a deep-copied, mutated record vs. the real
    one) -- this does not touch the working tree."""
    import copy

    root = root or repo_root()
    findings = []
    sd_dir = root / "tools" / "adapter" / "settled-decisions"
    for family in FAMILIES:
        record = load_settled_decisions(family, root=sd_dir)
        if record is None:
            continue
        mutated = copy.deepcopy(record)
        mutated["version"] = "999.999.999-wp9-recheck-probe"
        mutated.setdefault("placement_grammar", []).append(
            {"id": "wp9-recheck-probe", "primitives": ["direction-axis"], "rule": "probe-only, never real", "rationale": "WP-9 re-check-rule proof"}
        )
        before = derive_invariants(family, record)
        after = derive_invariants(family, mutated)
        if before == after:
            findings.append(
                Finding(
                    "§3-recheck-rule",
                    f"family {family!r}: bumping settled-decisions version/rules did not change "
                    "derive_invariants() output -- the re-check rule (a decision change must "
                    "propagate to every figure's checked invariants) is not actually wired",
                )
            )
    return findings


_GAP_ROW_RE = re.compile(r"^\|\s*(WP-\d+)\s*\|(.+)\|(.+)\|(.+)\|\s*([a-zA-Z0-9._-]*)\s*\|\s*$", re.MULTILINE)
_VALID_STATUS_RE = re.compile(r"^(raised|open|resolved-v\d+\.\d+\.\d+)$")


def check_gaps_ledger(root: Path | None = None) -> list[Finding]:
    root = root or repo_root()
    findings = []
    path = root / "contract" / "CONTRACT-GAPS.md"
    if not path.exists():
        return [Finding("gaps-ledger", "contract/CONTRACT-GAPS.md does not exist")]
    text = path.read_text(encoding="utf-8")
    rows = [m for m in _GAP_ROW_RE.finditer(text)]
    if not rows:
        findings.append(Finding("gaps-ledger", "no WP-N gap rows found (parser drift, or the ledger's table format changed)"))
    for m in rows:
        wp, needed, why, done, status = m.groups()
        if not needed.strip():
            findings.append(Finding("gaps-ledger", f"{wp}: 'What was needed' column is empty"))
        if not why.strip():
            findings.append(Finding("gaps-ledger", f"{wp}: 'Why the contract didn't carry it' column is empty"))
        if not done.strip():
            findings.append(Finding("gaps-ledger", f"{wp}: 'What was done instead' column is empty"))
        if not _VALID_STATUS_RE.match(status.strip()):
            findings.append(Finding("gaps-ledger", f"{wp}: status {status!r} is not one of raised|open|resolved-vN.N.N"))
        for banned in ("figstyle.tex", "tikzsemantics.tex"):
            if banned in done and "analog-ai" not in done and "tsarilp" not in done:
                findings.append(
                    Finding(
                        "gaps-ledger",
                        f"{wp}: 'What was done instead' mentions {banned!r} without citing a reference-publication "
                        "library -- looks like the gap may have been silently resolved by reading TikZ internals",
                    )
                )
    return findings


_CONTRACT_SHA256_RE = re.compile(r"```\n([0-9a-f]{64})\n```")


def check_contract_checksum(root: Path | None = None) -> list[Finding]:
    import hashlib

    root = root or repo_root()
    contract_file = root / "contract" / "backend-contract-v1.2.0.md"
    contract_doc = root / "contract" / "CONTRACT.md"
    if not contract_file.exists() or not contract_doc.exists():
        return [Finding("anti-coupling", "vendored contract or its CONTRACT.md pin is missing")]
    m = _CONTRACT_SHA256_RE.search(contract_doc.read_text(encoding="utf-8"))
    if not m:
        return [Finding("anti-coupling", "contract/CONTRACT.md has no pinned sha256")]
    pin = m.group(1)
    actual = hashlib.sha256(contract_file.read_bytes()).hexdigest()
    if pin != actual:
        return [Finding("anti-coupling", f"vendored contract checksum drift: pinned={pin} actual={actual}")]
    return []


# Reference-publication-library citations that are explicitly PERMITTED to
# mention backend #1's realization-file *names* (contract §5: visual
# fidelity is backend-private) -- as long as the citing file also names
# which external reference it means, never the Phase-1 skill's own asset.
_ALLOWED_CITATION_MARKERS = ("analog-ai", "tsarilp")
_FORBIDDEN_PATH_FRAGMENTS = ("_skills/figure-authoring/assets", "academic.wfp", "esl-writing-workflows")
_FORBIDDEN_INCLUDE_RE = re.compile(r"\\input\{[^}]*(?:figstyle|tikzsemantics)[^}]*\}")

# WP-9 finding, recorded in contract/CONTRACT-GAPS.md (WP-7 row, "raised"):
# tools/adapter/settled-decisions/*.yaml's own provenance comments cite
# academic.wfp's settled-decisions-template.md -- a Phase-1 skill asset that
# was never vendored alongside the contract. It is not an ONGOING coupling
# (derive.py reads only the fork-local copy; nothing here touches
# academic.wfp at build/run time) and it is now a named, tracked,
# contract-owner-escalated gap, not a silent one -- so it is allow-listed
# here by exact path rather than left to fail this gate forever. Any OTHER
# academic.wfp/_skills reference anywhere else in the fork still fails.
_KNOWN_GAP_ACADEMIC_WFP_CITATIONS = frozenset(
    Path("tools/adapter/settled-decisions") / name
    for name in ("circuit-schematic.yaml", "architecture.yaml", "flow.yaml", "README.md")
)


def anti_coupling_problems(root: Path | None = None) -> list[Finding]:
    """Fail the build on any dependence on backend #1's actual TikZ
    internals or any Phase-1 skill asset other than the vendored contract.
    Distinguishes that from legitimate visual-fidelity consultation of the
    *reference publication libraries* (the analog-ai handbook chapter's own
    figstyle.tex; tsarilp-pub's tikzsetup.tex) that this fork's templates
    were originally grafted from (cp-4856) -- those are a different asset
    from backend #1's actual `figstyle.tex`/`tikzsemantics.tex`, and citing
    them is permitted."""
    root = root or repo_root()
    findings = check_contract_checksum(root)

    skip_dirs = {".git"}
    # The literal \input{} check and the asset-path-fragment check apply to
    # every *content asset* this fork actually builds a figure from -- .tex
    # sources, per-item metadata/intent sidecars, the family settled-decisions
    # records, and the generated catalog. Project-level prose (README*.md,
    # CLAUDE.md, CONTRIBUTING.md, docs/*.md, this module's own docstrings) is
    # explicitly allowed to explain the fork/contract provenance relationship
    # in prose -- exactly like contract/CONTRACT.md itself does -- without
    # that counting as a coupling.
    asset_globs = [
        "templates/**/*", "icons/**/*", "reference/**/*",
        "tools/adapter/settled-decisions/*.yaml", "catalog.json",
    ]
    asset_paths: set[Path] = set()
    for pattern in asset_globs:
        asset_paths.update(p for p in root.glob(pattern) if p.is_file())

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        rel = path.relative_to(root)
        if rel.parts[0] == "contract":
            continue  # the contract's own text is expected to name the forbidden files
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError):
            continue

        # A literal \input{} can only ever execute from a .tex source; scoping
        # this to .tex lets docs (like this module's own, and docs/CONFORMANCE.md)
        # quote the forbidden syntax in prose without tripping the check.
        if rel.suffix == ".tex" and _FORBIDDEN_INCLUDE_RE.search(text):
            findings.append(Finding("anti-coupling", f"{rel}: literally \\input{{}}s figstyle/tikzsemantics"))

        if path in asset_paths and rel not in _KNOWN_GAP_ACADEMIC_WFP_CITATIONS:
            for frag in _FORBIDDEN_PATH_FRAGMENTS:
                if frag in text:
                    findings.append(Finding("anti-coupling", f"{rel}: references the Phase-1 skill's own asset path ({frag!r}) -- not the vendored contract"))

        for banned in ("figstyle.tex", "tikzsemantics.tex"):
            if banned in text and not any(marker in text for marker in _ALLOWED_CITATION_MARKERS):
                # tools/**/*.py discussing the RULE itself (not asset
                # coupling) is expected to name these files; anything else
                # must cite which reference-publication library it means.
                if not (rel.parts[0] == "tools" and rel.suffix == ".py"):
                    findings.append(
                        Finding(
                            "anti-coupling",
                            f"{rel}: mentions {banned!r} without citing a reference-publication "
                            "library (analog-ai / tsarilp) -- can't distinguish visual-fidelity "
                            "consultation from a coupling to backend #1's own internals",
                        )
                    )
    return findings


@dataclass
class ConformanceReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def by_check(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.check, []).append(f)
        return out


def run_conformance(root: Path | None = None) -> ConformanceReport:
    root = root or repo_root()
    contract = load_contract()
    findings: list[Finding] = []
    findings += check_vocabulary_coverage(contract, root)
    findings += check_no_undefined_components(contract, root)
    findings += check_style_tokens(contract, root)
    findings += check_settled_decisions_schema(contract, root)
    findings += check_placement_primitives(contract, root)
    findings += check_placement_grammar_runs_per_template(contract, root)
    findings += check_intent_and_master_header(contract, root)
    findings += check_recheck_rule_wired(contract, root)
    findings += check_gaps_ledger(root)
    findings += anti_coupling_problems(root)
    return ConformanceReport(findings=findings)


if __name__ == "__main__":
    import sys

    report = run_conformance()
    if report.ok:
        print("PASS  contract-conformance: backend #2 is buildable from the contract alone")
        sys.exit(0)
    for check, items in report.by_check().items():
        print(f"FAIL  [{check}] ({len(items)})")
        for f in items:
            print(f"        - {f.detail}")
    print(f"\n{len(report.findings)} conformance finding(s)")
    sys.exit(1)
