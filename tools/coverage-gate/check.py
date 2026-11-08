#!/usr/bin/env python3
"""Offline site publication checks, reusing the scanner's data contract."""
import argparse
import datetime as dt
import html.parser
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/coverage-scan'))
from check import check_release
from model import Invalid, VERSION, encoded, loads, require, safe_text, sha, timestamp


def ui_check(root):
    spec = importlib.util.spec_from_file_location('coverage_ui', ROOT / 'tools/coverage-ui-check/check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if root.resolve() == ROOT and subprocess.run(
            ['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'], capture_output=True).returncode:
        # Archive/unborn fixtures have no historical content to compare. All data,
        # table, geometry, year, DOM and budget checks still run against this root.
        module.ROOT = root / '__no_history__'
    module.check(root)


class Markup(html.parser.HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack, self.text = [], {}
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        key = attrs.get('id', tag if tag in ('title', 'h1', 'caption') else None)
        self.stack.append((tag, key))
        if key:
            self.text.setdefault(key, []).append('')

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        for _, key in self.stack:
            if key:
                self.text[key][-1] += data

    def one(self, key):
        values = self.text.get(key, [])
        require(len(values) == 1, 'year reference: missing or duplicate ' + key)
        return values[0].strip()


def years(root, index):
    default = loads((root / 'plans/data/coverage/providers-2026.json').read_bytes())
    year = default['year']
    for filename in ('index.html', 'coverage-table.html'):
        page = Markup((root / 'plans' / filename).read_text())
        title = page.one('coverage-title' if filename == 'index.html' else 'h1')
        require(title == f'Coverage for plan year {year}', 'year reference: coverage heading differs from dataset')
        require(re.match(rf'^Providers · (?:Plan year )?{year} · ', page.one('caption')),
                'year reference: table caption differs from dataset')
        if filename == 'coverage-table.html':
            require(page.one('title') == f'Providers / plan year {year} — OpenPlans',
                    'year reference: fallback page title differs from dataset')
        else:
            require(page.one('coverage-svg-title') == f'Provider source availability by state, {year}',
                    'year reference: map title differs from dataset')
    # Check the reader's actual assignments, not just a year string elsewhere in it.
    # Runtime/browser behavior remains B's separate optional browser suite.
    reader = (root / 'plans/coverage.js').read_text()
    require("const {layer, year} = d;" in reader and
            "$('title').textContent = `Coverage for plan year ${year}`;" in reader and
            'caption.textContent = `${labels[layer]} · Plan year ${year} · Figures as of ${date(d.as_of)}.' in reader,
            'year reference: reader title/caption must bind the selected dataset year')
    require('d.year === entry.year' in reader, 'year reference: reader must reject mismatched dataset year')
    require(all(type(d['year']) is int for d in index['datasets']), 'year reference: dataset year required')


def selection_binding(root, release, index):
    selection = loads((root / 'tools/coverage-scan/selection.example.json').read_bytes())
    safe_text(selection)
    inputs = {}
    for collection in ('sources', 'reports'):
        for key, spec in selection[collection].items():
            require(key not in inputs, 'selection: duplicate input identity')
            inputs[key] = spec['sha256']
            path = spec['path']
            require(path and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and '\\' not in path and not re.match(r'[A-Za-z]:', path),
                    'selection: unsafe relative input path')
    require(index['scanner']['version'] == VERSION, 'scanner: implementation version mismatch; migration required')
    require(index['scanner']['source_commit'] == selection['source_commit'], 'scanner: selected source commit mismatch')
    require(index['scanner']['inputs_digest'] == sha(encoded(dict(selection=selection, inputs=inputs))),
            'scanner: selected input digest mismatch')
    expected_provenance = {key: {k: spec[k] for k in ('url', 'title', 'vintage', 'retrieved_at', 'sha256')}
                           for key, spec in selection['sources'].items()}
    require(index['provenance'] == expected_provenance, 'selection: public source identity mismatch')
    seen, selected = {}, {}
    for spec in selection['premium_scopes']:
        selected[('premiums', spec['year'], spec['state'])] = spec
    for spec in selection['issuer_scopes']:
        key = (spec['layer'], spec['year'], spec['state'])
        require(key not in selected, 'selection: duplicate state/layer/year')
        selected[key] = spec
    require(len(selected) == len(selection['premium_scopes']) + len(selection['issuer_scopes']),
            'selection: duplicate state/layer/year')
    members = {}
    for path in sorted((release / 'evidence').glob('*.json')):
        ledger = loads(path.read_bytes())
        require(all(key in inputs and value == inputs[key] for key, value in ledger['inputs'].items()),
                'selection: ledger input hash mismatch')
        seen.update(ledger['inputs'])
        for state, scope in ledger['scopes'].items():
            key = (ledger['layer'], ledger['year'], state)
            require(key in selected, 'selection: unselected evidence scope')
            spec = selected.pop(key)
            require(scope['inventory']['source_id'] == spec['source'], 'selection: evidence source mismatch')
            keys = ('source', 'plan_source', 'report', 'serving_report') if ledger['layer'] == 'premiums' else ('source', 'report', 'audit')
            require(set(scope['input_ids']) == {spec[k] for k in keys if spec[k] is not None},
                    'selection: scope input identities mismatch')
            names = [('inventory', 'rate_member'), ('plan_inventory', 'plan_member')] if ledger['layer'] == 'premiums' else [('inventory', 'plan_member')]
            for field, member_field in names:
                inv = scope[field]
                source = spec['plan_source'] if field == 'plan_inventory' else spec['source']
                require(inv['source_id'] == source and inv['member'] == spec[member_field], 'selection: selected member mismatch')
                # Identical public member bytes cannot assert different state row identities.
                identity = (inputs[source], inv['member'], state, ledger['year'])
                require(identity not in members or members[identity] == inv, 'inventory: same source hash has inconsistent member rows')
                members[identity] = inv
            if ledger['layer'] == 'premiums':
                record = loads((release / f'premiums-{ledger["year"]}.json').read_bytes())['states'][state]
                if record['denominator'] is not None:
                    require(record['denominator'] == scope['inventory']['rows'], 'premium: denominator must equal selected source rows')
                if scope['reconciliation']:
                    require(scope['reconciliation']['report_id'] == spec['report'], 'selection: reconciliation report mismatch')
    require(not selected and seen == inputs, 'selection: missing selected evidence or unused input')


def refresh(previous, current):
    old, new = (loads((p / 'index.json').read_bytes()) for p in (previous, current))
    for field in ('schema_version', 'metric_version', 'scope', 'population', 'state_codes'):
        require(old[field] == new[field], 'refresh: scope/version/state change requires reviewed migration')
    require(old['scanner']['version'] == new['scanner']['version'], 'refresh: scanner version change requires reviewed migration')
    for field in ('as_of', 'generated_at'):
        require(timestamp(old[field]) <= timestamp(new[field]), 'refresh: publication timestamp moved backward')
    old_entries = {(d['layer'], d['year']): d for d in old['datasets']}
    require(set(old_entries) <= {(d['layer'], d['year']) for d in new['datasets']}, 'refresh: lost layer/year')
    for entry in new['datasets']:
        key = (entry['layer'], entry['year'])
        if key not in old_entries:
            continue
        prior = old_entries[key]
        before, after = (previous / prior['path']).read_bytes(), (current / entry['path']).read_bytes()
        require(prior['sha256'] != entry['sha256'] or before == after, 'refresh: same hash with different bytes')
        saved_states = loads(before)['states']
        for state, record in loads(after)['states'].items():
            saved = saved_states[state]
            if saved['evidence'] and record['evidence']:
                old_ledger = loads((previous / saved['evidence']['path']).read_bytes())
                new_ledger = loads((current / record['evidence']['path']).read_bytes())
                hashes = lambda r, ledger: {i: ledger['inputs'][i] for i in r['evidence']['input_ids']}
                same_scanner = all(old['scanner'][k] == new['scanner'][k] for k in ('version', 'source_commit'))
                if hashes(saved, old_ledger) == hashes(record, new_ledger) and same_scanner:
                    require(all(record[k] == saved[k] for k in record if k != 'evidence'),
                            'refresh: unchanged evidence changed counts or observation dates')
                    require(old_ledger['scopes'][state] == new_ledger['scopes'][state],
                            'refresh: unchanged evidence changed ledger assertions')
            require(not saved['evidence'] or record['evidence'], 'refresh: lost selected state evidence; review migration')


def check(root, previous=None):
    release = root / 'plans/data/coverage'
    index = check_release(release)
    now = dt.datetime.now(dt.timezone.utc)
    require(timestamp(index['generated_at']) <= now and timestamp(index['as_of']) <= now,
            'publication: future cutoff or generation timestamp')
    selection_binding(root, release, index)
    if previous:
        refresh(previous, release)
    years(root, index)
    ui_check(root)


def committed_release(root, ref, dest):
    result = subprocess.run(['git', '-C', str(root), 'ls-tree', '-r', '--name-only', ref, '--', 'plans/data/coverage'],
                            capture_output=True, text=True)
    require(result.returncode == 0, 'refresh: cannot read committed baseline')
    for name in result.stdout.splitlines():
        path = dest / Path(name).relative_to('plans/data/coverage')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(['git', '-C', str(root), 'show', ref + ':' + name]))
    require((dest / 'index.json').is_file(), 'refresh: committed baseline absent')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--previous', type=Path, help='Previous validated coverage release directory')
    parser.add_argument('--previous-ref', help='Local committed baseline (no network)')
    args = parser.parse_args()
    try:
        require(not (args.previous and args.previous_ref), 'refresh: choose one baseline')
        with tempfile.TemporaryDirectory() as tmp:
            previous = args.previous
            if args.previous_ref:
                previous = Path(tmp)
                committed_release(args.root, args.previous_ref, previous)
            check(args.root, previous)
        print('coverage publication: PASS (selected evidence, scanner, refresh, plan year, table and geometry)')
    except (Invalid, AssertionError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        reason = str(exc) if isinstance(exc, (Invalid, AssertionError)) else 'malformed or unreadable publication'
        print('FAIL: coverage publication: ' + reason, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
