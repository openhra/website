#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
# CI caches node_modules by the package lock. Keep the marker inside the cached
# directory so a restored tree can skip npm's clean install entirely.
LOCK_KEY=$(shasum -a 256 package-lock.json requirements-dev.txt | shasum -a 256 | cut -d ' ' -f 1)
if [ ! -f node_modules/.website-tools-lock ] || [ "$(cat node_modules/.website-tools-lock)" != "$LOCK_KEY" ]; then
  if ! npm ci --ignore-scripts --include=dev --no-audit --no-fund --offline; then
    # Environment overrides beat npmrc settings; clear both inherited spellings.
    npm_config_offline=false NPM_CONFIG_OFFLINE=false \
      npm_config_prefer_offline=false NPM_CONFIG_PREFER_OFFLINE=false \
      npm ci --ignore-scripts --include=dev --no-audit --no-fund
  fi
  printf '%s\n' "$LOCK_KEY" > node_modules/.website-tools-lock
fi
if [ ! -x .venv/bin/python3 ]; then python3 -m venv .venv; fi
PATH="$ROOT/.venv/bin:$PATH"
export PATH
# Keep the hashed Ruff wheel in a repository-local CI cache. This also works
# when the venv must be rebuilt after a Python patch-version change.
WHEELS="$ROOT/.cache/ruff-wheels"
mkdir -p "$WHEELS"
install_ruff() {
  .venv/bin/python3 -m pip install --disable-pip-version-check --no-index \
    --find-links "$WHEELS" --only-binary=:all: --require-hashes -r requirements-dev.txt
}
if ! .venv/bin/python3 -m ruff --version 2>/dev/null | grep -q '0\.17\.4'; then
  if ! install_ruff; then
    # Override inherited no-index settings for cold or cross-platform caches.
    PIP_NO_INDEX=0 python3 -m pip install --disable-pip-version-check \
      --only-binary=:all: --require-hashes -r requirements-dev.txt
    PIP_NO_INDEX=0 python3 -m pip download --disable-pip-version-check \
      --dest "$WHEELS" --only-binary=:all: --require-hashes -r requirements-dev.txt
  fi
fi
node_modules/.bin/prettier --version
node_modules/.bin/eslint --version
ruff --version
