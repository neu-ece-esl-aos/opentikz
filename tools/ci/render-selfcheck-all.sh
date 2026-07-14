#!/usr/bin/env bash
# D6 visual-self-check gate (ADR-0005 §D6, docs/VISUAL_SELFCHECK.md): render every
# templates/*/ item to PNG and run the mechanical half of the gate (overfull boxes,
# cross-label text-bbox overlap), failing if any item fails to compile/render or
# trips a mechanical check. This logic is already invoked as part of `tools/validate.py
# --strict`, which .github/workflows/ci.yml is *configured* to run on every push/PR
# (see README-ESL.md "CI logic convention") -- but GitHub Actions is currently
# DISABLED at the repo level on this fork (repo-admin-only to enable; escalated,
# tracked in tools/ci/pending/README.md), so nothing in .github/workflows/ actually
# executes today. Until an operator enables it, THIS script (or `validate.py
# --strict` directly) is how the gate actually runs -- standalone/locally, or as
# part of the authoring loop (skills/using-opentikz/SKILL.md). The moment Actions
# is enabled, the exact same commands start running there automatically, because
# that's already what ci.yml invokes -- no rewrite needed.
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
