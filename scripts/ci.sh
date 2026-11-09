#!/bin/sh
# Public checks use a disposable synthetic policy, never publication policy.
set -eu
export PYTHONDONTWRITEBYTECODE=1
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/website-ci.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
export OPENPLANS_DENYLIST_FILE="$TMP/synthetic-policy"
printf '%s%s\n' 'SyntheticCI' 'BlockedTerm42' > "$OPENPLANS_DENYLIST_FILE"
cd "$ROOT"
scripts/install-tools.sh
PATH="$ROOT/.venv/bin:$PATH"
export PATH
python3 scripts/check-ci.py --selftest
python3 --version
node --version
git --version
printf 'website CI: synthetic policy; publication approval requires private validation\n'
tools/gate.sh --full
python3 scripts/test-export.py --public
printf 'website CI: PASS (public checks only)\n'
