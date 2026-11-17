"""The release step copies the MCP tool manifest from the release commit, not from development.

Each test builds a throwaway Git repository with an OpenPlans folder: a release commit at the
version tools/mcp-tools-pin.json pins, then a development commit that adds a tool. Planted mutants of the pin script must
fail the same checks.
"""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts/pin-mcp-tools.py"
CHECKER = "tools/check-mcp.py"
MANIFEST = "plans/data/mcp-tools.json"
PIN = "tools/mcp-tools-pin.json"
# The checker only accepts a pin for the release the pages link, so the fixture uses that one.
RELEASE = json.loads((ROOT / PIN).read_text(encoding="utf-8"))["release"]
VERSION = RELEASE[1:]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def head(repo):
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class Fixture:
    """A website copy and a Git repository whose OpenPlans folder has two commits."""

    def __init__(self, base, script_source, prefix="openplans"):
        self.website = base / "website"
        for name in (SCRIPT, CHECKER):
            (self.website / name).parent.mkdir(parents=True, exist_ok=True)
        (self.website / SCRIPT).write_text(script_source, encoding="utf-8")
        shutil.copy2(ROOT / CHECKER, self.website / CHECKER)
        shutil.copy2(ROOT / PIN, self.website / PIN)
        (self.website / MANIFEST).parent.mkdir(parents=True)
        self.repo = base / "repo"
        self.openplans = self.repo / prefix if prefix else self.repo
        (self.openplans / "docs").mkdir(parents=True)
        git(self.repo, "init", "--quiet")

        self.released = (ROOT / MANIFEST).read_bytes()
        data = json.loads(self.released)
        data["tools"].append(
            {**data["tools"][0], "name": "planted_develop_tool", "title": "Planted"}
        )
        self.develop = (json.dumps(data, indent=2) + "\n").encode()

        self.commit(self.released, VERSION)
        self.release = head(self.repo)
        self.commit(self.develop, VERSION)

    def commit(self, manifest, version):
        (self.openplans / "docs/mcp-tools.json").write_bytes(manifest)
        (self.openplans / "package.json").write_text(
            json.dumps({"name": "openplans", "version": version}) + "\n"
        )
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "--quiet", "-m", "fixture " + version)

    def pin(self, release, ref):
        return subprocess.run(
            [
                sys.executable,
                str(self.website / SCRIPT),
                "--release",
                release,
                "--ref",
                ref,
                "--openplans",
                str(self.openplans),
                "--root",
                str(self.website),
            ],
            capture_output=True,
            text=True,
            check=False,
        )


def release_copy_problems(script_source, prefix="openplans"):
    """Run the release step in a fixture and list everything it got wrong."""
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Fixture(Path(tmp), script_source, prefix)
        result = fixture.pin(RELEASE, fixture.release)
        if result.returncode:
            return ["release pin failed: " + result.stderr.strip()]
        copy = (fixture.website / MANIFEST).read_bytes()
        if copy != fixture.released:
            problems.append("copy is not the release commit's manifest")
        pin = json.loads((fixture.website / PIN).read_text(encoding="utf-8"))
        if pin != {
            "schema_version": 1,
            "release": RELEASE,
            "sha256": hashlib.sha256(fixture.released).hexdigest(),
        }:
            problems.append("pin does not record the release copy")
        checker = load(fixture.website / CHECKER, "check_mcp_fixture")
        try:
            checker.check_pin(copy, json.dumps(pin))
        except ValueError as exc:
            problems.append("gate rejects the release copy: " + str(exc))
        if not checker.source_note(copy, fixture.develop):
            problems.append("development ahead of the release gives no note")

        before = {p: (fixture.website / p).read_bytes() for p in (MANIFEST, PIN)}
        wrong = fixture.pin("v0.5.0", fixture.release)
        if wrong.returncode == 0 or "not v0.5.0" not in wrong.stderr:
            problems.append("a release commit at another version was accepted")
        if any((fixture.website / p).read_bytes() != b for p, b in before.items()):
            problems.append("a refused pin changed the website files")
    return problems


class PinMcpToolsTest(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / SCRIPT).read_text(encoding="utf-8")

    def test_copies_the_release_commit(self):
        self.assertEqual(release_copy_problems(self.source), [])

    def test_standalone_openplans_repository(self):
        self.assertEqual(release_copy_problems(self.source, prefix=""), [])

    def test_rejects_an_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.source)
            before = (fixture.website / PIN).read_bytes()
            fixture.commit(b'{"schema_version": 1, "tools": []}\n', "0.5.0")
            result = fixture.pin("v0.5.0", "HEAD")
            self.assertEqual(result.returncode, 1)
            self.assertIn("not a valid manifest", result.stderr)
            self.assertEqual((fixture.website / PIN).read_bytes(), before)
            self.assertFalse((fixture.website / MANIFEST).exists())

    def test_rejects_a_malformed_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Fixture(Path(tmp), self.source)
            result = fixture.pin(VERSION, fixture.release)
            self.assertEqual(result.returncode, 1)
            self.assertIn("v1.2.3", result.stderr)

    def test_planted_mutants_fail(self):
        mutants = {
            "copies the working tree instead of the release commit": (
                'git(openplans, "show", f"{commit}:{prefix}docs/mcp-tools.json")',
                '(Path(openplans) / "docs/mcp-tools.json").read_bytes()',
                "copy is not the release commit's manifest",
            ),
            "skips the version check": (
                'if "v" + str(package.get("version")) != release:',
                "if False:",
                "another version was accepted",
            ),
            "records a hash of nothing": (
                '"sha256": hashlib.sha256(data).hexdigest(),',
                '"sha256": hashlib.sha256(b"").hexdigest(),',
                "pin does not record the release copy",
            ),
        }
        for name, (old, new, expected) in mutants.items():
            with self.subTest(name):
                self.assertEqual(self.source.count(old), 1, "mutant site moved")
                problems = release_copy_problems(self.source.replace(old, new))
                self.assertTrue(
                    any(expected in p for p in problems),
                    f"mutant survived: {name}: {problems}",
                )


if __name__ == "__main__":
    unittest.main()
