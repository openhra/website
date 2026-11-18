"""Visitor guidance for unavailable lowest-Silver results, without live requests."""

import unittest
from html.parser import HTMLParser
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "plans/lowest-silver.html"


class ResultHelp(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag = None
        self.term = ""
        self.states = {}
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("dt", "dd"):
            self.tag = tag
            if tag == "dt":
                self.term = ""

    def handle_endtag(self, tag):
        if tag == self.tag:
            self.tag = None

    def handle_data(self, text):
        self.text.append(text)
        if self.tag == "dt":
            self.term += text
        elif self.tag == "dd":
            self.states[self.term] = self.states.get(self.term, "") + text


class LowestResultCopy(unittest.TestCase):
    def check_copy(self, source):
        page = ResultHelp()
        page.feed(source)
        page.states = {
            key: " ".join(value.split()) for key, value in page.states.items()
        }
        text = " ".join(" ".join(page.text).split())
        self.assertIn("PREPARED FOR ACTIVATION", text)
        self.assertIn("awaiting operator activation", text)
        self.assertIn("A null amount means the price is unknown.", text)
        self.assertIn("Only a filed zero is $0.", text)
        self.assertIn("not the subsidy benchmark", text)
        self.assertIn("loaded catalog", page.states["no_plans"])
        self.assertIn(
            "Choose the county where the person lives",
            page.states["ambiguous / location_ambiguous"],
        )
        self.assertIn(
            "Missing data does not mean there are no plans", page.states["unknown"]
        )
        limited = page.states["location_requires_zip"]
        self.assertIn("cannot price this market, even with a ZIP", limited)
        self.assertNotRegex(
            limited.lower(),
            r"(?:re[- ]?enter|enter|provide|supply|try|choose).{0,30}zip",
        )
        self.assertIn(
            "has not been published or has expired", page.states["lowest_not_built"]
        )

    def test_result_help(self):
        self.check_copy(PAGE.read_text())

    def test_rejects_zero_zip_retry_and_live_launch_mutants(self):
        source = PAGE.read_text()
        mutants = [
            source.replace(
                "A null amount means the price is unknown.",
                "A null amount means the price is $0.",
            ),
            source.replace(
                "The amount stays unknown.", "Re-enter your ZIP to get a price."
            ),
            source.replace("The amount stays unknown.", "Try another ZIP."),
            source.replace("awaiting operator activation", "live now"),
        ]
        for mutant in mutants:
            self.assertNotEqual(mutant, source)
            with self.subTest(), self.assertRaises(AssertionError):
                self.check_copy(mutant)


if __name__ == "__main__":
    unittest.main()
