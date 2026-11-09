#!/usr/bin/env python3
"""Keep the public MCP preview honest and repository actions first."""

import argparse
import json
import re
import shlex
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://openplans.openhra.com/mcp"
REPO = "https://github.com/openhra/openplans"
RELEASE = "v0.2.0"
RELEASE_URL = REPO + "/releases/tag/" + RELEASE
# Owner rule: public pages never compare OpenPlans with another service.
FORBIDDEN_COMPARISON = re.compile(
    r"commercial[\s_-]+reference|reference[\s_-]+api\b|parity\s+with", re.IGNORECASE
)
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
    "quote_plans",
}
PUBLIC_TOOL_COUNT = 12
# Household quotes stay self-host only.
SELF_HOST_TOOL = "quote_premiums"
PERSONALIZED_TOOLS = (SELF_HOST_TOOL,)
# Old household names, removed from the product; pages must not offer them.
REMOVED_NAMES = ("estimate_premiums", "premium-estimates")
# Income and subsidies belong to household quotes, which are self-host only.
HOUSEHOLD_TERMS = re.compile(r"household|income|subsid")


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
                re.IGNORECASE,
            )
        ):
            return False
        node = node.parent
    return True


def check_app(root):
    sections = root.find(lambda n: n.attrs.get("id") == "connect-app")
    require(len(sections) == 1, "app connection section missing")
    section = sections[0]
    heading = section.find(lambda n: n.attrs.get("id") == "app-connect-title")
    require(
        section.tag == "section"
        and section.attrs.get("aria-labelledby") == "app-connect-title"
        and len(heading) == 1
        and heading[0].tag == "h3"
        and heading[0].text() == "Connect your app"
        and visible(section),
        "app connection region must be labelled",
    )
    siblings = section.parent.children
    position = siblings.index(section)
    require(
        position > 0
        and siblings[position - 1].attrs.get("aria-labelledby")
        == "agent-connect-title",
        "app connection must follow agent connection",
    )
    require(
        root.find(lambda n: n.tag == "a" and n.attrs.get("href") == "#connect-app"),
        "app navigation missing",
    )
    copy = normalized(section.text())
    require(
        all(
            term in copy
            for term in (
                "native json api",
                "a compatibility api for existing quoting integrations",
                "public preview",
                "read-only",
                "anonymous",
                "quotes by age and zip",
                "post /v1/quotes",
                "texas and florida",
                "2026–2027",
                "no account or api key",
                "household quotes require self-hosting with credentials",
                "not offered on the public endpoint",
            )
        ),
        "app scope or self-host restriction missing",
    )
    commands = section.find(lambda n: n.tag == "pre")
    require(len(commands) == 2, "app base path or request missing")
    require(
        commands[0].text() == "https://openplans.openhra.com/v1",
        "app base path differs",
    )
    command = commands[1].text().replace("\\\n", " ")
    require(
        shlex.split(command)
        == [
            "curl",
            "--get",
            "https://openplans.openhra.com/v1/plans",
            "--data-urlencode",
            "zip=77002",
            "--data-urlencode",
            "year=2026",
        ],
        "app example must use the verified read-only catalog request",
    )
    links = {n.attrs.get("href") for n in section.find(lambda n: n.tag == "a")}
    require(
        {
            REPO + "/blob/main/src/api/README.md",
            REPO + "#readme",
            REPO + "/blob/main/docs/self-host.md",
        }
        <= links,
        "app API or self-host documentation missing",
    )


def check_page(source, site):
    require(
        not FORBIDDEN_COMPARISON.search(source),
        "forbidden comparison text",
    )
    release_links = re.findall(
        r"https://github\.com/openhra/openplans/releases/(?:tag|download)/[^\"'\s<>]+",
        source,
    )
    require(
        all(link == RELEASE_URL for link in release_links),
        "unexpected release-tag link",
    )
    require(
        not any(name in source for name in REMOVED_NAMES),
        "removed name offered: estimate_premiums or /v1/premium-estimates",
    )
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
        not re.search(r"\b(?:stable|production(?:[ -]ready)?)\b", claims),
        "unsupported release claim",
    )
    require(
        RELEASE.lower() in claims,
        "v0.2.0 release status missing",
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
    statuses = root.find(lambda n: classed(n, "repo-status"))
    require(statuses, "release status missing")
    for status in statuses:
        require(
            visible(status)
            and status.find(
                lambda n: (
                    n.tag == "a"
                    and n.attrs.get("href") == RELEASE_URL
                    and n.text() == RELEASE
                    and visible(n)
                )
            ),
            "release status must link to v0.2.0",
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
                "catalog and quotes by age and zip",
                "texas and florida",
                "2026–2027",
                f"{PUBLIC_TOOL_COUNT} tools",
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
        personal = HOUSEHOLD_TERMS.search(text) or any(
            tool in text for tool in PERSONALIZED_TOOLS
        )
        if personal:
            require("self-host" in text, "household quotes must be self-host only")
        if "quote_plans" in text:
            require(
                "household" not in text, "quote_plans described as a household quote"
            )
        for sentence in re.split(r"[.!?]", text):
            if (
                HOUSEHOLD_TERMS.search(sentence)
                or any(tool in sentence for tool in PERSONALIZED_TOOLS)
            ) and "public" in sentence:
                require(
                    "not offered on the public endpoint" in sentence
                    or "not available on the public endpoint" in sentence,
                    "household quotes claimed public",
                )
    personalized = mcp[0].find(
        lambda n: n.tag == "code" and n.text() in PERSONALIZED_TOOLS
    )
    require(
        any(n.text() == SELF_HOST_TOOL for n in personalized),
        "self-host quote_premiums missing",
    )
    for tool in personalized:
        context = tool.parent
        if context.tag == "dt":
            context = context.parent
        require(
            visible(tool)
            and "self-host" in normalized(context.text())
            and "credentials" in normalized(context.text())
            and "not offered on the public endpoint" in normalized(context.text()),
            "quote_premiums must be self-host only with credentials",
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
                for label in ["code", "docs", "issues", "releases", RELEASE]
            )
            and directory.find(
                lambda n: (
                    n.tag == "a"
                    and n.attrs.get("href") == RELEASE_URL
                    and RELEASE in n.text()
                    and visible(n)
                )
            ),
            "repository contents/release status missing",
        )
    require(
        "git clone https://github.com/openhra/openplans.git" in all_text,
        "clone command missing",
    )
    if site == "plans":
        check_app(root)
        directory = root.find(lambda n: classed(n, "tool-directory"))[0]
        public, private, aliases = [], [], []
        for group in directory.children:
            codes = group.find(lambda n: n.tag == "code")
            names = [
                n.text()
                for n in group.find(lambda n: n.tag == "dt")[0].find(
                    lambda n: n.tag == "code"
                )
            ]
            require(all(visible(n) for n in codes), "tool inventory hidden")
            if group.attrs.get("data-tool-access") == "self-host":
                private.extend(names)
                aliases.extend(n.text() for n in codes if n.text() not in names)
                require(
                    "self-host only" in normalized(group.text()),
                    "self-host tool label missing",
                )
            else:
                require(
                    len(names) == len(codes),
                    "tool inventory mentions a tool outside its name",
                )
                public.extend(names)
                quoted = normalized(group.text())
                if "quote_plans" in names:
                    require(
                        "household" not in quoted,
                        "quote_plans described as a household quote",
                    )
                if HOUSEHOLD_TERMS.search(quoted):
                    require(
                        "self-host" in quoted, "public tool claims income or subsidies"
                    )
        require(
            len(public) == PUBLIC_TOOL_COUNT
            and set(public) == TOOLS
            and private == [SELF_HOST_TOOL]
            and aliases == [],
            "tool inventory must contain exactly 12 public tools and one self-host quote_premiums",
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
        connections = root.find(
            lambda n: (
                n.tag == "section"
                and n.attrs.get("aria-labelledby") == "agent-connect-title"
            )
        )
        require(len(connections) == 1, "agent connection region missing")
        panels = connections[0].find(lambda n: classed(n, "connection-panel"))
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
        "mcp: PASS (v0.2.0 release link, no comparison text, Public preview, live catalog and quote endpoint, 12 public tools + self-host household quotes, GitHub-first, handoff copies identical)"
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
                    lambda s: re.sub(r"(<title>.*?)Public preview", r"\1Planned", s),
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
                    lambda s: s.replace(
                        "Catalog and quotes by age and ZIP ·", "All data ·"
                    ),
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
                    lambda s: s.replace("12 tools", "11 tools"),
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
                    "wrong release tag v0.1.2",
                    lambda s: s.replace(RELEASE_URL, REPO + "/releases/tag/v0.1.2"),
                    "unexpected release-tag link",
                ),
                (
                    site,
                    "v0.2.0 link removed",
                    lambda s: s.replace(RELEASE_URL, REPO),
                    "release status must link to v0.2.0",
                ),
                (
                    site,
                    "v0.2.0 status text removed",
                    lambda s: s.replace(RELEASE + "</a>", "Release</a>"),
                    "release status must link to v0.2.0",
                ),
                (
                    site,
                    "status links elsewhere",
                    lambda s: s.replace(
                        '<a href="' + RELEASE_URL + '">' + RELEASE,
                        '<a href="https://example.invalid/">' + RELEASE,
                    ),
                    "release status must link to v0.2.0",
                ),
                (
                    site,
                    "public endpoint claimed production",
                    lambda s: s.replace(
                        "Coverage is limited.",
                        "Coverage is limited. The public endpoint is production.",
                    ),
                    "unsupported release claim",
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
                    "household tool label removed",
                    lambda s: s.replace("quote_premiums", "quote_costs"),
                    "quote_premiums",
                ),
                (
                    site,
                    "removed tool name offered",
                    lambda s: s.replace(
                        "Coverage is limited.",
                        "Coverage is limited. <code>estimate_premiums</code> also works.",
                    ),
                    "removed name",
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
                    "claimed public",
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
                        "Coverage is limited. The public endpoint offers quote_premiums, as does self-hosting.",
                    ),
                    "claimed public",
                ),
            ]
        )
        for claim in ["stable", "GA", "production-ready", "production"]:
            mutants.append(
                (
                    site,
                    "unsupported " + claim,
                    lambda s, claim=claim: s.replace(
                        "Coverage is limited.", "Coverage is limited. " + claim + "."
                    ),
                    "GA claim"
                    if claim == "GA"
                    else (
                        "unsupported GA claim"
                        if claim == "GA"
                        else "unsupported release claim"
                    ),
                )
            )
        for text in [
            "Compared with a Commercial-Reference catalog.",
            "Matches the reference_API totals.",
            "Built for parity\twith another service.",
        ]:
            mutants.append(
                (
                    site,
                    "comparison text: " + text,
                    lambda s, text=text: s.replace(
                        "Coverage is limited.", "Coverage is limited. " + text
                    ),
                    "forbidden comparison",
                )
            )
        mutants.append(
            (
                site,
                "comparison in a hidden comment",
                lambda s: s.replace(
                    "</body>", "<!-- commercial_reference check --></body>"
                ),
                "forbidden comparison",
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
                "public row claims income",
                lambda s: s.replace(
                    "Search the plan catalog and inspect one plan.",
                    "Search the plan catalog with income-based prices.",
                ),
                "self-host",
            ),
            (
                "plans",
                "public row claims a subsidy",
                lambda s: s.replace(
                    "Find drugs and check published formulary evidence.",
                    "Find drugs and estimate a subsidy.",
                ),
                "self-host",
            ),
            (
                "plans",
                "quote_plans row says household",
                lambda s: s.replace(
                    "Quote plans by age and ZIP, with provider",
                    "Quote household plans by age and ZIP, with provider",
                ),
                "household",
            ),
            (
                "plans",
                "quote_premiums row without self-host",
                lambda s: s.replace(
                    "Household quotes with income and subsidies require self-hosting with credentials. Not offered on the public endpoint.",
                    "Household quotes with income and subsidies, with credentials.",
                ),
                "self-host",
            ),
            (
                "plans",
                "quote_plans offered as self-host",
                lambda s: s.replace(
                    "<div><dt><code>quote_plans</code></dt>",
                    '<div data-tool-access="self-host"><dt><span>Self-host only</span><code>quote_plans</code></dt>',
                ),
                "tool inventory",
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
    mutants.extend(
        [
            (
                "plans",
                "app request posts instead of reads",
                lambda s: s.replace("curl --get", "curl --request POST"),
                "verified read-only catalog request",
            ),
            (
                "plans",
                "app request uses a household route",
                lambda s: s.replace("/v1/plans'", "/v1/premium-quotes'"),
                "verified read-only catalog request",
            ),
            (
                "plans",
                "app public scope removed",
                lambda s: s.replace(
                    "The public preview offers the catalog and quotes by age and ZIP",
                    "The public preview is unrestricted",
                ),
                "app scope",
            ),
            (
                "plans",
                "app accessible label missing",
                lambda s: s.replace('aria-labelledby="app-connect-title"', ""),
                "app connection region must be labelled",
            ),
            (
                "plans",
                "app navigation missing",
                lambda s: s.replace('href="#connect-app"', 'href="#api"'),
                "app navigation missing",
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
