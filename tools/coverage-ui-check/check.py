#!/usr/bin/env python3
"""Offline production markup/data/geometry parity, with isolated negative controls."""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/coverage-scan'))
from model import STATES, loads
from scan import table


def check(root):
    fragment = (root / 'tools/coverage-scan/default-providers-2026.html').read_text().strip()
    dataset = loads((root / 'plans/data/coverage/providers-2026.json').read_bytes())
    assert fragment == table(dataset).decode().strip(), 'scanner fragment differs from JSON'
    for name in ('index.html', 'coverage-table.html'):
        page = (root / 'plans' / name).read_text()
        assert '<div id="coverage-table">' + fragment + '</div>' in page, 'saved table differs: ' + name
        assert 'Coverage for plan year 2026' in page, 'missing default plan-year label'
        assert 'Figures as of November 8, 2026' in page, 'missing explicit default date'
        assert page.count('<th scope="row">') == 51, 'missing default state row'
    page = (root / 'plans/index.html').read_text()
    assert page.count('<script src="/coverage.js" defer></script>') == 1
    assert 'U.S. Census Bureau, 2024 cartographic boundaries' in page
    assert set(re.findall(r'<option value="([A-Z]{2})"',page)) == set(STATES)
    svg = (root / 'plans/brand/us-states.svg').read_text()
    ns = {'s':'http://www.w3.org/2000/svg'}
    expected = ET.fromstring((root / 'docs/coverage-map/map.svg').read_text())
    actual = ET.fromstring(svg)
    geometry = lambda el: {p.attrib['data-state']:p.attrib['d'] for p in el.findall('.//s:path[@data-state]', ns)}
    assert geometry(actual) == geometry(expected) and set(geometry(actual)) == set(STATES), 'Census geometry differs'
    assert len(actual.findall('.//s:path[@data-state]',ns)) == 51
    embedded = ET.fromstring(re.search(r'<svg\b.*?</svg>',page,re.S)[0])
    assert geometry(embedded) == geometry(actual), 'embedded map differs'
    assert {e.attrib['data-label'] for e in actual.findall('.//s:text[@data-label]',ns)} == set(STATES), 'missing state label'
    assert '37337db59415f010c594fba96a48aa6e950e633dc0e555cc7b1ce8edd794c673' in svg
    assert len(svg.encode()) <= 200*1024
    reader = (root / 'plans/coverage.js').read_text()
    assert len(reader.encode()) <= 16*1024, 'reader budget'
    assert not re.search(r'innerHTML|outerHTML|insertAdjacentHTML|eval\(', reader), 'unsafe DOM interpolation'
    assert "fetch('data/coverage/' + path" in reader, 'unexpected fetch path'
    css = (root / 'plans/style.css').read_text()
    assert len(css.split('/* Static coverage reader:',1)[1].encode()) <= 8*1024
    assert '.coverage { background: #ffffff;' in css, 'missing white coverage ground'
    if root.resolve() == ROOT and subprocess.run(
            ['git', '-C', str(ROOT), 'rev-parse', '--verify', 'HEAD'], capture_output=True).returncode == 0:
        prefix = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', '--show-prefix'], text=True).strip()
        baseline = 'main' if subprocess.run(
            ['git', '-C', str(ROOT), 'cat-file', '-e', 'main:' + prefix + 'plans/index.html'],
            capture_output=True).returncode == 0 else 'HEAD'
        original = lambda name: subprocess.check_output(['git', '-C', str(ROOT), 'show', baseline + ':' + prefix + name]).decode()
        # A page redesign is authorised. Keep the evidence, legal and contact
        # blocks byte-identical instead of freezing unrelated presentation copy.
        baseline_page = original('plans/index.html')
        protected_sections = (
            r'<section class="band alt verification">.*?</section>',
            r'<section class="band coverage"[^>]*>.*?</section>',
            r'<section class="band" id="publishers">.*?</section>',
            r'<section class="band alt" id="contact">.*?</section>',
            r'<footer>.*?</footer>',
            r'<p>This product uses publicly available data.*?</p>',
        )
        for pattern in protected_sections:
            before = re.search(pattern, baseline_page, re.S)
            after = re.search(pattern, page, re.S)
            assert before and after and before[0] == after[0], 'protected page block changed: ' + pattern
        assert re.findall(r'<script\b[^>]*>.*?</script>', page, re.S) == re.findall(
            r'<script\b[^>]*>.*?</script>', baseline_page, re.S), 'page scripts changed'
        assert css.startswith(original('plans/style.css')), 'existing styles changed'
        organisation = (root / 'openhra/index.html').read_text()
        original_organisation = original('openhra/index.html')
        for pattern in (r'<section class="band alt" id="contact">.*?</section>', r'<footer>.*?</footer>'):
            assert re.search(pattern, organisation, re.S)[0] == re.search(pattern, original_organisation, re.S)[0], 'organisation protected block changed'
        assert re.findall(r'<script\b[^>]*>.*?</script>', organisation, re.S) == re.findall(
            r'<script\b[^>]*>.*?</script>', original_organisation, re.S), 'organisation scripts changed'
        for name in ('plans/vercel.json','plans/contact.js','plans/api/contact.js','plans/brand/tokens.css',
                     'openhra/vercel.json','openhra/contact.js','openhra/api/contact.js','openhra/brand/tokens.css'):
            assert (root/name).read_text() == original(name), 'protected file changed: '+name


def negatives():
    mutations = {
        'table row removed': lambda s: s.replace('<tr><th scope="row">Alaska</th><td>Unknown</td><td>Unknown</td></tr>\n',''),
        'default value changed': lambda s: s.replace('14/32 (43.8%)','15/32 (46.9%)'),
        'plan year removed': lambda s: s.replace('Coverage for plan year 2026','Coverage'),
        'plan year mismatched': lambda s: s.replace('Coverage for plan year 2026','Coverage for plan year 2027'),
    }
    cases = [(name, 'plans/index.html', mutate) for name, mutate in mutations.items()]
    cases.append(('white ground removed', 'plans/style.css', lambda s: s.replace('.coverage { background: #ffffff;', '.coverage {')))
    for name, filename, mutate in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            for directory in ('plans','tools/coverage-scan','docs/coverage-map'):
                shutil.copytree(ROOT / directory,dest / directory)
            target = dest / filename; target.write_text(mutate(target.read_text()))
            try:
                check(dest)
            except AssertionError:
                print('negative control: PASS (' + name + ')')
            else:
                raise AssertionError('negative control was accepted: ' + name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=ROOT); parser.add_argument('--selftest',action='store_true'); args = parser.parse_args()
    try:
        check(args.root)
        if args.selftest: negatives()
    except (AssertionError,ValueError,KeyError) as exc:
        print('FAIL: coverage UI: ' + str(exc)); sys.exit(1)
    print('PASS: coverage UI static parity, default year/date, 51 Census paths and labels, safe DOM and budgets')
