#!/usr/bin/env python3
"""Export committed public files without writing into a working clone."""

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from public_paths import OWNER, OWNER_BYTES, public_paths, write_public_blame

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    result = subprocess.run(command, check=False, capture_output=True)
    if result.returncode:
        raise ValueError("required export command failed")
    return result.stdout


def git(*args):
    return run(["git", "-C", str(ROOT), *args]).decode().strip()


def destination(raw, repo):
    raw = Path(raw).absolute()
    if raw.is_symlink():
        raise ValueError("destination must not use symlinks")
    dest = raw.resolve()
    if dest == repo or repo in dest.parents or dest in repo.parents:
        raise ValueError(
            "destination must be outside and not contain the source checkout"
        )
    if dest.exists() and not dest.is_dir():
        raise ValueError("destination must be a directory")
    ancestor = dest
    while not ancestor.exists():
        ancestor = ancestor.parent
    probe = subprocess.run(
        ["git", "-C", str(ancestor), "rev-parse", "--absolute-git-dir"],
        check=False,
        capture_output=True,
    )
    if probe.returncode == 0:
        raise ValueError("destination is inside a Git checkout")
    if dest.exists():
        for directory, dirs, files in os.walk(dest, followlinks=False):
            for name in dirs + files:
                path = Path(directory) / name
                if path.is_symlink():
                    raise ValueError("destination contains a symlink")
                if name in (".git", ".vercel", ".lanes") or name.startswith(".env"):
                    raise ValueError("destination contains local state")
                if not path.is_dir() and not path.is_file():
                    raise ValueError("destination contains a special file")
        entries = list(dest.iterdir())
        if entries and (
            not (dest / OWNER).is_file() or (dest / OWNER).read_bytes() != OWNER_BYTES
        ):
            raise ValueError("destination must be empty or exporter-owned staging")
    return dest


def fingerprint(root):
    if not root.exists():
        return None
    return {
        p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mode & 0o777)
        for p in root.rglob("*")
        if p.is_file()
    }


def audit(tree, env):
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(tree / "tools/check-neutral.py"),
            str(tree),
            "--artifact",
        ],
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode or result.stdout.splitlines()[-1:] != ["denylist: PASS"]:
        # Checker diagnostics do not disclose policy matches or filenames.
        raise ValueError(result.stdout.strip() or "artifact audit did not print PASS")


def export(raw):
    policy = os.environ.get("OPENPLANS_DENYLIST_FILE")
    if not policy:
        raise ValueError("OPENPLANS_DENYLIST_FILE is required")
    if not Path(policy).is_file():
        raise ValueError("cannot read publication denylist")
    env = dict(
        os.environ,
        OPENPLANS_DENYLIST_FILE=str(Path(policy).resolve()),
        PYTHONDONTWRITEBYTECODE="1",
    )
    repo = Path(git("rev-parse", "--show-toplevel")).resolve()
    dest = destination(raw, repo)
    before = fingerprint(dest)
    commit = git("rev-parse", "--verify", "HEAD^{commit}")
    if git("status", "--porcelain", "--untracked-files=all", "--", "."):
        raise ValueError("source website tree is dirty; commit changes first")
    prefix = git("rev-parse", "--show-prefix").rstrip("/")
    tree_ref = commit + (":" + prefix if prefix else "^{tree}")
    with tempfile.TemporaryDirectory(prefix="website-export-") as temporary:
        work = Path(temporary)
        # Read policy from the same pinned commit as the payload.
        policy_blob = run(
            [
                "git",
                "-C",
                str(repo),
                "show",
                commit
                + ":"
                + (prefix + "/" if prefix else "")
                + "scripts/public-paths.json",
            ]
        )
        (work / "scripts").mkdir()
        (work / "scripts/public-paths.json").write_bytes(policy_blob)
        paths = public_paths(work)
        archive = run(["git", "-C", str(repo), "archive", tree_ref, "--", *paths])
        tree = work / "tree"
        tree.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                if not member.isfile() and not member.isdir():
                    raise ValueError("symlink or special file is not publishable")
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    raise ValueError("unsafe archive path")
                # Git tracks executable bits, not local umasks or tar permissions.
                member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
            tar.extractall(tree)
        # Private source revisions do not identify commits in extracted history.
        write_public_blame(tree)
        audit(tree, env)
        expected = fingerprint(tree)
        check = work / "check"
        shutil.copytree(tree, check)
        installed = subprocess.run(
            [str(check / "scripts/install-tools.sh")],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        if installed.returncode:
            raise ValueError("isolated locked tool installation failed")
        result = subprocess.run(
            [str(check / "tools/gate.sh"), "--full"],
            check=False,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if (
            result.returncode
            or not result.stdout.splitlines()
            or result.stdout.splitlines()[-1] != "PASS"
        ):
            raise ValueError("isolated full gate did not pass")
        print(result.stdout, end="")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".website-stage-", dir=dest.parent
        ) as assembly:
            assembled = Path(assembly) / "tree"
            assembled.mkdir()
            run(["rsync", "-a", str(tree) + "/", str(assembled) + "/"])
            audit(assembled, env)
            if fingerprint(assembled) != expected:
                raise ValueError("assembled artifact differs from committed files")
            # Recheck before replacing anything; a gate may take several minutes.
            destination(raw, repo)
            if fingerprint(dest) != before:
                raise ValueError("destination changed during export")
            (assembled / OWNER).write_bytes(OWNER_BYTES)
            backup = Path(assembly) / "previous"
            if dest.exists():
                dest.rename(backup)
            try:
                assembled.rename(dest)
            except OSError:
                if backup.exists():
                    backup.rename(dest)
                raise
    print("website-export: PASS")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: scripts/export-public.sh <staging-directory>")
        export(sys.argv[1])
    except (OSError, ValueError) as error:
        # Never print raw Git or filesystem diagnostics.
        print(
            "website-export: FAIL: "
            + (
                str(error)
                if isinstance(error, ValueError)
                else "filesystem operation failed"
            ),
            file=sys.stderr,
        )
        sys.exit(1)
