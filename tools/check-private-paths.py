#!/usr/bin/env python3
"""Reject machine-specific absolute paths anywhere in the website tree."""
import os
import re
import sys
from pathlib import Path


def check(root):
    # Keep the forbidden examples out of this source so the checker can scan itself.
    roots = ("Vol" + "umes", "Us" + "ers", "home", "private" + "/" + "tmp")
    pattern = re.compile("/" + "(?:" + "|".join(map(re.escape, roots)) + ")" + "/", re.I)
    count = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        base = Path(directory)
        directories[:] = [name for name in directories if name != ".git"]
        for name in files:
            path = base / name
            if path.is_symlink():
                continue
            try:
                content = path.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                raise ValueError("cannot read website file")
            if pattern.search(content):
                raise ValueError("private absolute path found in " + path.relative_to(root).as_posix())
            count += 1
    print(f"private paths: PASS ({count} files)")


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]).resolve())
    except (OSError, ValueError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)
