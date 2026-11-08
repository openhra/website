#!/usr/bin/env bash
# Build a checked public artifact in empty or exporter-owned staging.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$ROOT/scripts/export-public.py" "$@"
