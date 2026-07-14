"""Per-template placement-grammar validation (ADR-0005 D3 §3b row).

A family's ``placement_grammar`` (``tools/adapter/settled-decisions/<family>.yaml``)
states checkable relationship rules over the family's §1 named components. This
module validates one template's ``.tex`` + sidecar ``intent.yaml`` against its
family's rules and reports, per rule, one of four verdicts:

- ``PASS``            — proven to hold, from the template's node graph / the
                         generator's own coordinate arithmetic (no render needed).
- ``FAIL``             — proven to be violated (a real, blocking finding).
- ``NOT_APPLICABLE``   — the template has no instance of the component/situation
                         the rule concerns (e.g. no digital-domain component to
                         split, no mem-block to place) — not evidence either way.
- ``NEEDS_RENDER``     — the rule is genuinely only checkable against a rendered
                         image (glyph-level label clearance, "reads correctly");
                         this module does NOT invent a static proxy for these —
                         they route to WP-8's rendered-PNG self-check gate
                         (``tools/render_selfcheck.py`` / manual PNG read).

Only ``FAIL`` is wired into ``tools/validate.py``'s blocking exit code (see
``placement_grammar_problems``); the rest are reporting-only (``cli.py grammar``,
``tools/ci/placement-grammar-report.sh``) — this file is explicit and honest
about the boundary rather than pretending a render-only rule is automated.

Scope note (what this is NOT): this is a source-level static analyzer scoped to
the coordinate idioms this fork's ESL templates actually use (explicit
``at (x,y)`` pgfmath arithmetic for the \\foreach-generated array templates;
``positioning``/``calc`` relative placement for the hand-fixed templates) — it
is not a general TikZ interpreter. A template using an idiom this module
doesn't recognize gets ``NEEDS_RENDER`` for orthogonality-class rules rather
than a fabricated PASS; see ``_resolve_point`` / ``AxisTracker``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .intent import IntentRecord

PASS = "PASS"
FAIL = "FAIL"
NOT_APPLICABLE = "NOT_APPLICABLE"
NEEDS_RENDER = "NEEDS_RENDER"


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    verdict: str
    detail: str


# --------------------------------------------------------------------------- #
# tex source parsing helpers
# --------------------------------------------------------------------------- #

_FOREACH_VAR_RE = re.compile(r"\\foreach\s+(\\[a-zA-Z]+)\s+in")
_MACRO_DEF_RE = re.compile(
    r"\\(?:pgfmathsetmacro|pgfmathtruncatemacro)\{(\\[a-zA-Z]+)\}\{([^}]*)\}"
    r"|\\def(\\[a-zA-Z]+)\{([^}]*)\}"
)
_TOKEN_RE = re.compile(r"\\[a-zA-Z]+")

# Node/coordinate names in \foreach-generated templates carry LITERAL,
# unexpanded loop-variable tokens (e.g. "cell-\r-\c", "pe-\r-\c-\k") -- the
# source is scanned before TeX macro expansion, so a name-capturing group
# must allow an embedded backslash, not just \w/-/. (a bare [\w\-] class
# silently drops these and makes every \foreach-generated edge invisible).
_NAME = r"[\w\-.\\]"

_NODE_AT_RE = re.compile(
    r"\\node\s*\[[^\]]*\]\s*\((?P<name>" + _NAME + r"+)\)\s*at\s*\(\s*(?P<x>[^,()]+?)\s*,\s*(?P<y>[^()]+?)\s*\)"
)
_NODE_REL_RE = re.compile(
    r"\\node\s*\[(?P<opts>[^\]]*)\]\s*\((?P<name>" + _NAME + r"+)\)"
)
_REL_OF_RE = re.compile(r"\b(right|left|above|below)\s*=\s*[^,\]]*?\bof\s+(" + _NAME + "+)")
_FIT_OF_RE = re.compile(r"\bfit\s*=\s*((?:\(" + _NAME + r"+\))+)")
_FIT_MEMBERS_RE = re.compile(r"\((" + _NAME + r"+)\)")

_COORD_MID_RE = re.compile(
    r"\\coordinate\s*\((?P<name>" + _NAME + r"+)\)\s*at\s*\(\$\((?P<a>" + _NAME + r"+)\)\s*!\s*[\d.]+\s*!\s*\((?P<b>" + _NAME + r"+)\)\$\)"
)
_COORD_OFFSET_RE = re.compile(
    r"\\coordinate\s*\((?P<name>" + _NAME + r"+)\)\s*at\s*\(\$\((?P<a>" + _NAME + r"+)\)\s*\+\s*\(\s*(?P<dx>[^,]+?)\s*,\s*(?P<dy>[^)]+?)\s*\)\$\)"
)
_COORD_AT_RE = re.compile(
    r"\\coordinate\s*\((?P<name>" + _NAME + r"+)\)\s*at\s*\(\s*(?P<x>[^,()$]+?)\s*,\s*(?P<y>[^()$]+?)\s*\)"
)

_DRAW_RE = re.compile(r"\\draw\s*\[(?P<style>[^\]]*)\]\s*(?P<path>[^;]+);")
_POINT_TOKEN_RE = re.compile(r"\((" + _NAME + r"+)\)")

_SCOPE_BG_RE = re.compile(
    r"\\begin\{scope\}\s*\[[^\]]*on background layer[^\]]*\](?P<body>.*?)\\end\{scope\}",
    re.DOTALL,
)


def loop_vars(tex: str) -> set[str]:
    return set(_FOREACH_VAR_RE.findall(tex))


def macro_defs(tex: str) -> dict:
    defs: dict[str, str] = {}
    for m in _MACRO_DEF_RE.finditer(tex):
        if m.group(1):
            defs[m.group(1)] = m.group(2)
        elif m.group(3):
            defs[m.group(3)] = m.group(4)
    return defs


def resolve_loopvar_deps(expr: str, defs: dict, loopvars: set, _seen: frozenset = frozenset()) -> frozenset:
    """The set of \\foreach loop variables ``expr`` varies with (transitively
    through macro references). Fixed \\def parameters are constants (they don't
    vary across the figure) and are deliberately excluded."""
    deps: set[str] = set()
    for tok in _TOKEN_RE.findall(expr):
        if tok in _seen:
            continue
        if tok in loopvars:
            deps.add(tok)
        elif tok in defs:
            deps |= resolve_loopvar_deps(defs[tok], defs, loopvars, _seen | {tok})
    return frozenset(deps)


def try_eval_numeric(expr: str, defs: dict, loopvars: set, _seen: frozenset = frozenset()):
    """Fully substitute + evaluate ``expr`` to a float, ONLY if it contains no
    \\foreach loop-variable token (i.e. it is a fixed-parameter constant across
    the whole figure). Returns ``None`` if it can't be fully resolved this way
    (contains a loop var, an unknown macro, or anything but arithmetic)."""

    def subst(e: str, seen: frozenset):
        out = []
        for tok in re.findall(r"\\[a-zA-Z]+|[^\\]+", e):
            if tok.startswith("\\"):
                if tok in loopvars or tok in seen:
                    return None
                if tok not in defs:
                    return None
                sub = subst(defs[tok], seen | {tok})
                if sub is None:
                    return None
                out.append(f"({sub})")
            else:
                out.append(tok)
        return "".join(out)

    substituted = subst(expr, _seen)
    if substituted is None:
        return None
    if re.search(r"[^0-9.+\-*/()\s]", substituted):
        return None
    try:
        return float(eval(substituted, {"__builtins__": {}}, {}))  # noqa: S307 (guarded above)
    except Exception:
        return None


def same_axis_value(expr_a: str, expr_b: str, defs: dict, loopvars: set):
    """Compare two coordinate-expression strings for provable equality along
    one axis. Returns True (proven same), False (proven different), or None
    (can't determine statically)."""
    a, b = expr_a.strip(), expr_b.strip()
    va, vb = try_eval_numeric(a, defs, loopvars), try_eval_numeric(b, defs, loopvars)
    if va is not None and vb is not None:
        return abs(va - vb) < 1e-6
    deps_a, deps_b = resolve_loopvar_deps(a, defs, loopvars), resolve_loopvar_deps(b, defs, loopvars)
    if va is not None or vb is not None:
        # one is a bindable constant, the other varies with a loop var -> can
        # only be "equal" by coincidence at one value, not provably always.
        return False if (deps_a or deps_b) else None
    if not deps_a and not deps_b:
        # neither evaluated numerically nor has loop-var deps: unresolvable
        # macro/expression shape (e.g. references an undefined name) -- honest unknown.
        return None
    return deps_a == deps_b


def strip_anchor(token: str):
    """Split ``name.anchor`` -> (name, anchor); ``anchor`` is ``None`` if bare."""
    if "." in token:
        name, anchor = token.split(".", 1)
        return name, anchor
    return token, None


# --------------------------------------------------------------------------- #
# generated-array (\\foreach) coordinate model: nodes at explicit at(X,Y)
# --------------------------------------------------------------------------- #

def collect_at_coords(tex: str) -> dict:
    """Map node/coordinate name -> (x_expr, y_expr) for every explicit
    ``at (X,Y)`` node/coordinate declaration (the \\foreach-generator idiom)."""
    coords: dict[str, tuple] = {}
    for m in _NODE_AT_RE.finditer(tex):
        coords[m.group("name")] = (m.group("x"), m.group("y"))
    for m in _COORD_AT_RE.finditer(tex):
        coords.setdefault(m.group("name"), (m.group("x"), m.group("y")))
    return coords


def collect_generated_patterns(tex: str, loopvars: set, defs: dict) -> dict:
    """(stem, arity) -> (generic_index_tokens, x_expr, y_expr) for every
    declared name whose trailing ``-token`` segments include at least one
    \\foreach loop variable (e.g. "cell-\\r-\\c" -> ("cell", 2) ->
    (("\\r", "\\c"), "\\px", "\\py")). A ``\\draw`` line inside the same
    generator may reference a DIFFERENT concrete/parameter token in one
    position (e.g. "cell-1-\\c" -- fixed at the first row; "cell-\\r-\\ncols"
    -- fixed at the last column) rather than the exact declared name; this
    table is what ``resolve_generated_ref`` substitutes against.

    Soundness gate: a pattern is only registered if EVERY loop variable its
    x/y expression actually depends on (transitively, per
    ``resolve_loopvar_deps``) is one of the name's own index tokens. This
    rules out families like "pe-<row>-<col>-<k>" (contract §1b architecture)
    whose real position depends on an INNER sub-loop's variables (\\pr, \\pc)
    that are not the same variables exposed in the node's own name -- for
    those, substituting the one differing name-token is a no-op that would
    silently assert "same axis" with no actual evidence (two textually-
    identical, unresolved macro references aren't proof of equal position
    when that macro is redefined per inner-loop iteration). Withholding the
    pattern forces the caller down the honest NEEDS_RENDER path instead.
    """
    patterns: dict = {}
    for name, (x, y) in collect_at_coords(tex).items():
        parts = name.split("-")
        if len(parts) < 2:
            continue
        stem, tokens = parts[0], tuple(parts[1:])
        token_set = set(tokens)
        if not (token_set & loopvars):
            continue
        x_deps = resolve_loopvar_deps(x, defs, loopvars)
        y_deps = resolve_loopvar_deps(y, defs, loopvars)
        if not (x_deps <= token_set and y_deps <= token_set):
            continue
        patterns.setdefault((stem, len(tokens)), (tokens, x, y))
    return patterns


def resolve_generated_ref(ref_name: str, patterns: dict):
    """Resolve a (possibly non-exactly-declared) generated-node reference to
    an (x_expr, y_expr) pair by substituting this reference's own index
    tokens into its stem/arity's generic declared expression. Returns None if
    no matching pattern is registered."""
    parts = ref_name.split("-")
    if len(parts) < 2:
        return None
    stem, ref_tokens = parts[0], tuple(parts[1:])
    pattern = patterns.get((stem, len(ref_tokens)))
    if pattern is None:
        return None
    generic_tokens, x, y = pattern
    for generic_tok, ref_tok in zip(generic_tokens, ref_tokens):
        if generic_tok == ref_tok:
            continue
        sub_re = re.compile(re.escape(generic_tok) + r"(?![a-zA-Z])")
        # replacement is a literal string, not a regex-replacement template --
        # ref_tok itself starts with a backslash (a macro name), which
        # re.sub's repl-string mini-language would otherwise try to parse as
        # a backreference/escape (e.g. "\k" -> "bad escape" error).
        x, y = sub_re.sub(lambda _m: ref_tok, x), sub_re.sub(lambda _m: ref_tok, y)
    return x, y


def anchor_axis_keys(base_x, base_y, anchor: str | None):
    """(x_key, y_key) after applying an anchor to a base (x_expr, y_expr) pair,
    for the explicit-coordinate model. north/south only move y; east/west only
    move x -- the untouched axis keeps the base's expression as its key; the
    moved axis is tagged so two DIFFERENT anchors are never conflated."""
    if anchor in ("north", "south"):
        return base_x, (base_y, anchor)
    if anchor in ("east", "west"):
        return (base_x, anchor), base_y
    return base_x, base_y


def check_edge_orthogonal_generated(a_tok: str, b_tok: str, coords: dict, defs: dict, loopvars: set, patterns: dict | None = None):
    """Orthogonality check for an edge between two explicit-at(X,Y) points.

    Falls back to ``resolve_generated_ref`` (via ``patterns``) when a
    reference doesn't exactly match a declared name -- e.g. an edge-drawing
    loop referencing "cell-1-\\c" (fixed at the first row) or
    "cell-\\r-\\ncols" (fixed at the last column) against a declaration of
    "cell-\\r-\\c" (the generic per-iteration pattern).
    """
    a_name, a_anchor = strip_anchor(a_tok)
    b_name, b_anchor = strip_anchor(b_tok)
    a_coord = coords.get(a_name) or (resolve_generated_ref(a_name, patterns) if patterns else None)
    b_coord = coords.get(b_name) or (resolve_generated_ref(b_name, patterns) if patterns else None)
    if a_coord is None or b_coord is None:
        return None, f"{a_tok} -- {b_tok}: endpoint has no resolvable at(X,Y) coordinate"
    ax, ay = anchor_axis_keys(*a_coord, a_anchor)
    bx, by = anchor_axis_keys(*b_coord, b_anchor)
    same_x = same_axis_value(ax, bx, defs, loopvars) if isinstance(ax, str) and isinstance(bx, str) else (ax == bx or None)
    same_y = same_axis_value(ay, by, defs, loopvars) if isinstance(ay, str) and isinstance(by, str) else (ay == by or None)
    if same_x is True or same_y is True:
        return True, f"{a_tok} -- {b_tok}: orthogonal (shares {'x' if same_x else 'y'})"
    if same_x is False and same_y is False:
        return False, f"{a_tok} -- {b_tok}: neither x nor y match -- diagonal segment"
    return None, f"{a_tok} -- {b_tok}: could not prove same-axis statically"


# --------------------------------------------------------------------------- #
# hand-fixed (positioning + calc) coordinate model: a persistent class tracker
# --------------------------------------------------------------------------- #

class AxisTracker:
    """Tracks, per named node/coordinate, an opaque (x_key, y_key) pair built
    up in source order from the ``positioning`` + ``calc`` idioms this fork's
    hand-fixed templates use: a bare first node; ``right=/left=/above=/below=
    of REF``; a ``fit=(m1)(...)`` box (inherits its first member's keys); a
    calc midpoint ``($(A)!t!(B)$)``; a calc offset ``($(A)+(dx,dy)$)``.

    This is intentionally NOT a general TikZ coordinate evaluator -- an idiom
    it doesn't recognize leaves that node's keys unset, and any check touching
    it reports ``NEEDS_RENDER`` rather than a guess.
    """

    def __init__(self):
        self._x: dict[str, object] = {}
        self._y: dict[str, object] = {}
        self._counter = 0

    def _fresh(self):
        self._counter += 1
        return f"_fresh{self._counter}"

    def known(self, name: str) -> bool:
        return name in self._x and name in self._y

    def keys_for(self, token: str):
        """Resolve a possibly-anchored token (``name`` or ``name.anchor``) to
        (x_key, y_key), or (None, None) if unknown."""
        name, anchor = strip_anchor(token)
        if not self.known(name):
            return None, None
        x, y = self._x[name], self._y[name]
        if anchor in ("north", "south"):
            return x, (y, anchor)
        if anchor in ("east", "west"):
            return (x, anchor), y
        return x, y

    def set_independent(self, name: str):
        self._x[name] = self._fresh()
        self._y[name] = self._fresh()

    def set_right_left_of(self, name: str, ref: str):
        ref_x, ref_y = self.keys_for(ref)
        self._x[name] = self._fresh()
        self._y[name] = ref_y if ref_y is not None else self._fresh()

    def set_above_below_of(self, name: str, ref: str):
        ref_x, ref_y = self.keys_for(ref)
        self._x[name] = ref_x if ref_x is not None else self._fresh()
        self._y[name] = self._fresh()

    def set_fit(self, name: str, members: list):
        if members and self.known(members[0]):
            self._x[name] = self._x[members[0]]
            self._y[name] = self._y[members[0]]
        else:
            self.set_independent(name)

    def set_midpoint(self, name: str, a: str, b: str):
        ax, ay = self.keys_for(a)
        bx, by = self.keys_for(b)
        self._x[name] = ax if (ax is not None and ax == bx) else self._fresh()
        self._y[name] = ay if (ay is not None and ay == by) else self._fresh()

    def set_offset(self, name: str, a: str, dx: str, dy: str):
        ax, ay = self.keys_for(a)
        self._x[name] = ax if (_is_zero(dx) and ax is not None) else self._fresh()
        self._y[name] = ay if (_is_zero(dy) and ay is not None) else self._fresh()


def _is_zero(expr: str) -> bool:
    try:
        return abs(float(expr.strip())) < 1e-9
    except ValueError:
        return False


def build_axis_tracker(tex: str) -> AxisTracker:
    tracker = AxisTracker()
    # Walk the source top-to-bottom, dispatching each node/coordinate
    # declaration to the tracker in the order the file defines them (later
    # references always resolve against already-tracked earlier ones).
    stmt_re = re.compile(
        r"\\node\s*\[(?P<opts>[^\]]*)\]\s*\((?P<name>[\w\-]+)\)"
        r"|\\coordinate\s*\((?P<cname>[\w\-]+)\)\s*at\s*\((?P<cexpr>[^;]+?)\)\s*;"
    )
    for m in stmt_re.finditer(tex):
        if m.group("name"):
            name, opts = m.group("name"), m.group("opts")
            rel = _REL_OF_RE.search(opts)
            fit = _FIT_OF_RE.search(opts)
            if fit:
                members = _FIT_MEMBERS_RE.findall(fit.group(1))
                tracker.set_fit(name, members)
            elif rel:
                direction, ref = rel.group(1), rel.group(2)
                if direction in ("right", "left"):
                    tracker.set_right_left_of(name, ref)
                else:
                    tracker.set_above_below_of(name, ref)
            else:
                tracker.set_independent(name)
        else:
            name, expr = m.group("cname"), m.group("cexpr")
            mid = _COORD_MID_RE.search(f"\\coordinate ({name}) at ({expr})")
            off = _COORD_OFFSET_RE.search(f"\\coordinate ({name}) at ({expr})")
            if mid:
                tracker.set_midpoint(name, mid.group("a"), mid.group("b"))
            elif off:
                tracker.set_offset(name, off.group("a"), off.group("dx"), off.group("dy"))
            else:
                tracker.set_independent(name)
    return tracker


def check_edge_orthogonal_fixed(a_tok: str, b_tok: str, tracker: AxisTracker):
    ax, ay = tracker.keys_for(a_tok)
    bx, by = tracker.keys_for(b_tok)
    if ax is None or bx is None:
        return None, f"{a_tok} -- {b_tok}: endpoint uses an unrecognized positioning idiom"
    if ax == bx or ay == by:
        return True, f"{a_tok} -- {b_tok}: orthogonal ({'shares x' if ax == bx else 'shares y'})"
    return False, f"{a_tok} -- {b_tok}: neither x nor y match -- diagonal segment"


# --------------------------------------------------------------------------- #
# edges / fit / membership extraction (family-agnostic)
# --------------------------------------------------------------------------- #

@dataclass
class Edge:
    styles: set
    points: list       # path point tokens, in order (>= 2 when resolvable)
    raw: str
    unresolved: bool = False  # path uses an inline -|/|- combinator this module doesn't model


def parse_edges(tex: str) -> list:
    """Every ``\\draw[style] ...;`` statement -- including ones this module
    can't decompose into simple point tokens (an inline ``A -| B`` / ``A |- B``
    coordinate combinator, e.g. a trunk-and-branch orthogonal router). Those
    are returned with ``unresolved=True`` and an empty ``points`` list rather
    than silently dropped, so a caller counting "how many <style> edges exist"
    doesn't undercount, and a rule whose only evidence is such an edge reports
    NEEDS_RENDER instead of a falsely confident NOT_APPLICABLE/PASS.
    """
    edges = []
    for m in _DRAW_RE.finditer(tex):
        style = {s.strip() for s in m.group("style").split(",") if s.strip()}
        path = m.group("path")
        points = _POINT_TOKEN_RE.findall(path)
        has_combinator = bool(re.search(r"-\||\|-", path))
        if len(points) >= 2 and not has_combinator:
            edges.append(Edge(styles=style, points=points, raw=m.group(0)))
        else:
            edges.append(Edge(styles=style, points=[], raw=m.group(0), unresolved=True))
    return edges


def parse_literal_fit_membership(tex: str) -> dict:
    """node -> fit-box name, for LITERAL ``fit=(a)(b)(c)`` declarations (the
    hand-fixed-template idiom). Returns {} if no literal fit lists are found
    (e.g. a \\foreach template using a macro-accumulated fit list instead --
    see ``node_family_membership`` for that case)."""
    membership: dict[str, str] = {}
    for node_m in _NODE_REL_RE.finditer(tex):
        opts, fitname = node_m.group("opts"), node_m.group("name")
        fit = _FIT_OF_RE.search(opts)
        if fit:
            for member in _FIT_MEMBERS_RE.findall(fit.group(1)):
                membership[member] = fitname
    return membership


def fit_declared_after_members_and_backgrounded(tex: str) -> list:
    """For every ``\\node[..., fit=(a)(b)(...)] (name)`` declaration, verify it
    is textually declared after every member it fits AND sits inside a
    ``\\begin{scope}[on background layer] ... \\end{scope}`` block. Returns a
    list of (fit_name, ok: bool, detail: str)."""
    bg_spans = [(m.start(), m.end()) for m in _SCOPE_BG_RE.finditer(tex)]
    node_positions: dict[str, int] = {}
    results = []
    for node_m in _NODE_REL_RE.finditer(tex):
        name = node_m.group("name")
        node_positions.setdefault(name, node_m.start())
        opts = node_m.group("opts")
        fit = _FIT_OF_RE.search(opts)
        if not fit:
            continue
        members = _FIT_MEMBERS_RE.findall(fit.group(1))
        fit_pos = node_m.start()
        late_enough = all(node_positions.get(m, -1) != -1 and node_positions[m] < fit_pos for m in members)
        in_bg = any(start <= fit_pos < end for start, end in bg_spans)
        ok = late_enough and in_bg
        detail = (
            f"fit node {name!r} (members {members}): "
            f"declared-after-members={late_enough}, on-background-layer={in_bg}"
        )
        results.append((name, ok, detail))
    return results


# --------------------------------------------------------------------------- #
# per-family rule checkers
# --------------------------------------------------------------------------- #

@dataclass
class TemplateCtx:
    tex: str
    intent: IntentRecord
    is_generated: bool  # any entity uses node_family (vs. literal nodes)


def _entities_by_component(ctx: TemplateCtx, component: str):
    return [e for e in ctx.intent.entities if e.get("component") == component]


def _literal_nodes(entity: dict) -> list:
    return list(entity.get("nodes") or [])


_GENERATED_NAME_RE_CACHE: dict = {}


# One index segment in a generated name is either a literal digit run (a
# fully-instantiated concrete name) or a literal backslash-macro token (the
# unexpanded \foreach loop-variable form this fork's source actually uses,
# e.g. "cell-\r-\c") -- source is scanned before TeX macro expansion.
_INDEX_SEGMENT = r"-(?:\d+|\\[a-zA-Z]+)"
_INDEX_CAPTURE = r"-(\d+|\\[a-zA-Z]+)"


def _generated_name_regex(stem: str, n_indices: int):
    key = (stem, n_indices)
    if key not in _GENERATED_NAME_RE_CACHE:
        pattern = "^" + re.escape(stem) + _INDEX_SEGMENT * n_indices + "$"
        _GENERATED_NAME_RE_CACHE[key] = re.compile(pattern)
    return _GENERATED_NAME_RE_CACHE[key]


def _tile_key_for_node(node_name: str, tile_entity: dict, member_entities: list):
    """Resolve which tile (by a hashable key) ``node_name`` belongs to, for
    both the literal-fit-list idiom and the node_family index-prefix idiom.
    Returns None if the node isn't a recognized member/tile at all."""
    base, _anchor = strip_anchor(node_name)
    if "node_family" in tile_entity:
        stem, indices = tile_entity["node_family"]["stem"], tile_entity["node_family"]["indices"]
        rx = _generated_name_regex(stem, len(indices))
        if rx.match(base):
            return ("tile", base)  # a tile node itself: its own identity is its key
        for member in member_entities:
            if "node_family" not in member:
                continue
            mstem, mindices = member["node_family"]["stem"], member["node_family"]["indices"]
            mrx = _generated_name_regex(mstem, len(mindices))
            if mrx.match(base):
                tokens = re.findall(_INDEX_CAPTURE, base)
                prefix = tuple(tokens[: len(indices)])
                return ("member", prefix)
        return None
    else:
        nodes = _literal_nodes(tile_entity)
        if base in nodes:
            return ("tile", base)
        return None


# --- architecture ----------------------------------------------------------- #

def _arch_tile_entity(ctx: TemplateCtx):
    tiles = _entities_by_component(ctx, "tile")
    return tiles[0] if tiles else None


def _arch_member_entities(ctx: TemplateCtx):
    # Only components the family record's own rule text names as tile
    # members ("pe (and cpu-core / acc-core) nodes sit INSIDE their tile" --
    # pes-inside-tiles). mem-block is deliberately EXCLUDED: the family's own
    # shared-memory-locus rule places it OUTSIDE every tile, at one fixed
    # locus (e.g. esl-mpsoc-memory-hierarchy's mem-block pinned above the
    # tile row) -- requiring tile-containment for it would fail every
    # correct instance of that separate, already-checked rule.
    return [
        e for e in ctx.intent.entities
        if e.get("component") in ("pe", "cpu-core", "acc-core")
    ]


def _arch_membership_map(ctx: TemplateCtx):
    """node -> tile-key, for the LITERAL fit-list idiom only. Returns {} for a
    node_family (generator) template -- membership there is resolved lazily,
    per node, by ``_tile_key_for_node``'s index-prefix match (no enumeration
    of concrete generated names is needed or possible from source alone)."""
    tile_entity = _arch_tile_entity(ctx)
    if tile_entity is None or "node_family" in tile_entity:
        return {}, tile_entity
    mapping: dict[str, tuple] = {
        node: ("tile", fit_name) for node, fit_name in parse_literal_fit_membership(ctx.tex).items()
    }
    return mapping, tile_entity


def _resolve_container(node_token: str, ctx: TemplateCtx, literal_map: dict, tile_entity: dict, member_entities: list):
    base, _anchor = strip_anchor(node_token)
    if tile_entity and "node_family" in tile_entity:
        return _tile_key_for_node(base, tile_entity, member_entities)
    if base in literal_map:
        return literal_map[base]
    if tile_entity and base in _literal_nodes(tile_entity):
        return ("tile", base)
    return None


def _check_pes_inside_tiles(ctx: TemplateCtx) -> RuleResult:
    tile_entity = _arch_tile_entity(ctx)
    if tile_entity is None:
        return RuleResult("pes-inside-tiles", NOT_APPLICABLE, "no tile component in this template")
    members = _arch_member_entities(ctx)
    if not members:
        return RuleResult("pes-inside-tiles", NOT_APPLICABLE, "no pe/core/mem-block component in this template")
    literal_map, _ = _arch_membership_map(ctx)
    literal_members = [m for m in members if "node_family" not in m]
    generated_members = [m for m in members if "node_family" in m]
    orphans = []
    for member in literal_members:
        for node in _literal_nodes(member):
            if node not in literal_map:
                orphans.append(node)
    if orphans:
        return RuleResult("pes-inside-tiles", FAIL, f"nodes not contained by any tile fit box: {orphans}")
    if literal_members and not generated_members:
        return RuleResult("pes-inside-tiles", PASS, "every literal member node is fitted by a tile box")
    if generated_members and not literal_members:
        # membership for a \foreach-generated member is definitionally the
        # shared index prefix with its tile (cp-4883's naming ruling) -- no
        # node can "float" outside that naming scheme by construction. The
        # one thing that COULD go wrong -- the member's \node declarations
        # not actually nested inside the tile's own generation loop -- is
        # exactly what tile-fit-declared-after-members proves; this rule
        # reports that same evidence rather than re-deriving it.
        nested = _check_tile_fit_declared_after_members(ctx)
        if nested.verdict == FAIL:
            return RuleResult("pes-inside-tiles", FAIL, f"generated members not nested under their tile: {nested.detail}")
        if nested.verdict == PASS:
            return RuleResult("pes-inside-tiles", PASS, "generated members share their tile's index prefix by construction, and are nested under it (see tile-fit-declared-after-members)")
        return RuleResult("pes-inside-tiles", NEEDS_RENDER, "could not statically confirm generated members are nested under their tile")
    return RuleResult("pes-inside-tiles", PASS, "every literal member node is fitted by a tile box; generated members share their tile's index prefix by construction")


def _check_tile_fit_declared_after_members(ctx: TemplateCtx) -> RuleResult:
    tile_entity = _arch_tile_entity(ctx)
    if tile_entity is None or "node_family" in tile_entity:
        # the array generator's fit list is macro-accumulated (fit=\tilefitlist),
        # not literal text -- declaration-order is checkable structurally instead:
        # confirm the tilebox \node[...fit=...] line appears textually after
        # every member \node declaration it fits, both inside on-background-
        # layer. Found via the member entity's OWN node_family stem (never a
        # hardcoded loop-variable name like \pr/\pc -- this fork's templates
        # name their \foreach index variables differently per template, e.g.
        # esl-mpsoc-memory-hierarchy uses \t/\k, not \pr/\pc).
        m = re.search(r"\\node\s*\[[^\]]*fit\s*=\s*\\\w+[^\]]*\]\s*\((?P<name>" + _NAME + r"+)\)", ctx.tex)
        if not m:
            return RuleResult("tile-fit-declared-after-members", NOT_APPLICABLE, "no macro-based fit box found")
        bg_spans = [(s.start(), s.end()) for s in _SCOPE_BG_RE.finditer(ctx.tex)]
        in_bg = any(start <= m.start() < end for start, end in bg_spans)
        members = [e for e in _arch_member_entities(ctx) if "node_family" in e]
        member_end = None
        for member in members:
            stem = member["node_family"]["stem"]
            member_rx = re.compile(r"\\node\s*\[[^\]]*\]\s*\(" + re.escape(stem) + r"-" + _NAME + r"+\)")
            positions = [mm.end() for mm in member_rx.finditer(ctx.tex)]
            if positions:
                member_end = max(member_end or 0, max(positions))
        after_members = member_end is not None and m.start() > member_end
        if in_bg and after_members:
            return RuleResult("tile-fit-declared-after-members", PASS, "fit box follows every member's own generation loop, on background layer")
        return RuleResult(
            "tile-fit-declared-after-members", FAIL,
            f"fit box {m.group('name')!r}: on-background-layer={in_bg}, after member generation={after_members}",
        )
    results = fit_declared_after_members_and_backgrounded(ctx.tex)
    if not results:
        return RuleResult("tile-fit-declared-after-members", NOT_APPLICABLE, "no literal fit box found")
    bad = [d for _n, ok, d in results if not ok]
    if bad:
        return RuleResult("tile-fit-declared-after-members", FAIL, "; ".join(bad))
    return RuleResult("tile-fit-declared-after-members", PASS, "; ".join(d for _n, _ok, d in results))


def _orthogonality_verdicts(ctx: TemplateCtx, edges: list):
    """(fails, unknowns) detail-string lists for every segment of ``edges``.

    Two coordinate models coexist in this fork's templates independently of
    whether the intent record uses ``nodes:`` or ``node_family:`` (that split
    is about node NAMING, not which TikZ placement idiom a template uses):
    explicit ``at(X,Y)`` pgfmath arithmetic (both crossbar templates), and
    ``positioning``/``calc`` relative placement (the architecture templates).
    Resolve each endpoint against whichever model recognizes it; a segment
    whose two endpoints resolve in DIFFERENT models can't be compared and is
    reported unknown (route to render) rather than guessed.
    """
    defs, lv = macro_defs(ctx.tex), loop_vars(ctx.tex)
    coords = collect_at_coords(ctx.tex)
    patterns = collect_generated_patterns(ctx.tex, lv, defs)
    tracker = build_axis_tracker(ctx.tex)

    def in_generated_model(name):
        return name in coords or resolve_generated_ref(name, patterns) is not None

    verdicts = []
    for edge in edges:
        if edge.unresolved:
            verdicts.append((None, f"{edge.raw.strip()}: uses an inline -|/|- coordinate combinator this module doesn't model"))
            continue
        for i in range(len(edge.points) - 1):
            a_tok, b_tok = edge.points[i], edge.points[i + 1]
            a_name, _ = strip_anchor(a_tok)
            b_name, _ = strip_anchor(b_tok)
            if in_generated_model(a_name) and in_generated_model(b_name):
                verdicts.append(check_edge_orthogonal_generated(a_tok, b_tok, coords, defs, lv, patterns))
            elif not in_generated_model(a_name) and not in_generated_model(b_name):
                verdicts.append(check_edge_orthogonal_fixed(a_tok, b_tok, tracker))
            else:
                verdicts.append((None, f"{a_tok} -- {b_tok}: endpoints resolve in different coordinate models"))
    return [d for ok, d in verdicts if ok is False], [d for ok, d in verdicts if ok is None]


def _check_bus_scoping(ctx: TemplateCtx, style_name: str, rule_id: str, same_tile_required: bool) -> RuleResult:
    """Composite check for one bus style: (a) tile-scoping (intra-bus never
    crosses a tile; inter-bus always does) AND (b) orthogonality of every
    segment -- both are named in the same settled-decision rule text ("SHORT
    and orthogonal" / "routed ORTHOGONALLY along the gaps")."""
    tile_entity = _arch_tile_entity(ctx)
    if tile_entity is None:
        return RuleResult(rule_id, NOT_APPLICABLE, "no tile component in this template")
    members = _arch_member_entities(ctx)
    literal_map, _ = _arch_membership_map(ctx)
    edges = [e for e in parse_edges(ctx.tex) if style_name in e.styles]
    if not edges:
        return RuleResult(rule_id, NOT_APPLICABLE, f"no {style_name} edges drawn in this template")
    no_component_names = {
        e["nodes"][0] for e in ctx.intent.entities if "component" not in e and e.get("nodes")
    }  # e.g. the "io" hub (contract gap G1) -- exempt from tile-membership requirement
    scoping_violations = []
    unresolved = [
        f"{e.raw.strip()}: uses an inline -|/|- coordinate combinator this module doesn't model"
        for e in edges if e.unresolved
    ]
    resolvable_edges = [e for e in edges if not e.unresolved]
    for edge in resolvable_edges:
        keys = []
        skip = False
        for tok in (edge.points[0], edge.points[-1]):
            base, _anchor = strip_anchor(tok)
            if base in no_component_names:
                skip = True
                break
            keys.append(_resolve_container(tok, ctx, literal_map, tile_entity, members))
        if skip:
            continue
        if any(k is None for k in keys):
            # An unresolved endpoint is NOT itself a scoping violation -- it's
            # commonly a bare \coordinate helper (e.g. a routing "rail") or a
            # legitimately tile-external entity (a mem-block/hub the family's
            # OWN shared-memory-locus rule places outside every tile). Only a
            # genuine same-tile/cross-tile mismatch between two RESOLVED
            # endpoints is evidence of a violation; note the gap honestly
            # instead of asserting one.
            unresolved.append(f"{edge.raw.strip()}: an endpoint has no resolvable tile membership (helper coordinate or tile-external node)")
            continue
        same_tile = keys[0] == keys[1]
        if same_tile_required and not same_tile:
            scoping_violations.append(f"{edge.raw.strip()}: crosses a tile boundary (endpoints in different tiles)")
        elif not same_tile_required and same_tile:
            scoping_violations.append(f"{edge.raw.strip()}: stays within one tile (expected a cross-tile edge)")
    ortho_fails, ortho_unknown = _orthogonality_verdicts(ctx, resolvable_edges)
    if scoping_violations or ortho_fails:
        return RuleResult(rule_id, FAIL, "; ".join(scoping_violations + ortho_fails))
    if ortho_unknown or unresolved:
        return RuleResult(
            rule_id, NEEDS_RENDER,
            f"tile scoping OK for every resolvable {style_name} edge; unresolved: " + "; ".join(unresolved + ortho_unknown),
        )
    return RuleResult(rule_id, PASS, f"all {len(edges)} {style_name} edge(s) respect tile scoping and are orthogonal")


def _check_intra_bus_stays_in_tile(ctx: TemplateCtx) -> RuleResult:
    return _check_bus_scoping(ctx, "intrabus", "intra-bus-stays-in-tile", same_tile_required=True)


def _check_noc_spine_between_tiles(ctx: TemplateCtx) -> RuleResult:
    return _check_bus_scoping(ctx, "interbus", "noc-spine-between-tiles", same_tile_required=False)


def _check_ports_on_boundaries(ctx: TemplateCtx) -> RuleResult:
    """buses attach at a tile's boundary ANCHOR (.north/.south/.east/.west),
    never the bare tile-center node -- plus the same orthogonality evidence
    used by noc-spine-between-tiles (both rules name it)."""
    tile_entity = _arch_tile_entity(ctx)
    if tile_entity is None:
        return RuleResult("ports-on-boundaries", NOT_APPLICABLE, "no tile component in this template")
    edges = [e for e in parse_edges(ctx.tex) if "interbus" in e.styles]
    if not edges:
        return RuleResult("ports-on-boundaries", NOT_APPLICABLE, "no interbus edges drawn in this template")
    tile_rx = None
    if "node_family" in tile_entity:
        stem, indices = tile_entity["node_family"]["stem"], tile_entity["node_family"]["indices"]
        tile_rx = _generated_name_regex(stem, len(indices))
    tile_names = set(_literal_nodes(tile_entity)) if tile_rx is None else set()
    unresolved = [
        f"{e.raw.strip()}: uses an inline -|/|- coordinate combinator this module doesn't model"
        for e in edges if e.unresolved
    ]
    resolvable_edges = [e for e in edges if not e.unresolved]
    interior_hits = []
    for edge in resolvable_edges:
        for tok in (edge.points[0], edge.points[-1]):
            base, anchor = strip_anchor(tok)
            is_tile = base in tile_names or (tile_rx is not None and tile_rx.match(base))
            if is_tile and anchor is None:
                interior_hits.append(f"{edge.raw.strip()}: {tok!r} attaches to the tile's bare/center node, not a boundary anchor")
    ortho_fails, ortho_unknown = _orthogonality_verdicts(ctx, resolvable_edges)
    if interior_hits or ortho_fails:
        return RuleResult("ports-on-boundaries", FAIL, "; ".join(interior_hits + ortho_fails))
    if ortho_unknown or unresolved:
        return RuleResult("ports-on-boundaries", NEEDS_RENDER, "; ".join(ortho_unknown + unresolved))
    return RuleResult("ports-on-boundaries", PASS, f"all {len(edges)} interbus edge(s) attach via boundary anchors and are orthogonal")


ARCHITECTURE_CHECKERS: dict = {
    "hierarchy-is-organizer": _check_pes_inside_tiles,
    "pes-inside-tiles": _check_pes_inside_tiles,
    "tile-fit-declared-after-members": _check_tile_fit_declared_after_members,
    "intra-bus-stays-in-tile": _check_intra_bus_stays_in_tile,
    "noc-spine-between-tiles": _check_noc_spine_between_tiles,
    "ports-on-boundaries": _check_ports_on_boundaries,
}


# --- circuit-schematic ------------------------------------------------------- #

def _check_kcl_at_column_foot(ctx: TemplateCtx) -> RuleResult:
    kcl_entities = _entities_by_component(ctx, "kcl-node")
    if not kcl_entities:
        return RuleResult("kcl-at-column-foot", NOT_APPLICABLE, "no kcl-node component in this template")
    edges = [e for e in parse_edges(ctx.tex) if "awire" in e.styles]
    if not edges:
        return RuleResult("kcl-at-column-foot", NEEDS_RENDER, "no awire edges found to confirm column-foot termination")
    defs, lv = macro_defs(ctx.tex), loop_vars(ctx.tex)
    coords = collect_at_coords(ctx.tex)
    patterns = collect_generated_patterns(ctx.tex, lv, defs)
    kcl_names = set()
    for e in kcl_entities:
        kcl_names |= set(_literal_nodes(e))
        if "node_family" in e:
            kcl_names.add(e["node_family"]["stem"])  # prefix match below
    problems = []
    for edge in edges:
        if edge.unresolved:
            continue  # uses an inline -|/|- combinator this module doesn't model
        a, b = edge.points[0], edge.points[-1]
        b_base, _ = strip_anchor(b)
        is_kcl_target = b_base in kcl_names or any(b_base.startswith(stem + "-") for stem in kcl_names)
        if not is_kcl_target:
            continue
        a_coord = coords.get(a) or resolve_generated_ref(a, patterns)
        b_coord = coords.get(b) or resolve_generated_ref(b, patterns)
        if a_coord is None or b_coord is None:
            problems.append(f"{edge.raw.strip()}: cannot resolve coordinates to confirm foot placement")
            continue
        ay, by = a_coord[1], b_coord[1]
        cmp = None
        va, vb = try_eval_numeric(ay, defs, lv), try_eval_numeric(by, defs, lv)
        if va is not None and vb is not None:
            cmp = vb < va  # TikZ y grows upward; "foot" = strictly below the cell
        if cmp is False:
            problems.append(f"{edge.raw.strip()}: kcl-node is not below its feeding cell")
        elif cmp is None:
            pass  # can't evaluate (loop-var dependent) -- topology (awire terminates at kcl) already confirmed
    if problems:
        return RuleResult("kcl-at-column-foot", FAIL, "; ".join(problems))
    skipped = sum(1 for e in edges if e.unresolved)
    if skipped:
        return RuleResult(
            "kcl-at-column-foot", NEEDS_RENDER,
            f"every resolvable awire edge into a kcl-node terminates there, below its source; "
            f"{skipped} awire edge(s) use an inline -|/|- combinator this module doesn't model",
        )
    return RuleResult("kcl-at-column-foot", PASS, "every awire edge into a kcl-node terminates there, below its source")


def _check_adc_below_kcl(ctx: TemplateCtx) -> RuleResult:
    kcl_entities = _entities_by_component(ctx, "kcl-node")
    if not kcl_entities:
        return RuleResult("adc-below-kcl", NOT_APPLICABLE, "no kcl-node component in this template")
    m = _COORD_OFFSET_RE.search(ctx.tex)
    if not m:
        return RuleResult("adc-below-kcl", NOT_APPLICABLE, "no readout-device offset coordinate found (no adc/readout branch modeled)")
    problems = []
    for m in _COORD_OFFSET_RE.finditer(ctx.tex):
        dy = m.group("dy")
        try:
            if float(dy.strip()) >= 0:
                problems.append(f"{m.group('name')}: offset from {m.group('a')} has dy={dy} (not below)")
        except ValueError:
            pass
    if problems:
        return RuleResult("adc-below-kcl", FAIL, "; ".join(problems))
    return RuleResult("adc-below-kcl", PASS, "readout-device coordinate(s) offset strictly below their kcl-node")


def _check_rows_cols(ctx: TemplateCtx, rule_id: str, style_name: str) -> RuleResult:
    edges = [e for e in parse_edges(ctx.tex) if style_name in e.styles]
    if not edges:
        return RuleResult(rule_id, NOT_APPLICABLE, f"no {style_name} edges drawn in this template")
    fails, unknown = _orthogonality_verdicts(ctx, edges)
    if fails:
        return RuleResult(rule_id, FAIL, "; ".join(fails))
    if unknown:
        return RuleResult(rule_id, NEEDS_RENDER, "; ".join(unknown))
    return RuleResult(rule_id, PASS, f"all {len(edges)} {style_name} edge(s) proven orthogonal")


def _check_analog_digital_split(ctx: TemplateCtx) -> RuleResult:
    has_digital_component = any(
        e.get("component") == "adc" or "digital" in (e.get("role") or "").lower()
        for e in ctx.intent.entities
    ) or "adc" in ctx.tex.lower() or "digital" in ctx.intent.thesis.lower()
    if not has_digital_component:
        return RuleResult(
            "analog-digital-split", NOT_APPLICABLE,
            "no digital-domain component/thesis reference in this template -- nothing to split",
        )
    has_band = "\\domainband" in ctx.tex or "\\domainboundary" in ctx.tex
    if has_band:
        return RuleResult("analog-digital-split", PASS, "domain-band + domain-boundary macros present")
    return RuleResult(
        "analog-digital-split", FAIL,
        "template's thesis/entities reference an analog/digital split but draws no "
        "\\domainband/\\domainboundary -- the split is not visually carried (WP-5 scope,"
        " reported to cp-4883)",
    )


CIRCUIT_CHECKERS: dict = {
    "kcl-at-column-foot": _check_kcl_at_column_foot,
    "adc-below-kcl": _check_adc_below_kcl,
    "rows-are-inputs": lambda ctx: _check_rows_cols(ctx, "rows-are-inputs", "vwire"),
    "cols-are-weights": lambda ctx: _check_rows_cols(ctx, "cols-are-weights", "awire"),
    "current-sums-downward": _check_kcl_at_column_foot,  # same evidence: awire runs downward into the kcl foot
    "analog-digital-split": _check_analog_digital_split,
}

FAMILY_CHECKERS = {
    "architecture": ARCHITECTURE_CHECKERS,
    "circuit-schematic": CIRCUIT_CHECKERS,
    "flow": {},  # no flow templates exist in this fork yet (WP-6 scope) -- nothing to register
}


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

def evaluate_template(tex_text: str, intent: IntentRecord, family_record: dict) -> list:
    """Evaluate every placement_grammar rule in ``family_record`` against one
    template. Returns a list of ``RuleResult``, one per rule."""
    is_generated = any("node_family" in e for e in intent.entities)
    ctx = TemplateCtx(tex=tex_text, intent=intent, is_generated=is_generated)
    checkers = FAMILY_CHECKERS.get(intent.family, {})
    results = []
    for rule in family_record.get("placement_grammar", []) or []:
        rule_id = rule["id"]
        checker = checkers.get(rule_id)
        if checker is None:
            results.append(RuleResult(
                rule_id, NEEDS_RENDER,
                "no static checker implemented for this rule -- requires visual inspection "
                "(route to WP-8's rendered-PNG self-check gate)",
            ))
            continue
        try:
            result = checker(ctx)
            # a shared checker (e.g. hierarchy-is-organizer / pes-inside-tiles
            # both resolve to the same containment evidence) hardcodes ITS
            # OWN canonical rule_id in the RuleResult it builds; always
            # relabel to the family record's rule_id being evaluated so two
            # distinct settled-decision rules never collide under one label.
            results.append(RuleResult(rule_id, result.verdict, result.detail))
        except Exception as exc:  # a checker bug must not crash validate.py's whole run
            results.append(RuleResult(rule_id, NEEDS_RENDER, f"static checker raised {exc!r} -- falling back to render"))
    return results


def placement_grammar_problems(tex_text: str, intent: IntentRecord, family_record: dict | None) -> list:
    """FAIL-only problem strings, for wiring into tools/validate.py's blocking
    exit code. NOT_APPLICABLE/NEEDS_RENDER/PASS never block CI -- see
    ``tools/adapter/cli.py grammar`` / ``tools/ci/placement-grammar-report.sh``
    for the full per-rule breakdown."""
    if family_record is None:
        return []
    problems = []
    for result in evaluate_template(tex_text, intent, family_record):
        if result.verdict == FAIL:
            problems.append(f"placement_grammar[{result.rule_id}] violated: {result.detail}")
    return problems
