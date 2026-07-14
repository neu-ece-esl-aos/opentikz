# WP-4 array-scale acceptance evidence (ADR-0005 D5, cp-4892)

These are the two at-scale renders required by cp-4892's termination criteria: a
multi-tile MPSoC (≥32 tiles) and a large crossbar (≥64×64), both compiled from
the `\foreach` generator templates in this PR, then rendered to PNG and visually
read (ADR-0005 D6) — not just compiled.

**Revision history (coordinator review, PR #2).** The first version of this
evidence claimed the 32-tile MPSoC render was collision-free; it was not — the
coordinator caught a tile corner-label drawn on top of its PE node, and a
diagonal intra-tile bus segment, both reproducing at every tile and at default
scale too, by cropping and enlarging a single tile from the PNG (not by
glancing at the full 32-tile thumbnail). Both are now fixed in
`templates/esl-mpsoc-tile-array/template.tex`:

1. An asymmetric fit-box margin (the "fit margins" helper `esl-architecture-block`
   already uses) reserves dedicated headroom above the contained PEs for the
   corner label, so it can never sit on a node. `\tilegapy`'s default is raised
   0.9→1.3cm so vertically adjacent tiles also clear each other's margins.
2. The intra-tile bus is now an orthogonal row/column lattice (horizontal edges
   within a PE row, vertical edges within a PE column) instead of a
   boustrophedon reading-order chain, whose row-wrap edge was diagonal —
   contract §3a primitive 5 (`typed-routing`) requires orthogonal routing.

The branch was also rebased onto `dev` after WP-3 (cp-4891) merged a
palette-drift gate into `validate.py`: templates may no longer reference a raw
stock-xcolor/dvipsnames color name directly in a style, only the ESL
domain-semantic `\colorlet` tokens (contract §2). Both templates here are
retrofitted onto those tokens (`core-accent`/`intra-bus`/`inter-bus` for the
MPSoC template; `inputdomain`/`weightdomain`/`analogdomain`/`digitaldomain` for
the crossbar template), following the exact pattern WP-3 used on
`esl-architecture-block`/`esl-crossbar-kcl`. This is a color-binding change
only — every node position, name, and wiring rule is unchanged, and both
renders below were reproduced after the retrofit to confirm.

A **zoomed, enlarged single-tile/corner crop is committed for both templates**
(`mpsoc-32tile-zoom.png`, `crossbar-64x64-zoom.png`) specifically because a
602×1038 (or similarly-scaled) thumbnail of a 32-tile or 64×64 grid cannot
show a label/node collision or a stray diagonal segment — that is how the
original defect got through. Read the zoomed crop, not just the full-grid
overview.

Both `.tex.txt` files here are the exact template with only its top `\def`
parameter block edited (renamed `.txt` so `validate.py`/the catalog don't treat
them as library content — they are evidence artifacts, not shipped templates).
Diff either against its sibling `templates/*/template.tex` to see exactly which
parameters changed to reach scale; nothing below the parameter block was
touched, demonstrating requirement #2 (array size/spacing/labels are template
parameters; no consumer of the layer reasons in raw coordinates).

## `mpsoc-32tile.png` (full grid) + `mpsoc-32tile-zoom.png` (one cropped, enlarged tile) — from `templates/esl-mpsoc-tile-array/template.tex`

Parameters changed from the shipped default: `\ntilerows{8}`, `\ntilecols{4}`
(32 tiles), `\pelabelmode{none}` (was `index`). Everything else (PE sub-grid
2×2, spacing, mesh, the `\tilegapy{1.3}` default) is the shipped default.

**What the full-grid PNG shows:** an 8×4 grid of dashed tile-boundary boxes,
each containing its 2×2 PE sub-grid (containment primitive), joined by an
O(tiles) inter-tile mesh (each tile wires only to its right/below neighbor —
never a full mesh). Every tile boundary carries a legible `T<row>.<col>`
label, with a visible gap between each tile row and the next.

**What the zoomed single-tile crop shows (`T3.1`, representative of all 32,
≥400% enlargement):** the `T3.1` label sits entirely inside the dashed tile
boundary's top margin, clear of the 2×2 PE grid below it — not touching or
overlapping any PE. The intra-tile bus is a clean orthogonal lattice: a
horizontal segment across the top PE pair, a horizontal segment across the
bottom PE pair, and two vertical segments connecting top to bottom — no
diagonal anywhere.

**Legibility handling at this density:** PE nodes render as blank colored
squares (`\pelabelmode=none`) rather than printing each PE's numeric index —
128 PE labels at this pitch would start touching their neighbors' text. PE
identity is carried entirely by the node name (`pe-<r>-<c>-<k>`), which is
still 100% index-addressable; only the *printed* label is thinned. The tile
count is small enough (32) that every tile keeps its own text label with no
thinning needed there.

## `crossbar-64x64.png` (full grid) + `crossbar-64x64-zoom.png` (top-left corner, enlarged) — from `templates/esl-crossbar-array/template.tex`

Parameters changed from the shipped default: `\nrows{64}`, `\ncols{64}`,
`\rowgap{0.35}`, `\colgap{0.35}`, `\cellsize{0.25}` (tighter pitch so the sheet
stays a reasonable size), `\celllabelmode{none}` (was `full`),
`\edgelabelstride{8}` (was `1`).

**What the full-grid PNG shows:** a full 64×64 grid of crossbar cells, one
row-rail per row (voltage source through every cell in that row) and one
column-rail per column (top cell down through every cell to its KCL
summation node) — 128 edges total, not the 8192 a point-to-point wiring would
need.

**What the zoomed corner crop shows (top-left, rows 1–16 / cols 1–~30,
enlarged):** every row rail is a single clean navy line, every column rail a
single clean orange line, with no crossing clutter; row labels are thinned to
every 8th line (`V1`, `V9`, ...) with no overlap between adjacent circles or
labels.

**Legibility handling at this density:** cell nodes render blank
(`\celllabelmode=none`) — 4096 `$G_{r,c}$` subscripts would be illegible at
any print size and would visually merge into solid text. Row/column index
labels are thinned to every 8th line via `\edgelabelstride=8` (plus the
array's first and last row/col, always labeled regardless of stride) —
`V1, V9, V17, ..., V57, V64` down the left edge and `1, 9, 17, ..., 57, 64`
along the bottom, giving orientation without printing all 128 axis labels.
Cell/row/col identity is carried entirely by the node name (`cell-<r>-<c>`,
`vin-<r>`, `kcl-<c>`), independent of what text is shown.
