#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
FULL=0
BROWSER=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    # Opt-in: real-browser checks in a disposable headless Chrome.
    --browser) BROWSER=1 ;;
    *)
      printf 'FAIL: unknown argument: %s\n' "$arg" >&2
      exit 1
      ;;
  esac
done

if [ "$FULL" -eq 1 ]; then
  if [ -z "${OPENPLANS_DENYLIST_FILE:-}" ]; then
    printf 'FAIL: OPENPLANS_DENYLIST_FILE is required for --full\n' >&2
    exit 1
  fi
  if [ ! -r "$OPENPLANS_DENYLIST_FILE" ]; then
    printf 'FAIL: cannot read publication denylist\n' >&2
    exit 1
  fi
  # Resolve relative paths before running from any caller working directory.
  OPENPLANS_DENYLIST_FILE=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$OPENPLANS_DENYLIST_FILE")
  export OPENPLANS_DENYLIST_FILE
fi

if [ -x "$ROOT/.venv/bin/python3" ]; then
  PATH="$ROOT/.venv/bin:$PATH"
  export PATH
fi

if ! python3 - "$ROOT" <<'PY'
import html.parser
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(sys.argv[1]).resolve()
sites = (root / "openhra", root / "plans")
email_re = re.compile(rb"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

class PageParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = False
        self.in_title = False
        self.refs = []
        self.bad_tag = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
        for key, value in attrs:
            if key.lower() in ("href", "src") and value:
                self.refs.append(value)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() == "title":
            self.in_title = False

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and data.strip():
            self.title = True
        if re.search(r"<(?:[A-Za-z][A-Za-z0-9:-]*|/[^>\s]*)\s*$", data):
            self.bad_tag = True

def fail(reason):
    print(f"FAIL: {reason}")
    sys.exit(1)

required_pages = ("plans/index.html", "plans/availability.html", "plans/coverage-table.html", "plans/ask.html")
for name in required_pages:
    if not (root / name).is_file():
        fail("missing required page: " + name)

html_files = sorted(p for site in sites for p in site.rglob("*.html"))
for page in html_files:
    try:
        source = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(source)
        # HTMLParser buffers an unfinished final tag, then emits it in pieces at
        # close(); checking handle_data alone misses a planted trailing <broken.
        if re.search(r"<(?:[A-Za-z][A-Za-z0-9:-]*|/[^>\s]*)\s*$", source):
            parser.bad_tag = True
        parser.close()
    except (OSError, UnicodeError, html.parser.HTMLParseError) as exc:
        fail(f"HTML parse error in {page.relative_to(root)}: {exc}")
    if parser.bad_tag:
        fail(f"malformed tag in {page.relative_to(root)}")
    if not parser.title:
        fail(f"missing <title> in {page.relative_to(root)}")
    site_root = next(site for site in sites if page.is_relative_to(site))
    for ref in parser.refs:
        parts = urlsplit(ref)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        path = unquote(parts.path)
        target = (site_root / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
        if target.is_dir():
            target = target / "index.html"
        if path == "/availability" and site_root.name == "plans":
            target = site_root / "availability.html"
        if not target.is_file():
            fail(f"dead relative link in {page.relative_to(root)}: {ref}")

print(f"html: PASS ({len(html_files)} pages)")

for site in sites:
    for file in sorted(p for p in site.rglob("*") if p.is_file()):
        try:
            content = file.read_bytes()
        except OSError as exc:
            fail(f"cannot read {file.relative_to(root)}: {exc}")
        if email_re.search(content):
            fail(f"email address found in {file.relative_to(root)}")
print("email: PASS")

api_files = [root / "openhra/api/contact.js", root / "plans/api/contact.js"]
for api in api_files:
    try:
        source = api.read_text(encoding="utf-8")
    except OSError:
        fail(f"missing contact handler: {api.relative_to(root)}")
    if "process.env.CONTACT_EMAIL" not in source:
        fail(f"contact handler must read process.env.CONTACT_EMAIL: {api.relative_to(root)}")
print("contact env: PASS")

tokens = root / "plans/brand/tokens.css"
try:
    css = tokens.read_text(encoding="utf-8")
except OSError:
    fail("missing plans/brand/tokens.css")
if not re.search(r"--bg\s*:\s*#ffffff\s*;", css, re.I):
    fail("plans/brand/tokens.css must keep --bg: #ffffff")
print("background: PASS")
PY
then
  exit 1
fi

python3 "$ROOT/tools/check-private-paths.py" "$ROOT"
python3 "$ROOT/tools/check-neutral.py" "$ROOT"
# The tool list is plans/data/mcp-tools.json, copied from OpenPlans docs/mcp-tools.json at the
# release commit by scripts/pin-mcp-tools.py; check-mcp.py fails if it no longer matches
# tools/mcp-tools-pin.json. Where an OpenPlans checkout sits beside the website, a newer
# development manifest there prints a note and does not fail.
OPENPLANS_TOOLS="$ROOT/../openplans/docs/mcp-tools.json"
if [ -f "$OPENPLANS_TOOLS" ]; then
  python3 "$ROOT/tools/check-mcp.py" "$ROOT" --source "$OPENPLANS_TOOLS"
else
  python3 "$ROOT/tools/check-mcp.py" "$ROOT"
fi
python3 "$ROOT/tools/hosted-preview/check.py"
python3 "$ROOT/tools/a11y-check/check.py"

BACKGROUND=""
if [ "$FULL" -eq 1 ]; then
  (
    cd "$ROOT"
    if ! "$ROOT/scripts/install-tools.sh"; then
      printf 'FAIL: website lint/format tools unavailable; scripts/install-tools.sh could not provide the pinned tools\n' >&2
      exit 1
    fi
    PATH="$ROOT/.venv/bin:$PATH"
    export PATH
    npm run format:check
    npm run lint
  )
  # The two longest self-tests each run the gate on scratch copies of the site. They read the
  # checkout and write only to their own temporary folders, so they run beside the steps below.
  # The gate prints their output after those steps, and a failure in either fails the gate.
  BACKGROUND=$(mktemp -d "${TMPDIR:-/tmp}/website-gate.XXXXXX")
  trap 'rm -rf "$BACKGROUND"' EXIT
  trap 'exit 1' HUP INT TERM
  (cd "$ROOT" && PATH="$ROOT/.venv/bin:$PATH" node scripts/lint-selftest.mjs) >"$BACKGROUND/lint-selftest.log" 2>&1 &
  LINT_SELFTEST=$!
  "$ROOT/tools/gate-selftest.sh" >"$BACKGROUND/gate-selftest.log" 2>&1 &
  GATE_SELFTEST=$!
fi

set +e
(
  set -e
  python3 -m unittest discover -s "$ROOT/tests" -p 'test_launchcopy.py'
  node --test "$ROOT/tests/alerts.test.mjs"
  python3 -m unittest discover -s "$ROOT/tests" -p 'test_alert_sender.py'
  python3 -m unittest discover -s "$ROOT/tests" -p 'test_pin_mcp_tools.py'
  python3 -m unittest discover -s "$ROOT/tests" -p 'test_ask_page.py'
  # These tests mostly wait on loopback servers; the runner splits them across a few processes and
  # fails unless they run exactly the tests one discover loads.
  python3 "$ROOT/scripts/unittest_shards.py" "$ROOT/tests" 'edge_acceptance*.py'

  python3 "$ROOT/tools/coverage-scan/check.py" "$ROOT/plans/data/coverage"
  if git -C "$ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
    python3 "$ROOT/tools/coverage-gate/check.py" --previous-ref HEAD
  else
    # Isolated self-test copies are deliberately unborn repositories.
    python3 "$ROOT/tools/coverage-gate/check.py"
  fi

  if [ "$FULL" -eq 1 ]; then
    python3 "$ROOT/tools/check-mcp.py" "$ROOT" --selftest
    python3 "$ROOT/tools/hosted-preview/check.py" --selftest
    python3 "$ROOT/tools/a11y-check/check.py" --selftest
    python3 "$ROOT/tools/coverage-gate/selftest.py"
    python3 -m unittest discover -s "$ROOT/tools/coverage-scan/tests"
    python3 "$ROOT/tools/coverage-ui-check/check.py" --selftest
  fi
)
STATUS=$?
if [ -n "$BACKGROUND" ]; then
  # Wait for both even when a step above failed, so no self-test outlives the gate.
  wait "$LINT_SELFTEST"
  LINT_STATUS=$?
  wait "$GATE_SELFTEST"
  SELFTEST_STATUS=$?
  cat "$BACKGROUND/lint-selftest.log"
  cat "$BACKGROUND/gate-selftest.log"
  if [ "$LINT_STATUS" -ne 0 ]; then
    printf 'FAIL: scripts/lint-selftest.mjs exited %s\n' "$LINT_STATUS" >&2
    STATUS=1
  fi
  if [ "$SELFTEST_STATUS" -ne 0 ]; then
    printf 'FAIL: tools/gate-selftest.sh exited %s\n' "$SELFTEST_STATUS" >&2
    STATUS=1
  fi
fi
[ "$STATUS" -eq 0 ] || exit "$STATUS"
set -e
if [ "$BROWSER" -eq 1 ]; then
  "$ROOT/tools/coverage-ui-check/browser-gate.sh"
fi
printf 'PASS\n'
