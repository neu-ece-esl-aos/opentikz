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

## CI logic convention: `tools/ci/`, never `.github/workflows/`

**Do not add CI logic to `.github/workflows/ci.yml`.** The credential these
agent sessions push with carries `repo`/`read:org` scopes but not GitHub's
`workflow` scope, which GitHub requires for *any* push that touches a file
under `.github/workflows/` — so a commit that edits the workflow file cannot
land without an operator manually running `gh auth refresh -s workflow`
(interactive, browser-based; not something an agent can do on the operator's
behalf). Since several later work packages land CI logic (WP-3 palette-drift
check, WP-8 render/PNG self-check gate, WP-9 conformance test), routing all of
it through the workflow file would hit this wall repeatedly.

Instead, `ci.yml` is a **thin, generic shim** with one step:

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

Every check is a standalone, executable script under `tools/ci/`
(`validate-all.sh`, `check-contract-checksum.sh`, `render-all.sh`, ...),
runnable both in CI and locally (`./tools/ci/validate-all.sh`). **A later work
package that needs a new CI gate adds a new `tools/ci/*.sh` script and nothing
else** — the shim picks it up automatically, sorted by filename, with no edit
to `ci.yml` and therefore no `workflow` scope required. Only touch `ci.yml`
itself for things that are inescapably workflow-level (a new system
dependency for the TeX Live install, a trigger/branch change) — and expect
that one commit to need the operator's scope grant to land.
