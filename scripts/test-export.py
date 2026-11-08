#!/usr/bin/env python3
"""Exercise the real exporter in disposable Git repositories (no network or remotes)."""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd=None, env=None, expected=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if expected is None:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0 and expected in result.stdout + result.stderr, result.stdout + result.stderr
    return result.stdout


def git(root, *args):
    return run(['git', '-C', str(root), *args])


def commit(root):
    git(root, 'add', '--all')
    git(root, '-c', 'user.name=Export selftest', '-c', 'user.email=export-test' + '@' + 'example.invalid',
        'commit', '--quiet', '-m', 'website: isolated export fixture')


def snapshot(root):
    return {p.relative_to(root): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}



def verify_import(import_ref, public_source):
    """Replay the import proof without modifying the original public checkout."""
    repository = Path(git(ROOT, 'rev-parse', '--show-toplevel').strip())
    prefix = git(ROOT, 'rev-parse', '--show-prefix').strip().rstrip('/')
    tree = import_ref + (':' + prefix if prefix else '^{tree}')
    expected = git(public_source, 'rev-parse', 'a055916^{tree}').strip()
    assert git(ROOT, 'rev-parse', tree).strip() == expected, 'import tree differs from a055916'
    with tempfile.TemporaryDirectory(prefix='website-import-test-') as temporary:
        base = Path(temporary)
        archive, source, dest = base / 'import.tar', base / 'source', base / 'clone'
        source.mkdir()
        git(repository, 'archive', '--output=' + str(archive), tree)
        run(['tar', '-xf', str(archive), '-C', str(source)])
        run(['git', 'clone', '--quiet', '--no-hardlinks', str(public_source), str(dest)])
        git(dest, 'checkout', '--quiet', '--detach', 'a055916')
        run(['rsync', '-a', '--delete', '--exclude=/.git', '--exclude=/.vercel',
             '--exclude=/.lanes', '--exclude=/.env*', str(source) + '/', str(dest) + '/'])
        assert not git(dest, 'status', '--porcelain', '--untracked-files=all')
    print('import proof: PASS (identical tree; archived import export has zero diff against a055916)')


def main():
    with tempfile.TemporaryDirectory(prefix='website-export-test-') as temporary:
        base = Path(temporary)
        source, dest = base / 'source', base / 'destination'
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('.git', '.vercel', '.lanes', '.env*'))
        git(source, 'init', '--quiet')
        commit(source)
        baseline = snapshot(source)
        policy = base / 'denylist'
        policy.write_text('# synthetic policy\nprivate[- ]test[- ]marker\n')
        env = dict(os.environ, OPENPLANS_DENYLIST_FILE=str(policy), PYTHONDONTWRITEBYTECODE='1')
        command = [str(source / 'scripts/export-public.sh'), str(dest)]

        # A destination clone without a remote: root metadata and local settings survive.
        git(base, 'clone', '--quiet', '--no-hardlinks', str(source), str(dest))
        git(dest, 'remote', 'remove', 'origin')
        for name in ('.vercel', '.lanes'):
            (dest / name).mkdir()
            (dest / name / 'synthetic-sentinel').write_text('synthetic local settings\n')
        (dest / '.env.synthetic').write_text('SYNTHETIC_EXPORT_TEST=1\n')
        protected = {p: snapshot(dest)[p] for p in snapshot(dest) if p.parts[0].startswith(('.env', '.vercel', '.lanes'))}
        metadata = snapshot(dest / '.git')
        (dest / 'stale-public-file').write_text('must be deleted\n')
        # Only root exclusions are protected; a stale nested hosting directory is deleted.
        (dest / 'plans/.vercel').mkdir()
        (dest / 'plans/.vercel/stale').write_text('synthetic\n')

        missing = dict(env)
        missing.pop('OPENPLANS_DENYLIST_FILE')
        run(command, env=missing, expected='OPENPLANS_DENYLIST_FILE is required')
        print('export negative: PASS (missing policy)')
        readme = source / 'README.md'
        original = readme.read_bytes()
        readme.write_bytes(original + b'\nDirty fixture\n')
        run(command, env=env, expected='source website tree is dirty')
        readme.write_bytes(original)
        (source / 'untracked-fixture').write_text('synthetic\n')
        run(command, env=env, expected='source website tree is dirty')
        (source / 'untracked-fixture').unlink()
        print('export negative: PASS (tracked and untracked dirty source)')

        marker = 'PRIVATE' + ' TEST' + ' MARKER'
        cases = (
            ('private volume path', '/' + 'Volumes/fixture', 'private host path found'),
            ('private user path', '/' + 'Users/fixture', 'private host path found'),
            ('email literal', 'fixture' + '@' + 'example.invalid', 'email address found'),
            ('denylisted regex', marker, 'denylist term found'),
        )
        before = snapshot(dest)
        for name, mutation, diagnostic in cases:
            readme.write_bytes(original + ('\n' + mutation + '\n').encode())
            commit(source)
            run(command, env=env, expected=diagnostic)
            assert snapshot(dest) == before, 'failed preflight changed destination'
            readme.write_bytes(original)
            commit(source)
            print('export negative: PASS (' + name + '; destination unchanged)')

        # Prove the final destination check runs even after a successful gate/sync.
        # The wrapper delegates the real copy then plants a publication mutation.
        wrapper = base / 'bin'
        wrapper.mkdir()
        real_rsync = shutil.which('rsync')
        (wrapper / 'rsync').write_text('#!/bin/sh\n' + real_rsync + ' "$@"\n' +
                                     'printf "' + marker + '\\n" > "$EXPORT_TEST_DEST/planted-after-sync"\n')
        (wrapper / 'rsync').chmod(0o755)
        hooked = dict(env, PATH=str(wrapper) + os.pathsep + env['PATH'], EXPORT_TEST_DEST=str(dest))
        run(command, env=hooked, expected='denylist term found')
        assert (dest / 'planted-after-sync').is_file(), 'post-sync mutation never reached rsync'
        print('export negative: PASS (destination audit after rsync)')

        output = run(command, env=env)
        assert output.splitlines()[-1] == 'website-export: PASS'
        actual = snapshot(dest)
        assert all(actual[p] == value for p, value in protected.items()), 'protected destination data changed'
        assert snapshot(dest / '.git') == metadata, 'destination Git metadata changed'
        public = {p: value for p, value in actual.items() if p not in protected}
        assert public == baseline, 'clean export differs from committed website tree'
        assert snapshot(source) == baseline, 'export changed source tree'
        assert not git(source, 'status', '--porcelain'), 'export dirtied source checkout'
        print('export positive: PASS (committed tree exact; stale files deleted; rooted exclusions and Git metadata preserved)')
        print('website export selftest: PASS (isolated full gate; dirty source, policy and publication negative controls)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-ref', help='Optional incubator import commit for the original-tree proof')
    parser.add_argument('--public-source', type=Path, help='Read-only local public checkout containing a055916')
    args = parser.parse_args()
    if bool(args.import_ref) != bool(args.public_source):
        parser.error('--import-ref and --public-source must be supplied together')
    if args.import_ref:
        verify_import(args.import_ref, args.public_source.resolve())
    main()
