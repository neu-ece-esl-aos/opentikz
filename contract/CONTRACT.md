# Vendored Backend Contract — read-only

**File:** `backend-contract-v1.2.0.md`
**Source of truth:** `neu-ece-esl-aos/academic.wfp` (`dev` branch),
`esl-writing-workflows/_skills/figure-authoring/assets/backend-contract.md` —
the Phase-1 `academic/figure-author` skill package. That file, not this copy,
is where the contract is authored and versioned.

**Version pinned:** `1.2.0` (frozen, ADR-0004 R3.1 / ADR-0005 §D3).

**sha256 (of `backend-contract-v1.2.0.md` in this directory):**

```
e19bf8dbfabafd9d8753f154f2e4339bd497e0d6f6e2a433153c5873e5f80f03
```

## Consumption rule: read-only

This backend (`neu-ece-esl-aos/opentikz`, ADR-0005 Phase 2b) **consumes** the
contract. It is **never edited here**. The vendored copy exists so the
opentikz backend-adapter code and templates can be built and CI-checked
against a pinned, offline copy without a runtime dependency on the
`academic.wfp` repo.

CI (`.github/workflows/ci.yml`, job `contract-checksum`) fails the build if
`backend-contract-v1.2.0.md`'s sha256 drifts from the pin above — that is the
signal that either (a) this copy was edited in place (not allowed — revert and
re-vendor from the source of truth instead), or (b) the source contract
changed upstream and this vendored copy is stale and needs re-syncing to a new
pinned version.

## Change control

The contract's own change-control rule applies here unchanged (contract
"Change control" section): Phase 2b does not edit the contract unilaterally.

If a build step in this repo needs something the contract does not carry —
a semantic the adapter, a template, or `validate.py` had to infer without a
named contract counterpart — that is a **contract gap**, not a license to
patch this file:

1. Record it in [`CONTRACT-GAPS.md`](CONTRACT-GAPS.md) (what was needed, why
   the contract didn't carry it, what was done instead, status).
2. Raise it to the contract owner (`clp msg cp-4883`, the Phase-2b feature
   coordinator, who routes it to the Phase-1 contract owner) as a proposed new
   contract version + re-notify — the contract's own change-control process,
   never a silent edit here.
3. Once a new version is accepted upstream, re-vendor it as
   `backend-contract-v<new-version>.md`, update the pin in this file, and
   update `CONTRACT-GAPS.md`'s status column.

Never silently couple a build step to TikZ internals
(`figstyle.tex`/`tikzsemantics.tex`) to route around a contract gap — that
defeats the point of the renderer-independent seam (ADR-0005 D3 conformance
obligation). Record the gap instead.
