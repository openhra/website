#!/usr/bin/env python3
"""Keep unreleased agent previews honest and repository actions first."""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {'search', 'fetch', 'search_plans', 'get_plan', 'estimate_premiums',
         'search_providers', 'check_provider_network', 'search_drugs',
         'check_drug_coverage', 'lookup_geography', 'list_carriers_networks',
         'get_data_status'}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
        self.parts = []

    def text(self):
        return ' '.join(self.parts).strip()

    def find(self, predicate):
        result = []
        for child in self.children:
            if predicate(child):
                result.append(child)
            result.extend(child.find(predicate))
        return result


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.root = self.current = Node()
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {'meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'wbr'}:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent and node.tag != tag:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        node = self.current
        while node:
            node.parts.append(data)
            node = node.parent


def classed(node, name):
    return name in node.attrs.get('class', '').split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_page(source, site):
    root = Page(source).root
    all_text = root.text().lower()
    target = 'https://github.com/openhra' + ('/openplans' if site == 'plans' else '')
    previews = root.find(lambda n: 'data-mcp-preview' in n.attrs)
    require(len(previews) >= (7 if site == 'plans' else 3), 'missing MCP preview blocks')
    for preview in previews:
        labels = preview.find(lambda n: 'in development' in n.text().lower())
        require('in development' in preview.text().lower(), 'MCP preview missing In development')
        require('hidden' not in preview.attrs and all('hidden' not in n.attrs for n in labels),
                'MCP status hidden')
    require('not yet released or hosted' in all_text, 'MCP release/hosting limit missing')
    require('no release yet' in all_text, 'no-release status missing')
    require('streamable http' in all_text and 'stateless' in all_text and 'read-only' in all_text,
            'planned transport or read-only scope missing')
    require('unknown' in all_text and 'provenance' in all_text, 'evidence/unknown rule missing')
    nav = root.find(lambda n: n.tag == 'nav')[0]
    first = nav.find(lambda n: n.tag == 'ul')[0].find(lambda n: n.tag == 'a')[0]
    require(first.attrs.get('href') == target, 'GitHub must lead navigation')
    hero = root.find(lambda n: classed(n, 'hero'))[0]
    first = hero.find(lambda n: classed(n, 'actions'))[0].find(lambda n: n.tag == 'a')[0]
    require(first.attrs.get('href') == target and classed(first, 'button'), 'GitHub must lead hero actions')
    directories = root.find(lambda n: classed(n, 'repo-directory'))
    require(directories, 'repository directory missing')
    for directory in directories:
        text = directory.text().lower()
        require(all(label in text for label in ['code', 'docs', 'issues', 'releases', 'no release yet']),
                'repository contents/release status missing')
    require('git clone https://github.com/openhra/openplans.git' in all_text, 'clone command missing')
    if site == 'plans':
        directory = root.find(lambda n: classed(n, 'tool-directory'))[0]
        actual = [n.text() for n in directory.find(lambda n: n.tag == 'code')]
        require(len(actual) == len(TOOLS) and set(actual) == TOOLS, 'planned tool inventory differs')
        example = root.find(lambda n: classed(n, 'agent-example'))[0].text().lower()
        require('example agent exchange' in example and 'illustrative only' in example and 'no live request' in example,
                'agent exchange must be labelled illustrative')
        panels = root.find(lambda n: classed(n, 'connection-panel'))
        require(len(panels) == 2, 'connection previews missing')
        for panel in panels:
            require('planned' in panel.text().lower(), 'connection must be labelled planned')
        public = panels[0]
        require('not hosted' in public.text().lower(), 'public connection hosting limit missing')
        raw = public.find(lambda n: n.tag == 'pre')[0].text()
        config = json.loads(raw)
        require(config == {'mcpServers': {'openplans': {'url': 'https://openplans.openhra.com/mcp'}}},
                'generic MCP config differs')
        require('http://127.0.0.1:3000/mcp' in panels[1].text() and
                'openplans-mcp' in panels[1].text() and 'not released' in panels[1].text().lower(),
                'local planned interfaces missing')
        require('OPENPLANS_RAW_READ_ONLY=false docker compose run --build --rm worker bootstrap --states TX,FL --years 2026,2027' in root.text(),
                'README bootstrap command differs')


def run(root):
    for site in ['openhra', 'plans']:
        check_page((root / site / 'index.html').read_text(), site)
    require((root / 'openhra/brand/site.css').read_bytes() == (root / 'plans/brand/site.css').read_bytes(),
            'shared site styles differ')
    for name in ['index.html', 'style.css']:
        require((root / 'openhra' / name).read_bytes() == (root / 'plans/brand/openhra' / name).read_bytes(),
                'organisation handoff copy differs: ' + name)
    print('mcp: PASS (development labels, planned interfaces, 12 tools, GitHub-first actions, handoff parity)')


def selftest(root):
    sources = {site: (root / site / 'index.html').read_text() for site in ['openhra', 'plans']}
    mutants = [
        ('plans', 'MCP status removed', lambda s: s.replace('In development', 'Available now').replace('in development', 'available now'), 'In development'),
        ('openhra', 'organisation MCP status removed', lambda s: s.replace('In development', 'Available now').replace('in development', 'available now'), 'In development'),
        ('plans', 'local status removed', lambda s: s.replace('In development · not released', 'Not released'), 'In development'),
        ('plans', 'planned endpoint label removed', lambda s: s.replace('Planned public endpoint', 'Public endpoint'), 'labelled planned'),
        ('plans', 'hosted claim', lambda s: s.replace('not hosted', 'hosted now'), 'hosting limit'),
        ('plans', 'example label removed', lambda s: s.replace('Illustrative only', 'Live reply'), 'labelled illustrative'),
        ('plans', 'tool removed', lambda s: s.replace('<code>get_plan</code>', ''), 'inventory'),
        ('plans', 'wrong endpoint', lambda s: s.replace('https://openplans.openhra.com/mcp', 'https://plans.openhra.com/mcp'), 'config differs'),
        ('plans', 'no-release label removed', lambda s: re.sub('no release yet', 'released', s, flags=re.I), 'no-release'),
        ('plans', 'hero action displaced', lambda s: s.replace('class="button" href="https://github.com/openhra/openplans"', 'class="button" href="#connect"', 1), 'hero actions'),
    ]
    for site, name, mutate, diagnostic in mutants:
        try:
            check_page(mutate(sources[site]), site)
        except (ValueError, AssertionError) as exc:
            require(diagnostic in str(exc), 'unexpected mutant diagnostic: ' + name + ': ' + str(exc))
            print('mcp negative: PASS (' + name + ')')
        else:
            raise ValueError('mutant accepted: ' + name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', type=Path, default=ROOT)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    try:
        run(args.root)
        if args.selftest:
            selftest(args.root)
    except (ValueError, KeyError, IndexError) as exc:
        raise SystemExit('FAIL: MCP presentation: ' + str(exc))
