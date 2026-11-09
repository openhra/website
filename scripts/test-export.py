#!/usr/bin/env python3
"""Exercise the exporter in disposable repositories without touching remotes."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd=None, env=None, expected=None):
    result = subprocess.run(
        args, check=False, cwd=cwd, env=env, capture_output=True, text=True
    )
    if expected is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0 and expected in result.stdout + result.stderr, (
            result.stdout + result.stderr
        )
    return result.stdout


def git(root, *args):
    return run(["git", "-C", str(root), *args])


def commit(root):
    git(root, "add", "--all")
    git(
        root,
        "-c",
        "user.name=Export selftest",
        "-c",
        "user.email=export-test" + "@" + "example.invalid",
        "commit",
        "--quiet",
        "-m",
        "website: isolated export fixture",
    )


def snapshot(root):
    return {
        p.relative_to(root): (p.read_bytes(), p.stat().st_mode & 0o777)
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def verify_import(import_ref, public_source):
    """Replay the import proof without modifying the original public checkout."""
    repository = Path(git(ROOT, "rev-parse", "--show-toplevel").strip())
    prefix = git(ROOT, "rev-parse", "--show-prefix").strip().rstrip("/")
    tree = import_ref + (":" + prefix if prefix else "^{tree}")
    expected = git(public_source, "rev-parse", "a055916^{tree}").strip()
    assert git(ROOT, "rev-parse", tree).strip() == expected, (
        "import tree differs from a055916"
    )
    with tempfile.TemporaryDirectory(prefix="website-import-test-") as temporary:
        base = Path(temporary)
        archive, source, dest = base / "import.tar", base / "source", base / "clone"
        source.mkdir()
        git(repository, "archive", "--output=" + str(archive), tree)
        run(["tar", "-xf", str(archive), "-C", str(source)])
        run(
            ["git", "clone", "--quiet", "--no-hardlinks", str(public_source), str(dest)]
        )
        git(dest, "checkout", "--quiet", "--detach", "a055916")
        run(
            [
                "rsync",
                "-a",
                "--delete",
                "--exclude=/.git",
                "--exclude=/.vercel",
                "--exclude=/.lanes",
                "--exclude=/.env*",
                str(source) + "/",
                str(dest) + "/",
            ]
        )
        assert not git(dest, "status", "--porcelain", "--untracked-files=all")
    print(
        "import proof: PASS (identical tree; archived import export has zero diff against a055916)"
    )


def main():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from public_paths import OWNER, OWNER_BYTES, public_paths, selected_files

    with tempfile.TemporaryDirectory(prefix="website-export-test-") as temporary:
        base = Path(temporary).resolve()
        source, dest = base / "source", base / "destination"
        for path in selected_files(ROOT):
            target = source / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        git(source, "init", "--quiet")
        # These committed inputs must stay private; installed tools are ignored.
        (source / "docs").mkdir()
        (source / "docs/private-note.md").write_text("PRIVATE" + " TEST" + " MARKER\n")
        (source / "tools/coverage-scan/work-notes").mkdir()
        (source / "tools/coverage-scan/work-notes/capture.txt").write_text(
            "PRIVATE" + " TEST" + " MARKER\n"
        )
        commit(source)
        baseline = snapshot(source)
        policy = base / "denylist"
        policy.write_text("# synthetic policy\nprivate[- ]test[- ]marker\n")
        env = dict(
            os.environ, OPENPLANS_DENYLIST_FILE=str(policy), PYTHONDONTWRITEBYTECODE="1"
        )
        command = [str(source / "scripts/export-public.sh"), str(dest)]
        dest.mkdir()

        def rejected(args, diagnostic, test_env=env):
            before_source, before_dest = snapshot(source), snapshot(dest)
            run(args, env=test_env, expected=diagnostic)
            assert snapshot(source) == before_source, "rejection changed source"
            assert snapshot(dest) == before_dest, "rejection changed destination"
            print(
                "export negative: PASS ("
                + diagnostic
                + "; source and destination unchanged)",
                flush=True,
            )

        missing = dict(env)
        missing.pop("OPENPLANS_DENYLIST_FILE", None)
        rejected(command, "OPENPLANS_DENYLIST_FILE is required", missing)
        empty_policy = base / "empty-policy"
        empty_policy.write_text("# empty synthetic policy\n")
        rejected(
            command,
            "publication denylist must contain at least one pattern",
            dict(env, OPENPLANS_DENYLIST_FILE=str(empty_policy)),
        )
        readme = source / "README.md"
        original = readme.read_bytes()
        readme.write_bytes(original + b"\nDirty fixture\n")
        rejected(command, "source website tree is dirty")
        readme.write_bytes(original)
        (source / "untracked-fixture").write_text("synthetic\n")
        rejected(command, "source website tree is dirty")
        (source / "untracked-fixture").unlink()

        # An unowned directory is never cleaned, even if it resembles an export.
        (dest / "unrelated-sentinel").write_text("synthetic owner file\n")
        rejected(command, "destination must be empty or exporter-owned staging")
        (dest / OWNER).write_bytes(OWNER_BYTES)
        for metadata in (
            ".git",
            "plans/.git",
            "plans/.vercel",
            ".lanes",
            ".env.synthetic",
        ):
            path = dest / metadata
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic local state\n")
            rejected(command, "destination contains local state")
            path.unlink()
        outside = base / "outside"
        outside.mkdir()
        (outside / "sentinel").write_text("unrelated\n")
        link = dest / "plans/linked"
        link.symlink_to(outside, target_is_directory=True)
        rejected(command, "destination contains a symlink")
        assert (outside / "sentinel").read_text() == "unrelated\n"
        link.unlink()
        alias = base / "alias"
        alias.symlink_to(dest, target_is_directory=True)
        rejected([command[0], str(alias)], "destination must not use symlinks")

        # A Git worktree can be hidden by ignore rules or nested under owned staging.
        worktree_repo = base / "worktree-owner"
        worktree_repo.mkdir()
        git(worktree_repo, "init", "--quiet")
        (worktree_repo / "tracked").write_text("synthetic\n")
        commit(worktree_repo)
        (worktree_repo / ".gitignore").write_text("ignored/\n")
        nested = dest / "ignored/lane"
        git(worktree_repo, "worktree", "add", "--quiet", "--detach", str(nested))
        nested_before = snapshot(nested)
        rejected(command, "destination contains local state")
        assert snapshot(nested) == nested_before
        git(worktree_repo, "worktree", "remove", str(nested))
        ignored_inside = worktree_repo / "ignored/output"
        rejected(
            [command[0], str(ignored_inside)], "destination is inside a Git checkout"
        )
        assert not ignored_inside.exists()
        clone = base / "shared-clone"
        git(base, "clone", "--quiet", "--no-hardlinks", str(source), str(clone))
        clone_before, clone_metadata = snapshot(clone), snapshot(clone / ".git")
        rejected([command[0], str(clone)], "destination is inside a Git checkout")
        assert (
            snapshot(clone) == clone_before
            and snapshot(clone / ".git") == clone_metadata
        )

        marker = "PRIVATE" + " TEST" + " MARKER"
        cases = (
            ("private path", "/" + "Vol" + "umes/fixture", "private host path found"),
            (
                "private user path",
                "/" + "Us" + "ers/fixture",
                "private host path found",
            ),
            (
                "email literal",
                "fixture" + "@" + "example.invalid",
                "email address found",
            ),
            ("private note in public prose", marker, "denylist term found"),
        )
        for name, mutation, diagnostic in cases:
            readme.write_bytes(original + ("\n" + mutation + "\n").encode())
            commit(source)
            rejected(command, diagnostic)
            readme.write_bytes(original)
            commit(source)
        svg = source / "tests/reference/map.svg"
        svg_bytes = svg.read_bytes()
        svg.unlink()
        svg.symlink_to(source / "plans/brand/us-states.svg")
        commit(source)
        rejected(command, "symlink or special file is not publishable")
        svg.unlink()
        svg.write_bytes(svg_bytes)
        commit(source)
        path_policy = source / "scripts/public-paths.json"
        policy_bytes = path_policy.read_bytes()
        path_policy.unlink()
        commit(source)
        rejected(command, "required export command failed")
        path_policy.write_bytes(policy_bytes)
        commit(source)

        # The committed npm lock must agree with the manifest, even when tools
        # happen to be installed on the host running the exporter.
        lockfile = source / "package-lock.json"
        lock_bytes = lockfile.read_bytes()
        mutant = json.loads(lock_bytes)
        mutant["packages"]["node_modules/prettier"]["version"] = "0.0.0"
        lockfile.write_text(json.dumps(mutant, indent=2) + "\n")
        commit(source)
        rejected(command, "isolated locked tool installation failed")
        lockfile.write_bytes(lock_bytes)
        commit(source)

        # Real copying completes, then a benign untracked note is planted. Path-set
        # validation must reject it before replacing any destination bytes.
        wrapper = base / "bin"
        wrapper.mkdir()
        real_rsync = shutil.which("rsync")
        (wrapper / "rsync").write_text(
            '#!/bin/sh\n"'
            + real_rsync
            + '" "$@"\n'
            + "for last do :; done\n"
            + 'printf "synthetic note\\n" > "$last/planted-after-assembly.md"\n'
        )
        (wrapper / "rsync").chmod(0o755)
        hooked = dict(env, PATH=str(wrapper) + os.pathsep + env["PATH"])
        rejected(command, "unexpected file in public artifact", hooked)

        shutil.rmtree(dest)
        dest.mkdir()
        assert not (source / "node_modules").exists()
        assert not (source / ".venv").exists()
        output = run(command, env=env)
        assert output.splitlines()[-1] == "website-export: PASS"
        print(
            "export positive: PASS (clean source without installed tools)", flush=True
        )
        (dest / "stale-public-file").write_text("synthetic stale public content\n")
        # The first export warmed both caches. A second clean validation copy
        # must pass even when npm and pip are forbidden to use package indexes.
        global_tools = base / "global-tools"
        global_tools.mkdir()
        for name in ("prettier", "eslint", "ruff"):
            tool = global_tools / name
            tool.write_text("#!/bin/sh\necho 'global tool used' >&2\nexit 1\n")
            tool.chmod(0o755)
        global_python = base / "global-python"
        global_python.mkdir()
        (global_python / "ruff.py").write_text(
            "raise RuntimeError('global Python tool used')\n"
        )
        cached = dict(
            env,
            npm_config_offline="true",
            PIP_NO_INDEX="1",
            NODE_ENV="production",
            PATH=str(global_tools) + os.pathsep + env["PATH"],
            PYTHONPATH=str(global_python),
        )
        output = run(command, env=cached)
        assert output.splitlines()[-1] == "website-export: PASS"
        assert not (dest / "node_modules").exists()
        assert not (dest / ".venv").exists()
        print(
            "export positive: PASS (cached tools with package indexes disabled and global tool traps)",
            flush=True,
        )
        actual = snapshot(dest)
        assert actual.pop(Path(OWNER))[0] == OWNER_BYTES
        expected = {Path(name): baseline[Path(name)] for name in public_paths(source)}
        expected[Path(".git-blame-ignore-revs")] = baseline[
            Path("scripts/public-blame-ignore-revs")
        ]
        path_policy = Path("scripts/public-paths.json")
        mapped_policy = json.loads(baseline[path_policy][0])
        mapped_policy["files"] = sorted(
            set(mapped_policy["files"]) | {".git-blame-ignore-revs"}
        )
        expected[path_policy] = (
            (json.dumps(mapped_policy, indent=2) + "\n").encode(),
            baseline[path_policy][1],
        )
        assert actual == expected, "artifact differs from committed public selection"
        assert snapshot(source) == baseline, "export changed source tree"
        assert not git(source, "status", "--porcelain"), (
            "export dirtied source checkout"
        )
        assert not (dest / "docs").exists(), "private design files exported"
        assert not (dest / "tools/coverage-scan/work-notes").exists(), (
            "work notes exported"
        )
        print(
            "export positive: PASS (exact public files and mapped blame metadata; private notes excluded; owned stale files removed)",
            flush=True,
        )

        # Bare-artifact auditing excludes the staging ownership control.
        (dest / OWNER).unlink()
        run(
            ["python3", str(dest / "tools/check-neutral.py"), str(dest), "--artifact"],
            env=env,
        )

        public_blame = dest / ".git-blame-ignore-revs"
        mapped = public_blame.read_bytes()
        public_blame.write_bytes(b"0" * 40 + b"\n")
        run(
            ["python3", str(dest / "tools/check-neutral.py"), str(dest), "--artifact"],
            env=env,
            expected="public blame revisions differ",
        )
        public_blame.write_bytes(mapped)
        print("export negative: PASS (unmapped blame revision rejected)", flush=True)
        template = dest / "scripts/public-blame-ignore-revs"
        template.write_bytes(b"not-a-commit\n")
        public_blame.write_bytes(template.read_bytes())
        run(
            ["python3", str(dest / "tools/check-neutral.py"), str(dest), "--artifact"],
            env=env,
            expected="invalid public blame revisions",
        )
        template.write_bytes(mapped)
        public_blame.write_bytes(mapped)
        print("export negative: PASS (invalid blame metadata rejected)", flush=True)

        # Installed tool files containing private paths are outside source audits.
        for directory in ("node_modules", ".venv"):
            path = dest / directory / "synthetic-tool.txt"
            path.parent.mkdir()
            path.write_text("/" + "Us" + "ers/fixture\n" + marker)
        run(["python3", str(dest / "tools/check-private-paths.py"), str(dest)], env=env)
        run(["python3", str(dest / "tools/check-neutral.py"), str(dest)], env=env)
        run(
            ["python3", str(dest / "tools/check-neutral.py"), str(dest), "--artifact"],
            env=env,
            expected="unexpected",
        )
        shutil.rmtree(dest / "node_modules")
        shutil.rmtree(dest / ".venv")
        run([str(dest / "scripts/install-tools.sh")], env=env)
        output = run([str(dest / "tools/gate.sh"), "--full"], env=env)
        assert output.splitlines()[-1] == "PASS"
        assert snapshot(source) == baseline
        print(
            "export positive: PASS (exported full gate standalone; installed tooling excluded from source audits)",
            flush=True,
        )
        print("website export selftest: PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public",
        action="store_true",
        help="Run synthetic-policy tests only, without historical import inputs",
    )
    parser.add_argument(
        "--import-ref",
        help="Optional incubator import commit for the original-tree proof",
    )
    parser.add_argument(
        "--public-source",
        type=Path,
        help="Read-only local public checkout containing a055916",
    )
    args = parser.parse_args()
    if args.public and (args.import_ref or args.public_source):
        parser.error("--public cannot use historical import inputs")
    if bool(args.import_ref) != bool(args.public_source):
        parser.error("--import-ref and --public-source must be supplied together")
    if args.import_ref:
        verify_import(args.import_ref, args.public_source.resolve())
    main()
