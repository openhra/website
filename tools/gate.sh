#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
FULL=0
if [ "${1-}" = "--full" ]; then FULL=1; elif [ "$#" -ne 0 ]; then
  printf 'FAIL: unknown argument: %s\n' "$1" >&2
  exit 1
fi

if ! python3 - "$ROOT" <<'PY'
import html.parser
import os
import re
import subprocess
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
            self.title = True
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

html_files = sorted(p for site in sites for p in site.rglob("*.html"))
for page in html_files:
    try:
        source = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(source)
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

denylist = os.environ.get("OPENPLANS_DENYLIST_FILE")
if not denylist:
    print("denylist: SKIP")
else:
    try:
        terms = [line.strip() for line in Path(denylist).read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
    except OSError as exc:
        fail(f"cannot read denylist: {exc}")
    if terms:
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True,
                                 stdout=subprocess.PIPE).stdout.split(b"\0")
        for raw in tracked:
            if not raw:
                continue
            path = root / os.fsdecode(raw)
            try:
                data = path.read_bytes().decode("utf-8", errors="replace").casefold()
            except OSError:
                continue
            for term in terms:
                if term.casefold() in data:
                    fail(f"denylist term found in {os.fsdecode(raw)}: {term}")
    print("denylist: PASS")

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

if [ "$FULL" -eq 1 ]; then
  "$ROOT/tools/gate-selftest.sh"
fi
printf 'PASS\n'
