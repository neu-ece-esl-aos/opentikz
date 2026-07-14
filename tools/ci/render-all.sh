#!/usr/bin/env bash
# Render every templates/*/ item with render_preview.py (not just changed items), so a
# fixture that compiles but fails to render to a preview is still caught on every PR
# (ADR-0005 D6 visual-self-check tooling). See README-ESL.md "CI logic convention".
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

out_dir="${1:-/tmp/opentikz-ci-previews}"
mkdir -p "$out_dir"

for d in templates/*/; do
  d="${d%/}"
  echo "rendering $d"
  python3 tools/render_preview.py "$d" -o "$out_dir/$(basename "$d").svg"
done
