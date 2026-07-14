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
