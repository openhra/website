"""The ask page: counts built from a data-availability body equal the body."""

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build-ask.py"
FIXTURE = ROOT / "tests" / "fixtures" / "data-availability.json"
SHIPPED = ROOT / "plans" / "data" / "ask" / "ask.json"
PAGE = ROOT / "plans" / "ask.html"
LIVE = Path(os.environ.get("ASK_LIVE_BODY", "live-body.json"))

FAMILIES = {
    "premiums": "premium_status",
    "benefits": "catalog_status",
    "drugs": "drug_status",
    "providers": "provider_status",
}
ANSWERED = {"available", "complete"}


def build(body_path, tmp, *flags):
    out = Path(tmp) / "ask.json"
    subprocess.run(
        [
            "python3",
            "-I",
            str(BUILD),
            str(body_path),
            str(out),
            "--fetched-at",
            "2026-11-24T14:08:03Z",
            "--source-url",
            "https://example.invalid/v1/data-availability",
            *flags,
        ],
        check=True,
    )
    return json.loads(out.read_text())


def expected(body, family, state=None, year=None):
    """Counts straight from the body, written independently of build-ask.py."""
    key = FAMILIES[family]
    got = [0, 0, 0, 0]
    for row in body:
        if (state and row["state"] != state) or (year and row["plan_year"] != year):
            continue
        value = row.get(key) or "unknown"
        got[
            0
            if value in ANSWERED
            else 1
            if value == "partial"
            else 2
            if value == "unsupported"
            else 3
        ] += 1
    return got


def counts_from(data, family, state=None, year=None):
    got = [0, 0, 0, 0]
    for r in data["rows"]:
        if (
            r["family"] != family
            or (state and r["state"] != state)
            or (year and r["year"] != year)
        ):
            continue
        for i, k in enumerate(("answered", "partial", "unsupported", "unknown")):
            got[i] += r[k]
    return got


def page_counts(data, state, year):
    """The page's own summarize function, run under node."""
    js = (
        "require('vm').runInThisContext(require('fs').readFileSync(process.argv[1],'utf8'));const {summarize}=globalThis.askPage;"
        "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "console.log(JSON.stringify(summarize(d,process.argv[2],process.argv[3])));"
    )
    out = subprocess.run(
        ["node", "-e", js, str(ROOT / "plans" / "ask.js"), state, year],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {
        f["id"]: [f["answered"], f["partial"], f["unsupported"], f["unknown"]]
        for f in json.loads(out)
    }


class AskPage(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_fixture_is_synthetic_and_covers_every_status(self):
        body = json.loads(FIXTURE.read_text())
        self.assertEqual(len(body), 20)
        self.assertTrue(all(r["synthetic"] is True for r in body))
        seen = {
            r[k]
            for r in body
            for k in ("catalog_status", "premium_status", "provider_status")
        }
        for value in (
            "available",
            "partial",
            "unknown",
            "unavailable",
            "unsupported",
            "stale",
            "conflicted",
            "not_yet_verified",
        ):
            self.assertIn(value, seen)
        drugs = {r["drug_status"] for r in body}
        for value in ("complete", "partial", "failed", "access_denied", "unknown"):
            self.assertIn(value, drugs)

    def test_counts_equal_the_body(self):
        body = json.loads(FIXTURE.read_text())
        data = build(FIXTURE, self.tmp.name, "--synthetic")
        self.assertTrue(data["synthetic"])
        for family in FAMILIES:
            self.assertEqual(counts_from(data, family), expected(body, family), family)
            self.assertEqual(sum(expected(body, family)), len(body))
            for state in {r["state"] for r in body}:
                for year in {r["plan_year"] for r in body}:
                    self.assertEqual(
                        counts_from(data, family, state, year),
                        expected(body, family, state, year),
                        (family, state, year),
                    )

    def test_page_summary_equals_the_body(self):
        body = json.loads(FIXTURE.read_text())
        data = build(FIXTURE, self.tmp.name, "--synthetic")
        for state, year in (
            ("ALL", "ALL"),
            ("TX", "ALL"),
            ("ALL", "2027"),
            ("NY", "2026"),
        ):
            shown = page_counts(data, state, year)
            for family in FAMILIES:
                self.assertEqual(
                    shown[family],
                    expected(
                        body,
                        family,
                        None if state == "ALL" else state,
                        None if year == "ALL" else int(year),
                    ),
                    (family, state, year),
                )

    def test_unmapped_reason_is_shown_as_its_code(self):
        data = build(FIXTURE, self.tmp.name, "--synthetic")
        self.assertIn(
            "made_up_code_for_test", {c for r in data["rows"] for c in r["reasons"]}
        )
        self.assertNotIn("made_up_code_for_test", data["reason_words"])
        js = "require('vm').runInThisContext(require('fs').readFileSync(process.argv[1],'utf8'));const {words}=globalThis.askPage;console.log(words({a:'A'},'zz'),words({a:'A'},'a'))"
        out = subprocess.run(
            ["node", "-e", js, str(ROOT / "plans" / "ask.js")],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(out.split(), ["zz", "A"])

    def test_shipped_file_is_real_or_empty(self):
        data = json.loads(SHIPPED.read_text())
        if data["rows"]:
            self.assertFalse(data["synthetic"], "synthetic rows must not ship")
            self.assertTrue(data["fetched_at"] and data["source_url"])

    def test_page_wording(self):
        text = PAGE.read_text(encoding="utf-8") + (ROOT / "plans" / "ask.js").read_text(
            encoding="utf-8"
        )
        # Fragments are joined here so this file holds none of the phrases it rejects.
        words = (
            "par" + "ity",
            "compared" + r"\s+(?:with|against)",
            "reference" + r"\s+(?:API|service)",
            "commer" + "cial",
            "not" + r"\s+covered",
        )
        for pattern in (
            *(r"\b" + w + r"\b" if i == 0 else w for i, w in enumerate(words)),
            r"[\w.+-]+@[\w-]+\.[a-z]{2,}",
        ):
            self.assertIsNone(re.search(pattern, text, re.IGNORECASE), pattern)

    @unittest.skipUnless(LIVE.is_file(), "no live body saved")
    def test_live_body_counts(self):
        try:
            body = json.loads(LIVE.read_text())
        except ValueError:
            self.skipTest("saved live body is not JSON")
        data = build(LIVE, self.tmp.name)
        for family in FAMILIES:
            got = counts_from(data, family)
            self.assertEqual(got, expected(body, family))
            print(
                f"live {family}: answered {got[0]} partial {got[1]} unsupported {got[2]} unknown {got[3]} of {len(body)}"
            )


if __name__ == "__main__":
    unittest.main()
