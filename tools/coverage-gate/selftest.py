#!/usr/bin/env python3
"""Run named, diagnostic-checked mutations against isolated publication copies."""
import copy
import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/coverage-scan'))
from model import encoded, loads, percentage, sha


def write(path, value):
    path.write_bytes(encoded(value))


def dataset(root, edit, name='providers-2026.json'):
    release = root / 'plans/data/coverage'
    path = release / name
    value = loads(path.read_bytes())
    edit(value)
    write(path, value)
    index = loads((release / 'index.json').read_bytes())
    for entry in index['datasets']:
        if entry['path'] == name:
            entry.update(bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
    write(release / 'index.json', index)


def ledger(root, edit, state='TX', name='providers-2026.json', record_edit=None):
    release = root / 'plans/data/coverage'
    data = loads((release / name).read_bytes())
    old = data['states'][state]['evidence']['path']
    value = loads((release / old).read_bytes())
    edit(value, value['scopes'][state])
    raw = encoded(value)
    digest = sha(raw)
    new = 'evidence/' + digest + '.json'
    (release / old).unlink()
    (release / new).write_bytes(raw)

    def repin(data):
        for record in data['states'].values():
            if record['evidence'] and record['evidence']['path'] == old:
                record['evidence'].update(path=new, sha256=digest)
        if record_edit:
            record_edit(data['states'][state], value['scopes'][state])
    dataset(root, repin, name)


def index(root, edit):
    path = root / 'plans/data/coverage/index.json'
    value = loads(path.read_bytes())
    edit(value)
    write(path, value)


def replace(root, filename, old, new):
    path = root / filename
    source = path.read_text()
    assert old in source, 'mutation did not find target: ' + filename
    path.write_text(source.replace(old, new))


def replace_pattern(root, filename, pattern, replacement):
    path = root / filename
    source = path.read_text()
    changed, count = re.subn(pattern, replacement, source)
    assert count and changed != source, 'mutation did not find target: ' + filename
    path.write_text(changed)


def promote(root, state):
    def serving(ledger, scope):
        scope['serving'] = dict(basis='active_catalog', catalog_sha256=scope['reconciliation']['catalog_sha256'],
                                report_id=scope['reconciliation']['report_id'])

    def measured(record, scope):
        rows = scope['inventory']['rows']
        record.update(numerator=rows, denominator=rows, percent_tenths=1000, status='measured',
                      reason_codes=[], counts=dict(verified=rows, quarantined=0, unknown=0, not_imported=0),
                      serving_basis='active_catalog')
    ledger(root, serving, state, 'premiums-2026.json', measured)
    if state == 'OR':
        index(root, lambda i: i['provenance']['federal_rates_2026'].update(url='https://www.cms.gov/files/zip/oregonsbepuf2026.zip'))


def zero_denominator(root):
    def edit(data):
        r = data['states']['TX']
        r.update(numerator=0, denominator=0, percent_tenths=0)
        r['counts'] = dict.fromkeys(r['counts'], 0)
    dataset(root, edit)


def duplicate_state(root):
    path = root / 'plans/data/coverage/providers-2026.json'
    raw = path.read_bytes()
    assert b'"TX":' in raw
    path.write_bytes(raw.replace(b'"TX":', b'"TX":{},"TX":', 1))


def observation_changed(root):
    date = '2026-11-07T14:46:36.334Z'
    ledger(root, lambda l, s: s.update(observed_at=date),
           record_edit=lambda r, s: r.update(observed_at=date))


def premium_denominator(root):
    def edit(data):
        record = data['states']['CA']
        record['denominator'] += 1
        record['counts']['unknown'] = 1
        record['percent_tenths'] = percentage(record['numerator'], record['denominator'])
    dataset(root, edit, 'premiums-2026.json')


def advance_cutoff(root):
    release = root / 'plans/data/coverage'
    date = (dt.datetime.fromisoformat(loads((release / 'index.json').read_bytes())['as_of'].replace('Z', '+00:00')) + dt.timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    moved = {}
    for path in (release / 'evidence').glob('*.json'):
        value = loads(path.read_bytes())
        value['as_of'] = date
        raw = encoded(value)
        moved[path.relative_to(release).as_posix()] = (sha(raw), raw)
    for old, (digest, raw) in moved.items():
        (release / old).unlink()
        (release / ('evidence/' + digest + '.json')).write_bytes(raw)
    for path in release.glob('*-20*.json'):
        def edit(data):
            data['as_of'] = date
            for record in data['states'].values():
                if record['evidence']:
                    digest, _ = moved[record['evidence']['path']]
                    record['evidence'].update(path='evidence/' + digest + '.json', sha256=digest)
        dataset(root, edit, path.name)
    index(root, lambda i: i.update(as_of=date, generated_at=date))


def backward_publication(root):
    path = root.parent / 'previous/index.json'
    value = loads(path.read_bytes())
    value['generated_at'] = (dt.datetime.fromisoformat(value['generated_at'].replace('Z', '+00:00')) + dt.timedelta(seconds=2)).isoformat().replace('+00:00', 'Z')
    write(path, value)


def same_hash_different_bytes(root):
    path = root.parent / 'previous/providers-2026.json'
    path.write_bytes(path.read_bytes() + b' ')


def oversized(root, kind):
    release = root / 'plans/data/coverage'
    if kind == 'release':
        (release / 'oversized.json').write_bytes(b' ' * (2 * 1024**2))
    else:
        path, limit = {
            'index': (release / 'index.json', 16 * 1024),
            'dataset': (release / 'providers-2026.json', 64 * 1024),
            'ledger': (release / loads((release / 'providers-2026.json').read_bytes())['states']['TX']['evidence']['path'], 256 * 1024),
        }[kind]
        path.write_bytes(path.read_bytes() + b' ' * (limit + 1 - path.stat().st_size))


def cases():
    ds = lambda edit: lambda root: dataset(root, edit)
    tx = lambda **fields: ds(lambda d: d['states']['TX'].update(fields))
    ix = lambda edit: lambda root: index(root, edit)
    le = lambda edit: lambda root: ledger(root, edit)
    yield 'TX 14/32 stored as 50.0%', tx(percent_tenths=500), 'percentage: exact integer half-up rounding mismatch'
    yield 'DC omitted', ds(lambda d: d['states'].pop('DC')), 'dataset.states: missing required field'
    yield 'duplicate state key', duplicate_state, 'JSON: duplicate object key'
    yield 'duplicate layer/year', ix(lambda i: i['datasets'].__setitem__(1, copy.deepcopy(i['datasets'][0]))), 'duplicate array item|six unique layer/year'
    yield 'numerator exceeds denominator', tx(numerator=33), 'percentage: require 0 <= numerator <= denominator'
    for name, value, reason in [('negative', -1, 'integer bounds'), ('float', 14.0, 'wrong type'), ('bool', True, 'wrong type')]:
        yield name + ' count', tx(numerator=value), reason
    yield 'unknown null coerced to zero', ds(lambda d: d['states']['DC'].update(numerator=0, percent_tenths=0)), 'record: unknown denominator semantics'
    yield 'zero denominator with percent', zero_denominator, 'record: zero denominator requires proven empty inventory'
    yield 'active bucket includes quarantine', tx(numerator=31, percent_tenths=969), 'buckets: numerator is active/verified units only'
    yield 'quarantine relabelled ACTIVE', le(lambda l, s: s['roster'][0].update(classification='active_complete')), 'issuer: ACTIVE pointer and positive association required'
    yield 'ledger issuer removed', le(lambda l, s: s['roster'].pop()), 'roster: public denominator contains withheld or duplicate issuer'
    yield 'ledger issuer duplicated', le(lambda l, s: s['roster'].append(copy.deepcopy(s['roster'][0]))), 'roster: duplicate array item'
    yield 'ledger association wrong year', le(lambda l, s: next(r for r in s['roster'] if r['active_pointer']).update(association_year=2027)), 'issuer: positive association state/year mismatch'
    yield 'ledger scope wrong year', le(lambda l, s: s.update(year=2027)), 'lineage: state/year/layer mismatch'
    yield 'dataset hash altered', ix(lambda i: i['datasets'][0].update(sha256='0'*64)), 'hash: dataset digest/bytes mismatch'
    yield 'dataset bytes altered', ix(lambda i: i['datasets'][0].update(bytes=1)), 'hash: dataset digest/bytes mismatch'
    yield 'public source hash altered', ix(lambda i: i['provenance']['federal_plans_2026'].update(sha256='0'*64)), 'lineage: public archive hash mismatch'
    yield 'report hash altered and ledger rehashed', le(lambda l, s: l['inputs'].update(p6c_audit='0'*64)), 'selection: ledger input hash mismatch'
    yield 'future state observation', tx(observed_at='2099-01-01T00:00:00Z'), 'record: observation later than as_of'
    yield 'future publication timestamp', ix(lambda i: i.update(generated_at='2099-01-01T00:00:00Z')), 'publication: future cutoff or generation timestamp'
    yield 'mixed as-of timestamps', ds(lambda d: d.update(as_of='2026-11-07T13:00:00Z')), 'dataset: scope or timestamp mismatch'
    yield 'unauthorized URL', ix(lambda i: i['provenance']['federal_plans_2026'].update(url='http://example.invalid/catalog.zip')), 'source URL: require public HTTPS'
    yield 'parent traversal', ix(lambda i: i['datasets'][0].update(path='../providers-2026.json')), 'unsupported string format'
    yield 'private path', ix(lambda i: i['provenance']['federal_plans_2026'].update(title='/private/fixture')), 'privacy: private absolute path'
    for kind in ('index', 'dataset', 'ledger', 'release'):
        yield kind + ' size budget', lambda r, k=kind: oversized(r, k), 'budget: ' + (kind + ' exceeded' if kind != 'release' else 'release exceeds 2 MiB')
    yield 'SVG missing DC', lambda r: replace(r, 'plans/brand/us-states.svg', 'data-state="DC"', 'data-state="XX"'), 'Census geometry differs'
    yield 'saved section stale value', lambda r: replace(r, 'plans/index.html', '203592/203592 (100.0%)', '203591/203592 (100.0%)'), 'saved table differs: index.html'
    yield 'standalone stale value', lambda r: replace(r, 'plans/coverage-table.html', '14/32 (43.8%)', '15/32 (46.9%)'), 'saved table differs: coverage-table.html'
    for state in ('NY', 'VT', 'OR'):
        yield state + ' supplemental/SHOP serving denominator', lambda r, s=state: promote(r, s), ('supplemental NY/VT rows cannot be promoted' if state != 'OR' else 'OR SHOP cannot replace federal catalog')
    yield 'premium denominator padded beyond source rows', premium_denominator, 'premium: denominator must equal selected source rows'
    yield 'dataset year absent', ds(lambda d: d.pop('year')), 'dataset: missing required field'
    yield 'dataset year mismatched', ds(lambda d: d.update(year=2027)), 'dataset: scope or timestamp mismatch'
    yield 'coverage heading wrong year', lambda r: replace(r, 'plans/index.html', 'Coverage for plan year 2026', 'Coverage for plan year 2027'), 'year reference: coverage heading differs'
    yield 'fallback page title wrong year', lambda r: replace(r, 'plans/coverage-table.html', 'Providers / plan year 2026 —', 'Providers / plan year 2027 —'), 'year reference: fallback page title differs'
    yield 'caption wrong year', lambda r: replace_pattern(r, 'plans/index.html', r'(<caption>\s*Premiums · )2026', r'\g<1>2027'), 'year reference: table caption differs'
    yield 'reader heading frozen year', lambda r: replace(r, 'plans/coverage.js', 'Coverage for plan year ${year}', 'Coverage for plan year 2026'), 'year reference: reader title/caption must bind'
    yield 'reader caption frozen year', lambda r: replace_pattern(r, 'plans/coverage.js', r'(caption\.textContent\s*=\s*`\$\{labels\[layer\]\} · Plan year )\$\{year\}', r'\g<1>2026'), 'year reference: reader title/caption must bind'
    yield 'scanner version migration absent', ix(lambda i: i['scanner'].update(version='2.0.0')), 'index.scanner.version: unsupported enum value'
    yield 'selected scanner commit altered', ix(lambda i: i['scanner'].update(source_commit='0'*40)), 'scanner: selected source commit mismatch'
    yield 'selected input digest altered', ix(lambda i: i['scanner'].update(inputs_digest='0'*64)), 'scanner: selected input digest mismatch'
    yield 'unchanged evidence observation altered', observation_changed, 'refresh: unchanged evidence changed counts or observation dates'
    yield 'generation precedes cutoff', ix(lambda i: i.update(generated_at='2026-11-08T12:59:59Z')), 'index: generated_at before as_of'
    yield 'publication timestamp moves backward', backward_publication, 'refresh: publication timestamp moved backward'
    yield 'same hash with different bytes', same_hash_different_bytes, 'refresh: same hash with different bytes'


def main():
    # Both the publication checker and A's checker execute against actual temp files.
    # Rehash semantic mutants to ensure the intended predicate, rather than hash failure.
    originals = {p.relative_to(ROOT): p.read_bytes() for directory in ('plans', 'tools/coverage-scan')
                 for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    with tempfile.TemporaryDirectory(prefix='coverage-gate-') as tmp:
        root = Path(tmp) / 'site'
        for directory in ('plans', 'tools/coverage-scan', 'tools/coverage-ui-check', 'tests/reference'):
            shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy(ROOT / 'tools/gate.sh', root / 'tools/gate.sh')
        previous = Path(tmp) / 'previous'
        shutil.copytree(root / 'plans/data/coverage', previous)
        previous_baseline = {p.relative_to(previous): p.read_bytes() for p in previous.rglob('*') if p.is_file()}
        baseline = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        command = [sys.executable, '-B', str(ROOT / 'tools/coverage-gate/check.py'), '--root', str(root), '--previous', str(previous)]

        def run():
            result = subprocess.run(command, capture_output=True, text=True)
            return result.returncode, result.stdout + result.stderr

        code, output = run()
        assert code == 0 and 'coverage publication: PASS' in output, 'clean fixture rejected: ' + output
        print('coverage selftest: clean temporary copy PASS', flush=True)
        count = 0
        for name, mutate, reason in cases():
            mutate(root)
            changed = any(not (root / p).exists() or (root / p).read_bytes() != raw for p, raw in baseline.items())
            changed |= any(p.relative_to(root) not in baseline for p in root.rglob('*') if p.is_file())
            changed |= any((previous / p).read_bytes() != raw for p, raw in previous_baseline.items())
            assert changed, 'mutation was a no-op: ' + name
            code, output = run()
            assert code != 0 and 'FAIL: coverage publication:' in output and re.search(reason, output), name + ': expected ' + reason + '; got ' + output
            print('coverage negative: PASS (' + name + '; ' + reason + ')', flush=True)
            count += 1
            for path in root.rglob('*'):
                if path.is_file() and path.relative_to(root) not in baseline:
                    path.unlink()
            for name_in_copy, raw in baseline.items():
                path = root / name_in_copy
                if not path.exists() or path.read_bytes() != raw:
                    path.write_bytes(raw)
            for name_in_copy, raw in previous_baseline.items():
                (previous / name_in_copy).write_bytes(raw)
        advance_cutoff(root)
        code, output = run()
        assert code == 0, 'unchanged observations at a validated later cutoff rejected: ' + output
        print('coverage positive: PASS (later cutoff retains original observations and assertions)', flush=True)
        for path in root.rglob('*'):
            if path.is_file() and path.relative_to(root) not in baseline:
                path.unlink()
        for name_in_copy, raw in baseline.items():
            (root / name_in_copy).write_bytes(raw)
        code, output = run()
        assert code == 0 and 'coverage publication: PASS' in output, 'restored fixture rejected: ' + output
        assert all((root / p).read_bytes() == raw for p, raw in baseline.items()), 'temporary originals changed'
    assert all((ROOT / p).read_bytes() == raw for p, raw in originals.items()), 'committed originals changed'
    print(f'coverage selftest: PASS (clean and restored copies; {count} diagnostic-checked negative controls; originals byte-identical)')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        print('FAIL: coverage selftest: ' + str(exc), file=sys.stderr)
        sys.exit(1)
