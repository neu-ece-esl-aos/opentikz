#!/usr/bin/env bash
# Human-facing WP-9 contract-conformance report (ADR-0005 D3, the feature's
# exit gate): every §1a/§1b/§2/§3a/§3b/§4 contract element, walked from the
# vendored contract document itself, with a PASS/FAIL per finding-category.
#
# tools/validate.py --strict already BLOCKS on any conformance finding
# (folded in as the "contract-conformance (WP-9)" item); this script is not
# a separate gate -- it is the same check run standalone, with the full
# per-check breakdown, for local iteration and CI log readability.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

python3 tools/adapter/conformance.py
