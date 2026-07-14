#!/usr/bin/env bash
# Human-facing placement-grammar verdict breakdown (WP-7, ADR-0005 D3 §3b row)
# for every adapter-governed (esl-architecture domain-tagged) template.
#
# tools/validate.py --strict already BLOCKS on any FAIL verdict (folded into
# adapter_problems -> placement_grammar_problems); this script is not a gate
# -- it is the full PASS/FAIL/NOT_APPLICABLE/NEEDS_RENDER report so a human
# (or WP-8) can see exactly what was proven, what doesn't apply, and what
# static analysis explicitly declines to guess at and routes to the
# rendered-PNG self-check gate instead. Never silently drops a rule: every
# placement_grammar entry in every family record produces one verdict line
# per template.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

status=0
for meta in templates/*/template.meta.json; do
  dir=$(dirname "$meta")
  if ! grep -q '"esl-architecture"' "$meta"; then
    continue
  fi
  echo "::group::$dir"
  python3 tools/adapter/cli.py grammar "$dir" || status=1
  echo "::endgroup::"
done
exit "$status"
