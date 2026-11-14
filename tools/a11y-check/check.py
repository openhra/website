#!/usr/bin/env python3
"""Check every public page for accessibility basics.

The rules cover page language, zoom, headings, image and SVG names, link and
button names, decorative arrows in links, form labels, tab order, skip links,
ID references, keyboard access to code blocks, and the shared focus and
reduced-motion styles. The check reads
committed sources only, so links inside a closed <details> are checked too. Browser checks live in tools/coverage-ui-check.
--selftest breaks one rule at a time in a copy and expects each to fail.
"""

import argparse
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITES = ("openhra", "plans")
SHARED_CSS = ("plans/brand/site.css", "openhra/brand/site.css")
ARROWS = "↗↘↓→←↑"
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children = []

    def hidden(self):
        node = self
        while node is not None:
            if node.attrs.get("aria-hidden") == "true":
                return True
            node = node.parent
        return False

    def inside(self, *tags):
        node = self.parent
        while node is not None:
            if node.tag in tags:
                return True
            node = node.parent
        return False

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def text(self, spoken=False):
        parts = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif spoken and child.attrs.get("aria-hidden") == "true":
                continue
            elif spoken and child.tag == "img":
                parts.append(child.attrs.get("alt") or "")
            elif spoken and child.tag == "svg":
                parts.append(child.attrs.get("aria-label") or "")
            else:
                parts.append(child.text(spoken))
        return " ".join(" ".join(parts).split())


class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None)
        self.current = self.root
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(
            Node(tag, {k: (v or "") for k, v in attrs}, self.current)
        )

    def handle_endtag(self, tag):
        node = self.current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def page_problems(source):
    """Return accessibility problems found in one HTML page."""
    problems = []
    nodes = list(Tree(source).root.walk())
    ids = [n.attrs["id"] for n in nodes if n.attrs.get("id")]
    id_set = set(ids)
    labelled = {n.attrs.get("for") for n in nodes if n.tag == "label"}

    def named(node):
        if node.attrs.get("aria-label", "").strip():
            return True
        refs = node.attrs.get("aria-labelledby", "").split()
        if refs and all(ref in id_set for ref in refs):
            return True
        return bool(node.text(spoken=True))

    # On plans pages, style.css lets code blocks scroll sideways on phones. Each
    # must be a named, focusable region so keyboard users can scroll it.
    body = next((n for n in nodes if n.tag == "body"), None)
    scrolling_pre = (
        body is not None and "plans-site" in body.attrs.get("class", "").split()
    )

    html = next((n for n in nodes if n.tag == "html"), None)
    if html is None or not html.attrs.get("lang", "").strip():
        problems.append("missing page language")

    for meta in (n for n in nodes if n.tag == "meta"):
        if meta.attrs.get("name") != "viewport":
            continue
        content = meta.attrs.get("content", "").replace(" ", "").lower()
        scale = re.search(r"maximum-scale=([0-9.]+)", content)
        if "user-scalable=no" in content or (scale and float(scale[1]) < 2):
            problems.append("viewport blocks zoom")

    levels = [int(n.tag[1]) for n in nodes if re.fullmatch(r"h[1-6]", n.tag)]
    if levels.count(1) != 1:
        problems.append(f"expected one h1, found {levels.count(1)}")
    for before, after in zip(levels, levels[1:]):
        if after > before + 1:
            problems.append(f"heading level skips from h{before} to h{after}")
            break

    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append("duplicate id: " + duplicate)

    for node in nodes:
        for attr in ("aria-labelledby", "aria-describedby", "aria-controls"):
            for ref in node.attrs.get(attr, "").split():
                if ref not in id_set:
                    problems.append(f"{attr} points to missing id: {ref}")
        tabindex = node.attrs.get("tabindex", "").strip()
        if tabindex.lstrip("-").isdigit() and int(tabindex) > 0:
            problems.append("positive tabindex on <" + node.tag + ">")

        if (
            node.tag == "pre"
            and scrolling_pre
            and not (
                node.attrs.get("tabindex", "").strip() == "0"
                and node.attrs.get("role") == "region"
                and node.attrs.get("aria-label", "").strip()
            )
        ):
            problems.append(
                "scrollable <pre> needs tabindex=0, role=region and aria-label"
            )

        if node.tag == "img" and "alt" not in node.attrs:
            problems.append("image without alt: " + node.attrs.get("src", "?"))
        outer_svg = node.tag == "svg" and not node.inside("svg")
        if (
            outer_svg
            and not node.hidden()
            and not (node.attrs.get("role") == "img" and named(node))
        ):
            problems.append("SVG needs role=img with a name, or aria-hidden")

        if node.tag in ("a", "button") and not node.hidden():
            if node.tag == "a" and "href" not in node.attrs:
                continue
            if not named(node):
                problems.append(f"<{node.tag}> without an accessible name")
            if any(arrow in node.text(spoken=True) for arrow in ARROWS):
                problems.append(
                    "decorative arrow read aloud in link: " + node.text(spoken=True)
                )

        control = node.tag in ("select", "textarea") or (
            node.tag == "input"
            and node.attrs.get("type", "text") not in ("hidden", "submit", "button")
        )
        if control and not (
            node.inside("label")
            or (node.attrs.get("id") and node.attrs["id"] in labelled)
            or named(node)
        ):
            problems.append("form control without a label")

        if node.tag == "a" and "skip-link" in node.attrs.get("class", "").split():
            target = node.attrs.get("href", "")
            if not target.startswith("#") or target[1:] not in id_set:
                problems.append("skip link target missing: " + target)
    return problems


def css_problems(css):
    """Return problems in a shared site stylesheet."""
    problems = []
    plain = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    focus = re.search(r":focus-visible\s*\{([^}]*)\}", plain)
    if not focus or not re.search(r"outline\s*:\s*[1-9]", focus[1]):
        problems.append("missing visible :focus-visible outline")
    if re.search(r"outline\s*:\s*(?:none|0)\s*[;}]", plain):
        problems.append("outline removed")
    motion = re.search(
        r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{(.*?\})\s*\}",
        plain,
        re.DOTALL,
    )
    if not motion or not all(
        rule in motion[1]
        for rule in (
            "animation: none",
            "transition: none",
            "scroll-behavior: auto",
        )
    ):
        problems.append("missing reduced-motion rules")
    return problems


def check(root):
    failures = []
    for site in SITES:
        for page in sorted((root / site).rglob("*.html")):
            for problem in page_problems(page.read_text(encoding="utf-8")):
                failures.append(f"{page.relative_to(root)}: {problem}")
    for name in SHARED_CSS:
        for problem in css_problems((root / name).read_text(encoding="utf-8")):
            failures.append(f"{name}: {problem}")
    return failures


def replace_once(path, old, new):
    source = path.read_text(encoding="utf-8")
    if source.count(old) < 1:
        raise AssertionError(f"mutant anchor missing in {path.name}: {old!r}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


MUTANTS = (
    ("page language", "openhra/index.html", '<html lang="en">', "<html>"),
    (
        "decorative arrow read aloud",
        "plans/index.html",
        'and self-host <span aria-hidden="true">↗</span>',
        "and self-host ↗",
    ),
    (
        "decorative arrow read aloud",
        "openhra/index.html",
        'and containers <span aria-hidden="true">↗</span>',
        "and containers ↗",
    ),
    ("image without alt", "openhra/index.html", 'alt="OpenHRA"', ""),
    ("expected one h1", "plans/availability.html", "<h1", "<h2"),
    ("heading level skips", "plans/index.html", "<h2", "<h4"),
    ("skip link target missing", "plans/index.html", 'id="main"', 'id="content"'),
    (
        "without an accessible name",
        "plans/index.html",
        'aria-label="Main"',
        'aria-label="Main"><a href="/"></a',
    ),
    (
        "without an accessible name",
        "plans/index.html",
        ">All state records (JSON)</a></p></details>",
        "></a></p></details>",
    ),
    ("positive tabindex", "plans/index.html", 'tabindex="0"', 'tabindex="3"'),
    (
        "scrollable <pre> needs tabindex=0",
        "plans/index.html",
        '<pre tabindex="0" role="region" aria-label="Local stdio command">',
        '<pre role="region" aria-label="Local stdio command">',
    ),
    (
        "scrollable <pre> needs tabindex=0",
        "plans/index.html",
        '<pre tabindex="0" role="region" aria-label="Commands to get the code">',
        '<pre tabindex="0" role="region">',
    ),
    (
        "scrollable <pre> needs tabindex=0",
        "plans/index.html",
        '<pre tabindex="0" role="region" aria-label="MCP HTTP request headers">',
        '<pre tabindex="0" aria-label="MCP HTTP request headers">',
    ),
    ("viewport blocks zoom", "plans/index.html", "initial-scale=1", "user-scalable=no"),
    ("form control without a label", "plans/index.html", "<main", "<input><main"),
    ("SVG needs role=img", "plans/index.html", 'role="img"', 'role="presentation"'),
    ("missing id", "plans/availability.html", 'id="coverage-svg-title"', ""),
    ("duplicate id", "openhra/index.html", 'id="main"', 'id="main"><i id="main"></i'),
    (
        "missing visible :focus-visible outline",
        "plans/brand/site.css",
        "outline: 3px solid var(--accent);\n  outline-offset: 5px;\n  border-radius",
        "outline-offset: 5px;\n  border-radius",
    ),
    (
        "outline removed",
        "openhra/brand/site.css",
        ".skip-link:focus {",
        "a:focus { outline: none; }\n.skip-link:focus {",
    ),
    (
        "missing reduced-motion rules",
        "openhra/brand/site.css",
        "transition: none !important;",
        "",
    ),
)


def selftest():
    baseline = check(ROOT)
    assert not baseline, "baseline must pass:\n" + "\n".join(baseline)
    for expected, name, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            for site in SITES:
                shutil.copytree(
                    ROOT / site, copy / site, ignore=shutil.ignore_patterns("data")
                )
            replace_once(copy / name, old, new)
            failures = check(copy)
            assert any(expected in failure for failure in failures), (
                f"mutant not caught ({expected}) in {name}: {failures}"
            )
    print(f"a11y selftest: PASS ({len(MUTANTS)} mutants caught)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    failures = check(ROOT)
    for failure in failures:
        print("FAIL: " + failure)
    if failures:
        sys.exit(1)
    print("a11y: PASS")


if __name__ == "__main__":
    main()
