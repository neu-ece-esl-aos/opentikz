#!/usr/bin/env bash
# Schema + structural rules + standalone compile, across every icon/template/example.
# Invoked by .github/workflows/ci.yml, which stays a thin shim — this is where later
# work packages add/extend validation logic without touching .github/ (see
# README-ESL.md "CI logic convention").
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

python3 tools/validate.py --strict
