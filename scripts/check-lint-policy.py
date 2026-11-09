#!/usr/bin/env python3
"""Reject lint exceptions and unexpected suppression baselines."""

import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root):
    if (root / "eslint-suppressions.json").exists():
        raise ValueError("ESLint suppression baselines are not permitted")
    files = subprocess.check_output(
        [sys.executable, "-m", "ruff", "check", "--show-files", "."],
        cwd=root,
        text=True,
    ).splitlines()
    for name in files:
        if Path(name).suffix not in (".py", ".pyi"):
            continue
        with tokenize.open(name) as source:
            for token in tokenize.generate_tokens(source.readline):
                if token.type == tokenize.COMMENT and re.search(
                    r"\bnoqa\b", token.string, re.IGNORECASE
                ):
                    raise ValueError(
                        "inline Python lint exception: "
                        + str(Path(name).relative_to(root))
                    )


if __name__ == "__main__":
    try:
        check(ROOT)
        print("lint policy: PASS (no inline Python exceptions)")
    except (OSError, ValueError, tokenize.TokenError) as error:
        sys.exit("lint policy: FAIL: " + str(error))
