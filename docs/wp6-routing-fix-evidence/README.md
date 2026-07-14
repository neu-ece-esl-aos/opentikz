# WP-6 visual-verification evidence (cp-4895, responding to cp-4883's ruling)

Committed evidence for the D6 gate (`docs/VISUAL_SELFCHECK.md`), rendered at
400dpi and read/zoomed by hand — not certified from a thumbnail. See PR #6.

## Orthogonal-routing fix (contract §3a #5 typed-routing)

- `esl-architecture-block-full-400dpi.png` — full render, post-fix. The
  inter-tile bus (I/O <-> Tile 0 / Tile 1) is now a trunk-and-branch
  orthogonal route, replacing the pre-existing cp-4856-port diagonal.
- `esl-architecture-block-orthogonal-routing-zoom.png` — 2x crop of both
  bend points (I/O drop + the two tile-top stubs). Confirms right-angle
  bends only, no diagonal segment, no overlap with the tile boundary.
- `esl-mpsoc-memory-hierarchy-full-400dpi.png` — full render, post-fix. This
  template's first draft copied `esl-architecture-block`'s pre-fix diagonal
  pattern (3 tiles fanning diagonally into the shared mem-block); replaced
  with the same orthogonal trunk-and-branch, generalized to N tiles via
  `\foreach`.
- `esl-mpsoc-memory-hierarchy-orthogonal-rail-zoom.png` — 3x crop of the
  T1/T2 rail junction. Confirms the horizontal rail runs clear of both tile
  boundaries and their corner labels.

## esl-mpsoc-tile-array — re-verified, not re-fixed

cp-4883 flagged two defects in the WP-4 `\foreach` generator layer (tile
corner-label overlapping a contained PE node; intra-bus routed at 45°). Both
were checked firsthand at 400dpi/3x zoom in the copy this branch inherits
from `dev` (landed via WP-2's "cover WP-4 array templates" work, which
carried cp-4905's fix) and found **already fixed** — not re-fixed here, since
`origin/feat/foreach-array-generator` is expected to be rewritten again by
cp-4905 and this file isn't WP-6's to own.

- `esl-mpsoc-tile-array-label-headroom-zoom.png` — 3x crop of the T1.1
  corner label. Clear margin above the contained PE nodes, no overlap.
- `esl-mpsoc-tile-array-orthogonal-intrabus-zoom.png` — 3x crop of one
  tile's PE sub-grid. Intra-bus is a horizontal/vertical lattice only, no
  45° segment.

## New templates — full renders, D6-checklist-clean

- `esl-flow-pipeline-full-400dpi.png`
- `esl-sequence-timeline-full-400dpi.png`

Both read against their `intent.yaml` sidecar's `check_questions` (contract
§4 semantic gate, `docs/VISUAL_SELFCHECK.md` item 6) directly from these
renders; no collisions found against checklist items 1-5.
