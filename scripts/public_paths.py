"""Shared, exact public-file selection for source audits and artifact assembly."""

import json
import os
import re
from pathlib import Path, PurePosixPath

OWNER = ".website-export-owned"
OWNER_BYTES = b'{"schema_version":1,"kind":"website-public-stage"}\n'


def public_paths(root):
    try:
        policy = json.loads((root / "scripts/public-paths.json").read_text())
    except (OSError, ValueError):
        raise ValueError("cannot read public path policy")
    if (
        not isinstance(policy, dict)
        or set(policy) != {"schema_version", "files"}
        or type(policy["schema_version"]) is not int
        or policy["schema_version"] != 1
    ):
        raise ValueError("invalid public path policy")
    files = policy["files"]
    if (
        not isinstance(files, list)
        or not files
        or any(not isinstance(p, str) for p in files)
    ):
        raise ValueError("invalid public path policy")
    if files != sorted(set(files)):
        raise ValueError("public paths must be sorted and unique")
    for name in files:
        path = PurePosixPath(name)
        if (
            not path.parts
            or path.is_absolute()
            or path.as_posix() != name
            or any(
                p
                in (
                    ".",
                    "..",
                    "docs",
                    "work-notes",
                    "node_modules",
                    "__pycache__",
                    ".venv",
                )
                or p in (".git", ".vercel", ".lanes", OWNER)
                or p.startswith(".env")
                for p in path.parts
            )
        ):
            raise ValueError("unsafe public path policy")
    if "scripts/public-paths.json" not in files:
        raise ValueError("public path policy must include itself")
    return files


def selected_files(root):
    for name in public_paths(root):
        path = root / name
        parts = Path(name).parts
        if any(
            root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)
        ):
            raise ValueError("symlink is not publishable")
        if not path.is_file():
            raise ValueError("required public file missing")
        yield path


def public_blame_bytes(root):
    content = (root / "scripts/public-blame-ignore-revs").read_bytes()
    revisions = [
        line for line in content.splitlines() if line and not line.startswith(b"#")
    ]
    if not revisions or any(
        re.fullmatch(rb"[0-9a-f]{40}", line) is None for line in revisions
    ):
        raise ValueError("invalid public blame revisions")
    return content


def write_public_blame(root):
    target = root / ".git-blame-ignore-revs"
    target.write_bytes(public_blame_bytes(root))
    target.chmod(0o644)
    path = root / "scripts/public-paths.json"
    policy = json.loads(path.read_text())
    policy["files"] = sorted(set(policy["files"]) | {".git-blame-ignore-revs"})
    path.write_text(json.dumps(policy, indent=2) + "\n")


def artifact_files(root):
    expected = set(public_paths(root))
    directories = {
        p.as_posix()
        for name in expected
        for p in PurePosixPath(name).parents
        if p.as_posix() != "."
    }
    actual = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in dirs + files:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ValueError("symlink is not publishable")
            if name in dirs:
                if relative not in directories:
                    raise ValueError("unexpected directory in public artifact")
            elif relative not in expected:
                raise ValueError("unexpected file in public artifact")
            else:
                actual.add(relative)
    if actual != expected:
        raise ValueError("required public file missing")
    if ".git-blame-ignore-revs" in expected and (
        (root / ".git-blame-ignore-revs").read_bytes() != public_blame_bytes(root)
    ):
        raise ValueError("public blame revisions differ from mapped metadata")
    return list(selected_files(root))
