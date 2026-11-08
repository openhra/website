#!/usr/bin/env python3
"""Check this design preview only; production scanner/gate are future slices."""
import argparse
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CODES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def check(data, svg, html):
    require(set(data['states']) == CODES, 'state inventory')
    require(data['as_of'] == '2026-11-08', 'preview date')
    require(set(data['datasets']) == {f'{l}-{y}' for l in ['premiums', 'providers', 'prescriptions'] for y in [2026, 2027]}, 'dataset inventory')
    for key, rows in data['datasets'].items():
        require(set(rows) == CODES, 'dataset state set')
        for state, row in rows.items():
            n, d, pct = [row[f] for f in ['numerator', 'denominator', 'percent_tenths']]
            if d is None:
                require(n is None and pct is None and row['status'] == 'unknown', 'unknown fraction')
            else:
                require(type(n) is int and type(d) is int and type(pct) is int and 0 <= n <= d and d > 0, 'count bounds')
                require(pct == (2000 * n + d) // (2 * d), 'percentage mismatch')
            if 'issuer_evidence' in row:
                ledger = row['issuer_evidence']
                require(len(ledger) == len({r['issuer'] for r in ledger}) == d, 'issuer roster')
                active = sum(r['bucket'] in ['active_complete', 'active_partial'] for r in ledger)
                partial = sum(r['bucket'] == 'active_partial' for r in ledger)
                quarantine = sum(r['bucket'] == 'quarantined' for r in ledger)
                require(sum(r['bucket'] == 'unknown' for r in ledger) == row['unknown'], 'unknown bucket mismatch')
                require(active == n and partial == row['active_partial'] and quarantine == row['quarantined'] and active + quarantine + row['unknown'] == d, 'issuer bucket mismatch')
            require(all(k in data['evidence'] for k in row['evidence']), 'evidence reference')
    for inventory in data['public_inventory'].values():
        for state, roster in inventory['issuers'].items():
            for layer in ['providers', 'prescriptions']:
                row = data['datasets'][layer + '-2026'][state]
                require(set(roster) == {r['issuer'] for r in row['issuer_evidence']}, 'public roster mismatch')
    for key, expected in [('providers-2026', {'TX': (14, 32, 438), 'FL': (11, 26, 423), 'NC': (6, 13, 462), 'GA': (0, 16, 0)}), ('prescriptions-2026', {'TX': (11, 32, 344), 'FL': (9, 26, 346), 'NC': (3, 13, 231), 'GA': (0, 16, 0)})]:
        for state, values in expected.items():
            row = data['datasets'][key][state]
            require(tuple(row[k] for k in ['numerator', 'denominator', 'percent_tenths']) == values, 'report-derived golden')
    for year, total in [(2026, 49), (2027, 29)]:
        require(sum(r['status'] == 'measured' for r in data['datasets'][f'premiums-{year}'].values()) == total, 'premium scope count')
    ids = re.findall(r'id="state-([A-Z]{2})"', svg)
    require(len(ids) == 51 and set(ids) == CODES, 'map state set')
    require(html.count('<th scope="row">') == 51, 'fallback row count')
    table_rows = re.findall(r'<tr><th scope="row">([^<]+)</th><td><strong>([^<]+)</strong><span class="sub">([^<]+)</span>', html)
    by_name = {name: state for state, name in data['states'].items()}
    require(len(table_rows) == 51 and len({r[0] for r in table_rows}) == 51, 'fallback state inventory')
    for name, label, fraction in table_rows:
        require(name in by_name, 'fallback state name')
        row = data['datasets']['providers-2026'][by_name[name]]
        expected = 'Unknown' if row['status'] == 'unknown' else 'Quarantined' if row['status'] == 'quarantined' else f"{row['percent_tenths'] / 10:.1f}%"
        count = 'Denominator unverified' if row['denominator'] is None else f"{row['numerator']} / {row['denominator']} issuers"
        require(label == expected and fraction == count, 'fallback value mismatch')
    require('Mockup, figures as of November 8, 2026' in html, 'preview label')
    require('script src="http' not in html, 'remote script')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'mockup-data.json').read_text())
    svg = (ROOT / 'map.svg').read_text()
    html = (ROOT / 'mockup.html').read_text()
    check(data, svg, html)
    if args.self_test:
        mutants = []
        m = copy.deepcopy(data); m['datasets']['providers-2026']['TX']['percent_tenths'] = 500
        mutants.append((m, svg, html, 'percentage mismatch'))
        m = copy.deepcopy(data); del m['datasets']['premiums-2027']['DC']
        mutants.append((m, svg, html, 'dataset state set'))
        m = copy.deepcopy(data); m['datasets']['providers-2026']['AK']['numerator'] = 0
        mutants.append((m, svg, html, 'unknown fraction'))
        m = copy.deepcopy(data); m['datasets']['providers-2026']['TX']['issuer_evidence'][0]['bucket'] = 'active_complete'
        mutants.append((m, svg, html, 'issuer bucket mismatch'))
        mutants.append((data, svg.replace('id="state-DC"', 'id="removed-DC"'), html, 'map state set'))
        mutants.append((data, svg, html.replace('<th scope="row">', '<th>', 1), 'fallback row count'))
        mutants.append((data, svg, html.replace('<strong>43.8%</strong>', '<strong>50.0%</strong>'), 'fallback value mismatch'))
        for m, s, h, expected in mutants:
            try:
                check(m, s, h)
            except ValueError as exc:
                require(str(exc) == expected, f'wrong rejection: {exc}; expected {expected}')
                print(f'negative control: PASS ({expected})')
            else:
                raise ValueError(f'mutant survived: {expected}')
        check(data, svg, html)
    print('mockup: PASS (6 datasets, 51 states each, exact percentages, issuer ledgers, SVG and fallback)')


if __name__ == '__main__':
    main()
