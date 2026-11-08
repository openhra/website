#!/usr/bin/env python3
"""Audit every publishable file, including files not yet in a destination's index."""
import os
import re
import sys
from pathlib import Path


def protected(name):
    return name in ('.git', '.vercel', '.lanes') or name.startswith('.env')


def check(root):
    if not root.is_dir():
        raise ValueError('public tree must be a directory')
    policy = os.environ.get('OPENPLANS_DENYLIST_FILE')
    terms = []
    if policy:
        try:
            terms = [re.compile(line.strip(), re.I) for line in Path(policy).read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith('#')]
        except (OSError, UnicodeError, re.error):
            raise ValueError('cannot read or compile publication denylist')
        if not terms:
            raise ValueError('publication denylist must contain at least one pattern')
    # Split the host path markers so this checker contains no forbidden literal.
    private = re.compile('/' + r'(?:Volumes|Users)/', re.I)
    email = re.compile(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}', re.I)
    def unreadable(error):
        raise error

    count = 0
    for directory, directories, files in os.walk(root, followlinks=False, onerror=unreadable):
        base = Path(directory)
        if base == root:
            directories[:] = [name for name in directories if not protected(name)]
            files = [name for name in files if not protected(name)]
        for name in directories + files:
            if (base / name).is_symlink():
                raise ValueError('symlink is not publishable')
        for name in files:
            path = base / name
            relative = path.relative_to(root).as_posix()
            content = relative + '\n' + path.read_bytes().decode('utf-8', errors='replace')
            # Do not print matched content, filenames or policy terms: they may be private.
            if private.search(content):
                raise ValueError('private host path found in public tree')
            if email.search(content):
                raise ValueError('email address found in public tree')
            if any(term.search(content) for term in terms):
                raise ValueError('denylist term found in public tree')
            count += 1
    print(f'neutrality: PASS ({count} files)')
    print('denylist: PASS' if policy else 'denylist: SKIP (no policy supplied)')


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]).resolve())
    except (OSError, ValueError) as exc:
        print('FAIL: ' + (str(exc) if isinstance(exc, ValueError) else 'unreadable public tree'), file=sys.stderr)
        sys.exit(1)
