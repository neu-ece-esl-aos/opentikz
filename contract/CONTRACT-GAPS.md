# Contract Gaps Ledger

Every work package (WP-1 … WP-10, ADR-0005 §D8) appends a row here when it
hits something the frozen backend contract (`backend-contract-v1.2.0.md`)
should have carried but doesn't. This is **not** a place to patch around a
gap — see `CONTRACT.md` for the change-control rule (raise to the contract
owner as a new version + re-notify; never edit the vendored contract copy or
silently couple to TikZ internals to route around a gap).

| WP | What was needed | Why the contract didn't carry it | What was done instead | Status |
|----|------------------|-----------------------------------|------------------------|--------|
| _(none yet)_ | | | | |

## Column guide

- **WP** — the work package that hit the gap (e.g. `WP-2`, `WP-7`).
- **What was needed** — the concrete thing the build required (a semantic, a
  field, a rule) that has no contract counterpart.
- **Why the contract didn't carry it** — the specific §-reference or omission
  in `backend-contract-v1.2.0.md` that left this undefined.
- **What was done instead** — the interim resolution used to keep the build
  moving (must not be a silent TikZ-internals coupling — name the workaround).
- **Status** — one of: `raised` (sent to contract owner, awaiting a new
  version), `resolved-vN.N.N` (a new contract version closed the gap; note the
  version), `open` (not yet raised).
