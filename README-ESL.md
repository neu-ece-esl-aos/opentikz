# README-ESL — this fork's relationship to upstream

This repository (`neu-ece-esl-aos/opentikz`) is an **ESL-org fork** of
[`opentikz/opentikz`](https://github.com/opentikz/opentikz) (MIT code / CC0
content), created to build **backend #2** of the ESL figure-authoring
capability — see `decisions/ADR-0005-opentikz-tikz-backend-phase2b.md` in the
`cp-workflows` workspace repo for the full design. This file is ESL-specific;
it does not replace or edit upstream's own `README.md`, `CONTRIBUTING.md`,
`LICENSE-CODE`, `LICENSE-CONTENT`, or `CITATION.cff`, which continue to
describe the project as a general-purpose OpenTikZ library.

## Why a fork (not a plugin, not an upstream contribution)

ADR-0005 D1 decided this is an **adopt-and-extend fork**: most of the ESL
extension work (backend-adapter boundary, palette extension, a `\foreach`
scaling layer, family-level settled-decisions enforcement, a visual self-check
gate) edits opentikz's own code/model rather than only adding
templates/icons in-tree — opentikz has no plugin/extension-point API for that
kind of change. The extensions are ESL-contract-specific, not generally
applicable, so this is a fork to build against, **not** an upstream
contribution.

## Remotes

| Remote | URL | Direction |
|---|---|---|
| `origin` | `https://github.com/neu-ece-esl-aos/opentikz.git` | read/write — this fork |
| `upstream` | `https://github.com/opentikz/opentikz.git` | **pull-only** — never push |

`upstream` is kept configured so improvements to the original library (new
icons, bug fixes, tooling improvements) can be tracked and selectively merged
in:

```bash
git fetch upstream
git log upstream/main --oneline -10   # see what's new upstream
# to pull in an upstream improvement:
git merge upstream/main               # (into dev, then resolve/PR as usual)
```

Never `git push` to `upstream` — it is not ours to write to.

## Branch model

| Branch | Role |
|---|---|
| `main` | Mirrors the fork's release state. Advances only via a human-approved `dev → main` PR at release. |
| `dev` | **The ESL integration branch — the PR target for every work package (WP-1 … WP-10).** All ESL feature work lands here first. |
| `feat/<slug>` | Per-work-package feature branches, branched from `dev`, PR'd back into `dev`. |

This mirrors the `academic.wfp` convention used elsewhere in this project
(see `cp-workflows/CLAUDE.md` "Branching Policy"): a stable integration branch
that accumulates reviewed work, with `main` reserved for release cuts.

## Contract consumption

Everything under `contract/` is a **read-only, checksum-pinned vendor copy**
of the frozen Phase-1 backend contract — see `contract/CONTRACT.md` for the
source of truth, the pin, and the change-control rule. This fork consumes
that contract; it never edits it.

## CI logic convention: land gates in `tools/`, not `.github/workflows/`

**Prefer landing new CI logic in `tools/` over editing `.github/workflows/ci.yml`.**
The credential these agent sessions push with carries `repo`/`read:org` scopes
but not GitHub's `workflow` scope, which GitHub requires for *any* push that
touches a file under `.github/workflows/` — so a commit that edits the
workflow file cannot land without an operator manually running
`gh auth refresh -s workflow` (interactive, browser-based; not something an
agent can do on the operator's behalf). Since several later work packages land
CI logic (WP-3 palette-drift check, WP-8 render/PNG self-check gate, WP-9
conformance test), routing all of it through the workflow file would hit this
wall repeatedly. Two ways around it, in priority order:

1. **Fold the check into `tools/validate.py` (or a module it imports) whenever
   it can run alongside an already-existing CI invocation.** The unedited,
   upstream `ci.yml` already runs `python3 tools/validate.py --strict` on
   every PR — so a check added *inside* `validate.py` starts running in CI
   immediately, with **zero** workflow-file edits and no `workflow` scope
   needed. This is how the vendored-contract checksum gate is wired
   (`_contract_checksum_problem` in `tools/validate.py`): it's not a separate
   script, it's a few extra lines in the tool CI already calls.
2. **For genuinely new CI steps that have no existing hook to ride along
   with** (e.g. a full-template-set `render_preview.py` pass, WP-8's
   rendered-PNG gate), write them as standalone, executable scripts under
   `tools/ci/` (`validate-all.sh`, `render-all.sh`, ...), runnable both
   locally and from CI. These are ready to wire in via a thin, generic shim
   step:
   ```yaml
   - name: Run CI checks (tools/ci/*.sh)
     run: |
       set -euo pipefail
       for script in tools/ci/*.sh; do
         echo "::group::$script"
         "$script"
         echo "::endgroup::"
       done
   ```
   but until that one shim edit lands in `ci.yml` (parked, pending the
   operator's scope grant — see the branch/SHA noted in the cp-4889 PR),
   `tools/ci/*.sh` scripts are **not yet invoked by CI** — they exist for
   local runs and are ready to be picked up automatically (sorted by
   filename, no further `ci.yml` edits) the moment the shim step lands.

**Known gap until the shim lands:** the upstream `ci.yml`'s `pull_request:
paths:` filter does not include `contract/**`, so a PR that only touches
`contract/` (no `icons/`/`templates/`/`examples/`/`tools/` change) does not
trigger CI at all. The parked `ci.yml` commit also adds `contract/**` to that
filter.

WP-2's adapter checks (below) ride the existing, unedited `ci.yml` a
different way: they're folded straight into `tools/validate.py`, which
`ci.yml` was already calling before this shim discussion — so they run in CI
with zero new files and zero workflow-file edits either way.

## Backend-adapter layer (`tools/adapter/`) — ADR-0005 D2/D3, WP-2

`tools/adapter/` loads the vendored, frozen contract
(`contract/backend-contract-v1.2.0.md`) as structured data and derives each
ESL-contract template's `edit_contract` from it — the contract stays the
single source of truth; `edit_contract` is a **derived, mechanical view**,
never a second place semantic decisions live (D2). It does not govern every
template in this fork — only ones carrying the `esl-architecture` domain tag
(`templates/esl-architecture-block/`, `templates/esl-crossbar-kcl/` today).

| File | Role |
|---|---|
| `contract_loader.py` | Parses the contract into `Contract` (§1 component vocabulary, §2 style/color tokens, §3a placement primitives, §3b/§4 schema field sketches). |
| `intent.py` | The per-figure **intent layer** (net-new — opentikz has no analog): loads a template's `intent.yaml` sidecar (contract §4 shape + two adapter extensions — `entities[].component`/`nodes` and a top-level `parameters` "what varies" list) and the `.tex` master-header comment block. |
| `derive.py` | Projects `node_naming` (§1 components → concrete node names), `styles` (mechanical `.style` scan), `parameters` (copied from the intent record), and `invariants` (adapter baseline + the WP-7 family settled-decisions seam — see `settled-decisions/README.md`) into an `edit_contract`-shaped dict. `operations` is intentionally not derived (no contract-element source) and passes through unchanged. |
| `checks.py` | The three enforcement checks, wired into `tools/validate.py` for every ESL-contract template: `edit_contract` re-derivability (drift), the §1 extensibility rule (no undefined semantic component), and master-header ↔ sidecar agreement. |
| `cli.py` | `python3 tools/adapter/cli.py derive <template-dir> [--write]` / `... check <template-dir>` — regenerate or inspect a template's derived `edit_contract` directly. |

Every template governed by the adapter ships an `intent.yaml` sidecar beside
`template.tex` (see the two ESL fixtures for worked examples) — author a new
one from `intent-record-template.md` (the contract's fillable §4 form) plus
the adapter's two extensions, then run
`python3 tools/adapter/cli.py derive <dir> --write` to populate
`edit_contract`.
