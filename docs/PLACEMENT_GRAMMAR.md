# Placement-grammar validation (WP-7, ADR-0005 D3 §3b row)

Every family's `placement_grammar` (`tools/adapter/settled-decisions/<family>.yaml`)
states checkable relationship rules over the family's §1 named components —
never coordinates — each tagged with the §3a generic primitive(s) it
instantiates. `tools/adapter/placement_grammar.py` validates one template's
`.tex` + sidecar `intent.yaml` against its family's rules and reports, per
rule, one of four verdicts:

| Verdict | Meaning |
|---|---|
| `PASS` | Proven to hold, from the template's node graph or the generator's own coordinate arithmetic. No render needed. |
| `FAIL` | Proven to be violated — a real, blocking finding. |
| `NOT_APPLICABLE` | The template has no instance of the component/situation the rule concerns (e.g. no digital-domain component to split, no mem-block to place). Not evidence either way. |
| `NEEDS_RENDER` | Genuinely only checkable against a rendered image (glyph-level label clearance, "reads correctly"). Routed to WP-8's rendered-PNG self-check gate (`tools/render_selfcheck.py` / a manual PNG read) — this module never invents a static proxy for these. |

**Only `FAIL` blocks CI.** `tools/validate.py --strict` folds in
`placement_grammar_problems()` (via `tools/adapter/checks.py`), which returns
only `FAIL` verdicts as blocking problems. `NOT_APPLICABLE`/`NEEDS_RENDER` are
reporting-only — see `tools/adapter/cli.py grammar <template-dir>` for the
full per-rule breakdown for one template, or
`tools/ci/placement-grammar-report.sh` for every adapter-governed template.

## What is checked statically, and how

This is a **source-level static analyzer scoped to the coordinate idioms this
fork's ESL templates actually use** — not a general TikZ interpreter. Two
coordinate models coexist, independent of whether a template's `intent.yaml`
uses literal `nodes:` or a generator's `node_family:` (that split is about
node *naming*, not which TikZ placement idiom a template's `.tex` uses):

1. **Explicit `at (X,Y)` pgfmath arithmetic** (`esl-crossbar-kcl`,
   `esl-crossbar-array`). Orthogonality of a `\draw` edge is proven by
   comparing the two endpoints' X (or Y) expressions: fully bindable
   constants are evaluated numerically (`try_eval_numeric`); expressions that
   vary with a `\foreach` loop variable are compared by their **loop-variable
   dependency set** (`resolve_loopvar_deps`) — sound *only* within one edge
   statement, where both endpoints share the same active loop bindings.//
   A `\foreach`-generated array's edges sometimes reference a **different**
   concrete/parameter token than the generic declaration used in one index
   position (`cell-1-\c` fixed at the first row vs. the declared
   `cell-\r-\c`; `cell-\r-\ncols` fixed at the last column) —
   `collect_generated_patterns` / `resolve_generated_ref` substitute the
   differing token before comparing. **Soundness gate:** a pattern is only
   trusted if every loop variable its coordinate expression truly depends on
   is one of the node's own name-index tokens; the `pe-<row>-<col>-<k>`
   family fails this test (its real position depends on an *inner* sub-loop's
   `\pr`/`\pc`, not `\k`) and correctly falls back to `NEEDS_RENDER` rather
   than a guessed verdict — see the docstring on `collect_generated_patterns`
   for the concrete failure mode this closes.

2. **`positioning` + `calc` relative placement** (`esl-architecture-block`,
   `esl-mpsoc-tile-array`'s tile-level layout). `AxisTracker` assigns each
   named node/coordinate an opaque (x-class, y-class) pair in source order:
   a bare first node gets fresh classes; `right=/left= of REF` preserves
   REF's y-class; `above=/below= of REF` preserves REF's x-class; a
   `fit=(m1)(...)` box inherits its first member's classes; a calc midpoint
   `($(A)!t!(B)$)` inherits an axis only if `A` and `B` already share it,
   else gets a fresh class; a calc offset `($(A)+(dx,dy)$)` inherits an axis
   only if that axis's offset is literally zero. Two points are orthogonal
   iff they share an x-class or a y-class. This is exactly what proves the
   live `esl-architecture-block` finding below.

An idiom this module doesn't recognize (a third coordinate system, a
multi-segment `-|`/`|-` route, an anchor combination not modeled) makes that
specific comparison `NEEDS_RENDER`, never a fabricated `PASS`. Concretely:
`parse_edges` tags any `\draw` statement using an inline `-|`/`|-` coordinate
combinator (e.g. `esl-mpsoc-memory-hierarchy`'s orthogonal trunk-and-branch
router: `(tile-\t.north) -- (tile-\t.north |- rail)`) as `unresolved=True`
rather than silently dropping it from the edge count — every caller counts
these explicitly and reports `NEEDS_RENDER`, never treats their absence of
evidence as a passing verdict (an earlier version of this module silently
dropped such edges entirely, which could have under-evaluated a rule down to
a false `PASS`/`NOT_APPLICABLE` — caught and fixed against this exact
template before landing).

## `typed-routing` is checked via WP-8's compiled geometry probe, not re-derived

**cp-4883 ruling (after WP-8's `render_selfcheck.compile_geometry_probe` /
`detect_diagonal_edges` merged on `dev` @ `aea3a26`, PR #11): this module
consumes that compiled probe for every `typed-routing`-tagged rule instead of
proving orthogonality from static source analysis.** The compiled probe
instruments a copy of the `.tex`, compiles it for real, and hooks pgf's own
path/node primitives to log exact coordinates — so it sees the ACTUAL
rendered geometry regardless of source syntax, including constructs this
module's static parser cannot decompose (an inline `-|`/`|-`
coordinate-combinator route, e.g.). `_compiled_typed_routing_fails` calls it
once per template (memoized on `TemplateCtx`) and filters its findings to
node pairs relevant to the rule being checked (`_architecture_relevance` /
`_entity_node_pattern_relevance`); the static `AxisTracker`/`at(X,Y)` engine
above is now the **fallback only** for when the probe can't run (no
`tex_path`, or the instrumented compile fails), and stays the primary (only)
engine for rules NOT tagged `typed-routing` (e.g. circuit-schematic's
`rows-are-inputs`/`cols-are-weights`).

This closed a real gap: before this integration, `esl-mpsoc-tile-array`'s
`ports-on-boundaries`/`noc-spine-between-tiles`/`intra-bus-stays-in-tile` were
stuck at `NEEDS_RENDER` (the mesh routing's `-|`/`|-` combinators and its
`\ka`/`\kb` flat-index aliasing defeated the static engine, correctly per its
own soundness gate) — after wiring in the compiled probe, all three go to a
proven `PASS`. Same for `esl-architecture-block`'s `ports-on-boundaries`.

**Both of cp-4883's falsifiable proof obligations, demonstrated:**
1. **PASSes the current tree.** `python3 tools/validate.py --strict` is
   **88/88** (see below).
2. **FAILs a reintroduced diagonal.** A scratch copy of
   `esl-architecture-block` with the pre-fix `\draw[interbus] (tile1.north)
   -- (io);` / `(tile2.north) -- (io);` pattern restored (in place of the
   `trunk`-based orthogonal route currently on `dev`) produces:
   ```
   FAIL   ports-on-boundaries        non-orthogonal edge from 'tile1' to 'io'
                                      ((32.7pt,57.6pt) -> (131.1pt,85.5pt)) --
                                      15.8° from horizontal, contract §3a
                                      typed-routing requires orthogonal routing; ...
   FAIL   intra-bus-stays-in-tile    (same finding, shared relevance -- see below)
   FAIL   noc-spine-between-tiles    (same finding, shared relevance -- see below)
   ```
   Real angles (15.8°, 22.4°) from an actual compile, not an assumption.
   **Attribution note:** all three architecture typed-routing rules share
   ONE relevance test (`_architecture_relevance`: either endpoint resolves to
   a tile or tile-member) rather than being finely split per bus style —
   every drawn edge in these templates is one of these three kinds, so a
   real diagonal always surfaces under all three labels rather than risking
   under-attribution; this is documented over-attribution, never a hidden
   defect.

`FLOW_CHECKERS` now registers `edges-follow-data` (tagged `typed-routing`)
the same way, via `_entity_node_pattern_relevance` (a family-agnostic version
that matches any modeled entity's literal nodes/`node_family` pattern, since
flow has no tile-style containment hierarchy to key off). It only proves the
geometric half of the rule (no non-orthogonal segment) — it does NOT confirm
edge direction follows the data, or that crossings are minimized (both stay
`NEEDS_RENDER`).

## Live findings (as of this PR, evaluated against `dev` @ `aea3a26`)

This PR was rebased once, mid-flight, onto a `dev` that had moved substantially
(WP-5 circuit family, WP-6 architecture/flow family, and WP-8's rendered-PNG
gate all landed). That rebase — plus the compiled-probe integration above —
surfaced four real bugs in this checker itself, all found by validating
against real templates rather than assumed correct:

1. `pes-inside-tiles`/`hierarchy-is-organizer` wrongly required the
   architecture family's shared `mem-block` to be tile-contained, when
   `shared-memory-locus` places it outside every tile by design (found
   against `esl-mpsoc-memory-hierarchy`).
2. The array-generator branch of `tile-fit-declared-after-members` hardcoded
   `esl-mpsoc-tile-array`'s `\pr` loop-variable name instead of reading it
   from the member entity's own `node_family` indices, so it silently didn't
   generalize to `esl-mpsoc-memory-hierarchy`'s `\t`/`\k` naming.
3. `noc-spine-between-tiles`'s tile-scoping check treated *any* unresolvable
   endpoint (a bare routing `\coordinate`, or the shared `mem-block` itself)
   as a scoping violation, when an endpoint that isn't tile-scoped at all
   can't meaningfully be judged same-tile/cross-tile — fixed to report
   `NEEDS_RENDER` instead of a fabricated `FAIL`.
4. **`analog-digital-split` matched `"adc"` as a raw case-insensitive
   substring anywhere in the `.tex`**, which fired on an unrelated provenance
   comment (`esl-crossbar-kcl`'s header cites `adcbuffer.tex` and mentions
   the sibling `esl-crossbar-kcl-adc` template) and produced a **false**
   `FAIL` on a template that has no ADC/digital component at all (a purely
   analog sense-resistor/current-source readout) — every prior run of this
   checker reported this to cp-4883 as a "genuine grammar-vs-template
   disagreement needing a ruling." **It never was one; it was this
   checker's own false positive.** Fixed to require a REAL contract §1a
   `adc` component in the structured intent record, never a text-substring
   guess against prose/comments/citations. Corrected with cp-4883 directly
   rather than left standing.

**Current state: `python3 tools/validate.py --strict` is 88/88 — zero open
findings across all 8 ESL templates.** (Bug #1 in the diagonal-bus finding
this task's brief originally flagged for `esl-architecture-block` was ALSO
independently resolved, by WP-6's fix merging to `dev` mid-task — see the
compiled-probe section above for how it's now proven, not just absent.)

## Known gap: `flow` family has one registered checker, not a full set

`FLOW_CHECKERS` registers only `edges-follow-data` (via the compiled probe —
see above); `monotone-stage-direction`, `layer-assignment`,
`crossing-minimization`, `fork-join-alignment`, `params-off-axis`,
`timeline-pinned-axis`, and `lifelines-parallel` still report `NEEDS_RENDER`
for both `esl-flow-pipeline` and `esl-sequence-timeline` (WP-6's first flow
templates, landing after this module's checker set was originally designed
against circuit-schematic/architecture only). `params-off-axis` looks
tractable with the static engine (`param-out`'s `below=of stage-\nstages`
positioning idiom vs. the stage row's `at(\sx,0)` generated idiom) but needs
a cross-model "prove DIFFERENT" comparison this module doesn't have yet
(only "prove same" exists, for orthogonality); the Sugiyama-layering rules
(`layer-assignment`, `crossing-minimization`) are a genuinely different,
harder class of property than anything this module currently proves.
Flagged as follow-up rather than rushed under this task's time budget.

## The six §3a primitives, realized natively in TikZ (never a seventh)

Contract §3a names exactly six backend-agnostic placement primitives; this
backend realizes each with the TikZ idiom the contract's own realization
column already names — it never invents a primitive the core doesn't name
(confirmed: `grep -h "primitives:" tools/adapter/settled-decisions/*.yaml`
only ever emits these six ids, across every family record).

| Primitive | TikZ realization | Where (array-scale in bold) |
|---|---|---|
| `direction-axis` | `positioning` relative offsets / explicit row-major coordinates | crossbar row left→right (`esl-crossbar-kcl`); **`esl-crossbar-array`'s `\foreach \r`/`\foreach \c` row/col generator** |
| `containment` | `fit` + `backgrounds` (`on background layer`, declared after every fitted member — `tile-fit-declared-after-members`) | `esl-architecture-block`'s two `fit=(core)(acc)(cfg)` tile boxes; **`esl-mpsoc-tile-array`'s `fit=\tilefitlist` accumulated over the nested PE generator** |
| `alignment-symmetry` | `positioning`'s shared-anchor relations (`right=of`, `below=of`) / uniform `\foreach` pitch arithmetic | `tile2` aligned to `tile1` via `right=\tilesep of tile1`; **`esl-mpsoc-tile-array`'s `\tilepitchx`/`\tilepitchy` uniform grid** |
| `relative-placement` | `positioning` (`right=/left=/above=/below= of REF`) / `calc` (`($(A)!t!(B)$)`, `($(A)+(dx,dy)$)`) | `cfg1` = `right=10pt of core1`; `io` = `above=18pt of tilemid`; **crossbar-array's `cell-\r-\c` relative to its row/col rail** |
| `typed-routing` | dedicated orthogonal edge styles (`intrabus`/`interbus`, `awire`/`dwire`/`vwire`), validated orthogonal via WP-8's **compiled** geometry probe (`detect_diagonal_edges`), not static analysis | intra/inter-bus edges; **`esl-mpsoc-tile-array`'s O(tiles) inter-tile mesh, O(1)-per-row/col crossbar rails, and its `-\|`-combinator trunk-and-branch routing** |
| `pinned-axis` | a fixed anchor/rail coordinate independent of the figure's other content | KCL-node's readout device pinned via a fixed offset coordinate (`($(k1)+(0,-1.15)$)`); crossbar-array's row-0/col-0 origin |

## Adding a new checked rule

Register a `rule_id -> Callable[[TemplateCtx], RuleResult]` entry in
`ARCHITECTURE_CHECKERS` / `CIRCUIT_CHECKERS` (or a new family's dict in
`FAMILY_CHECKERS`). A rule with no registered checker defaults to
`NEEDS_RENDER` — this is deliberate: silence about a rule is never read as
"passing."
