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

`validate.py --strict` proves a `.tex` **compiles**. It does not prove the
figure is **legible**. The PoC `esl-crossbar-kcl` template (ported into this
fork with its defect intact, see `templates/esl-crossbar-kcl/`) is the
motivating case: it passed `validate.py --strict` at every revision while it
visually collided (see "Demonstrated catch" below, now fixed by WP-5/cp-4894)
— a defect only the rendered image revealed. A verify loop that stops at "it
compiles" is not sufficient (ADR-0004 §D2; ADR-0005 §D6).

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

**Mechanically checked but NOT what makes this gate trustworthy on its own:**
these checks are the "anything mechanically detectable" ADR-0005 §D6 asks CI
to catch. They are real, they run today via `tools/validate.py --strict` /
`tools/ci/render-selfcheck-all.sh`, and they are wired for CI to run the
moment Actions is enabled (see above — CI does not actually execute them
yet). They are also narrow — see the next section for exactly what they miss.

**Requires the agent (or a human) to look at the image — cannot be automated
with the toolchain available here:**

- **Symbol/graphic overlap involving a non-node element** (part of checklist
  item 2) — a circuitikz bipole (`to[R]`, `to[I]`, ...) is drawn as a raw
  path, not a named TikZ node, so it is invisible to the node-collision
  check. **This is not a hypothetical gap**: it is exactly why the
  `esl-crossbar-kcl` catch below (a KCL node overlapping a circuitikz device
  symbol) is reported as mechanically clean.
- **Legibility at a specific print size** (item 5) — resolution/scale is a
  judgment call about a target venue, not a pass/fail geometry check.
- **The `check_questions` semantic gate** (item 6) — inherently requires
  reading the image and reasoning about what it communicates; no tool
  substitutes for this.

Do not treat a mechanically-clean `validate.py` run as "the figure is fine."
The tool's own output says so explicitly (see the `note:`/`PASS` messages) —
read the PNG anyway.

## Demonstrated catches

### `esl-crossbar-kcl` (fixed by WP-5/cp-4894) — symbol overlap invisible to any mechanical check

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
side is a circuitikz bipole, not a TikZ node — a real, principled toolchain
limit (see above), not an unscoped gap that the node-collision check could
have caught. It was found exactly the way this gate requires: compile,
render, and *look* — the mechanical checks did not and structurally cannot
catch it. Reported to cp-4883 and to cp-4894 (WP-5, circuit template family).
**Fixed by WP-5 (cp-4894):** the KCL-node-to-readout-device offset was
`-1.15cm` (too short for circuitikz's default bipole size); `-1.8cm` clears
the collision for both symbol types, verified by re-rendering. The
scaled/broadened sibling template `templates/esl-crossbar-kcl-adc/` (three
readout device types — resistor, capacitor, current source — plus an ADC
stage and the domain-band/boundary convention) uses the same collision-free
clearance from the start; its own render evidence is
`docs/wp5-defect-fix-evidence/esl-crossbar-kcl-adc-full.png` and
`docs/wp5-defect-fix-evidence/esl-crossbar-kcl-adc-readout-band-zoom.png`
(600 DPI crop, ~6x a 96 DPI baseline reading size).

### `esl-mpsoc-memory-hierarchy` — label-over-node, caught mechanically

Coordinator review (cp-4883) surfaced a live regression in WP-4's
`\foreach`-generator output: a tile's corner label drawn on top of its own
contained PE node, in 3 of 3 tiles, invisible at thumbnail scale across three
separate agent visual-inspection passes. `detect_node_node_collisions` now
catches this class of defect **mechanically** — no agent judgment required.
Running it against the *sibling* template `esl-mpsoc-memory-hierarchy`
(same generator lineage, not previously known to have this defect) found a
**live, previously-undiscovered instance**: `python3 tools/validate.py
--strict` fails with `node 'pe-1-1' and node 'tikz@f@1' bounding boxes
overlap 49%...` for all 3 of its tiles. Reading the render
(`docs/gate-demo/esl-mpsoc-memory-hierarchy-full.png`, zoomed crop:
`docs/gate-demo/esl-mpsoc-memory-hierarchy-collision-zoom.png`) confirms it:
"T1" is drawn directly on top of PE node "1". Reported to cp-4883 and to
whichever WP owns this template — not fixed here, per this task's scope.
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
