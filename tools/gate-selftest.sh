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
  if "$TMP/repo/tools/gate.sh" >"$TMP/output" 2>&1; then
    cat "$TMP/output"
    printf 'FAIL: self-test expected the gate to reject %s\n' "$1" >&2
    exit 1
  fi
  if ! grep -Fq "$2" "$TMP/output"; then
    cat "$TMP/output"
    printf 'FAIL: self-test failure did not include a reason\n' >&2
    exit 1
  fi
  printf 'selftest negative: PASS (%s)\n' "$1"
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
printf 'selftest: clean copy PASS\n'
printf 'fixture %s\n' '/'"Users"'/fixture' > "$TMP/repo/private-path-fixture"
check_fail private-path 'FAIL: private absolute path found in private-path-fixture'
rm "$TMP/repo/private-path-fixture"
page="$TMP/repo/openhra/index.html"
cp "$page" "$TMP/original.html"
printf '\n<broken' >> "$page"
check_fail html 'FAIL: malformed tag in openhra/index.html'
cp "$TMP/original.html" "$page"
sed 's#<title>[^<]*</title>##' "$page" > "$TMP/page" && mv "$TMP/page" "$page"
check_fail title 'FAIL: missing <title> in openhra/index.html'
cp "$TMP/original.html" "$page"
sed 's#href="/style.css"#href="/missing-file.css"#' "$page" > "$TMP/page" && mv "$TMP/page" "$page"
check_fail link 'FAIL: dead relative link in openhra/index.html: /missing-file.css'
cp "$TMP/original.html" "$page"
printf '\ncontact test%s%s\n' '@' 'example.invalid' >> "$page"
check_fail email 'FAIL: email address found in openhra/index.html'
cp "$TMP/original.html" "$page"
printf 'openhra\n# ignored-comment\n' > "$TMP/denylist"
if OPENPLANS_DENYLIST_FILE="$TMP/denylist" "$TMP/repo/tools/gate.sh" >"$TMP/output" 2>&1; then
  cat "$TMP/output"
  printf 'FAIL: self-test expected the denylist to reject\n' >&2
  exit 1
fi
grep -Fq 'FAIL: denylist term found in ' "$TMP/output" || { cat "$TMP/output"; exit 1; }
printf 'selftest negative: PASS (denylist)\n'
cp "$TMP/repo/plans/brand/tokens.css" "$TMP/original.css"
sed 's/--bg: #ffffff/--bg: #101010/' "$TMP/repo/plans/brand/tokens.css" > "$TMP/tokens"
cp "$TMP/tokens" "$TMP/repo/plans/brand/tokens.css"
check_fail background 'FAIL: plans/brand/tokens.css must keep --bg: #ffffff'
cp "$TMP/original.css" "$TMP/repo/plans/brand/tokens.css"
check_pass
printf 'selftest: PASS (clean and restored copies; 7 diagnostic-checked negative controls)\n'
