#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
# A warm cache must work without contacting the registry, including audit calls.
if ! npm ci --ignore-scripts --include=dev --no-audit --no-fund --offline; then
  npm ci --ignore-scripts --include=dev --no-audit --no-fund --prefer-offline --fetch-retries=0
fi
if [ ! -x .venv/bin/python3 ]; then python3 -m venv .venv; fi
# pip's HTTP cache is not a wheel index. Keep reusable wheels outside the tree
# so subsequent disposable environments can install with indexes disabled.
WHEELS="$(.venv/bin/python3 -m pip cache dir)/website-devtools"
mkdir -p "$WHEELS"
install_ruff() {
  .venv/bin/python3 -m pip install --disable-pip-version-check --no-index \
    --find-links "$WHEELS" --only-binary=:all: --require-hashes -r requirements-dev.txt
}
if ! install_ruff; then
  .venv/bin/python3 -m pip download --disable-pip-version-check --retries 0 \
    --dest "$WHEELS" --only-binary=:all: --require-hashes -r requirements-dev.txt
  install_ruff
fi
