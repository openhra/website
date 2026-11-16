#!/usr/bin/env python3
"""Keep the public MCP preview honest and repository actions first."""

import argparse
import hashlib
import json
import re
import shlex
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://openplans.openhra.com/mcp"
REPO = "https://github.com/openhra/openplans"
RELEASE = "v0.4.11"
RELEASE_URL = REPO + "/releases/tag/" + RELEASE
# Owner rule: public pages never compare OpenPlans with another service.
# The banned words are split so they never appear whole in this public file.
FORBIDDEN_COMPARISON = re.compile(
    r"com" + r"mercial[\s_-]+reference|reference[\s_-]+" + r"api\b|par" + r"ity\s+with",
    re.IGNORECASE,
)
# The tool list comes from OpenPlans: docs/mcp-tools.json, generated from its code. Each
# release copies it, from the release commit, to plans/data/mcp-tools.json with
# scripts/pin-mcp-tools.py, which records the release and the copy's SHA-256 in PIN.
# No tool name is written here.
MANIFEST = "plans/data/mcp-tools.json"
PIN = "tools/mcp-tools-pin.json"
# The plugin the hosted preview loads; its tools count toward the hosted total.
HOSTED_PLUGINS = {"@openplans/plugin-status"}
# Owner, 2026-11-09: every tool is available by default, household quotes included.
HOUSEHOLD_TOOL = "quote_premiums"
# Restriction labels the owner removed; no page may show them again.
RESTRICTION_LABEL = re.compile(
    r"self[- ]?host(?:ed|ing)?[- ]only|need(?:s)? self-hosting|require(?:s)? self-hosting"
    r"|not offered on the public endpoint|not available on the public endpoint"
)
# Old household names, removed from the product; pages must not offer them.
REMOVED_NAMES = ("estimate_premiums", "premium-estimates")
# Income and subsidies belong to household quotes, never to quote_plans.
HOUSEHOLD_TERMS = re.compile(r"household|income|subsid")


class Tools:
    """The MCP tools named in the manifest, split the way the pages describe them."""

    def __init__(self, text):
        data = json.loads(text)
        require(
            isinstance(data, dict) and data.get("schema_version") == 1,
            "tool manifest schema_version must be 1",
        )
        tools = data.get("tools")
        require(isinstance(tools, list) and tools, "tool manifest lists no tools")
        names = []
        for tool in tools:
            require(
                isinstance(tool, dict)
                and all(
                    isinstance(tool.get(key), str) and tool[key].strip()
                    for key in ("name", "title", "description")
                )
                and "\n" not in tool["description"]
                and (tool.get("kind"), tool.get("listed"))
                in {("core", "always"), ("core", "switched"), ("plugin", "plugin")}
                and (tool["kind"] == "plugin") == isinstance(tool.get("plugin"), str),
                "tool manifest entry malformed: " + str(tool.get("name")),
            )
            names.append(tool["name"])
        require(len(names) == len(set(names)), "tool manifest repeats a tool")
        # Core tools every server lists; the hosted preview adds its plugins' tools.
        self.core = {t["name"] for t in tools if t["listed"] == "always"}
        self.plugin = {
            t["name"]
            for t in tools
            if t["kind"] == "plugin" and t["plugin"] in HOSTED_PLUGINS
        }
        self.switched = {t["name"] for t in tools if t["listed"] == "switched"}
        self.hosted = len(self.core) + len(self.plugin)


def read_tools(root):
    return Tools((root / MANIFEST).read_text(encoding="utf-8"))


def hosted_tool_names(root=ROOT):
    """Every tool the hosted preview lists: the core tools and its plugins' tools."""
    tools = read_tools(root)
    return tools.core | tools.plugin


def check_pin(copy, pin_text):
    """The copy is the one the last release pinned, for the release the pages link."""
    try:
        pin = json.loads(pin_text)
    except ValueError:
        pin = None
    require(
        isinstance(pin, dict)
        and pin.get("schema_version") == 1
        and isinstance(pin.get("release"), str)
        and isinstance(pin.get("sha256"), str),
        f"{PIN} malformed",
    )
    require(
        pin["release"] == RELEASE,
        f"{MANIFEST} is pinned for {pin['release']}, but the pages link {RELEASE};"
        " run scripts/pin-mcp-tools.py with the release commit",
    )
    have = hashlib.sha256(copy).hexdigest()
    require(
        have == pin["sha256"],
        f"{MANIFEST} differs from the copy pinned for {RELEASE}"
        f" (sha256 {have[:12]}, pinned {pin['sha256'][:12]}); it changes only in a"
        " release, through scripts/pin-mcp-tools.py",
    )


def source_note(copy, source):
    """OpenPlans development may be ahead of the release; the site keeps the release's list."""
    if copy == source:
        return None
    return (
        f"mcp: note: OpenPlans docs/mcp-tools.json (sha256"
        f" {hashlib.sha256(source).hexdigest()[:12]}) differs from the {RELEASE} copy."
        " The site lists the released tools; the next release pins the new list."
    )


# "15 core tools", "15 read-only core tools", "15 tools and get_status" count the core tools.
# Any other "N tools" or "N read-only tools" counts everything the hosted preview lists.
TOOL_COUNT = re.compile(r"\b(\d+) (read-only )?(core )?tools?\b( and ([a-z_]+))?")


def check_counts(text, tools):
    for match in TOOL_COUNT.finditer(text):
        count = int(match[1])
        if match[3] or (match[5] and match[5] in tools.plugin):
            expected, what = len(tools.core), "core"
        else:
            expected, what = tools.hosted, "hosted"
        require(
            count == expected,
            f"tool count claim '{match[0]}' differs from the manifest:"
            f" {expected} {what} tools",
        )


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
                "48 states and dc for 2026",
                "29 states for 2027",
                "status: unknown",
                "no account or api key",
                "post /v1/premium-quotes",
                "subsidy estimates",
                "does not log request bodies, income, ages or zip codes",
            )
        ),
        "app scope or household quote route missing",
    )
    commands = section.find(lambda n: n.tag == "pre")
    require(len(commands) == 3, "app base path or requests missing")
    require(
        commands[0].text() == "https://openplans.openhra.com/v1",
        "app base path differs",
    )
    # Hosted-preview examples must name ZIPs the preview serves: a Texas ZIP for 2026 and a
    # Florida ZIP for 2027, both listed for those years in plans/data/hosted-preview.json.
    for command, zip_code, year in (
        (commands[1], "77002", "2026"),
        (commands[2], "33101", "2027"),
    ):
        require(
            shlex.split(command.text().replace("\\\n", " "))
            == [
                "curl",
                "--get",
                "https://openplans.openhra.com/v1/plans",
                "--data-urlencode",
                "zip=" + zip_code,
                "--data-urlencode",
                "year=" + year,
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


def check_page(source, site, tools):
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
    require(
        not RESTRICTION_LABEL.search(normalized(source)),
        "removed restriction label: household quotes are public",
    )
    require(
        "data-tool-access" not in source,
        "removed restriction label: tool access groups are gone",
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
    if site == "plans":
        # The plans page names each tool the hosted preview adds through a plugin.
        for name in sorted(tools.plugin):
            require(
                any(
                    visible(n)
                    for n in mcp[0].find(
                        lambda n, name=name: n.tag == "code" and n.text() == name
                    )
                ),
                "hosted plugin tool missing: " + name,
            )
    check_counts(claims, tools)
    require(
        not re.search(r"\b(?:stable|production(?:[ -]ready)?)\b", claims),
        "unsupported release claim",
    )
    require(
        RELEASE.lower() in claims,
        "v0.4.11 release status missing",
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
            "release status must link to v0.4.11",
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
                "quotes by age and zip",
                "household quotes",
                "hosted preview",
                "48 states and dc for 2026",
                "29 states for 2027",
                f"{len(tools.core)} tools",
                "where their data is loaded",
            ]
        ),
        "catalog scope or loaded-data limit missing",
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
        if "quote_plans" in text:
            require(
                "household" not in text, "quote_plans described as a household quote"
            )
    household = mcp[0].find(lambda n: n.tag == "code" and n.text() == HOUSEHOLD_TOOL)
    require(
        household and all(visible(n) for n in household),
        "public quote_premiums missing",
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
        public = []
        for group in directory.children:
            codes = group.find(lambda n: n.tag == "code")
            names = [
                n.text()
                for n in group.find(lambda n: n.tag == "dt")[0].find(
                    lambda n: n.tag == "code"
                )
            ]
            require(all(visible(n) for n in codes), "tool inventory hidden")
            require(
                len(names) == len(codes),
                "tool inventory mentions a tool outside its name",
            )
            public.extend(names)
            quoted = normalized(group.text())
            if "quote_plans" in names:
                require(
                    "household" not in quoted
                    and not re.search(r"income|subsid", quoted),
                    "quote_plans described as a household quote",
                )
            if HOUSEHOLD_TOOL in names:
                require(
                    "income" in quoted and "texas 2026" in quoted,
                    "quote_premiums row must state income and the checked scope",
                )
        require(
            len(public) == len(tools.core) and set(public) == tools.core,
            f"tool inventory must contain exactly the {len(tools.core)} core tools"
            f" in {MANIFEST}",
        )
        require(
            mcp[0].find(
                lambda n: n.tag == "a" and n.attrs.get("href") == "/" + MANIFEST[6:]
            ),
            "link to the tool manifest missing",
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


def run(root, source=None):
    tools = read_tools(root)
    copy = (root / MANIFEST).read_bytes()
    check_pin(copy, (root / PIN).read_text(encoding="utf-8"))
    note = None if source is None else source_note(copy, source.read_bytes())
    if note:
        print(note)
    for site in ["openhra", "plans"]:
        check_page((root / site / "index.html").read_text(), site, tools)
    require(
        (root / "openhra/brand/site.css").read_bytes()
        == (root / "plans/brand/site.css").read_bytes(),
        "shared site styles differ",
    )
    # openhra/ is the only source of the organisation page. A copy under the
    # plans root would be served on the plans host with the wrong stylesheet.
    require(
        not (root / "plans/brand/openhra").exists(),
        "organisation page copied into the plans site",
    )
    require(
        (root / "openhra/favicon.svg").read_bytes()
        == (root / "plans/brand/favicon-openhra.svg").read_bytes(),
        "organisation favicon copy differs",
    )
    require(
        (root / "openhra/mcp-copy.js").read_bytes()
        == (root / "plans/mcp-copy.js").read_bytes(),
        "clipboard scripts differ",
    )
    print(
        "mcp: PASS (v0.4.11 release link, no comparison text, Public preview, live catalog and quote endpoint,"
        f" {len(tools.core)} core tools and {len(tools.plugin)} plugin tool(s) from {MANIFEST}"
        + f", copy pinned for {RELEASE}"
        + (", same as OpenPlans" if source is not None and not note else "")
        + ", household quotes, no restriction labels, GitHub-first, no organisation page copy on the plans site)"
    )


def selftest(root):
    tools = read_tools(root)
    manifest = (root / MANIFEST).read_text(encoding="utf-8")
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
                        "Catalog, quotes by age and ZIP and household quotes ·",
                        "All data ·",
                    ),
                    "catalog scope",
                ),
                (
                    site,
                    "wrong states",
                    lambda s: s.replace("48 states and DC", "All states"),
                    "catalog scope",
                ),
                (
                    site,
                    "wrong years",
                    lambda s: s.replace("29 states for 2027 ·", "29 states for 2025 ·"),
                    "catalog scope",
                ),
                (
                    site,
                    "wrong public tool count",
                    lambda s: s.replace("15 tools", "12 tools"),
                    "tool count claim",
                ),
                (
                    site,
                    "hero counts only the core tools",
                    lambda s: s.replace(
                        "through 16 read-only tools", "through 15 read-only tools"
                    ),
                    "tool count claim",
                ),
                (
                    site,
                    "wrong core tool count",
                    lambda s: s.replace("15 core tools", "14 core tools"),
                    "tool count claim",
                ),
                (
                    site,
                    "loaded-data limit removed",
                    lambda s: s.replace(
                        "Other states answer where their data is loaded.", ""
                    ),
                    "loaded-data limit",
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
                    "v0.4.11 link removed",
                    lambda s: s.replace(RELEASE_URL, REPO),
                    "release status must link to v0.4.11",
                ),
                (
                    site,
                    "v0.4.11 status text removed",
                    lambda s: s.replace(RELEASE + "</a>", "Release</a>"),
                    "release status must link to v0.4.11",
                ),
                (
                    site,
                    "status links elsewhere",
                    lambda s: s.replace(
                        '<a href="' + RELEASE_URL + '">' + RELEASE,
                        '<a href="https://example.invalid/">' + RELEASE,
                    ),
                    "release status must link to v0.4.11",
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
                    "household tool removed",
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
                    "self-host only label restored",
                    lambda s: s.replace(
                        "Coverage is limited.",
                        "Coverage is limited. Household quotes are Self-host only.",
                    ),
                    "removed restriction label",
                ),
                (
                    site,
                    "restriction restored in metadata",
                    lambda s: s.replace(
                        'name="description" content="',
                        'name="description" content="Household quotes need self-hosting. ',
                    ),
                    "removed restriction label",
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
                    "household tool withdrawn from the endpoint",
                    lambda s: s.replace(
                        "Coverage is limited.",
                        "Coverage is limited. quote_premiums is not offered on the public endpoint.",
                    ),
                    "removed restriction label",
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
            "Com" + "pared with a Com" + "mercial-Reference catalog.",
            "Matches the reference_" + "API totals.",
            "Built for par" + "ity\twith another service.",
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
                    "</body>", "<!-- com" + "mercial_reference check --></body>"
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
                "hosted plugin tool unnamed",
                lambda s: (
                    s.replace(
                        '<p class="endpoint-note"><code>get_status</code>',
                        '<p class="endpoint-note">The status tool',
                    )
                    .replace(
                        "The public instance also offers <code>get_status</code>.", ""
                    )
                    .replace("15 tools and <code>get_status</code>", "15 core tools")
                ),
                "hosted plugin tool missing",
            ),
            (
                "plans",
                "manifest link removed",
                lambda s: s.replace('href="/data/mcp-tools.json"', 'href="#mcp"'),
                "link to the tool manifest",
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
                "household tool dropped from the inventory",
                lambda s: s.replace(
                    "<div><dt><code>check_ichra_affordability</code></dt>",
                    "<div><dt><code>search_plans</code></dt>",
                ),
                "tool inventory",
            ),
            (
                "plans",
                "quote_plans row claims a subsidy",
                lambda s: s.replace(
                    "Quote plans by age and ZIP, with provider",
                    "Quote plans by age and ZIP with a subsidy, with provider",
                ),
                "household quote",
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
                "quote_premiums row loses its checked scope",
                lambda s: s.replace(
                    "Subsidy figures are checked against source for Texas 2026 so far. ",
                    "",
                ),
                "checked scope",
            ),
            (
                "plans",
                "self-host access group restored",
                lambda s: s.replace(
                    "<div><dt><code>quote_premiums</code></dt>",
                    '<div data-tool-access="self-host"><dt><code>quote_premiums</code></dt>',
                ),
                "removed restriction label",
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
                "app example uses a state the preview does not hold",
                lambda s: s.replace("'zip=33101'", "'zip=30301'"),
                "verified read-only catalog request",
            ),
            (
                "plans",
                "app unknown-state answer removed",
                lambda s: s.replace(
                    "returns <code>status: unknown</code>", "returns plans"
                ),
                "app scope",
            ),
            (
                "plans",
                "app public scope removed",
                lambda s: s.replace(
                    "It offers the catalog, quotes by age and ZIP and household quotes.",
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
            check_page(mutated, site, tools)
        except (ValueError, AssertionError) as exc:
            require(
                diagnostic in str(exc),
                "unexpected mutant diagnostic: " + name + ": " + str(exc),
            )
            print("mcp negative: PASS (" + name + ")")
        else:
            raise ValueError("mutant accepted: " + name)

    manifest_selftest(sources, manifest)
    pin_selftest(root)


def with_tool(manifest, **fields):
    data = json.loads(manifest)
    data["tools"].append({**data["tools"][0], **fields})
    return json.dumps(data)


def manifest_selftest(sources, manifest):
    """The pages stay as they are; a changed manifest must make them fail."""
    data = json.loads(manifest)
    without_plugin = json.dumps(
        {**data, "tools": [t for t in data["tools"] if t["kind"] != "plugin"]}
    )
    mutants = [
        (
            "extra core tool",
            with_tool(manifest, name="planted_extra_tool"),
            "tool count claim",
        ),
        ("hosted plugin tool removed", without_plugin, "tool count claim"),
        (
            "plugin tool without its plugin",
            with_tool(manifest, name="planted_plugin_tool", kind="plugin"),
            "malformed",
        ),
        (
            "unknown listing",
            with_tool(manifest, name="planted_tool", listed="sometimes"),
            "malformed",
        ),
        (
            "repeated tool",
            with_tool(manifest),
            "repeats a tool",
        ),
        (
            "multi-line description",
            with_tool(manifest, name="x", description="a\nb"),
            "malformed",
        ),
    ]
    for name, text, diagnostic in mutants:
        try:
            tools = Tools(text)
            for site in ["openhra", "plans"]:
                check_page(sources[site], site, tools)
        except (ValueError, KeyError) as exc:
            require(
                diagnostic in str(exc),
                "unexpected manifest mutant diagnostic: " + name + ": " + str(exc),
            )
            print("mcp manifest negative: PASS (" + name + ")")
        else:
            raise ValueError("manifest mutant accepted: " + name)
    # Counts updated for a new core tool, directory not: the inventory check must fail.
    tools = Tools(with_tool(manifest, name="planted_extra_tool"))
    core, hosted = len(tools.core), tools.hosted
    page = sources["plans"]
    for before, after in (
        (f"{hosted - 1} read-only tools", f"{hosted} read-only tools"),
        (f"{core - 1} read-only core tools", f"{core} read-only core tools"),
        (f"{core - 1} core tools", f"{core} core tools"),
        (f"{core - 1} tools and", f"{core} tools and"),
    ):
        page = page.replace(before, after)
    try:
        check_page(page, "plans", tools)
    except ValueError as exc:
        require(
            "tool inventory" in str(exc), "unexpected directory diagnostic: " + str(exc)
        )
        print("mcp manifest negative: PASS (directory without the new tool)")
    else:
        raise ValueError("manifest mutant accepted: directory without the new tool")


def pin_selftest(root):
    """A copy changed outside a release, or a pin for another release, must fail."""
    copy = (root / MANIFEST).read_bytes()
    pin_text = (root / PIN).read_text(encoding="utf-8")
    pin = json.loads(pin_text)
    check_pin(copy, pin_text)
    ahead = with_tool(copy.decode(), name="planted_develop_tool").encode()
    require(
        source_note(copy, copy) is None and "differs" in source_note(copy, ahead),
        "OpenPlans ahead of the release must be a note",
    )
    print("mcp pin: PASS (OpenPlans ahead of the release is a note, not a failure)")
    mutants = [
        ("copy taken from OpenPlans development", ahead, pin_text, "differs from"),
        (
            "pin for an older release",
            copy,
            json.dumps({**pin, "release": "v0.0.1"}),
            "pinned for v0.0.1",
        ),
        ("pin without a hash", copy, json.dumps({**pin, "sha256": None}), "malformed"),
        ("pin not JSON", copy, "{", "malformed"),
    ]
    for name, data, text, diagnostic in mutants:
        try:
            check_pin(data, text)
        except ValueError as exc:
            require(
                diagnostic in str(exc),
                "unexpected pin mutant diagnostic: " + name + ": " + str(exc),
            )
            print("mcp pin negative: PASS (" + name + ")")
        else:
            raise ValueError("pin mutant accepted: " + name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument(
        "--source",
        type=Path,
        help="OpenPlans docs/mcp-tools.json; a difference from the pinned release copy"
        " is reported as a note",
    )
    args = parser.parse_args()
    try:
        run(args.root, args.source)
        if args.selftest:
            selftest(args.root)
    except (ValueError, KeyError, IndexError) as exc:
        raise SystemExit("FAIL: MCP presentation: " + str(exc))
