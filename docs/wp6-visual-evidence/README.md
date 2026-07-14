# WP-6 visual self-check evidence (ADR-0005 D6, cp-4895)

Rendered PNGs + ≥400% zoomed crops for every template this PR adds or
modifies, per the coordinator's review of PR #6 ("commit a ≥400% zoomed crop
as evidence for each new template ... that is your job, not mine").

## Two real defects caught by zooming in, not by the full-frame render

The full-frame render of every template here looked clean at a glance. Zooming
into the actual junction/label areas at ≥400% (the same method WP-4's own
review round used — see `docs/wp4-scale-evidence/README.md`) surfaced two real
collisions that a quick look at the whole figure did not:

1. **`esl-architecture-block`'s first orthogonal-routing fix (BLOCKING 2)
   coincided the bus with the tile border.** Replacing the diagonal
   `tile.north -- io` edges with an orthogonal path used `(tile.north -| pt)`,
   which preserves `tile.north`'s own y-coordinate — i.e. the tile box's own
   border height — so the horizontal trunk ran directly on top of the tile's
   dashed boundary for its inner span (`esl-architecture-block-bus-junction-zoom.png`
   shows this class of defect on `esl-mpsoc-memory-hierarchy`'s equivalent bug,
   see below; the pre-fix version of this file is not committed, only the
   fixed one). Fixed by introducing an explicit `\trunk` coordinate with a
   real `+10pt` vertical offset above the tile tops, so the riser/trunk/stem
   segments have visible clearance from the tile border on every side.
2. **`esl-mpsoc-memory-hierarchy` shipped with the same class of bug twice**,
   inherited independently: (a) its own tile→mem bus trunk had the identical
   coincident-height defect as (1) above, same root cause, same fix (an
   explicit `\rail` coordinate offset); (b) its tile corner label (`T1`, `T2`,
   `T3`) had no headroom margin and was drawn directly on top of the first PE
   node in each tile — the exact defect class WP-4's own review round found
   and fixed in `esl-mpsoc-tile-array` (see `docs/wp4-scale-evidence/README.md`)
   via the `fit margins` helper, which this template had not yet adopted.
   Fixed by adding the same `fit margins` style (6pt sides, 16pt top) already
   used by `esl-architecture-block`/`esl-mpsoc-tile-array`.

Both fixes are visible in the `-zoom.png` crops below: real, visible white
space between the bus lines and the tile borders, and between the corner
labels and the PE nodes.

## Per-template evidence

### `esl-architecture-block-full.png` + `esl-architecture-block-bus-junction-zoom.png`

The fixed orthogonal inter-tile bus (BLOCKING 2): a vertical riser from each
tile top, a horizontal trunk connecting both risers ~10pt above the tile
tops, and one vertical stem into the shared `io` hub. The zoom crop shows the
trunk with clear vertical separation from Tile 0's dashed top border — no
overlap, unlike the pre-fix version.

### `esl-mpsoc-memory-hierarchy-full.png` + `esl-mpsoc-memory-hierarchy-tile-corner-zoom.png`

Same orthogonal trunk-and-branch pattern applied to a 3-tile row sharing one
`mem-block`. The zoom crop is the T1/T2 corner: both tile labels sit cleanly
inside their tile's headroom margin, and the bus riser is clearly separated
from the tile border above it.

### `esl-flow-pipeline-full.png` + `esl-flow-pipeline-group-box-zoom.png`

The zoom crop is the "fused" group-box caption over stages S2/S3: clear
vertical gap between the caption text and the dashed group-box border, and
between the border and the stage boxes it contains.

### `esl-sequence-timeline-full.png` + `esl-sequence-timeline-sync-marker-zoom.png`

The zoom crop is the t1/t2 region: the `req` life-message arrow sits clear of
both lifeline heads it connects, and the two sync-markers at `t2` land
exactly on their lifelines with no text/marker overlap. (The coordinator
independently rendered and read this template at 400% during PR review and
found it clean; this crop reproduces that check.)

## Validation

`python3 tools/validate.py --strict` (run after every fix in this evidence
set, most recently after the `node_family` intent-record update below):

```
82 item(s): 82 passed, 0 failed, 0 skipped
```

`python3 tools/adapter/cli.py check templates/<name>` passes with zero drift
for `esl-architecture-block`, `esl-mpsoc-memory-hierarchy`,
`esl-flow-pipeline`, and `esl-sequence-timeline`.

## `node_family` convention adopted

All three new templates' intent records originally expressed their
`\foreach`-generated components (`pe`, `tile`, `stage`, `lifeline`,
`sync-marker`) as a `nodes: ["stem-<i>"]` pattern-placeholder string. Once
rebased onto `dev` post-WP-2-merge, the "cp-4883 ruling" `node_family:
{stem, indices}` convention (already applied to `esl-mpsoc-tile-array` /
`esl-crossbar-array`, see their `intent.yaml`) was available and is the
correct, sanctioned way to express an indexed family — all three intent
records were updated to use it instead, and `edit_contract.node_naming` was
regenerated (`tools/adapter/cli.py derive --write`) to match.
