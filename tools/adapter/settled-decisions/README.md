# Family settled-decisions records — WP-7 seam

This directory is the seam `tools/adapter/derive.py`'s `load_settled_decisions()`
reads from: `tools/adapter/settled-decisions/<family>.yaml`, one file per
contract family (`flow` | `architecture` | `circuit-schematic`), in the
`settled-decisions-template.md` schema (contract §3/§3a/§3b).

**No family record lands here in WP-2.** Per ADR-0005 D3's §3 row, the
family-level settled-decisions record is WP-7's deliverable, not WP-2's —
WP-2 only builds the seam (the loader + the projection into each template's
derived `edit_contract.invariants`). Until a `<family>.yaml` exists here,
`derive_invariants()` falls back to the adapter baseline (the §1
extensibility rule + the §2 token-binding rule) plus an explicit note that
no family record has landed yet — see the `edit_contract.invariants` on
`esl-architecture-block` / `esl-crossbar-kcl` for what that looks like today.

**Starting material for WP-7.** `settled-decisions-template.md` (in
`academic.wfp`, read-only spec) already carries a worked-example instance for
each family (circuit-schematic, architecture, flow), survey-grounded per
cp-4870. WP-7 should also fold in the template-specific invariants the two
cp-4856 fixtures shipped with *before* WP-2's adapter regenerated their
`edit_contract` mechanically (see git history at
`ffcf370 feat(templates): port esl-architecture-block + esl-crossbar-kcl
fixtures (cp-4889)` for the original hand-authored invariants) — several are
genuine family-wide rules that were only scoped to one template because
there was nowhere else to put them, e.g.:

- **architecture**: the inter-tile bus is always dashed, the intra-tile bus
  always solid; a tile's boundary `fit` node is declared after all nodes it
  fits, inside an `on background layer` scope, so it renders behind them.
- **circuit-schematic**: `awire`/`vwire` colors are reserved for the
  analog-current / voltage-source domains respectively and never swapped;
  every KCL node needs a labeled incoming-current annotation clear of
  neighboring columns (the cp-4856 PoC's one real render-catchable bug).

Once `<family>.yaml` lands here, `derive_invariants()` automatically projects
its `placement_grammar[].rule`, `style_decisions[].decision`, and
`semantic_decisions[].decision` entries into every template's derived
`edit_contract.invariants` for that family — no other adapter code changes.
