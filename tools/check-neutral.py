#!/usr/bin/env python3
"""Audit every publishable file, including files not yet in a destination's index."""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from public_paths import artifact_files, selected_files


def check(root, artifact=False):
    if not root.is_dir():
        raise ValueError("public tree must be a directory")
    policy = os.environ.get("OPENPLANS_DENYLIST_FILE")
    terms = []
    if policy:
        try:
            terms = [
                re.compile(line.strip(), re.I)
                for line in Path(policy).read_text().splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        except (OSError, UnicodeError, re.error):
            raise ValueError("cannot read or compile publication denylist")
        if not terms:
            raise ValueError("publication denylist must contain at least one pattern")
    # Split the host path markers so this checker contains no forbidden literal.
    private = re.compile("/" + r"(?:Volumes|Users)/", re.I)
    email = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
    count = 0
    files = artifact_files(root) if artifact else selected_files(root)
    for path in files:
        relative = path.relative_to(root).as_posix()
        content = relative + "\n" + path.read_bytes().decode("utf-8", errors="replace")
        # Do not disclose matched content, filenames or policy terms.
        if private.search(content):
            raise ValueError("private host path found in public tree")
        if email.search(content):
            raise ValueError("email address found in public tree")
        if any(term.search(content) for term in terms):
            raise ValueError("denylist term found in public tree")
        count += 1
    print(f"neutrality: PASS ({count} files)")
    print("denylist: PASS" if policy else "denylist: SKIP (no policy supplied)")


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]).resolve(), artifact="--artifact" in sys.argv[2:])
    except (OSError, ValueError) as exc:
        print(
            "FAIL: "
            + (str(exc) if isinstance(exc, ValueError) else "unreadable public tree"),
            file=sys.stderr,
        )
        sys.exit(1)
