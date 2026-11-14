"""Check hosted-preview copy against plans/data/hosted-preview.json.

Every hosted-preview block must give the year-specific scope counts. The snapshot
lists each state separately by year, so a 2026 catalog never implies 2027 support.
With --selftest, planted mutants must fail.
"""

import html.parser
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = "plans/data/hosted-preview.json"
PAGES = (
    "plans/index.html",
    "plans/availability.html",
    "openhra/index.html",
)
BLOCKS = {"p", "li", "dd", "td", "h1", "h2", "h3", "h4"}
PREVIEW = re.compile(r"hosted preview", re.IGNORECASE)


class Blocks(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.depth, self.text = [], 0, []
        self.options = {}
        self.option = None

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self.option = dict(attrs).get("value")
        if tag in BLOCKS:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "option":
            self.option = None
        if tag in BLOCKS and self.depth:
            self.depth -= 1
            if not self.depth:
                self.blocks.append(" ".join("".join(self.text).split()))
                self.text = []

    def handle_data(self, data):
        if self.option and re.fullmatch("[A-Z]{2}", self.option):
            self.options[self.option] = data.strip()
        if self.depth:
            self.text.append(data)


def parse(path):
    parser = Blocks()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check(root=ROOT):
    snapshot = json.loads((root / SNAPSHOT).read_text(encoding="utf-8"))
    require(snapshot.get("schema_version") == 2, "unknown snapshot version")
    names = parse(root / "plans/index.html").options
    require(len(names) == 51, "state names missing from the plans page")
    scopes = snapshot["catalog_states_by_year"]
    require(set(scopes) == {"2026", "2027"}, "unexpected catalog years")
    for year, states in scopes.items():
        require(
            states and len(set(states)) == len(states) and set(states) <= names.keys(),
            f"invalid scopes for {year}",
        )
    counts = []
    for year, states in scopes.items():
        count = len(states) - ("DC" in states)
        counts.append(
            f"{count} states" + (" and DC" if "DC" in states else "") + f" for {year}"
        )
    summary = " and ".join(counts)
    for page in PAGES:
        blocks = [b for b in parse(root / page).blocks if PREVIEW.search(b)]
        require(blocks, f"{page}: no hosted-preview statement")
        for block in blocks:
            require(
                summary in block,
                f"{page}: hosted preview omits year-specific scopes: {block}",
            )
            require(
                not re.search(r"\b(?:all states|every state)\b", block, re.IGNORECASE),
                f"{page}: hosted preview claims every state",
            )
    evidence = (
        snapshot["provider_evidence_states"] + snapshot["formulary_evidence_states"]
    )
    landing = (root / "plans/index.html").read_text(encoding="utf-8")
    require(
        bool(evidence) != ("with no provider or drug files" in landing),
        "provider and drug wording disagrees with the hosted-preview snapshot",
    )


def selftest():
    from reduce import reduce as reduce_availability

    # Synthetic availability rows: one year must never authorize another.
    rows = [
        {
            "state": state,
            "plan_year": year,
            "catalog_status": status,
            "provider_status": "unknown",
            "formulary_status": "unknown",
        }
        for state, year, status in [
            ("CA", 2026, "available"),
            ("TX", 2026, "available"),
            ("TX", 2027, "available"),
            ("GA", 2027, "quarantined"),
        ]
    ]
    reduced = reduce_availability(rows, "2026-11-10")
    require(
        reduced["catalog_states_by_year"] == {"2026": ["CA", "TX"], "2027": ["TX"]},
        "availability reducer crossed state/year boundaries",
    )
    require(
        reduced["schema_version"] == 2 and reduced["status"] == "observed",
        "reducer metadata missing",
    )
    mutants = (
        (SNAPSHOT, lambda s: s.replace('"AK",', "", 1), "omits"),
        (
            "plans/index.html",
            lambda s: s.replace(
                "Georgia is available for 2026;",
                "The hosted preview covers every state. Georgia is available for 2026;",
            ),
            "claims",
        ),
        (
            "openhra/index.html",
            lambda s: s.replace(
                "48 states and DC for 2026", "47 states and DC for 2026"
            ),
            "omits",
        ),
        (
            SNAPSHOT,
            lambda s: s.replace(
                '"provider_evidence_states": []', '"provider_evidence_states": ["TX"]'
            ),
            "provider and drug",
        ),
        (
            "plans/availability.html",
            lambda s: s.replace("hosted preview", "public endpoint"),
            "no hosted-preview statement",
        ),
    )
    for name, mutate, expected in mutants:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            for item in {Path(p).parent for p in PAGES} | {Path(SNAPSHOT).parent}:
                shutil.copytree(ROOT / item, dest / item, dirs_exist_ok=True)
            target = dest / name
            before = target.read_text(encoding="utf-8")
            target.write_text(mutate(before), encoding="utf-8")
            require(
                target.read_text(encoding="utf-8") != before,
                f"no-op mutant: {expected}",
            )
            try:
                check(dest)
            except AssertionError as exc:
                require(
                    expected in str(exc), f"mutant failed for another reason: {exc}"
                )
                print(f"hosted-preview negative: PASS ({expected}, {name})")
                continue
            raise AssertionError(f"mutant passed: {expected} in {name}")


def main():
    try:
        check()
        if "--selftest" in sys.argv[1:]:
            selftest()
    except AssertionError as exc:
        print(f"FAIL: hosted preview copy: {exc}")
        return 1
    print("hosted preview copy: PASS (pages agree with plans/data/hosted-preview.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
