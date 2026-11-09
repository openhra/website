#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
npm ci --ignore-scripts --no-audit --no-fund
if [ ! -x .venv/bin/python3 ]; then python3 -m venv .venv; fi
.venv/bin/python3 -m pip install --disable-pip-version-check --require-hashes -r requirements-dev.txt
