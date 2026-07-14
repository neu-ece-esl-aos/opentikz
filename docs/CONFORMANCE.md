# Contract-conformance test (WP-9, ADR-0005 D3 — the feature's exit gate)

**Question this answers, mechanically, every run:** is backend #2 buildable
from `contract/backend-contract-v1.2.0.md` **alone** — never from reading
backend #1's TikZ internals (`figstyle.tex` / `tikzsemantics.tex`) or any
other un-vendored Phase-1 skill asset?

```
python3 tools/adapter/conformance.py       # or: tools/adapter/cli.py conformance
bash tools/ci/conformance-report.sh        # same check, CI-log framing
```

Folded into `tools/validate.py --strict` as the `contract-conformance (WP-9)`
item (no `.github/workflows/` edit — same convention as every earlier WP's
gate). A finding in **any** of the categories below fails that item.

## What it checks, and how — driven off the contract document itself

`tools/adapter/conformance.py` never hand-maintains "the list of components
we remember naming." Every check below reads `contract/backend-contract-v1.2.0.md`
through `tools/adapter/contract_loader.py` (the same parser WP-2 built) and
walks whatever that parse returns — so a future contract re-freeze that adds
an element shows up here as a new, unchecked row on the next run, not a
silently-missed one.

| Contract element | Check | Function |
|---|---|---|
| §1a/§1b vocabulary | every component has a realized counterpart in this fork's own `templates/`/`icons/`; the reverse — no intent record names a component the contract doesn't define | `check_vocabulary_coverage` / `check_no_undefined_components` |
| §2 style tokens | every token exists in the palette doc with its role + neutral-hex binding intact | `check_style_tokens` |
| §3b settled-decisions schema | a `family`/`version`/`placement_grammar`/`style_decisions`/`semantic_decisions`/`constraints` record exists per family, matching the contract's own §3b field sketch | `check_settled_decisions_schema` |
| §3b placement grammar | every family's `placement_grammar` rules are actually evaluated against every one of its templates (not silently skipped) | `check_placement_grammar_runs_per_template` |
| §3 re-check rule | bumping a family's settled-decisions content actually changes what gets baked into every template's `edit_contract.invariants` (proven in-memory, no working-tree mutation) | `check_recheck_rule_wired` |
| §3a 6-primitive core | every primitive is tagged by some family's grammar (realized); no rule ever tags a 7th, undefined primitive | `check_placement_primitives` |
| §4 intent record | every template has a sidecar `intent.yaml` + matching master-header block, and `edit_contract.parameters` is derived from it; the adapter's required-field list still matches the contract's own §4 field sketch | `check_intent_and_master_header` |
| Gaps ledger | every `CONTRACT-GAPS.md` row has all columns filled and a valid status; no "what was done instead" cell reads like a silent TikZ-internals resolution | `check_gaps_ledger` |
| Anti-coupling | vendored-contract checksum intact; no `\input{figstyle}`/`\input{tikzsemantics}`; no reference to the Phase-1 skill's own asset path outside an explicitly cited, gap-tracked exception; any in-tree mention of `figstyle.tex`/`tikzsemantics.tex` outside `contract/`/`tools/**/*.py` must cite a reference-publication library (`analog-ai`/`tsarilp`), never bare | `anti_coupling_problems` |

**Every check above was proven non-vacuous by tampering** (a real, temporary
edit to a real file — the same standard every earlier WP's gate was held to
— confirmed FAIL, then reverted; `git status` clean afterward). See the
WP-9 PR description for the tamper log.

## §1 vocabulary coverage — full table (30/30 realized)

| § | Component | Evidence |
|---|---|---|
| 1b | `acc-core` | intent-record entity |
| 1a | `adc` | intent-record entity |
| 1a | `analog-wire` | `awire` style, `esl-crossbar-array/template.tex` |
| 1b | `cpu-core` | intent-record entity |
| 1a | `crossbar-array` | explicit `§1a \`crossbar-array\`` citation (whole-figure realization — no single node stands for the array, see `esl-crossbar-array/intent.yaml`'s own reasoning) |
| 1a | `crossbar-cell` | intent-record entity |
| 1a | `current-label` | `currentlbl` style, `esl-crossbar-kcl/template.tex` |
| 1a | `digital-label` | `digitallbl` style (same contract row as `current-label`; parser attributes one shared realization string to all four split names — verified present by direct grep, not just the tool's own evidence line) |
| 1a | `digital-wire` | `dwire` style, `esl-crossbar-kcl/template.tex` |
| 1a | `domain-band` | intent-record entity |
| 1a | `domain-boundary` | intent-record entity |
| 1b | `flow-edge` | `flowedge` style, `esl-flow-pipeline/template.tex` |
| 1b | `group-box` | intent-record entity |
| 1b | `inter-bus` | `interbus` style, `esl-architecture-block/template.tex` |
| 1b | `intra-bus` | `intrabus` style, `esl-architecture-block/template.tex` |
| 1a | `kcl-node` | intent-record entity |
| 1b | `life-message` | `lifemsg` style, `esl-sequence-timeline/template.tex` |
| 1b | `lifeline` | intent-record entity |
| 1b | `mem-block` | intent-record entity |
| 1b | `param-node` | intent-record entity |
| 1b | `pe` | intent-record entity |
| 1b | `proc-stage` | intent-record entity |
| 1a | `sidenote` | `sidenote` style (verified present directly; same shared-realization-string note as `digital-label`) |
| 1b | `sync-marker` | intent-record entity |
| 1b | `task-node` | intent-record entity |
| 1b | `tile` | intent-record entity |
| 1b | `time-axis` | intent-record entity |
| 1a | `v-source` | intent-record entity |
| 1a | `voltage-label` | `voltagelbl` style (same shared-realization-string note) |
| 1a | `voltage-wire` | `vwire` style, `esl-crossbar-array/template.tex` |

**Known imprecision, not a gap:** the contract's own §1a table gives one row
"`current-label` / `voltage-label` / `digital-label` / `sidenote`" with one
shared "TikZ realization" cell (`currentlbl`/`voltagelbl`/`digitallbl`/
`sidenote` styles) covering all four names — `contract_loader.py` (WP-2)
attributes the *whole* cell to each split name, so `conformance.py`'s
evidence line for three of the four shows `currentlbl` rather than its own
specific style. All four styles are independently confirmed present (`grep
-n "sidenote/\.style\|currentlbl/\.style\|voltagelbl/\.style\|digitallbl/\.style"`
across the circuit templates) — this is a cosmetic evidence-reporting
artifact of the shared-cell parse, not a missing realization.

## Anti-coupling: the two kinds of "figstyle.tex" in this project

The obligation is specific: don't read backend #1's actual TikZ internals
(`figstyle.tex`/`tikzsemantics.tex`, the Phase-1 ESL skill's own realization
assets, vendored nowhere in this fork — confirmed by
`find . -iname figstyle.tex -o -iname tikzsemantics.tex` returning nothing
under this repo). A *different* thing entirely — the **analog-ai handbook
chapter's own** `fig/figstyle.tex` and `tsarilp-pub`'s `tikzsetup.tex` — are
the **reference publication libraries** this fork's ESL templates were
originally grafted from (cp-4856, Phase 2a, before this contract existed).
Backend #1's own `figstyle.tex` says as much in its own header: it was
"DISTILLED FROM ... the analog-ai EmbML chapter figure family" — i.e. backend
#1 and this fork's templates share a common external ancestor; neither reads
the other's actual file. Consulting the reference libraries for **visual
fidelity** (colors, proportions) is explicitly contract-permitted (§5:
coordinates/geometry are backend-private); every style/macro *name* this
fork uses (`kclnode`, `awire`, `intrabus`, ...) is independently traceable to
the contract's own §1a/§1b "TikZ realization" column text, not to reading
either `figstyle.tex`. `anti_coupling_problems()` enforces the distinction
mechanically: any in-tree mention of the two forbidden filenames outside
`contract/` (the vendored text itself, expected to name them) or `tools/**/*.py`
(code discussing the rule) must co-occur with an `analog-ai`/`tsarilp`
citation, or the build fails.

## The one gap this test found: WP-7's settled-decisions content

`tools/adapter/settled-decisions/{circuit-schematic,architecture,flow}.yaml`'s
own provenance comments admit reading `academic.wfp`'s
`settled-decisions-template.md` directly (a Phase-1 skill asset that was
**never vendored** into `contract/`, unlike `backend-contract-v1.2.0.md`) and
transcribing its worked-example content — verbatim for `flow` (~95% textual
match by `difflib.SequenceMatcher`), substantially for the other two
(folded in with the pre-existing cp-4856-fixture invariants). This is **not**
a coupling to backend #1's TikZ macros (neither `figstyle.tex` nor
`tikzsemantics.tex` was read) and there is no *ongoing*/runtime dependency
(`load_settled_decisions()` reads only this fork's own committed YAML) — but
it IS a one-time authoring-time dependency on an un-vendored Phase-1 skill
asset, which the D3 obligation as given to this task names explicitly
("any Phase-1 skill asset other than the vendored contract itself"). It was
never recorded in `contract/CONTRACT-GAPS.md` until this WP. Recorded now as
the WP-7 row; `anti_coupling_problems()` allow-lists this exact, named,
now-tracked citation (`tools/adapter/settled-decisions/*.yaml` +
`README.md` mentioning `academic.wfp`) rather than either silently passing
it forever or perpetually failing a known, contract-owner-escalated issue —
the same treatment G1/G2 already established for the §1-vocabulary gaps.
**Resolution is the contract owner's call** (extend WP-1's vendoring scope to
include `settled-decisions-template.md`/`intent-record-template.md`
checksum-pinned alongside the contract, or fold the worked examples directly
into the contract text) — not something this feature may do unilaterally.

## Verdict: **conformant-with-5-gaps**

Every contract element (§1a/§1b vocabulary, §2 tokens, §3a primitives, §3b
schema + placement grammar + re-check rule, §4 intent/master-header) has a
realized, checked counterpart in this fork. No template names a component,
token, or primitive the contract doesn't define. No build step in this fork
couples to backend #1's actual TikZ internals. Five gaps are open, all
**raised** to the contract owner via `contract/CONTRACT-GAPS.md` (routed to
cp-4883 for change-control escalation), none resolved by silently reading
TikZ:

1. **G1** (WP-2) — no §1b bus-hub/junction component name.
2. **G2** (WP-2) — no §1a raw EE device-primitive component name (resistor/current-source).
3. (WP-5) — the same device-primitive gap, op-amp instance (active/multi-terminal device class).
4. (WP-5) — the same device-primitive gap, capacitor instance.
5. **(WP-9, new)** — WP-7's settled-decisions worked-example content was sourced from an un-vendored Phase-1 skill asset (`settled-decisions-template.md`), not from the vendored contract alone.
