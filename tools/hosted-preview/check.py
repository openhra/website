"""Check hosted-preview copy against plans/data/hosted-preview.json.

Every block of page text that mentions the hosted preview must name each state
the snapshot lists. A sentence about the hosted preview may name another state
only to say the preview does not hold it. With --selftest, planted mutants must
fail.
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
    "plans/brand/openhra/index.html",
)
BLOCKS = {"p", "li", "dd", "td", "h1", "h2", "h3", "h4"}
NEGATION = re.compile(r"\b(?:not|unknown|no)\b", re.IGNORECASE)
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
    require(snapshot.get("schema_version") == 1, "unknown snapshot version")
    names = parse(root / "plans/index.html").options
    require(len(names) == 51, "state names missing from the plans page")
    held = {names[s] for s in snapshot["catalog_states"]}
    require(held, "snapshot lists no hosted-preview states")
    for page in PAGES:
        blocks = [b for b in parse(root / page).blocks if PREVIEW.search(b)]
        require(blocks, f"{page}: no hosted-preview statement")
        for block in blocks:
            missing = sorted(n for n in held if n not in block)
            require(not missing, f"{page}: hosted preview omits {missing}: {block}")
            for sentence in re.split(r"(?<=[.!?])\s+", block):
                if not PREVIEW.search(sentence) or NEGATION.search(sentence):
                    continue
                extra = sorted(
                    n for n in names.values() if n in sentence and n not in held
                )
                require(not extra, f"{page}: hosted preview claims {extra}")
    evidence = (
        snapshot["provider_evidence_states"] + snapshot["formulary_evidence_states"]
    )
    landing = (root / "plans/index.html").read_text(encoding="utf-8")
    require(
        bool(evidence) != ("with no provider or drug files" in landing),
        "provider and drug wording disagrees with the hosted-preview snapshot",
    )


def selftest():
    mutants = (
        (SNAPSHOT, lambda s: s.replace('"FL",', '"FL",\n    "GA",'), "omits"),
        (
            "plans/index.html",
            lambda s: s.replace(
                "holds only Texas and Florida, not Georgia.",
                "holds Texas, Florida and Georgia.",
            ),
            "claims",
        ),
        (
            "openhra/index.html",
            lambda s: s.replace(
                "The hosted preview covers Texas and Florida",
                "The hosted preview covers Texas",
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
