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

**Mechanically checked but NOT what makes this gate trustworthy on its own:**
these two checks are the "anything mechanically detectable" ADR-0005 §D6 asks
CI to catch. They are real, they run today via `tools/validate.py --strict`
/ `tools/ci/render-selfcheck-all.sh`, and they are wired for CI to run the
moment Actions is enabled (see above — CI does not actually execute them
yet). They are also narrow — see the next section for exactly what they miss.

**Requires the agent (or a human) to look at the image — cannot be automated
with the toolchain available here:**

- **Symbol/node/graphic overlap** (checklist items 2-4) — the mechanical text
  checker only sees `pdftotext`'s word boxes; it is blind to TikZ shape fills,
  circuitikz device glyphs, wires, and backgrounds entirely. **This is not a
  hypothetical gap**: it is exactly why the demonstrated catch below is a
  *symbol* collision that the mechanical checker reports as clean.
- **Label containment** (item 3) in the general case — a text bounding box
  sitting fully inside its node's bounding box is geometrically checkable in
  principle, but nothing in this toolchain currently extracts a TikZ node's
  own bounding box (as opposed to a word's) to compare against; not
  implemented.
- **Legibility at a specific print size** (item 5) — resolution/scale is a
  judgment call about a target venue, not a pass/fail geometry check.
- **The `check_questions` semantic gate** (item 6) — inherently requires
  reading the image and reasoning about what it communicates; no tool
  substitutes for this.

Do not treat a mechanically-clean `validate.py` run as "the figure is fine."
The tool's own output says so explicitly (see the `note:`/`PASS` messages) —
read the PNG anyway.

## Demonstrated catch: `esl-crossbar-kcl` (fixed by WP-5/cp-4894)

Run originally against the ported `esl-crossbar-kcl` fixture
(`tools/render_selfcheck.py templates/esl-crossbar-kcl`): the mechanical
checks reported **no problems** — zero overfull boxes, zero text-bbox
overlaps. `validate.py --strict` also passed. By the "verify by compiling"
standard alone, this template looked fine.

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

This was a **symbol/node overlap** (checklist item 2), the same class of
"compiles cleanly, visually broken" defect the cp-4856 PoC's original
colliding-label incident demonstrated. It was found exactly the way this gate
requires: compile, render, and *look* — the mechanical checks did not and
structurally cannot catch it (see above). **Fixed by WP-5 (cp-4894):** the
KCL-node-to-readout-device offset was `-1.15cm` (too short for circuitikz's
default bipole size); `-1.8cm` clears the collision for both symbol types,
verified by re-rendering. The scaled/broadened sibling template
`templates/esl-crossbar-kcl-adc/` (three readout device types — resistor,
capacitor, current source — plus an ADC stage and the domain-band/boundary
convention) uses the same collision-free clearance from the start; its own
render evidence is `docs/wp5-defect-fix-evidence/esl-crossbar-kcl-adc-full.png`
and `docs/wp5-defect-fix-evidence/esl-crossbar-kcl-adc-readout-band-zoom.png`
(600 DPI crop, ~6x a 96 DPI baseline reading size).

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
