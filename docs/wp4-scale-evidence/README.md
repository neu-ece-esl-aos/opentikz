# WP-4 array-scale acceptance evidence (ADR-0005 D5, cp-4892)

These are the two at-scale renders required by cp-4892's termination criteria: a
multi-tile MPSoC (≥32 tiles) and a large crossbar (≥64×64), both compiled from
the `\foreach` generator templates in this PR, then rendered to PNG and visually
read (ADR-0005 D6) — not just compiled.

**Revision note (coordinator review, PR #2).** The first version of this
evidence claimed the 32-tile MPSoC render was collision-free; it was not — the
coordinator caught a tile corner-label drawn on top of its PE node, and a
diagonal intra-tile bus segment, both reproducing at every tile and at default
scale too, by cropping and enlarging a single tile from the PNG (not by
glancing at the full 32-tile thumbnail). Both are now fixed in
`templates/esl-mpsoc-tile-array/template.tex` (asymmetric fit-box margins that
reserve dedicated label headroom, plus an orthogonal row/column lattice for the
intra-tile bus instead of a boustrophedon chain — see that file and its
`edit_contract.invariants` for the detail) and this directory's PNGs/crop were
regenerated from the fixed template. `mpsoc-32tile-zoom.png` (a single cropped
and enlarged tile) is now committed alongside the full render specifically so
this class of defect is checkable without re-rendering.

Both `.tex.txt` files here are the exact template with only its top `\def`
parameter block edited (renamed `.txt` so `validate.py`/the catalog don't treat
them as library content — they are evidence artifacts, not shipped templates).
Diff either against its sibling `templates/*/template.tex` to see exactly which
parameters changed to reach scale; nothing below the parameter block was touched,
demonstrating requirement #2 (array size/spacing/labels are template parameters;
no consumer of the layer reasons in raw coordinates).

## `mpsoc-32tile.png` (full grid) + `mpsoc-32tile-zoom.png` (one cropped, enlarged tile) — from `templates/esl-mpsoc-tile-array/template.tex`

Parameters changed from the shipped default: `\ntilerows{8}`, `\ntilecols{4}`
(32 tiles), `\pelabelmode{none}` (was `index`). Everything else (PE sub-grid
2×2, spacing, mesh, the now-fixed `\tilegapy{1.3}` default) is the shipped
default.

**What the full-grid PNG shows:** an 8×4 grid of dashed tile-boundary boxes,
each containing its 2×2 PE sub-grid (containment primitive), joined by an
O(tiles) inter-tile mesh (each tile wires only to its right/below neighbor —
never a full mesh). Every tile boundary carries a legible `T<row>.<col>`
label, with a visible gap between each tile row and the next.

**What the zoomed single-tile crop shows (`mpsoc-32tile-zoom.png`, tile
`T3.1`, representative of all 32):** the `T3.1` label sits entirely inside the
dashed tile boundary's top margin, clear of the 2×2 PE grid below it — not
touching or overlapping any PE. The intra-tile bus is a clean orthogonal
lattice: a horizontal segment across the top PE pair, a horizontal segment
across the bottom PE pair, and two vertical segments connecting top to
bottom — no diagonal anywhere. This is the crop that caught (pre-fix) and now
confirms (post-fix) both defects the coordinator flagged; every other tile in
the full-grid PNG follows the same generated geometry.

**Legibility handling at this density:** PE nodes render as blank colored
squares (`\pelabelmode=none`) rather than printing each PE's numeric index —
128 PE labels at this pitch would start touching their neighbors' text. PE
identity is carried entirely by the node name (`pe-<r>-<c>-<k>`), which is
still 100% index-addressable; only the *printed* label is thinned. The tile
count is small enough (32) that every tile keeps its own text label with no
thinning needed there.

## `crossbar-64x64.png` — from `templates/esl-crossbar-array/template.tex`

Parameters changed from the shipped default: `\nrows{64}`, `\ncols{64}`,
`\rowgap{0.35}`, `\colgap{0.35}`, `\cellsize{0.25}` (tighter pitch so the sheet
stays a reasonable size), `\celllabelmode{none}` (was `full`),
`\edgelabelstride{8}` (was `1`).

**What the PNG shows:** a full 64×64 grid of crossbar cells, one row-rail per
row (voltage source through every cell in that row) and one column-rail per
column (top cell down through every cell to its KCL summation node) — 128
edges total, not the 8192 a point-to-point wiring would need. Zoomed crops
(top-left and bottom-right corners, checked during review, not committed here)
confirm every rail is a single clean line with no crossing clutter, and every
KCL Σ glyph is fully legible with no overlap between adjacent columns.

**Legibility handling at this density:** cell nodes render blank
(`\celllabelmode=none`) — 4096 `$G_{r,c}$` subscripts would be
illegible at any print size and would visually merge into solid text.
Row/column index labels are thinned to every 8th line via `\edgelabelstride=8`
(plus the array's first and last row/col, always labeled regardless of
stride) — `V1, V9, V17, ..., V57, V64` down the left edge and
`1, 9, 17, ..., 57, 64` along the bottom, giving orientation without printing
all 128 axis labels. Cell/row/col identity is carried entirely by the node
name (`cell-<r>-<c>`, `vin-<r>`, `kcl-<c>`), independent of what text is shown.
