#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/openhra-gate.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

python3 - "$ROOT" "$TMP/repo" <<'PY'
import shutil
import subprocess
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", ".claude", ".lanes"))
subprocess.run(["git", "-C", str(target), "init", "--quiet"], check=True)
subprocess.run(["git", "-C", str(target), "add", "--all"], check=True)
PY

check_fail() {
  if "$TMP/repo/tools/gate.sh" "$@" >"$TMP/output" 2>&1; then
    cat "$TMP/output"
    printf 'FAIL: self-test expected the gate to reject %s\n' "$1" >&2
    exit 1
  fi
  if ! grep -q '^FAIL:' "$TMP/output"; then
    cat "$TMP/output"
    printf 'FAIL: self-test failure did not include a reason\n' >&2
    exit 1
  fi
}

check_pass() {
  if ! "$TMP/repo/tools/gate.sh" "$@" >"$TMP/output" 2>&1; then
    cat "$TMP/output"
    printf 'FAIL: self-test clean copy was rejected\n' >&2
    exit 1
  fi
  grep -q '^PASS$' "$TMP/output" || { cat "$TMP/output"; exit 1; }
}

check_pass
page="$TMP/repo/openhra/index.html"
cp "$page" "$TMP/original.html"
printf '\n<broken' >> "$page"
check_fail html
cp "$TMP/original.html" "$page"
sed 's#<title>[^<]*</title>##' "$page" > "$TMP/page" && mv "$TMP/page" "$page"
check_fail title
cp "$TMP/original.html" "$page"
sed 's#href="/style.css"#href="/missing-file.css"#' "$page" > "$TMP/page" && mv "$TMP/page" "$page"
check_fail link
cp "$TMP/original.html" "$page"
printf '\ncontact test@example.invalid\n' >> "$page"
check_fail email
cp "$TMP/original.html" "$page"
printf 'openhra\n# ignored-comment\n' > "$TMP/denylist"
if OPENPLANS_DENYLIST_FILE="$TMP/denylist" "$TMP/repo/tools/gate.sh" >"$TMP/output" 2>&1; then
  cat "$TMP/output"
  printf 'FAIL: self-test expected the denylist to reject\n' >&2
  exit 1
fi
grep -q '^FAIL:' "$TMP/output" || { cat "$TMP/output"; exit 1; }
sed 's/--bg: #ffffff/--bg: #101010/' "$TMP/repo/plans/brand/tokens.css" > "$TMP/tokens"
cp "$TMP/tokens" "$TMP/repo/plans/brand/tokens.css"
check_fail background
printf 'selftest: PASS (clean copy and 6 negative controls)\n'
