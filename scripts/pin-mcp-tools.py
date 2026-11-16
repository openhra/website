#!/usr/bin/env python3
"""Copy the OpenPlans MCP tool manifest from a release commit into the website.

The website lists the tools of the released OpenPlans version, not the tools on its
development branch. Each release runs this once with the release commit and commits the
two files it writes:

- plans/data/mcp-tools.json: docs/mcp-tools.json from that commit, byte for byte;
- tools/mcp-tools-pin.json: the release and the SHA-256 of that copy.

tools/check-mcp.py fails when the copy no longer matches the pin, or when the pin names a
release other than the one the pages link.

    python3 scripts/pin-mcp-tools.py --release v0.4.9 --ref <release commit> \
        [--openplans ../openplans]
"""

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "plans/data/mcp-tools.json"
PIN = "tools/mcp-tools-pin.json"
RELEASE = re.compile(r"v\d+\.\d+\.\d+")


class PinError(Exception):
    pass


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise PinError(f"git {' '.join(args)}: {message}")
    return result.stdout


def pin_text(release, data):
    pin = {
        "schema_version": 1,
        "release": release,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return json.dumps(pin, indent=2) + "\n"


def load_checker(root):
    spec = importlib.util.spec_from_file_location(
        "check_mcp", root / "tools/check-mcp.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def pin(root, openplans, ref, release):
    """Copy the manifest at `ref` and record the pin. Returns the SHA-256 of the copy."""
    if not RELEASE.fullmatch(release):
        raise PinError(f"release must look like v1.2.3, got {release!r}")
    # Inside a larger repository OpenPlans sits in a subfolder; read paths from there.
    prefix = git(openplans, "rev-parse", "--show-prefix").decode().strip()
    commit = git(openplans, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    try:
        package = json.loads(git(openplans, "show", f"{commit}:{prefix}package.json"))
    except ValueError:
        raise PinError(f"package.json at {ref} is not JSON")
    if "v" + str(package.get("version")) != release:
        raise PinError(
            f"OpenPlans at {ref} is version {package.get('version')}, not {release}"
        )
    data = git(openplans, "show", f"{commit}:{prefix}docs/mcp-tools.json")
    try:
        load_checker(root).Tools(data.decode("utf-8"))
    except (ValueError, AssertionError, UnicodeError) as exc:
        raise PinError(f"docs/mcp-tools.json at {ref} is not a valid manifest: {exc}")
    write(root / MANIFEST, data)
    write(root / PIN, pin_text(release, data).encode())
    return hashlib.sha256(data).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--release", required=True, help="release tag, such as v0.4.9")
    parser.add_argument("--ref", required=True, help="the release commit in OpenPlans")
    parser.add_argument(
        "--openplans",
        type=Path,
        default=ROOT.parent / "openplans",
        help="OpenPlans checkout (default: ../openplans)",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        digest = pin(args.root, args.openplans, args.ref, args.release)
    except PinError as exc:
        print(f"FAIL: pin MCP tools: {exc}", file=sys.stderr)
        return 1
    print(f"pinned {MANIFEST} to {args.release} (sha256 {digest[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
