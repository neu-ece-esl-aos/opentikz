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

## Live findings (as of this PR, evaluated against `dev` @ `aea3a26`)

This PR was rebased once, mid-flight, onto a `dev` that had moved substantially
(WP-5 circuit family, WP-6 architecture/flow family, and WP-8's rendered-PNG
gate all landed). That rebase is what surfaced everything below — both the
findings and three real bugs in this checker itself, caught by validating
against templates that didn't exist when this module was first written:

- The diagonal `esl-architecture-block` inter-bus defect this task's brief
  flagged is **now fixed on `dev`** (WP-6's `railmid`-based orthogonal
  trunk-and-branch route merged) — `ports-on-boundaries` /
  `noc-spine-between-tiles` both went from `FAIL` to `PASS` across the rebase,
  live confirmation the checker tracks real repo state rather than a fixed
  snapshot.
- Three checker bugs, found and fixed against `esl-mpsoc-memory-hierarchy`
  (a template that landed after this module's first pass): (1)
  `pes-inside-tiles`/`hierarchy-is-organizer` wrongly required the family's
  own shared `mem-block` to be tile-contained, when `shared-memory-locus`
  places it outside every tile by design; (2) the array-generator branch of
  `tile-fit-declared-after-members` hardcoded `esl-mpsoc-tile-array`'s `\pr`
  loop-variable name instead of reading it from the member entity's own
  `node_family` indices, so it silently didn't generalize to this template's
  `\t`/`\k` naming; (3) `noc-spine-between-tiles`'s tile-scoping check treated
  *any* unresolvable endpoint (a bare routing `\coordinate` like `rail`, or
  the shared `mem-block` itself) as a scoping violation, when an endpoint
  that isn't tile-scoped at all can't meaningfully be judged same-tile/
  cross-tile — fixed to report it as `NEEDS_RENDER` evidence instead of a
  fabricated `FAIL`.

```
$ python3 tools/adapter/cli.py grammar templates/esl-crossbar-kcl
...
FAIL   analog-digital-split   template's thesis/entities reference an analog/digital split
                              but draws no \domainband/\domainboundary -- ... (WP-5 scope,
                              reported to cp-4883)
```
`esl-crossbar-kcl`'s thesis is explicitly about the analog accumulation vs.
the digital readout, but the template draws no `\domainband`/`\domainboundary`
(WP-5's `esl-crossbar-kcl-adc` adds the domain-band to a *separate*, richer
template — not to this simple 2×2 fixture). Whether this simple fixture is
exempt from the family's `analog-digital-split` rule, or should also carry a
domain-band, is a genuine grammar-vs-template disagreement — reported to
cp-4883 rather than silently resolved either way. This is the **only**
finding left across all 8 ESL templates as of this PR.

## Known gap: no `flow`-family checkers registered yet

`FAMILY_CHECKERS["flow"]` is empty — WP-6's `esl-flow-pipeline` and
`esl-sequence-timeline` are the first flow-family templates to exist in this
fork, landing after this module's checker set was designed against the
circuit-schematic/architecture families only. Every flow `placement_grammar`
rule therefore reports `NEEDS_RENDER` (`no static checker implemented`) for
both templates — honest (no false `PASS`), but the least amount of automated
coverage in this PR. `params-off-axis` and `monotone-stage-direction` look
tractable with this module's existing coordinate models (`param-out`'s
`below=of stage-\nstages` positioning idiom vs. the stage row's `at(\sx,0)`
generated idiom, respectively) but need a cross-model "prove different" (not
just "prove same") comparison this module doesn't have yet — flagged as
follow-up rather than rushed.

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
| `typed-routing` | dedicated orthogonal edge styles (`intrabus`/`interbus`, `awire`/`dwire`/`vwire`), validated orthogonal by this module | intra/inter-bus edges; **`esl-mpsoc-tile-array`'s O(tiles) inter-tile mesh, O(1)-per-row/col crossbar rails** |
| `pinned-axis` | a fixed anchor/rail coordinate independent of the figure's other content | KCL-node's readout device pinned via a fixed offset coordinate (`($(k1)+(0,-1.15)$)`); crossbar-array's row-0/col-0 origin |

## Adding a new checked rule

Register a `rule_id -> Callable[[TemplateCtx], RuleResult]` entry in
`ARCHITECTURE_CHECKERS` / `CIRCUIT_CHECKERS` (or a new family's dict in
`FAMILY_CHECKERS`). A rule with no registered checker defaults to
`NEEDS_RENDER` — this is deliberate: silence about a rule is never read as
"passing."
