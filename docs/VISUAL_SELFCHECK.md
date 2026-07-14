# Visual self-check gate (D6)

**This gate is mandatory and blocking.** A template or figure that compiles
cleanly is not done. Delivery (Mode A: handing a figure to a user; Mode B:
committing to this repo) requires:

```
compile  ->  render to PNG  ->  READ THE PNG  ->  check against the checklist below
                                                          |
                                                    all clear? -> deliver
                                                    a problem? -> fix, then re-run the gate
```

## Why this exists

figure is **legible**. Two motivating failures, both real, both in this
fork's own history:

- The PoC `esl-crossbar-kcl` template (ported into this fork with its defect
  intact, see `templates/esl-crossbar-kcl/`) passed `validate.py --strict` at
  every revision while it visually collided (see "Demonstrated catches"
  below, now fixed by WP-5/cp-4894) — a symbol overlap only the rendered
  image revealed.
- **WP-4's 32-tile MPSoC render (cp-4892, PR #2) was reviewed by three
  separate agent passes, and all three declared it clean** — while it had a
  tile corner-label drawn on top of its PE node and a diagonal intra-tile bus
  edge, both reproducing at every tile. The coordinator caught both, not by
  re-reading the same full-figure thumbnail a fourth time, but by **cropping
  a single tile and enlarging it to 900%**: at thumbnail scale (602×1038 px
  for 32 tiles) the defect is physically invisible; at 900% it is
  unmistakable. This is the harder lesson — **"render a PNG and have the
  agent look at it" is not sufficient by itself.** It failed in two distinct
  ways: a *resolution* failure (the defect was there but too small to see)
  and a *reclassification* failure (an agent that did notice an anomaly
  talked itself out of calling it a defect: "cosmetic", "by design",
  "acceptable at this density"). Both are closed below — forcing resolution
  (the zoomed-crop requirement) and removing discretion (the
  no-reclassification rule).

A verify loop that stops at "it compiles" is not sufficient (ADR-0004 §D2;
ADR-0005 §D6), and neither is one that stops at "an agent glanced at a
full-figure thumbnail."

## The checklist (read the PNG against every item)

1. **No overlapping/colliding labels.** Two text labels do not sit on top of
   each other.
2. **No symbol/node overlap.** Two drawn shapes/symbols (a node fill, a
   circuitikz device glyph, a domain-band) do not visually intersect unless
   the figure explicitly intends it (e.g. a deliberate `fit` background).
3. **Every node's label is inside its node.** Text does not spill past the
   shape that is supposed to contain it.
4. **Edges do not pass through unrelated nodes.** A wire/arrow's path does not
   cross through a node it isn't connecting to.
5. **Text is legible at the figure's intended print size.** Check at the
   actual target size (a single-column figure shrunk to ~8.4cm can turn
   readable-on-screen text into a gray smear) — see
   `skills/using-opentikz/SKILL.md` §4 "Adapt to a venue/column width" for how
   a figure gets resized; re-render and re-check at that final size.
6. **The render still answers its intent record's `check_questions`.**
   Contract §4 (`backend-contract-v1.2.0.md`): "3-5 questions answerable from
   the RENDER ALONE." This is the semantic half of the gate — it is not about
   whether elements collide, it is about whether the figure still says what
   it was supposed to say. If the figure carries an intent-record sidecar,
   answer every one of its `check_questions` by looking at the PNG only (no
   peeking at the `.tex` or the brief). If it does not yet carry one (true
   today for every template in this fork — the intent-record sidecar is
   WP-2's, not yet landed), state 3-5 check questions ad hoc from the
   template's `meta.json` `description` and `edit_contract.invariants`, then
   answer them from the render. Once WP-2 lands, consume its sidecar's
   `check_questions` directly instead.

Items 1-4 are the label/symbol-collision class D6 exists to close (grounded
directly in the cp-4856 crossbar failure). Item 5 is legibility. Item 6 is the
semantic gate the contract requires.

### No reclassification — read this before you check anything off

**A collision is a collision.** If a label's bounding box overlaps a node it
is not the content of, that IS checklist item 3, full stop. Permitted
verdicts for a genuine overlap are exactly two: "fix it" or "this is an
explicit, recorded, coordinator-approved exception" (a `selfcheck` opt-out in
the item's `meta.json`, see below — committed, reviewable, never a runtime
agent decision). The following are **not** permitted verdicts, because all
three were actually used, on this fork, to wave away a real defect:

- "cosmetic" / "a minor imperfection"
- "acceptable at this density/scale"
- "by design" (without an actual recorded design decision to point to)

If an overlap is genuinely intended (e.g. a `fit` background meant to sit
behind its own contents), that is a **containment** relationship, not a
collision, and the mechanical checks below already know the difference (see
`detect_node_node_collisions`'s `containment_ratio`). Anything short of full
containment is a collision. Do not grade your own homework.

### Force the resolution — a full-figure thumbnail is not evidence

A full-page render of a dense figure (many tiles, a large array) can hide a
defect that is obvious once you crop and zoom. **Whenever you inspect a
multi-element figure (an array, a grid, anything with more than a handful of
repeated components), commit a zoomed crop (≥400%) of at least one
representative unit as part of your evidence** — not only the full-figure
PNG. A full-page thumbnail is evidence the figure exists; it is **not**
evidence the figure is collision-free at the density it's drawn at. See
`docs/gate-demo/` for the pattern: every demonstrated catch below ships both
a full render and a zoomed crop.

```bash
# recipe used throughout docs/gate-demo/
convert <full.png> -crop <W>x<H>+<X>+<Y> +repage -resize 400% <zoom.png>
```

## What is mechanical vs. what needs your eyes — be honest about this split

**Mechanically checked** (`tools/validate.py`, via `tools/render_selfcheck.py`
— runs automatically whenever `validate.py` compiles a `.tex`):

**Enforced today: locally / in the authoring loop, not in CI.**
`.github/workflows/ci.yml` already invokes `python3 tools/validate.py
--strict` on every push/PR, so this gate is *wired* to run there with no
further edit needed — but **GitHub Actions is currently disabled at the repo
level on this fork** (0 workflows registered, 0 runs ever; enabling it is
repo-admin-only, escalated and tracked in `tools/ci/pending/README.md`) and
the agent credential separately lacks the `workflow` OAuth scope needed to
land the parked ci.yml shim commit there. **Until an operator enables
Actions, nothing in `.github/workflows/` executes, and no PR into this repo
gets a real GitHub CI check, green or otherwise** — do not read a merged PR
or an open one without a red X as evidence this gate ran. What actually
enforces it today is running `tools/validate.py --strict` or
`tools/ci/render-selfcheck-all.sh` yourself (or an agent doing so as part of
the authoring loop in §6 below) — the moment Actions is turned on, the exact
same commands start running automatically with **no rewrite**, because
they're already what `ci.yml` invokes.

- The `.tex` compiles and renders to PNG at all.
- **Overfull/underfull `\hbox`/`\vbox`** in the compile log — content that does
  not fit the box LaTeX gave it. A real signal, but partial: it only fires for
  LaTeX's own box model, not for TikZ nodes sized by `minimum width`/`height`
  (most of this library's collisions, including the crossbar one below, are
  TikZ shapes overlapping, which never produce an `Overfull` warning).
- **Cross-label text-bounding-box overlap**, via `pdftotext -bbox-layout` word
  rectangles (`tools/render_selfcheck.py::detect_text_overlaps`). This catches
  two independently-positioned **text** labels whose glyphs genuinely overlap
  (scored as a fraction of the smaller word's area, not an absolute size, so
  it isn't fooled by the inflated axis-aligned bounding box `pdftotext`
  reports for rotated text — see the function's docstring for the
  `examples/flash-attention` false-positive this was tuned against).
- **Node/node bounding-box collision** and **non-orthogonal node-to-node
  edges** (`detect_node_node_collisions`, `detect_diagonal_edges`), via a
  real geometry probe: a temporary, instrumented copy of the `.tex` (never
  the original) that hooks pgf's own path/node primitives (`\pgfpathmoveto`,
  `\pgfpathlineto`, `every node/.append style`) to `\typeout` exact
  coordinates during compilation. Every label in this library's convention is
  itself a `\node` (named or anonymous), so the node-collision check ALSO
  catches **a label overlapping a node it doesn't belong to** — the class of
  defect that motivated this addition (see "Demonstrated catches" below) —
  without needing `pdftotext` at all. Both checks are **scoped to
  ESL-contract-conforming templates** (`meta.json` `domain` includes
  `esl-architecture`) — see `_is_esl_family`'s docstring: an earlier, unscoped
  version of the orthogonality check flagged dozens of *intentional* diagonal
  connections in upstream content (neural-net's fully-connected layers, a GAN
  figure's convergent arrows), where a diagonal line is the correct visual,
  not a defect. A template may declare an explicit, reviewable opt-out via
  `"selfcheck": {"allow_diagonal_edges": true, "allow_diagonal_edges_reason":
  "..."}` in its `meta.json` for a genuinely intentional diagonal — a
  committed, diff-visible waiver, never a runtime agent decision.
  **A circuitikz bipole (`to[R]`, `to[I]`, ...) IS covered by this check the
  moment it carries a `name=<id>` key**: `name=` gives circuitikz's own
  bipole a real PGF node (plus `<id>start`/`<id>end`/`<id>label` anchors),
  which the `every node/.append style` hook above already fires for, exactly
  like any other named node — no separate code path, no new tooling (WP-11,
  cp-4925). For the `circuit-schematic` family this is not optional: every
  `to[...]` bipole is *required* to carry `name=<id>`
  (`settled-decisions/circuit-schematic.yaml`'s
  `circuitikz-bipole-node-identity`), enforced statically by
  `tools/adapter/checks.py::bipole_naming_problems` — a template with an
  unnamed bipole in this family fails `validate.py --strict` outright, before
  any render is even attempted. See "Demonstrated catches" below for the
  `esl-crossbar-kcl` case this was built to close.

**Mechanically checked but NOT what makes this gate trustworthy on its own:**
these checks are the "anything mechanically detectable" ADR-0005 §D6 asks CI
to catch. They are real, they run today via `tools/validate.py --strict` /
`tools/ci/render-selfcheck-all.sh`, and they are wired for CI to run the
moment Actions is enabled (see above — CI does not actually execute them
yet). They are also narrow — see the next section for exactly what they miss.

**Requires the agent (or a human) to look at the image — cannot be automated
with the toolchain available here:**

- **Symbol/graphic overlap involving a genuinely un-named element** (part of
  checklist item 2). This was previously documented here as a *permanent*
  toolchain limit — it is not, and stating it that way was itself the
  problem: it stopped two follow-on agents (WP-7, WP-8's successor) from even
  trying. **WP-11 (cp-4925) closed the concrete case**: a circuitikz bipole
  is a raw drawing path with no PGF node identity ONLY as long as it carries
  no `name=<id>` key; add one and it becomes a real, named node the existing
  `detect_node_node_collisions` probe already covers — no new tooling, and
  for the `circuit-schematic` family it is no longer a matter of remembering
  to add it: an unnamed `to[...]` bipole fails `validate.py --strict`
  outright (`tools/adapter/checks.py::bipole_naming_problems`). What
  genuinely remains un-automatable, stated honestly rather than declared
  unsolvable: (a) any bipole a template author still leaves unnamed in a
  family this rule does NOT cover (today: `flow` and `architecture` — a
  `circuit-schematic`-only rule, since only that family draws circuitikz
  bipoles at all), and (b) any other anonymous decorative path with no node
  identity of any kind (a `\draw` with no `\node`/bipole behind it at all —
  nothing to hook `every node/.append style` onto). Both are real, but both
  are now a matter of **whether a convention was actually applied**, not an
  unclosable toolchain gap — which is exactly why this is enforced
  (`checks.py`), not merely documented as a best practice.
- **Legibility at a specific print size** (item 5) — resolution/scale is a
  judgment call about a target venue, not a pass/fail geometry check.
- **The `check_questions` semantic gate** (item 6) — inherently requires
  reading the image and reasoning about what it communicates; no tool
  substitutes for this.

Do not treat a mechanically-clean `validate.py` run as "the figure is fine."
The tool's own output says so explicitly (see the `note:`/`PASS` messages) —
read the PNG anyway.

## Demonstrated catches

### `esl-crossbar-kcl` (fixed by WP-5/cp-4894; made mechanically catchable by WP-11/cp-4925) — symbol overlap that no longer needs an agent's eyes

Run originally against the ported `esl-crossbar-kcl` fixture
(`tools/render_selfcheck.py templates/esl-crossbar-kcl`): the mechanical
checks reported **no problems** — zero overfull boxes, zero text-bbox
overlaps, zero node-bbox collisions. `validate.py --strict` also passed. By
the "verify by compiling" standard alone, this template looked fine.

**It was not.** Reading the render (`docs/gate-demo/esl-crossbar-kcl-full.png`,
committed evidence of the *original defect* — this PNG predates the fix and is
kept as the motivating example; regenerate the *current, fixed* render
yourself with `python3 tools/render_selfcheck.py templates/esl-crossbar-kcl`)
showed the per-column KCL summation node (the orange "Σ" circle) visually
overlapping the circuitikz readout-device symbol drawn directly beneath it —
in **both** columns (zoomed crop, also the pre-fix state:
`docs/gate-demo/esl-crossbar-kcl-collision-zoom.png`):

- Column 1: the resistor `R_sense` zigzag's top lead ran up into the Σ
  node's circle.
- Column 2: the current-source `I_ref` circle overlapped the Σ node's circle
  outright — the two circles visually merged.

This was a **symbol/node overlap** (checklist item 2) where the "node" on one
side was a circuitikz bipole with no PGF node identity at all — invisible to
the node-collision check *at the time*, not because the check was
structurally incapable of it, but because the bipole carried no `name=`.
It was found the way this gate requires: compile, render, and *look* — the
mechanical checks available at the time did not catch it. Reported to
cp-4883 and to cp-4894 (WP-5, circuit template family). **Fixed by WP-5
(cp-4894):** the KCL-node-to-readout-device offset was `-1.15cm` (too short
for circuitikz's default bipole size); `-1.8cm` clears the collision for both
symbol types, verified by re-rendering.

**Closed mechanically by WP-11 (cp-4925):** `name=rsense` / `name=iref` were
added to the two bipoles (settled-decisions/circuit-schematic.yaml
`circuitikz-bipole-node-identity`, enforced by
`tools/adapter/checks.py::bipole_naming_problems`), giving both a real PGF
node the geometry probe already covers. Reintroducing the original defect in
a scratch copy (the `-1.8cm` clearance reverted back to the ported fixture's
`-1.15cm`, `name=` left intact) now fails mechanically, no render-reading
required:

```
$ python3 tools/render_selfcheck.py /tmp/wp11-defect/esl-crossbar-kcl
wrote /tmp/wp11-defect/esl-crossbar-kcl/template.selfcheck.png
MECHANICAL-ISSUE  /tmp/wp11-defect/esl-crossbar-kcl/template.tex: node 'kcl-1' and node 'rsense' bounding boxes overlap 44% of the smaller node's area -- a collision, not a containment relationship
$ echo $?
1
```

Zoomed crop of the reintroduced defect (the resistor's top lead running into
the Σ circle in column 1, the current-source circle merging into it in
column 2 — visually identical to the original pre-WP-5 defect):
`docs/wp11-name-convention-evidence/esl-crossbar-kcl-defect-reintroduced-zoom.png`.
The current, fixed `dev` template renders collision-free at the same zoom:
`docs/wp11-name-convention-evidence/esl-crossbar-kcl-readout-zoom.png`.

(Column 2's `iref`/`kcl-2` overlap comes in under this check's 40%
`min_ratio` threshold at this particular offset — the current-source glyph is
smaller than the resistor's — so this run reports one collision, not two;
column 1 alone is sufficient to demonstrate the check now fires where it
previously could not, and the real, un-reverted `dev` tree below still passes
88/88 with zero false positives.) Fixing this also required a real bug in
`_extract_node_bboxes_texframe`: `\pgfpointanchor`'s `south west`/`north
east` queries are answered in a node's own (possibly rotated) local frame,
and a circuitikz bipole drawn along a vertical wire returns those two corners
with the "north east" corner's y *below* the "south west" corner's — a
negative-area box that `detect_node_node_collisions`'s `area <= 0: continue`
guard silently discarded. The extraction step now normalizes every box to
true `(min-x, min-y, max-x, max-y)` before handing it to any consumer; see
that function's docstring for detail.

The scaled/broadened sibling template `templates/esl-crossbar-kcl-adc/` (three
readout device types — resistor, capacitor, current source — plus an ADC
stage and the domain-band/boundary convention) uses the same collision-free
clearance from the start and the same `name=` convention; its own render
evidence is
`docs/wp5-defect-fix-evidence/esl-crossbar-kcl-adc-full.png` and
`docs/wp5-defect-fix-evidence/esl-crossbar-kcl-adc-readout-band-zoom.png`
(600 DPI crop, ~6x a 96 DPI baseline reading size).

### `esl-mpsoc-memory-hierarchy` — label-over-node, caught mechanically (now fixed)

Coordinator review (cp-4883) surfaced a live regression in WP-4's
`\foreach`-generator output: a tile's corner label drawn on top of its own
contained PE node, in 3 of 3 tiles, invisible at thumbnail scale across three
separate agent visual-inspection passes. `detect_node_node_collisions` now
catches this class of defect **mechanically** — no agent judgment required.
Running it against the *sibling* template `esl-mpsoc-memory-hierarchy` (same
generator lineage, not previously known to have this defect) found a
**live, previously-undiscovered instance**: `python3 tools/validate.py
--strict` failed with `node 'pe-1-1' and node 'tikz@f@1' bounding boxes
overlap 49%...` for all 3 of its tiles. Reading the render
(`docs/gate-demo/esl-mpsoc-memory-hierarchy-full.png`, committed evidence of
the *original defect*; zoomed crop:
`docs/gate-demo/esl-mpsoc-memory-hierarchy-collision-zoom.png`) confirmed it:
"T1" was drawn directly on top of PE node "1". Reported to cp-4883 and to
WP-6 (cp-4895, which owns this template); **fixed by WP-6** in the same
follow-up that addressed the coordinator's PR #6 review (orthogonal bus +
label-clearance fixes) — `python3 tools/render_selfcheck.py
templates/esl-mpsoc-memory-hierarchy` is clean on the current `dev`, and the
committed evidence PNGs above are kept as the motivating pre-fix example.
(The overlapping node's name — `tikz@f@N` — is TikZ's own auto-generated
name for an anonymous node, not a bug in the check: this repo's corner
labels are placed without an explicit `(name)`, and TikZ still names and
tracks them internally.)

`templates/esl-mpsoc-tile-array` — the original WP-4 defect's actual
template, now fixed on `dev` — passes both checks cleanly, confirming no
false positive on the corrected geometry.

## Running it yourself

```bash
# One template, write the PNG next to the .tex as <name>.selfcheck.png:
python3 tools/render_selfcheck.py templates/<name>

# Every template/icon/example, mechanical-only, as part of the full validator:
python3 tools/validate.py --strict            # writes PNGs under _selfcheck-pngs/
python3 tools/validate.py --no-render-selfcheck  # skip the render+check step (fast metadata iteration)

# Every template, standalone (local or CI use), regardless of validate.py:
tools/ci/render-selfcheck-all.sh
```

None of these commands are a substitute for reading the PNG. They get you to
the point of having one to read.
