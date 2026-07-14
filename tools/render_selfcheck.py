#!/usr/bin/env python3
"""Render a content item to PNG and run the *mechanical half* of the D6 visual
self-check gate (ADR-0005 §D6; see docs/VISUAL_SELFCHECK.md).

This is deliberately separate from ``render_preview.py`` (which produces the
trimmed ``.svg`` shipped in the catalog). This tool exists for the **gate**:
compile -> rasterize at print resolution -> run the checks a machine actually
can run -> hand the PNG to whoever (agent or CI) does the check a machine
cannot: looking at it.

Mechanical checks (see ``docs/VISUAL_SELFCHECK.md`` for what these do and do
NOT cover):
  1. Overfull/underfull \\hbox / \\vbox warnings in the compile log -- content
     that does not fit the box LaTeX gave it (a real, if partial, proxy for
     "label not contained" / illegible-at-size).
  2. Text-bounding-box overlap, via ``pdftotext -bbox-layout`` word rectangles
     (scored as a fraction of the smaller word's area, not an absolute size --
     see ``detect_text_overlaps`` for why) -- catches two *independently
     positioned* text labels whose glyphs genuinely overlap. It does NOT see
     graphics (a TikZ node's fill, a circuitikz device symbol) at all, so it
     cannot catch a symbol-vs-symbol or symbol-vs-label collision that
     involves no overlapping *text* -- that class of defect is exactly what
     the agent's own read of the PNG is for.
  3. Node/node bounding-box collision (``detect_node_node_collisions``) and
     non-orthogonal node-to-node edges (``detect_diagonal_edges``), both via
     a real geometry probe: a temporary, instrumented COPY of the ``.tex``
     (never the original) that hooks pgf's own path/node primitives to
     ``\\typeout`` exact coordinates during compilation. Every label in this
     library's convention is itself a ``\\node`` (named or anonymous), so
     this ALSO catches a label overlapping a node it doesn't belong to (the
     cp-4893 WP-4 tile-label-over-PE regression this was built to catch) --
     without needing ``pdftotext`` at all. An earlier version compared a
     pgf-derived node bbox against a ``pdftotext``-derived word bbox for
     this; that comparison was dropped, not tuned, after it produced a false
     "collision" on a template with no defect (see
     ``detect_node_node_collisions``'s docstring) -- crossing between PGF's
     logical-box metrics and pdftotext's glyph-ink metrics turned out to be
     unreliable by a margin comparable to genuine collisions. Comparing
     node-vs-node, all in PGF's own coordinate system, has no such mismatch.

Exit code is non-zero if the item fails to compile/render or a mechanical
problem is found (use in CI); pass ``--no-fail`` to only report.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_preview import resolve_tex  # noqa: E402  (reuse the same path resolution)

DEFAULT_DPI = 300  # ADR-0004 D2: render at >=300 dpi for the visual self-check.
_OVERFULL_RE = re.compile(r"^(Overfull|Underfull) \\(hbox|vbox)", re.MULTILINE)

# --- geometry instrumentation (node/node collision, edge orthogonality) -----
#
# Compiles a temporary, INSTRUMENTED copy of the .tex (never the original) that
# hooks two pgf primitives to \typeout real coordinates during compilation:
#   - \pgfpathmoveto / \pgfpathlineto -- every straight-line segment TikZ draws
#     (a `--` edge, a rectangle/fit-box side) reduces to these two primitives in
#     the picture's own local coordinate frame, before any low-level PDF `cm`
#     transform is applied -- this is what makes edge-orthogonality checkable
#     without parsing the compiled PDF's content stream.
#   - `every node/.append style={append after command=...}` + `\tikzlastnode` --
#     fires once per node, however its name was generated (including inside a
#     \foreach, or left anonymous -- a label like a tile's corner text IS a
#     node in this library's convention, just an unnamed one; TikZ still auto-
#     names it, e.g. `tikz@f@1`, and `\tikzlastnode` still resolves it), giving
#     an exact node bounding box via \pgfpointanchor. Source regexes cannot do
#     this: a \foreach-driven template's node names (e.g. `pe-\r-\c-\k`) don't
#     exist as literal text until TeX expands them, and an anonymous node has
#     no literal name at all until TikZ generates one at compile time.
# Both are real pgf coordinates in the SAME picture-local frame, which is also
# the frame every collision check below compares in -- deliberately never
# converted to PDF page space (see detect_node_node_collisions's docstring).
_INSTRUMENT_HARNESS = r"""
\makeatletter
\let\selfcheckorigmoveto\pgfpathmoveto
\def\pgfpathmoveto#1{%
  \pgf@process{#1}%
  \typeout{SELFCHECK-MOVETO \the\pgf@x\space\the\pgf@y}%
  \selfcheckorigmoveto{\pgfqpoint{\pgf@x}{\pgf@y}}%
}
\let\selfcheckoriglineto\pgfpathlineto
\def\pgfpathlineto#1{%
  \pgf@process{#1}%
  \typeout{SELFCHECK-LINETO \the\pgf@x\space\the\pgf@y}%
  \selfcheckoriglineto{\pgfqpoint{\pgf@x}{\pgf@y}}%
}
\tikzset{
  every node/.append style={
    append after command={
      \pgfextra{
        \edef\selfchecknodename{\tikzlastnode}%
        \pgfpointanchor{\selfchecknodename}{south west}%
        \edef\selfchecksx{\the\pgf@x}\edef\selfchecksy{\the\pgf@y}%
        \pgfpointanchor{\selfchecknodename}{north east}%
        \edef\selfcheckex{\the\pgf@x}\edef\selfcheckey{\the\pgf@y}%
        \typeout{SELFCHECK-BBOX-NODE \selfchecknodename\space\selfchecksx\space\selfchecksy\space\selfcheckex\space\selfcheckey}%
      }
    }
  }
}
\makeatother
"""

_OP_RE = re.compile(r"SELFCHECK-(MOVETO|LINETO) (-?[\d.]+)pt (-?[\d.]+)pt")
_BBOX_NODE_RE = re.compile(
    r"SELFCHECK-BBOX-NODE (\S+) (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt (-?[\d.]+)pt"
)


def _inject_geometry_harness(tex_text: str) -> str:
    """Return a copy of ``tex_text`` with the geometry probe wired in.

    Never mutates the caller's file -- ``compile_geometry_probe`` always
    writes this to a fresh temp copy. Harness goes right after
    ``\\begin{document}`` so every node/path in the (single, per this
    library's convention) tikzpicture is hooked.
    """
    idx = tex_text.find("\\begin{document}")
    if idx == -1:
        return tex_text
    insert_at = idx + len("\\begin{document}")
    return tex_text[:insert_at] + _INSTRUMENT_HARNESS + tex_text[insert_at:]


def compile_geometry_probe(tex: Path) -> tuple[bool, str]:
    """Compile an instrumented COPY of ``tex`` in a fresh temp dir; never
    touches the original file or directory. Returns (ok, log) -- the log
    carries the ``SELFCHECK-*`` typeout lines the geometry checks parse."""
    text = tex.read_text(encoding="utf-8")
    instrumented = _inject_geometry_harness(text)
    with tempfile.TemporaryDirectory(prefix="opentikz-selfcheck-geom-") as tmp:
        work = Path(tmp)
        probe_tex = work / tex.name
        probe_tex.write_text(instrumented, encoding="utf-8")
        ok, log, _ = compile_pdf(probe_tex, work)
        return ok, log


def _extract_segments(log: str) -> list[tuple[float, float, float, float]]:
    """Reconstruct straight-line segments from ordered MOVETO/LINETO log lines.

    A MOVETO resets the path's current point; each LINETO defines one segment
    from the current point to the new one, then becomes the new current point
    -- this is exactly how a PDF path (and a TikZ ``--`` chain) is built.
    """
    segments: list[tuple[float, float, float, float]] = []
    cur: tuple[float, float] | None = None
    for m in _OP_RE.finditer(log):
        op, x, y = m.group(1), float(m.group(2)), float(m.group(3))
        if op == "MOVETO":
            cur = (x, y)
        else:
            if cur is not None:
                segments.append((cur[0], cur[1], x, y))
            cur = (x, y)
    return segments


def _distance_to_bbox(px: float, py: float, bbox: tuple[float, float, float, float]) -> float:
    """Euclidean distance from a point to the nearest point of a bbox (0 if inside)."""
    x1, y1, x2, y2 = bbox
    dx = max(x1 - px, 0.0, px - x2)
    dy = max(y1 - py, 0.0, py - y2)
    return math.hypot(dx, dy)


def _nearest_node(
    px: float, py: float, node_boxes: dict[str, tuple[float, float, float, float]], tol: float = 6.0
) -> str | None:
    """Return the node whose bbox is closest to (px,py), if within ``tol``.

    A straight ``(nodeA) -- (nodeB)`` edge's logged endpoint is TikZ's computed
    *border*-intersection point -- exactly on a rectangle node's bbox edge,
    strictly inside a circle node's bbox (a circle only touches its own bbox
    at the 4 cardinal points), and a few points short of either for an
    `>=Stealth`-shortened arrow. Nearest-by-distance (not "first node whose
    expanded bbox contains the point") matters because adjacent nodes with a
    small gap (e.g. `\\pegap`) have overlapping expanded-bbox regions near
    their shared corner -- picking by proximity, not iteration order, is what
    correctly resolves e.g. a segment landing exactly on pe-1-1-2's corner as
    "belongs to pe-1-1-2", not whichever neighbor happened to be logged first.
    """
    best_name, best_dist = None, None
    for name, bbox in node_boxes.items():
        d = _distance_to_bbox(px, py, bbox)
        if best_dist is None or d < best_dist:
            best_name, best_dist = name, d
    if best_dist is not None and best_dist <= tol:
        return best_name
    return None


def detect_diagonal_edges(
    log: str,
    node_boxes_texframe: dict[str, tuple[float, float, float, float]],
    angle_tol_deg: float = 3.0,
    min_length_pt: float = 15.0,
) -> list[str]:
    """Flag non-orthogonal straight-line segments between two NAMED nodes.

    Contract §3a primitive 5 (``typed-routing``): "orthogonal, no stray
    crossings" -- a rule about edges connecting named components, not about
    every straight line in a figure. Restricting to segments whose BOTH
    endpoints sit at/near a distinct named node's border is essential: a
    circuitikz resistor's zigzag symbol, a decorative arrow/chevron, or an
    icon's glyph outline are ALSO drawn via straight ``\\pgfpathlineto``
    segments and are legitimately non-orthogonal -- an earlier, unscoped
    version of this check flagged those across nearly the entire library
    (found and fixed via a full-library sweep, same discipline as
    ``detect_text_overlaps``'s tuning). A plain rectangle/fit-box outline is
    exempt for a different reason (verified separately): it is drawn via a
    dedicated pgf primitive, not individual ``\\pgfpathlineto`` calls.

    ``min_length_pt=15`` filters short segments too: a tiny (~4pt) segment
    near a shared border between a container and the node it contains (e.g.
    ``esl-architecture-block``'s tile/core nesting) can register as a
    "non-orthogonal edge between the two" purely because it lands within
    ``_nearest_node``'s tolerance of both -- it is corner/rounding geometry,
    not a drawn inter-component edge. A genuine typed-routing connection
    between two distinct components is a real, visible line, not a few points
    long; this threshold was raised after finding that false case on a real
    ESL template, not assumed up front.

    This check (and ``detect_node_node_collisions``) is scoped by the caller
    to ESL-family templates (``domain`` includes ``esl-architecture`` in the
    sibling ``.meta.json``) -- see ``_is_esl_family``. The contract's
    typed-routing rule is a placement-grammar rule for ADR-0005's
    contract-conforming families; it says nothing about upstream/generic
    opentikz content such as a neural-net diagram's fully-connected layers or
    a GAN figure's convergent arrows, where a diagonal line is the intended
    visual, not a defect -- an earlier, unscoped version flagged dozens of
    those across the library.
    """
    problems = []
    for x1, y1, x2, y2 in _extract_segments(log):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < min_length_pt:
            continue  # degenerate/near-zero segment (rounding, closepath)

        node_a = _nearest_node(x1, y1, node_boxes_texframe)
        node_b = _nearest_node(x2, y2, node_boxes_texframe)
        if node_a is None or node_b is None or node_a == node_b:
            continue  # not a node-to-node edge (a symbol/icon/decoration path)

        angle = math.degrees(math.atan2(abs(dy), abs(dx)))  # 0=horizontal, 90=vertical
        if angle_tol_deg < angle < (90 - angle_tol_deg):
            problems.append(
                f"non-orthogonal edge from {node_a!r} to {node_b!r} "
                f"(({x1:.1f}pt,{y1:.1f}pt) -> ({x2:.1f}pt,{y2:.1f}pt)) -- "
                f"{angle:.1f}\N{DEGREE SIGN} from horizontal, contract §3a "
                "typed-routing requires orthogonal routing"
            )
    return problems


def _extract_node_bboxes_texframe(log: str) -> dict[str, tuple[float, float, float, float]]:
    """Return {node_name: (sx,sy,ex,ey)} in tex-pt, y-up, picture-local origin,
    normalized so ``sx<=ex`` and ``sy<=ey`` (a true south-west/north-east box).

    ``\\pgfpointanchor``'s ``south west``/``north east`` queries are answered
    in the node's OWN local frame, then mapped through whatever canvas
    rotation is active -- for an ordinary (unrotated) ``\\node`` that frame
    lines up with the picture's global axes, but a circuitikz bipole draws
    its symbol rotated to lie along the wire it is placed on (e.g. a bipole
    running top-to-bottom between two vertically-stacked nodes), so its
    "south west"/"north east" anchors can land with a LARGER global y than
    its "north east" -- the corners are correct, just not already
    min/max-ordered. Left un-normalized, a negative-area box silently
    vanishes from every consumer below (``detect_node_node_collisions``'s
    ``area <= 0: continue`` guard, ``_distance_to_bbox``'s min/max-vs-point
    logic) -- exactly why a name=<id> bipole compiled cleanly through this
    probe yet still produced zero reported collisions against a genuinely
    overlapping node, until this normalization was added (WP-11, cp-4925).
    """
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for m in _BBOX_NODE_RE.finditer(log):
        sx, sy, ex, ey = (float(g) for g in m.groups()[1:])
        boxes[m.group(1)] = (min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
    return boxes


def detect_node_node_collisions(
    node_boxes_texframe: dict[str, tuple[float, float, float, float]],
    min_ratio: float = 0.40,
    containment_ratio: float = 0.80,
) -> list[str]:
    """Flag two named nodes (or nodes and labels -- see module docstring)
    whose bounding boxes partially overlap.

    Both boxes come from the SAME instrumented compile, in the SAME pgf
    tex-frame coordinate system -- deliberately never converted to PDF page
    space. An earlier version compared a page-space-converted PGF node bbox
    against a real label's ``pdftotext``-derived WORD bbox instead (to
    isolate "is this a label" from "is this a shape"), which requires
    knowing exactly where tex-frame (0,0) lands on the compiled page.
    Neither of the two ways tried to derive that (assuming ``standalone``
    crops symmetrically around the picture's bounding box; calibrating
    against an `overlay` marker node placed at the origin and read back via
    ``pdftotext``) held up: the first broke on any template whose
    documentclass omits the `tikz` option (verified: only the templates
    that DO carry it had symmetric margins); the second correctly
    calibrated position, but a bare/undrawn text node's own PGF bbox
    (logical TeX-box metrics: advance width, side bearings) systematically
    disagreed with `pdftotext`'s glyph-ink bbox for the SAME word by 60-90%
    of the word's area for ordinary multi-character labels (confirmed on
    ``encoder-decoder``'s "Encoder"/"enc" and this fixture's own tile
    label/tile-box pair) -- a false-collision magnitude indistinguishable
    from a genuine one. Comparing node-vs-node, entirely within PGF's own
    coordinate and metric system, has neither problem: every label in this
    library's convention is itself a ``\\node`` (see module docstring), so
    this check already covers "label overlaps a node it doesn't belong to"
    without ever touching `pdftotext` or page-space at all.

    Excludes near-total containment (>=``containment_ratio`` of the smaller
    node's area) -- that is a deliberate ``fit``/containment relationship
    (e.g. a tile box fully containing its PE nodes, or fully containing its
    own corner label), not a collision. Only catches TikZ ``\\node``-vs-
    ``\\node`` overlap; a circuitikz bipole (``to[R]``, ``to[I]``, ...) is
    not a named node and is invisible to this check -- see
    docs/VISUAL_SELFCHECK.md for why that gap is real.
    """
    problems = []
    names = list(node_boxes_texframe)
    for i in range(len(names)):
        a = names[i]
        ax1, ay1, ax2, ay2 = node_boxes_texframe[a]
        area_a = (ax2 - ax1) * (ay2 - ay1)
        if area_a <= 0:
            continue
        for j in range(i + 1, len(names)):
            b = names[j]
            bx1, by1, bx2, by2 = node_boxes_texframe[b]
            area_b = (bx2 - bx1) * (by2 - by1)
            if area_b <= 0:
                continue
            ox = max(0.0, min(ax2, bx2) - max(ax1, bx1))
            oy = max(0.0, min(ay2, by2) - max(ay1, by1))
            overlap = ox * oy
            smaller = min(area_a, area_b)
            ratio = overlap / smaller
            if min_ratio <= ratio < containment_ratio:
                problems.append(
                    f"node {a!r} and node {b!r} bounding boxes overlap "
                    f"{ratio:.0%} of the smaller node's area -- a collision, "
                    "not a containment relationship"
                )
    return problems


def _allow_diagonal_edges(tex: Path) -> bool:
    """Read the declared, reviewable opt-out from the sibling *.meta.json, if any.

    This is the "explicit, declared opt-out per template" the D6 gate requires
    for a legitimate diagonal (docs/VISUAL_SELFCHECK.md) -- a committed schema
    field a reviewer sees in the diff, never a runtime agent decision.
    """
    for meta_path in tex.parent.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        selfcheck_cfg = meta.get("selfcheck") or {}
        if selfcheck_cfg.get("allow_diagonal_edges"):
            return True
    return False


def _is_esl_family(tex: Path) -> bool:
    """Is this item part of an ADR-0005 ESL contract-conforming family?

    Checked via the sibling ``.meta.json``'s ``domain`` array carrying
    ``esl-architecture`` -- the tag every ESL template in this fork
    (esl-architecture-block, esl-crossbar-kcl/array, esl-mpsoc-*,
    esl-flow-pipeline, esl-sequence-timeline) consistently carries, and no
    upstream/generic template does. This gates both geometry checks below:
    the contract's §3a typed-routing rule ("orthogonal, no stray crossings")
    and the general expectation that a label sits inside its own node are
    ADR-0005 placement-grammar concerns for these families specifically --
    NOT a universal rule for every diagram in this library. An earlier,
    unscoped version of the diagonal-edge check flagged dozens of legitimate
    diagonal connections in upstream content (neural-net's fully-connected
    layers, a GAN figure's convergent arrows, a generic network icon's mesh)
    where a diagonal line is the intended visual, not a defect.
    """
    for meta_path in tex.parent.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "esl-architecture" in (meta.get("domain") or []):
            return True
    return False


def detect_geometry_problems(tex: Path, allow_diagonal_edges: bool = False) -> list[str]:
    """Run the geometry-based mechanical checks: node/node collision (which
    covers label-vs-node, since every label is a node here) and edge
    orthogonality -- scoped to ESL contract-conforming templates (see
    ``_is_esl_family``). Compiles a SEPARATE, instrumented copy of ``tex``;
    never touches the caller's files."""
    if not _is_esl_family(tex):
        return []

    ok, glog = compile_geometry_probe(tex)
    if not ok:
        return [
            "geometry probe failed to compile (see tools/render_selfcheck.py's "
            "instrumented-copy log) -- node-collision and edge-orthogonality "
            "checks were SKIPPED for this item; overfull-box/text-overlap checks "
            "above still apply"
        ]

    node_boxes = _extract_node_bboxes_texframe(glog)
    problems: list[str] = []
    if not allow_diagonal_edges:
        problems += detect_diagonal_edges(glog, node_boxes)
    problems += detect_node_node_collisions(node_boxes)
    return problems


def compile_pdf(tex: Path, out_dir: Path) -> tuple[bool, str, Path]:
    """Compile ``tex`` to PDF in ``out_dir``. Returns (ok, log, pdf_path)."""
    proc = subprocess.run(
        [
            "latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
            f"-output-directory={out_dir}", tex.name,
        ],
        cwd=tex.parent,
        capture_output=True,
        text=True,
    )
    log = proc.stdout + proc.stderr
    pdf = out_dir / (tex.stem + ".pdf")
    ok = proc.returncode == 0 and pdf.exists()
    return ok, log, pdf


def render_png(pdf: Path, out_png_stem: Path, dpi: int = DEFAULT_DPI) -> Path:
    """Rasterize ``pdf`` (single page) to ``<out_png_stem>.png`` via pdftoppm.

    ``out_png_stem`` is treated as an opaque string root, NOT a ``Path`` whose
    suffix gets manipulated: ``pdftoppm -singlefile`` appends the literal
    string ``.png`` to whatever root it is given, even if that root already
    contains dots (a template/icon id can). Using ``Path.with_suffix`` here
    previously mis-derived the expected output name whenever the stem had an
    embedded dot (e.g. an item path built from ``*.meta.json``), replacing the
    wrong "suffix" instead of appending ``.png`` -- always use string
    concatenation for this, never ``with_suffix``.
    """
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), "-singlefile", str(pdf), str(out_png_stem)],
        check=True, capture_output=True, text=True,
    )
    png = Path(str(out_png_stem) + ".png")
    if not png.exists():
        sys.exit(f"error: pdftoppm did not produce {png}")
    return png


def detect_overfull(log: str) -> list[str]:
    """Return the Overfull/Underfull hbox/vbox warning lines in a compile log."""
    return [
        line for line in log.splitlines()
        if _OVERFULL_RE.match(line.strip())
    ]


def _iter_word_boxes(bbox_xml: str) -> list[tuple[str, float, float, float, float, str]]:
    """Parse ``pdftotext -bbox-layout`` XHTML into (block_id, x1,y1,x2,y2, word)."""
    root = ET.fromstring(bbox_xml)
    ns = {"h": "http://www.w3.org/1999/xhtml"}
    # pdftotext's -bbox-layout output declares an xhtml namespace but tools vary;
    # fall back to no-namespace tags if the namespaced search comes up empty.
    blocks = root.findall(".//h:block", ns) or root.findall(".//block")
    out: list[tuple[str, float, float, float, float, str]] = []
    for bi, block in enumerate(blocks):
        words = block.findall(".//h:word", ns) or block.findall(".//word")
        for w in words:
            out.append((
                f"b{bi}",
                float(w.get("xMin")), float(w.get("yMin")),
                float(w.get("xMax")), float(w.get("yMax")),
                w.text or "",
            ))
    return out


def detect_text_overlaps(pdf: Path, min_ratio: float = 0.25) -> list[str]:
    """Return descriptions of overlapping text-word bounding boxes.

    Compares every pair of words on the page. LaTeX never overlaps the glyphs
    of a single run it typesets itself (ordinary kerning/subscripts sit flush,
    never on top of one another) -- a substantial overlap only occurs when
    two *independently positioned* pieces of content (two different TikZ
    nodes/labels placed too close, or literally on top of each other) collide.
    ``pdftotext``'s own block/line grouping is layout-reconstruction heuristic
    for reading order, not a safe/unsafe signal, so it is deliberately not
    used to exclude pairs here -- two labels merged into the same
    reconstructed block is itself often evidence they are spatially
    colliding, not evidence they are safe to skip.

    The overlap is scored as a **ratio of the smaller word's area**, not an
    absolute area, because ``pdftotext`` reports an axis-aligned bounding box
    even for *rotated* text (e.g. a sideways "Inner Loop" label next to a
    horizontal one) -- its AABB is inflated well past the visible glyph
    footprint and can graze a neighbor's AABB by a sliver with no real ink
    overlap at all. A small absolute overlap area is exactly that grazing
    case; a real collision (two labels genuinely on top of each other, as in
    the cp-4856 crossbar/collision fixture below) covers a large fraction of
    at least one of the two words. ``min_ratio=0.25`` was picked empirically:
    the rotated-label false positive found in ``examples/flash-attention``
    measures ~5-7%; a real full-word collision measures 70-90%+.
    """
    proc = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        check=True, capture_output=True, text=True,
    )
    boxes = _iter_word_boxes(proc.stdout)
    problems: list[str] = []
    for i in range(len(boxes)):
        _, ax1, ay1, ax2, ay2, aw = boxes[i]
        area_a = (ax2 - ax1) * (ay2 - ay1)
        for j in range(i + 1, len(boxes)):
            _, bx1, by1, bx2, by2, bw = boxes[j]
            area_b = (bx2 - bx1) * (by2 - by1)
            ox = max(0.0, min(ax2, bx2) - max(ax1, bx1))
            oy = max(0.0, min(ay2, by2) - max(ay1, by1))
            overlap = ox * oy
            smaller = min(area_a, area_b)
            if smaller > 0 and overlap / smaller >= min_ratio:
                problems.append(
                    f"text overlap: {aw!r} and {bw!r} bounding boxes overlap "
                    f"{overlap / smaller:.0%} of the smaller word's area "
                    "-- likely a label collision"
                )
    return problems


def selfcheck(tex: Path, png_out: Path, dpi: int = DEFAULT_DPI) -> tuple[bool, list[str], Path | None]:
    """Compile + render + run mechanical checks. Returns (ok, problems, png_path)."""
    with tempfile.TemporaryDirectory(prefix="opentikz-selfcheck-") as tmp:
        work = Path(tmp)
        ok, log, pdf = compile_pdf(tex, work)
        if not ok:
            tail = "\n".join(log.strip().splitlines()[-15:])
            return False, [f"compile failed:\n{tail}"], None
        problems = detect_overfull(log)
        problems += detect_text_overlaps(pdf)
        problems += detect_geometry_problems(tex, allow_diagonal_edges=_allow_diagonal_edges(tex))
        png_out.parent.mkdir(parents=True, exist_ok=True)
        png = render_png(pdf, png_out.with_suffix(""), dpi=dpi)
        final_png = png.rename(png_out) if png != png_out else png
        return not problems, problems, final_png


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="path to a .tex file or an item directory")
    parser.add_argument("-o", "--output", type=Path, help="output .png path (default: <name>.selfcheck.png beside the .tex)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--no-fail", action="store_true", help="report problems but always exit 0")
    args = parser.parse_args(argv)

    tex = resolve_tex(args.target)
    png_out = args.output or tex.with_suffix("").with_suffix(".selfcheck.png")

    ok, problems, png = selfcheck(tex, png_out, dpi=args.dpi)
    if png:
        print(f"wrote {png}")
    for p in problems:
        print(f"MECHANICAL-ISSUE  {tex}: {p}")
    if not problems:
        print(f"mechanical checks: no problems found for {tex} "
              f"(this does NOT mean the figure is correct -- read the PNG; "
              f"see docs/VISUAL_SELFCHECK.md)")

    if args.no_fail:
        return 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
