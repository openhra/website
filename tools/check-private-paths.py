#!/usr/bin/env python3
"""Reject machine-specific absolute paths in publishable website files."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from public_paths import selected_files


def check(root):
    # Keep the forbidden examples out of this source so the checker can scan itself.
    roots = ("Vol" + "umes", "Us" + "ers", "home", "private" + "/" + "tmp")
    pattern = re.compile(
        "/" + "(?:" + "|".join(map(re.escape, roots)) + ")" + "/", re.I
    )
    count = 0
    for path in selected_files(root):
        content = path.read_bytes().decode("utf-8", errors="replace")
        if pattern.search(content):
            raise ValueError(
                "private absolute path found in " + path.relative_to(root).as_posix()
            )
        count += 1
    print(f"private paths: PASS ({count} files)")


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]).resolve())
    except (OSError, ValueError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)
