#!/usr/bin/env python3
"""Check production markup, data and geometry with isolated negative controls."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/coverage-scan"))
from model import STATES, loads
from scan import table


class Markup(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.events = []
        self.tags = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.events.append(("start", tag, tuple(sorted(attrs))))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.events.append(("text", text))

    def has(self, tag, **attrs):
        return any(
            t == tag and all(a.get(k.replace("_", "-")) == v for k, v in attrs.items())
            for t, a in self.tags
        )


def reader_safety(reader):
    assert not re.search(
        r"\b(?:innerHTML|outerHTML|insertAdjacentHTML)\b|\beval\s*\(", reader
    ), "unsafe DOM interpolation"
    calls = re.findall(r"\bfetch\s*\(", reader)
    safe = re.findall(r"\bfetch\s*\(\s*(['\"])data/coverage/\1\s*\+\s*path\s*,", reader)
    assert len(calls) == len(safe) == 1, "unexpected fetch path"


def coverage_css(css):
    assert "/* Static coverage reader:" in css, "missing coverage CSS marker"
    assert len(css.split("/* Static coverage reader:", 1)[1].encode()) <= 8 * 1024, (
        "coverage CSS budget"
    )
    rules = re.findall(
        r"(?m)([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    )
    backgrounds = []
    for selector, body in rules:
        if ".coverage" in [part.strip() for part in selector.split(",")]:
            backgrounds.extend(
                re.findall(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", body)
            )
    assert backgrounds and all(
        value.strip().lower() == "#ffffff" for value in backgrounds
    ), "missing white coverage ground"


MCP_COPY_SCRIPT = '<script src="/mcp-copy.js" defer></script>'


def scripts_with_mcp(source):
    scripts = re.findall(r"<script\b[^>]*>.*?</script>", source, re.DOTALL)
    if MCP_COPY_SCRIPT not in scripts:
        scripts.insert(1, MCP_COPY_SCRIPT)
    return scripts


def check_scripts(source, baseline, diagnostic="page scripts changed"):
    # Preserve every existing tag and its order; allow only the exact local addition.
    assert re.findall(
        r"<script\b[^>]*>.*?</script>", source, re.DOTALL
    ) == scripts_with_mcp(baseline), diagnostic


def script_negatives(root):
    mutations = {
        "different MCP script": lambda s: s.replace(
            MCP_COPY_SCRIPT, '<script src="/different.js" defer></script>'
        ),
        "extra script": lambda s: s + '<script src="/extra.js" defer></script>',
        "duplicate MCP script": lambda s: s + MCP_COPY_SCRIPT,
        "missing MCP script": lambda s: s.replace(MCP_COPY_SCRIPT, ""),
        "MCP defer removed": lambda s: s.replace(
            MCP_COPY_SCRIPT, '<script src="/mcp-copy.js"></script>'
        ),
        "MCP inline payload": lambda s: s.replace(
            MCP_COPY_SCRIPT, '<script src="/mcp-copy.js" defer>unexpected()</script>'
        ),
        "contact script removed": lambda s: s.replace(
            '<script src="/contact.js" defer></script>', ""
        ),
        "contact script changed": lambda s: s.replace(
            "/contact.js", "/different-contact.js"
        ),
    }
    for site in ("plans", "openhra"):
        source = (root / site / "index.html").read_text()
        assert source.count(MCP_COPY_SCRIPT) == 1, "expected one MCP script per page"
        for label, baseline in (
            ("before MCP", source.replace(MCP_COPY_SCRIPT, "")),
            ("with MCP", source),
        ):
            check_scripts(source, baseline)
            for name, mutate in mutations.items():
                mutant = mutate(source)
                assert mutant != source, "script mutation was a no-op: " + name
                try:
                    check_scripts(mutant, baseline)
                except AssertionError as exc:
                    assert str(exc) == "page scripts changed", (
                        "wrong script mutation diagnostic"
                    )
                    print(
                        "negative control: PASS ("
                        + site
                        + ", "
                        + label
                        + ", "
                        + name
                        + ")"
                    )
                else:
                    raise AssertionError("script mutation was accepted: " + name)


def check(root):
    for layer, pages in (
        ("providers", ("coverage-table.html",)),
        ("premiums", ("index.html", "availability.html")),
    ):
        fragment = (
            (root / f"tools/coverage-scan/default-{layer}-2026.html")
            .read_text()
            .strip()
        )
        dataset = loads((root / f"plans/data/coverage/{layer}-2026.json").read_bytes())
        assert fragment == table(dataset).decode().strip(), (
            "scanner fragment differs from JSON"
        )
        for name in pages:
            page = (root / "plans" / name).read_text()
            saved = re.findall(
                r'<div\b[^>]*\bid=["\']coverage-table["\'][^>]*>(.*?)</div>',
                page,
                re.DOTALL,
            )
            assert (
                len(saved) == 1 and Markup(saved[0]).events == Markup(fragment).events
            ), "saved table differs: " + name
            assert "Coverage for plan year 2026" in page, (
                "missing default plan-year label"
            )
            assert "Figures as of November 8, 2026" in page, (
                "missing explicit default date"
            )
            assert (
                sum(
                    tag == "th" and attrs.get("scope") == "row"
                    for tag, attrs in Markup(page).tags
                )
                == 51
            ), "missing default state row"
    page = (root / "plans/index.html").read_text()
    full = (root / "plans/availability.html").read_text()
    for source in (page, full):
        markup = Markup(source)
        assert (
            sum(
                tag == "script"
                and attrs.get("src") == "/coverage.js"
                and "defer" in attrs
                for tag, attrs in markup.tags
            )
            == 1
        )
        assert "U.S. Census Bureau, 2024 cartographic boundaries" in source
        assert {
            attrs.get("value")
            for tag, attrs in markup.tags
            if tag == "option" and re.fullmatch("[A-Z]{2}", attrs.get("value", ""))
        } == set(STATES)
        assert markup.has("button", id="coverage-share") and any(
            attrs.get("id") == "coverage-share-message"
            and attrs.get("role") == "status"
            and attrs.get("aria-live") == "polite"
            for _, attrs in markup.tags
        ), "missing accessible share action"
        assert 'id="coverage-summary"' in source and "not yet measured" in source, (
            "missing measured-state summary"
        )
        for layer, label in (
            ("providers", "Providers"),
            ("prescriptions", "Prescriptions"),
            ("premiums", "Premiums"),
        ):
            saved = loads(
                (root / f"plans/data/coverage/{layer}-2026.json").read_bytes()
            )
            measured = sum(r["status"] == "measured" for r in saved["states"].values())
            assert f"{label}: {measured} of 51 states measured" in source, (
                "saved measured-state summary differs from JSON"
            )
    assert (
        'class="coverage-table-disclosure"' in page
        and "Open the full availability page" in page
    ), "landing must link to full page and collapse table"
    assert (
        "coverage-methodology-heading" in full
        and "coverage-table-disclosure" not in full
    ), "full page methodology/table absent"
    assert "<title>Data availability by state · OpenPlans</title>" in full
    for tag in (
        "description",
        "og:title",
        "og:description",
        "og:url",
        "twitter:card",
        "twitter:title",
        "twitter:description",
        "og:image",
        "og:image:alt",
        "twitter:image",
        "twitter:image:alt",
    ):
        assert any(
            t == "meta"
            and (attrs.get("name") == tag or attrs.get("property") == tag)
            and attrs.get("content")
            for t, attrs in Markup(full).tags
        ), "full page metadata absent: " + tag
    assert (root / "plans/brand/repo/social-preview.png").stat().st_size < 64 * 1024, (
        "social image budget"
    )
    config = json.loads((root / "plans/vercel.json").read_text())
    assert config.get("cleanUrls") is True and not any(
        r["source"] in ("/availability", "/(.*)", "/:path*")
        for r in config.get("rewrites", [])
    ), "availability clean URL absent or shadowed"
    gate = (root / "tools/gate.sh").read_text()
    assert (
        '"plans/availability.html"'
        in gate.split("required_pages = (", 1)[-1].split(")", 1)[0]
    ), "availability missing from gate page list"
    svg = (root / "plans/brand/us-states.svg").read_text()
    ns = {"s": "http://www.w3.org/2000/svg"}
    expected = ET.fromstring((root / "tests/reference/map.svg").read_text())
    actual = ET.fromstring(svg)
    geometry = lambda el: {
        p.attrib["data-state"]: p.attrib["d"]
        for p in el.findall(".//s:path[@data-state]", ns)
    }
    assert geometry(actual) == geometry(expected) and set(geometry(actual)) == set(
        STATES
    ), "Census geometry differs"
    assert len(actual.findall(".//s:path[@data-state]", ns)) == 51
    for source in (page, full):
        embedded = ET.fromstring(re.search(r"<svg\b.*?</svg>", source, re.DOTALL)[0])
        assert geometry(embedded) == geometry(actual), "embedded map differs"
        for shape in embedded.findall(".//s:path[@data-state]", ns):
            record = dataset["states"][shape.attrib["data-state"]]
            expected_fill = (
                "url(#coverage-unknown)"
                if record["status"] == "unknown"
                else "var(--teal-800)"
            )
            assert shape.attrib["fill"] == expected_fill, (
                "saved premium map differs from JSON"
            )
    assert {
        e.attrib["data-label"] for e in actual.findall(".//s:text[@data-label]", ns)
    } == set(STATES), "missing state label"
    assert "37337db59415f010c594fba96a48aa6e950e633dc0e555cc7b1ce8edd794c673" in svg
    assert len(svg.encode()) <= 200 * 1024
    reader = (root / "plans/coverage.js").read_text()
    assert len(reader.encode()) <= 24 * 1024, "reader budget"
    reader_safety(reader)
    css = (root / "plans/style.css").read_text()
    coverage_css(css)
    if (
        root.resolve() == ROOT
        and subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"],
            check=False,
            capture_output=True,
        ).returncode
        == 0
    ):
        prefix = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--show-prefix"], text=True
        ).strip()
        baseline = (
            "main"
            if subprocess.run(
                [
                    "git",
                    "-C",
                    str(ROOT),
                    "cat-file",
                    "-e",
                    "main:" + prefix + "plans/index.html",
                ],
                check=False,
                capture_output=True,
            ).returncode
            == 0
            else "HEAD"
        )
        original = lambda name: subprocess.check_output(
            ["git", "-C", str(ROOT), "show", baseline + ":" + prefix + name]
        ).decode()
        # A page redesign is authorised. Keep the evidence, legal and contact
        # blocks byte-identical instead of freezing unrelated presentation copy.
        baseline_page = original("plans/index.html")
        # Verification row labels and the caption may be reworded. The checked
        # figures, their order and the run date stay exactly as validated.
        evidence = r'<section class="band alt verification">.*?</section>'
        figures = lambda block: (
            re.findall(r'<td class="num">([^<]*)</td>', block),
            "Figures from the November 8, 2026 validation run." in block,
        )
        before = re.search(evidence, baseline_page, re.DOTALL)
        after = re.search(evidence, page, re.DOTALL)
        assert before and after and figures(before[0]) == figures(after[0]), (
            "protected page block changed: " + evidence
        )
        protected_sections = (
            r'<section class="band" id="publishers">.*?</section>',
            r'<section class="band alt" id="contact">.*?</section>',
            r"<footer>.*?</footer>",
            r"<p>This product uses publicly available data.*?</p>",
        )
        for pattern in protected_sections:
            before = re.search(pattern, baseline_page, re.DOTALL)
            after = re.search(pattern, page, re.DOTALL)
            assert before and after and before[0] == after[0], (
                "protected page block changed: " + pattern
            )
        check_scripts(page, baseline_page)
        assert css.startswith(original("plans/style.css")), "existing styles changed"
        organisation = (root / "openhra/index.html").read_text()
        original_organisation = original("openhra/index.html")
        for pattern in (
            r'<section class="band alt" id="contact">.*?</section>',
            r"<footer>.*?</footer>",
        ):
            assert (
                re.search(pattern, organisation, re.DOTALL)[0]
                == re.search(pattern, original_organisation, re.DOTALL)[0]
            ), "organisation protected block changed"
        check_scripts(
            organisation, original_organisation, "organisation scripts changed"
        )
        assert (
            config["headers"] == json.loads(original("plans/vercel.json"))["headers"]
        ), "protected hosting headers changed"
        for name in (
            "plans/contact.js",
            "plans/api/contact.js",
            "plans/brand/tokens.css",
            "openhra/vercel.json",
            "openhra/contact.js",
            "openhra/api/contact.js",
            "openhra/brand/tokens.css",
        ):
            assert (root / name).read_text() == original(name), (
                "protected file changed: " + name
            )

    result = subprocess.run(
        ["node", str(Path(__file__).with_name("selection-test.mjs")), str(root)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def negatives(root=ROOT):
    script_negatives(root)
    mutations = {
        "table row removed": lambda s: re.sub(
            r'<tr>\s*<th\s+scope=["\']row["\']>Alaska</th>.*?</tr>\s*',
            "",
            s,
            flags=re.DOTALL,
        ),
        "default value changed": lambda s: s.replace(
            "203592/203592 (100.0%)", "203591/203592 (100.0%)"
        ),
        "plan year removed": lambda s: s.replace(
            "Coverage for plan year 2026", "Coverage"
        ),
        "plan year mismatched": lambda s: s.replace(
            "Coverage for plan year 2026", "Coverage for plan year 2027"
        ),
    }
    cases = [(name, "plans/index.html", mutate) for name, mutate in mutations.items()]
    cases.extend(
        [
            (
                "URL state ignored",
                "plans/coverage.js",
                lambda s: re.sub(
                    r"state:\s*Object\.hasOwn\(\s*states,\s*params\.get\(['\"]state['\"]\),?\s*\)\s*\?\s*params\.get\(['\"]state['\"]\)\s*:\s*ALL_STATES",
                    "state: 'TX'",
                    s,
                ),
            ),
            (
                "share drops selection",
                "plans/coverage.js",
                lambda s: re.sub(
                    r"const url = link\(\)\.href;",
                    "const url = new URL('/availability', location.origin).href;",
                    s,
                ),
            ),
            (
                "clipboard confirmation absent",
                "plans/coverage.js",
                lambda s: re.sub(
                    r"\$\(['\"]share-message['\"]\)\.textContent\s*=\s*['\"]Link copied['\"];",
                    "$('share-message').textContent = '';",
                    s,
                ),
            ),
            (
                "unknown rendered as measured",
                "plans/coverage.js",
                lambda s: re.sub(
                    r"unknown:\s*['\"]Unknown, not yet measured['\"]",
                    "unknown: '0.0%'",
                    s,
                ),
            ),
            (
                "availability missing from gate page list",
                "tools/gate.sh",
                lambda s: s.replace(', "plans/availability.html"', ""),
            ),
        ]
    )
    cases.extend(
        [
            (
                "white ground removed",
                "plans/style.css",
                lambda s: re.sub(
                    r"(\.coverage\s*\{)\s*background:\s*#ffffff;", r"\1", s
                ),
            ),
            (
                "nonwhite coverage override",
                "plans/style.css",
                lambda s: s + "\n.coverage { background: black; }\n",
            ),
            (
                "unsafe DOM insertion",
                "plans/coverage.js",
                lambda s: s + '\ndocument.body.innerHTML = "unsafe";\n',
            ),
            ("spaced eval", "plans/coverage.js", lambda s: s + '\neval ("unsafe");\n'),
            (
                "wrong fetch origin",
                "plans/coverage.js",
                lambda s: re.sub(
                    r"(['\"])data/coverage/\1\s*\+\s*path",
                    '"https://example.invalid/" + path',
                    s,
                ),
            ),
            (
                "additional fetch origin",
                "plans/coverage.js",
                lambda s: s + '\nfetch("https://example.invalid/");\n',
            ),
            (
                "canonical map changed",
                "plans/brand/us-states.svg",
                lambda s: s.replace('data-state="TX"', 'data-state="ZZ"'),
            ),
            (
                "embedded map changed",
                "plans/index.html",
                lambda s: s.replace('data-state="TX"', 'data-state="ZZ"'),
            ),
            (
                "generated table changed",
                "tools/coverage-scan/default-premiums-2026.html",
                lambda s: s.replace("203592/203592 (100.0%)", "203591/203592 (100.0%)"),
            ),
        ]
    )
    for name, filename, mutate in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            for directory in ("plans", "tools/coverage-scan", "tests/reference"):
                shutil.copytree(
                    root / directory,
                    dest / directory,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            shutil.copy(root / "tools/gate.sh", dest / "tools/gate.sh")
            target = dest / filename
            before = target.read_text()
            target.write_text(mutate(before))
            assert target.read_text() != before, "mutation was a no-op: " + name
            try:
                check(dest)
            except AssertionError as exc:
                expected = {
                    "URL state ignored": "URL state ignored on load or history",
                    "share drops selection": "share link drops selection",
                    "clipboard confirmation absent": "clipboard confirmation absent",
                    "unknown rendered as measured": "unknown state rendered as measured",
                    "availability missing from gate page list": "availability missing from gate page list",
                    "unsafe DOM insertion": "unsafe DOM interpolation",
                    "spaced eval": "unsafe DOM interpolation",
                    "wrong fetch origin": "unexpected fetch path",
                    "additional fetch origin": "unexpected fetch path",
                    "nonwhite coverage override": "missing white coverage ground",
                    "canonical map changed": "Census geometry differs",
                    "embedded map changed": "embedded map differs",
                    "generated table changed": "scanner fragment differs from JSON",
                }
                if name in expected:
                    assert expected[name] in str(exc), (
                        "wrong negative diagnostic: " + name + ": " + str(exc)
                    )
                print("negative control: PASS (" + name + ")")
            else:
                raise AssertionError("negative control was accepted: " + name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        check(args.root)
        if args.selftest:
            negatives()
    except (AssertionError, ValueError, KeyError) as exc:
        print("FAIL: coverage UI: " + str(exc))
        sys.exit(1)
    print(
        "PASS: coverage UI static consistency, default year/date, 51 Census paths and labels, safe DOM and budgets"
    )
