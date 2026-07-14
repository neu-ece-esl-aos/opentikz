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

Exit code is non-zero if the item fails to compile/render or a mechanical
problem is found (use in CI); pass ``--no-fail`` to only report.
"""
from __future__ import annotations

import argparse
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
