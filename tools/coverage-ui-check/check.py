#!/usr/bin/env python3
"""Offline production markup/data/geometry parity, with isolated negative controls."""
import argparse
import json
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
    for layer, pages in (('providers', ('coverage-table.html',)), ('premiums', ('index.html', 'availability.html'))):
        fragment = (root / f'tools/coverage-scan/default-{layer}-2026.html').read_text().strip()
        dataset = loads((root / f'plans/data/coverage/{layer}-2026.json').read_bytes())
        assert fragment == table(dataset).decode().strip(), 'scanner fragment differs from JSON'
        for name in pages:
            page = (root / 'plans' / name).read_text()
            assert '<div id="coverage-table">' + fragment + '</div>' in page, 'saved table differs: ' + name
            assert 'Coverage for plan year 2026' in page, 'missing default plan-year label'
            assert 'Figures as of November 8, 2026' in page, 'missing explicit default date'
            assert page.count('<th scope="row">') == 51, 'missing default state row'
    page = (root / 'plans/index.html').read_text()
    full = (root / 'plans/availability.html').read_text()
    for source in (page, full):
        assert source.count('<script src="/coverage.js" defer></script>') == 1
        assert 'U.S. Census Bureau, 2024 cartographic boundaries' in source
        assert set(re.findall(r'<option value="([A-Z]{2})"',source)) == set(STATES)
        assert 'id="coverage-share"' in source and 'id="coverage-share-message" role="status" aria-live="polite"' in source, 'missing accessible share action'
        assert 'id="coverage-summary"' in source and 'not yet measured' in source, 'missing measured-state summary'
        for layer, label in (('providers', 'Providers'), ('prescriptions', 'Prescriptions'), ('premiums', 'Premiums')):
            saved = loads((root / f'plans/data/coverage/{layer}-2026.json').read_bytes())
            measured = sum(r['status'] == 'measured' for r in saved['states'].values())
            assert f'{label}: {measured} of 51 states measured' in source, 'saved measured-state summary differs from JSON'
    assert 'class="coverage-table-disclosure"' in page and 'Open the full availability page' in page, 'landing must link to full page and collapse table'
    assert 'coverage-methodology-heading' in full and 'coverage-table-disclosure' not in full, 'full page methodology/table absent'
    assert '<title>Data availability by state · OpenPlans</title>' in full
    for tag in ('description', 'og:title', 'og:description', 'og:url', 'twitter:card', 'twitter:title', 'twitter:description', 'og:image', 'og:image:alt', 'twitter:image', 'twitter:image:alt'):
        assert re.search(r'<meta (?:name|property)="' + tag + '" content="[^"]+"', full), 'full page metadata absent: ' + tag
    assert (root / 'plans/brand/repo/social-preview.png').stat().st_size < 64 * 1024, 'social image budget'
    config = json.loads((root / 'plans/vercel.json').read_text())
    assert config.get('cleanUrls') is True and not any(r['source'] in ('/availability', '/(.*)', '/:path*') for r in config.get('rewrites', [])), 'availability clean URL absent or shadowed'
    gate = (root / 'tools/gate.sh').read_text()
    assert '"plans/availability.html"' in gate.split('required_pages = (', 1)[-1].split(')', 1)[0], 'availability missing from gate page list'
    svg = (root / 'plans/brand/us-states.svg').read_text()
    ns = {'s':'http://www.w3.org/2000/svg'}
    expected = ET.fromstring((root / 'tests/reference/map.svg').read_text())
    actual = ET.fromstring(svg)
    geometry = lambda el: {p.attrib['data-state']:p.attrib['d'] for p in el.findall('.//s:path[@data-state]', ns)}
    assert geometry(actual) == geometry(expected) and set(geometry(actual)) == set(STATES), 'Census geometry differs'
    assert len(actual.findall('.//s:path[@data-state]',ns)) == 51
    for source in (page, full):
        embedded = ET.fromstring(re.search(r'<svg\b.*?</svg>',source,re.S)[0])
        assert geometry(embedded) == geometry(actual), 'embedded map differs'
        for shape in embedded.findall('.//s:path[@data-state]', ns):
            record = dataset['states'][shape.attrib['data-state']]
            expected_fill = 'url(#coverage-unknown)' if record['status'] == 'unknown' else 'var(--teal-800)'
            assert shape.attrib['fill'] == expected_fill, 'saved premium map differs from JSON'
    assert {e.attrib['data-label'] for e in actual.findall('.//s:text[@data-label]',ns)} == set(STATES), 'missing state label'
    assert '37337db59415f010c594fba96a48aa6e950e633dc0e555cc7b1ce8edd794c673' in svg
    assert len(svg.encode()) <= 200*1024
    reader = (root / 'plans/coverage.js').read_text()
    assert len(reader.encode()) <= 24*1024, 'reader budget'
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
        assert config['headers'] == json.loads(original('plans/vercel.json'))['headers'], 'protected hosting headers changed'
        for name in ('plans/contact.js','plans/api/contact.js','plans/brand/tokens.css',
                     'openhra/vercel.json','openhra/contact.js','openhra/api/contact.js','openhra/brand/tokens.css'):
            assert (root/name).read_text() == original(name), 'protected file changed: '+name

    result = subprocess.run(['node', str(Path(__file__).with_name('selection-test.mjs')), str(root)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def negatives():
    mutations = {
        'table row removed': lambda s: re.sub(r'<tr><th scope="row">Alaska</th>.*?</tr>\n', '', s),
        'default value changed': lambda s: s.replace('203592/203592 (100.0%)','203591/203592 (100.0%)'),
        'plan year removed': lambda s: s.replace('Coverage for plan year 2026','Coverage'),
        'plan year mismatched': lambda s: s.replace('Coverage for plan year 2026','Coverage for plan year 2027'),
    }
    cases = [(name, 'plans/index.html', mutate) for name, mutate in mutations.items()]
    cases.extend([
        ('URL state ignored', 'plans/coverage.js', lambda s: s.replace("state: Object.hasOwn(states, params.get('state')) ? params.get('state') : 'TX'", "state: 'TX'")),
        ('share drops selection', 'plans/coverage.js', lambda s: s.replace("const url = link().href;", "const url = new URL('/availability', location.origin).href;")),
        ('clipboard confirmation absent', 'plans/coverage.js', lambda s: s.replace("$('share-message').textContent = 'Link copied';", "$('share-message').textContent = '';")),
        ('unknown rendered as measured', 'plans/coverage.js', lambda s: s.replace("unknown: 'Unknown, not yet measured'", "unknown: '0.0%'")),
        ('availability missing from gate page list', 'tools/gate.sh', lambda s: s.replace(', "plans/availability.html"', '')),
    ])
    cases.append(('white ground removed', 'plans/style.css', lambda s: s.replace('.coverage { background: #ffffff;', '.coverage {')))
    for name, filename, mutate in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            for directory in ('plans','tools/coverage-scan','tests/reference'):
                shutil.copytree(ROOT / directory,dest / directory)
            shutil.copy(ROOT / 'tools/gate.sh', dest / 'tools/gate.sh')
            target = dest / filename; before = target.read_text(); target.write_text(mutate(before))
            assert target.read_text() != before, 'mutation was a no-op: ' + name
            try:
                check(dest)
            except AssertionError as exc:
                expected = {
                    'URL state ignored': 'URL state ignored on load or history',
                    'share drops selection': 'share link drops selection',
                    'clipboard confirmation absent': 'clipboard confirmation absent',
                    'unknown rendered as measured': 'unknown state rendered as measured',
                    'availability missing from gate page list': 'availability missing from gate page list',
                }
                if name in expected:
                    assert expected[name] in str(exc), 'wrong negative diagnostic: ' + name + ': ' + str(exc)
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
