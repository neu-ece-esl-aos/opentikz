#!/usr/bin/env bash
# Fails if the vendored contract/backend-contract-v1.2.0.md drifts from the sha256
# pinned in contract/CONTRACT.md -- either it was edited in place (not allowed; the
# contract is consumed read-only, re-vendor from the source of truth instead) or the
# upstream contract changed and this copy is stale (see contract/CONTRACT.md for the
# change-control rule). See README-ESL.md "CI logic convention".
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

pin=$(grep -A1 '^```$' contract/CONTRACT.md | grep -E '^[0-9a-f]{64}$' | head -1)
if [ -z "$pin" ]; then
  echo "::error file=contract/CONTRACT.md::could not find a pinned sha256 in contract/CONTRACT.md"
  exit 1
fi

actual=$(sha256sum contract/backend-contract-v1.2.0.md | cut -d' ' -f1)
if [ "$pin" != "$actual" ]; then
  echo "::error file=contract/backend-contract-v1.2.0.md::checksum drift: pinned=$pin actual=$actual"
  echo "The vendored contract copy no longer matches its pin. If you edited it, revert and"
  echo "re-vendor read-only from academic.wfp's figure-authoring/assets/backend-contract.md"
  echo "instead (never edit the vendored copy). If the source contract changed upstream,"
  echo "re-vendor the new version, update the pin in contract/CONTRACT.md, and record the bump."
  exit 1
fi

echo "contract checksum OK: $actual"
