# WP-5 visual-verification evidence (cp-4894, responding to cp-4883's ruling)

Committed evidence for the D6 gate (`docs/VISUAL_SELFCHECK.md`), rendered at
high DPI and read/zoomed by hand at >=400% -- not certified from a
thumbnail. See PR #7.

## esl-crossbar-kcl: KCL-node / readout-device symbol collision, fixed

The ported cp-4856 fixture's KCL-node-to-readout-device offset (`-1.15cm`)
was too short for circuitikz's default bipole size, so the KCL summation
node's circle visually overlapped the readout-device glyph in **both**
columns -- the same "compiles cleanly, visually broken" defect class cp-4856
originally reported. Fixed by widening the offset to `-1.8cm`.

- `esl-crossbar-kcl-full.png` -- full render, post-fix, 600dpi.
- `esl-crossbar-kcl-col1-readout-zoom.png` -- 500x500px crop (>=400% zoom)
  of the column-1 KCL-node/resistor junction. Clear gap, no overlap.
- `esl-crossbar-kcl-col2-readout-zoom.png` -- 500x500px crop (>=400% zoom)
  of the column-2 KCL-node/current-source junction. Clear gap, no overlap
  (this was the more severe of the two collisions pre-fix: the current
  source's larger circle glyph visibly merged into the KCL node's circle).

No separate label-on-label collision found anywhere in the full render
(checklist item 1): the per-column current-sum labels
($I_{1,1}{+}I_{2,1}$ / $I_{1,2}{+}I_{2,2}$), the "col. N readout" sidenotes,
and $I_{\text{out}}$ all sit clear of each other and of every node.

## esl-crossbar-kcl-adc: broadened circuitikz coverage, domain-band convention

- `esl-crossbar-kcl-adc-full.png` -- full render at 600dpi. Three different
  circuitikz device types (resistor, capacitor, current source) mixed with
  the hand-styled crossbar/KCL/vsource nodes; the analog and digital
  domain-bands separated by the dashed domain-boundary; no collisions
  against the D6 checklist.
- `esl-crossbar-kcl-adc-readout-band-zoom.png` -- crop across all three
  readout columns at once, confirming none of the three device types
  (R/C/I) collide with their KCL node above regardless of the glyph's own
  size/shape.

## Node-naming migration (cp-4883 ruling C8)

Not separately screenshotted (a naming change, not a geometry change): all
of `esl-crossbar-kcl`'s node identifiers were migrated from cp-4856's
concatenated-digit style (`v1`, `g11`, `k1`, `k1out`) to the family-wide
dash-separated, index-addressable pattern (`vin-1`, `cell-1-1`, `kcl-1`,
`dev-1`), matching `esl-crossbar-array`/`esl-crossbar-kcl-adc`. Re-rendered
and re-verified collision-free above; the rendered `$G_{i,j}$`/`$I_{i,j}$`
LaTeX labels are unaffected -- only the underlying TikZ node names changed.
