# Parked CI commit — needs `workflow` OAuth scope to land

`0001-ci-shim-circuitikz.patch` is a real, verified commit (`d4f099c`, cp-4889) that
**cannot be pushed** by the agent credential: it modifies `.github/workflows/ci.yml`,
and GitHub rejects any push touching a workflow file unless the token carries the
`workflow` OAuth scope. Ours has `read:org, repo` only.

It is parked here as a patch so it survives worktree cleanup and stays reviewable.

## What it does

1. Reduces `.github/workflows/ci.yml` to a thin shim that loops over `tools/ci/*.sh`,
   so future checks are added by dropping a script into `tools/ci/` — never by
   editing a workflow file we cannot push. (See `README-ESL.md`.)
2. Adds `circuitikz` + `amsmath` to CI's TeX Live package list. **Without this the
   circuit-schematic family cannot compile in CI** (ADR-0005 D4, WP-5).
3. Scopes the triggers to `dev`/`main` and adds `contract/**` to the `paths:` filter
   (an unfixed gap: a contract-only PR currently skips CI entirely).

## How to land it

```sh
gh auth refresh -s workflow          # operator, interactive — one time
git am tools/ci/pending/0001-ci-shim-circuitikz.patch
git push origin HEAD:dev
git rm -r tools/ci/pending && git commit -m "chore(ci): land parked shim; unpark"
```

## Note: this patch alone does not turn CI on

GitHub Actions is **disabled at the repo level** on this fork — the default for new
forks (`actions/workflows` reports `total_count: 0`; zero runs have ever executed).
Enabling it needs **repo admin**, which the agent credential does not have
(`permissions.admin: false`; `actions/permissions` returns 403).

So there are two independent gates, and **both** are operator-only:

| Gate | Fix | Without it |
|---|---|---|
| Actions disabled on the fork | admin: Settings → Actions → enable | nothing runs, ever |
| No `workflow` OAuth scope | `gh auth refresh -s workflow` | this patch cannot land |

Enabling Actions is the dominant one: until it is on, landing this patch changes nothing.
