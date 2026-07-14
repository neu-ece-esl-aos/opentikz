#!/usr/bin/env bash
# D6 visual-self-check gate (ADR-0005 §D6, docs/VISUAL_SELFCHECK.md): render every
# templates/*/ item to PNG and run the mechanical half of the gate (overfull boxes,
# cross-label text-bbox overlap), failing if any item fails to compile/render or
# trips a mechanical check. This is already invoked as part of `tools/validate.py
# --strict` (which .github/workflows/ci.yml already runs on every push/PR -- see
# README-ESL.md "CI logic convention"); this script exists so the same gate is also
# runnable standalone/locally without the rest of validate.py's metadata checks,
# and so a future ci.yml shim (see README-ESL.md) can pick it up directly.
#
# NOTE — mechanical does not mean sufficient: passing this script means the PNGs
# exist and no overfull box / text-label overlap was found. It does NOT mean the
# figures are correct -- an agent (or human) must still read every PNG against the
# docs/VISUAL_SELFCHECK.md checklist before calling any of them done. The known
# esl-crossbar-kcl symbol-overlap defect (see docs/VISUAL_SELFCHECK.md "Demonstrated
# catch") is invisible to this script for exactly that reason.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

out_dir="${1:-/tmp/opentikz-ci-selfcheck-pngs}"
mkdir -p "$out_dir"

status=0
for d in templates/*/; do
  d="${d%/}"
  name="$(basename "$d")"
  echo "self-checking $d"
  if ! python3 tools/render_selfcheck.py "$d" -o "$out_dir/${name}.png"; then
    status=1
  fi
done

if [ "$status" -ne 0 ]; then
  echo "::error::one or more templates failed the D6 mechanical self-check (see above)"
fi
exit "$status"
