#!/usr/bin/env python3
"""Keep the public MCP preview honest and repository actions first."""

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://openplans.openhra.com/mcp"
TOOLS = {
    "search",
    "fetch",
    "search_plans",
    "get_plan",
    "search_providers",
    "check_provider_network",
    "search_drugs",
    "check_drug_coverage",
    "lookup_geography",
    "list_carriers_networks",
    "get_data_status",
}


class Node:
    def __init__(self, tag="", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
        self.parts = []

    def text(self):
        return " ".join(self.parts).strip()

    def find(self, predicate):
        result = []
        for child in self.children:
            if predicate(child):
                result.append(child)
            result.extend(child.find(predicate))
        return result


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.root = self.current = Node()
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {"meta", "link", "img", "br", "hr", "input", "source", "wbr"}:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent and node.tag != tag:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        node = self.current
        while node:
            node.parts.append(data)
            node = node.parent


def classed(node, name):
    return name in node.attrs.get("class", "").split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalized(text):
    return " ".join(text.lower().split())


def visible(node):
    while node.parent:
        if (
            "hidden" in node.attrs
            or node.attrs.get("aria-hidden") == "true"
            or re.search(
                r"display\s*:\s*none|visibility\s*:\s*hidden",
                node.attrs.get("style", ""),
                re.I,
            )
        ):
            return False
        node = node.parent
    return True


def check_page(source, site):
    root = Page(source).root
    all_text = normalized(root.text())
    metadata = root.find(
        lambda n: n.tag == "meta" and n.attrs.get("name") == "description"
    )
    titles = root.find(lambda n: n.tag == "title" and n.parent.tag == "head")
    require(
        len(metadata) == len(titles) == 1
        and "public preview" in normalized(metadata[0].attrs.get("content", ""))
        and "public preview" in normalized(titles[0].text()),
        "metadata must say Public preview",
    )
    # Word boundaries avoid rejecting the Georgia postal abbreviation in the map.
    # GA is forbidden in MCP presentation, not in protected coverage data.
    mcp = root.find(lambda n: n.attrs.get("id") in {"mcp", "agents"})
    require(len(mcp) == 1, "MCP section missing")
    claims = all_text + " " + normalized(metadata[0].attrs["content"])
    require(
        not re.search(r"\b(?:stable|production[ -]ready|released)\b", claims),
        "unsupported release claim",
    )
    presentation = normalized(
        mcp[0].text() + " " + titles[0].text() + " " + metadata[0].attrs["content"]
    )
    require(
        not re.search(r"\bga\b|general availability", presentation),
        "unsupported GA claim",
    )
    previews = root.find(lambda n: "data-mcp-preview" in n.attrs)
    require(
        len(previews) >= (7 if site == "plans" else 4), "missing MCP preview blocks"
    )
    for preview in previews:
        labels = preview.find(
            lambda n: "public preview" in normalized(n.text()) and not n.children
        )
        require(
            visible(preview) and any(visible(n) for n in labels),
            "MCP block must show Public preview",
        )
        require(
            not re.search(
                r"\bin development\b|\bplanned\b|\bnot (?:yet )?hosted\b",
                normalized(preview.text()),
            ),
            "stale MCP status",
        )
    nav = root.find(lambda n: n.tag == "nav")[0]
    badge = nav.find(lambda n: n.tag == "small")
    require(
        any(normalized(n.text()) == "public preview" and visible(n) for n in badge),
        "navigation must show Public preview",
    )
    require(
        "no release yet" in all_text
        and "no tagged openplans release exists yet" in all_text,
        "no-release status missing",
    )
    require(
        "outside acceptance run is still pending" in presentation
        and "coverage is limited" in presentation,
        "preview acceptance limit missing",
    )
    require(
        all(
            term in presentation
            for term in [
                "streamable http",
                "stateless",
                "read-only",
                "unknown",
                "provenance",
                "not covered",
            ]
        ),
        "transport or evidence rule missing",
    )
    cards = root.find(lambda n: classed(n, "endpoint-card"))
    require(len(cards) == 1, "endpoint card missing")
    card = cards[0]
    addresses = card.find(lambda n: n.attrs.get("id") == "mcp-endpoint")
    require(
        len(addresses) == 1
        and visible(addresses[0])
        and addresses[0].text() == ENDPOINT,
        "exact live endpoint missing",
    )
    require(
        "public preview endpoint" in normalized(card.text()),
        "endpoint must say Public preview",
    )
    scope = card.find(lambda n: classed(n, "endpoint-scope"))
    require(
        len(scope) == 1
        and visible(scope[0])
        and all(
            term in normalized(scope[0].text())
            for term in [
                "catalog only",
                "texas and florida",
                "2026–2027",
                "11 tools",
                "household quotes need self-hosting with credentials",
            ]
        ),
        "catalog scope or household restriction missing",
    )
    buttons = card.find(
        lambda n: (
            n.tag == "button" and n.attrs.get("data-copy-endpoint") == "mcp-endpoint"
        )
    )
    status = card.find(
        lambda n: (
            n.attrs.get("role") == "status" and n.attrs.get("aria-live") == "polite"
        )
    )
    require(
        len(buttons) == len(status) == 1 and buttons[0].text() == "Copy URL",
        "accessible copy affordance missing",
    )
    require(
        root.find(
            lambda n: (
                n.tag == "script"
                and n.attrs.get("src") == "/mcp-copy.js"
                and "defer" in n.attrs
            )
        ),
        "clipboard script missing",
    )
    # Inspect small copy units so a valid self-host disclaimer elsewhere cannot
    # excuse a contradictory public-quote claim. Keep the coverage section out.
    units = mcp[0].find(lambda n: n.tag in {"p", "dd", "li", "h2", "h3", "h4"})
    units += root.find(lambda n: classed(n, "hero-preview"))
    description = Node("meta")
    description.parts.append(metadata[0].attrs["content"])
    units.append(description)
    for unit in units:
        require(
            not re.search(r"\bga\b|general availability", normalized(unit.text())),
            "unsupported GA claim",
        )
    for unit in units:
        text = normalized(unit.text())
        if "household" in text or "estimate_premiums" in text:
            require("self-host" in text, "household quotes must be self-host only")
        for sentence in re.split(r"[.!?]", text):
            if (
                "household" in sentence or "estimate_premiums" in sentence
            ) and "public" in sentence:
                require(
                    "not offered on the public endpoint" in sentence
                    or "not available on the public endpoint" in sentence,
                    "household quotes claimed public",
                )
    estimates = mcp[0].find(
        lambda n: n.tag == "code" and n.text() == "estimate_premiums"
    )
    require(estimates, "self-host estimate_premiums missing")
    for estimate in estimates:
        context = estimate.parent
        if context.tag == "dt":
            context = context.parent
        require(
            visible(estimate)
            and "self-host" in normalized(context.text())
            and "credentials" in normalized(context.text())
            and "not offered on the public endpoint" in normalized(context.text()),
            "estimate_premiums must be self-host only with credentials",
        )
    target = "https://github.com/openhra" + ("/openplans" if site == "plans" else "")
    first = nav.find(lambda n: n.tag == "ul")[0].find(lambda n: n.tag == "a")[0]
    require(first.attrs.get("href") == target, "GitHub must lead navigation")
    hero = root.find(lambda n: classed(n, "hero"))[0]
    first = hero.find(lambda n: classed(n, "actions"))[0].find(lambda n: n.tag == "a")[
        0
    ]
    require(
        first.attrs.get("href") == target and classed(first, "button"),
        "GitHub must lead hero actions",
    )
    directories = root.find(lambda n: classed(n, "repo-directory"))
    require(directories, "repository directory missing")
    for directory in directories:
        require(
            all(
                label in normalized(directory.text())
                for label in ["code", "docs", "issues", "releases", "no release yet"]
            ),
            "repository contents/release status missing",
        )
    require(
        "git clone https://github.com/openhra/openplans.git" in all_text,
        "clone command missing",
    )
    if site == "plans":
        directory = root.find(lambda n: classed(n, "tool-directory"))[0]
        public, private = [], []
        for group in directory.children:
            codes = group.find(lambda n: n.tag == "code")
            require(all(visible(n) for n in codes), "tool inventory hidden")
            if group.attrs.get("data-tool-access") == "self-host":
                private.extend(n.text() for n in codes)
                require(
                    "self-host only" in normalized(group.text()),
                    "self-host tool label missing",
                )
            else:
                public.extend(n.text() for n in codes)
        require(
            len(public) == 11
            and set(public) == TOOLS
            and private == ["estimate_premiums"],
            "tool inventory must contain exactly 11 public tools and one self-host estimate_premiums",
        )
        example = root.find(lambda n: classed(n, "agent-example"))[0].text().lower()
        require(
            all(
                term in example
                for term in [
                    "example agent exchange",
                    "illustrative only",
                    "no live request",
                    "agent · example reply",
                ]
            ),
            "agent exchange must be labelled illustrative",
        )
        panels = root.find(lambda n: classed(n, "connection-panel"))
        require(len(panels) == 2, "connection options missing")
        raw = panels[0].find(lambda n: n.tag == "pre")[0].text()
        config = json.loads(raw)
        require(
            config == {"mcpServers": {"openplans": {"url": ENDPOINT}}},
            "generic MCP config differs",
        )
        headers = panels[0].find(lambda n: n.tag == "pre")[1].text()
        require(
            headers.splitlines()
            == [
                "Content-Type: application/json",
                "Accept: application/json, text/event-stream",
                "MCP-Protocol-Version: 2026-07-28",
            ],
            "HTTP headers differ",
        )
        require(
            "2025-11-25" in panels[0].text()
            and "CORS from the allowed origin" in panels[0].text(),
            "client compatibility missing",
        )
        require(
            "http://127.0.0.1:3000/mcp" in panels[1].text()
            and "openplans-mcp" in panels[1].text()
            and "source installation" in panels[1].text(),
            "self-host interfaces missing",
        )
        require(
            "OPENPLANS_RAW_READ_ONLY=false docker compose run --build --rm worker bootstrap --states TX,FL --years 2026,2027"
            in root.text(),
            "README bootstrap command differs",
        )


def run(root):
    for site in ["openhra", "plans"]:
        check_page((root / site / "index.html").read_text(), site)
    require(
        (root / "openhra/brand/site.css").read_bytes()
        == (root / "plans/brand/site.css").read_bytes(),
        "shared site styles differ",
    )
    for name in ["index.html", "style.css"]:
        require(
            (root / "openhra" / name).read_bytes()
            == (root / "plans/brand/openhra" / name).read_bytes(),
            "organisation handoff copy differs: " + name,
        )
    require(
        (root / "openhra/mcp-copy.js").read_bytes()
        == (root / "plans/mcp-copy.js").read_bytes(),
        "clipboard scripts differ",
    )
    print(
        "mcp: PASS (Public preview, live catalog endpoint, 11 public tools + self-host estimates, GitHub-first, handoff parity)"
    )


def selftest(root):
    sources = {
        site: (root / site / "index.html").read_text() for site in ["openhra", "plans"]
    }
    mutants = []
    for site in ["plans", "openhra"]:
        mutants.extend(
            [
                (
                    site,
                    "preview status removed",
                    lambda s: s.replace("Public preview", "Available now"),
                    "Public preview",
                ),
                (
                    site,
                    "hidden preview badge",
                    lambda s: s.replace(
                        'class="mcp-badge"', 'class="mcp-badge" hidden'
                    ).replace("Public preview endpoint", "Endpoint"),
                    "Public preview",
                ),
                (
                    site,
                    "metadata stale",
                    lambda s: s.replace("MCP Public preview", "MCP planned"),
                    "metadata",
                ),
                (
                    site,
                    "wrong endpoint",
                    lambda s: s.replace(ENDPOINT, "https://plans.openhra.com/mcp"),
                    "exact live endpoint",
                ),
                (
                    site,
                    "catalog-only limit removed",
                    lambda s: s.replace("Catalog only", "All data"),
                    "catalog scope",
                ),
                (
                    site,
                    "wrong states",
                    lambda s: s.replace("Texas and Florida", "All states"),
                    "catalog scope",
                ),
                (
                    site,
                    "wrong years",
                    lambda s: s.replace("2026–2027", "2025–2027"),
                    "catalog scope",
                ),
                (
                    site,
                    "wrong public tool count",
                    lambda s: s.replace("11 tools", "12 tools"),
                    "catalog scope",
                ),
                (
                    site,
                    "household restriction removed",
                    lambda s: s.replace(
                        "Household quotes need self-hosting with credentials.", ""
                    ),
                    "household restriction",
                ),
                (
                    site,
                    "outside acceptance removed",
                    lambda s: s.replace(
                        "An outside acceptance run is still pending.", ""
                    ),
                    "acceptance limit",
                ),
                (
                    site,
                    "missing copy announcement",
                    lambda s: s.replace(
                        'aria-live="polite" aria-atomic="true"', 'aria-atomic="true"'
                    ),
                    "copy affordance",
                ),
                (
                    site,
                    "release disclaimer removed",
                    lambda s: s.replace("No tagged OpenPlans release exists yet.", ""),
                    "no-release",
                ),
                (
                    site,
                    "self-host credentials omitted",
                    lambda s: s.replace(
                        "with credentials", "without a setup requirement"
                    ),
                    "restriction",
                ),
                (
                    site,
                    "estimate tool label removed",
                    lambda s: s.replace("estimate_premiums", "estimate_costs"),
                    "estimate_premiums",
                ),
                (
                    site,
                    "public household claim",
                    lambda s: s.replace(
                        "Coverage is limited.",
                        "Coverage is limited. Public household quotes are available. Self-hosting is optional.",
                    ),
                    "claimed public",
                ),
                (
                    site,
                    "public quotes in metadata",
                    lambda s: s.replace(
                        'name="description" content="',
                        'name="description" content="Public household quotes are available. ',
                    ),
                    "claimed public" if site == "plans" else "self-host only",
                ),
                (
                    site,
                    "GA in hero",
                    lambda s: s.replace(
                        "<strong>MCP · Public preview</strong>",
                        "<strong>MCP · Public preview</strong> GA.",
                    ),
                    "GA claim",
                ),
                (
                    site,
                    "public estimate claim",
                    lambda s: s.replace(
                        "Coverage is limited.",
                        "Coverage is limited. The public endpoint offers estimate_premiums, as does self-hosting.",
                    ),
                    "claimed public",
                ),
            ]
        )
        for claim in ["stable", "GA", "production-ready", "released"]:
            mutants.append(
                (
                    site,
                    "unsupported " + claim,
                    lambda s, claim=claim: s.replace(
                        "Coverage is limited.", "Coverage is limited. " + claim + "."
                    ),
                    "GA claim" if claim == "GA" else "release claim",
                )
            )
    mutants.extend(
        [
            (
                "plans",
                "tool removed",
                lambda s: s.replace("<code>get_plan</code>", ""),
                "tool inventory",
            ),
            (
                "plans",
                "hidden live tool",
                lambda s: s.replace(
                    "<code>get_plan</code>", "<code hidden>get_plan</code>"
                ),
                "inventory hidden",
            ),
            (
                "plans",
                "config URL differs from card",
                lambda s: s.replace(
                    '"url": "' + ENDPOINT, '"url": "https://example.invalid/mcp'
                ),
                "config differs",
            ),
            (
                "plans",
                "tool duplicated",
                lambda s: s.replace(
                    "<code>get_plan</code>",
                    "<code>get_plan</code><code>get_plan</code>",
                ),
                "tool inventory",
            ),
            (
                "plans",
                "estimate offered publicly",
                lambda s: s.replace(
                    'data-tool-access="self-host"', 'data-tool-access="public"'
                ),
                "tool inventory",
            ),
            (
                "plans",
                "self-host badge removed",
                lambda s: s.replace("Self-host only", "Public tool"),
                "self-host tool label",
            ),
            (
                "plans",
                "example label removed",
                lambda s: s.replace("Illustrative only", "Live reply"),
                "labelled illustrative",
            ),
            (
                "plans",
                "stale planned label",
                lambda s: s.replace(
                    "Public preview endpoint", "Planned public endpoint"
                ),
                "stale MCP",
            ),
            (
                "plans",
                "wrong header protocol",
                lambda s: s.replace(
                    "MCP-Protocol-Version: 2026-07-28",
                    "MCP-Protocol-Version: 2024-01-01",
                ),
                "HTTP headers",
            ),
            (
                "plans",
                "missing stdio",
                lambda s: s.replace("openplans-mcp</code>", "missing</code>"),
                "self-host interfaces",
            ),
            (
                "plans",
                "hero action displaced",
                lambda s: s.replace(
                    'class="button" href="https://github.com/openhra/openplans"',
                    'class="button" href="#connect"',
                    1,
                ),
                "hero actions",
            ),
        ]
    )
    for site, name, mutate, diagnostic in mutants:
        mutated = mutate(sources[site])
        require(mutated != sources[site], "mutant is a no-op: " + name)
        try:
            check_page(mutated, site)
        except (ValueError, AssertionError) as exc:
            require(
                diagnostic in str(exc),
                "unexpected mutant diagnostic: " + name + ": " + str(exc),
            )
            print("mcp negative: PASS (" + name + ")")
        else:
            raise ValueError("mutant accepted: " + name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        run(args.root)
        if args.selftest:
            selftest(args.root)
    except (ValueError, KeyError, IndexError) as exc:
        raise SystemExit("FAIL: MCP presentation: " + str(exc))
