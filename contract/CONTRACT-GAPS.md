# Contract Gaps Ledger

Every work package (WP-1 … WP-10, ADR-0005 §D8) appends a row here when it
hits something the frozen backend contract (`backend-contract-v1.2.0.md`)
should have carried but doesn't. This is **not** a place to patch around a
gap — see `CONTRACT.md` for the change-control rule (raise to the contract
owner as a new version + re-notify; never edit the vendored contract copy or
silently couple to TikZ internals to route around a gap).

| WP | What was needed | Why the contract didn't carry it | What was done instead | Status |
|----|------------------|-----------------------------------|------------------------|--------|
| WP-2 | A §1b component name for `esl-architecture-block`'s shared `io` node — the hub a two-tile figure's inter-tile NoC bus edges both attach to, distinct from a `tile`, `pe`, `cpu-core`/`acc-core`, or the bus edge itself. | §1b (Architecture / flow family) names cores, tiles, PEs, mem-block, and the bus edge types (`intra-bus`/`inter-bus`), but no node type for a bare inter-tile junction/hub a bus routes *through* rather than *between named endpoints*. | Modeled `io` as an intent-record entity with a `role` but **no** `component:` field, so the adapter's node_naming derivation and §1-extensibility check simply skip it (not invented as a fake vocabulary id) — see `templates/esl-architecture-block/intent.yaml`. | raised |
| WP-2 | A §1a component name for `esl-crossbar-kcl`'s per-column readout-device branch (a real circuitikz bipole — sense resistor / reference current source — reading a KCL node's summed current). | §1a names conceptual circuit components (`crossbar-cell`, `kcl-node`, `adc`, wire/label types) but no entry for a raw EE device primitive (resistor, current source); it is unclear whether the contract intends these as backend-private (§5, "coordinates ... a backend may implement any way it likes") or as a missing §1 vocabulary gap. | Modeled the readout branch as an intent-record entity with a `role` explaining the ambiguity but **no** `component:` field (same skip-don't-invent treatment as the `io` row above) — see `templates/esl-crossbar-kcl/intent.yaml`. | raised |

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
