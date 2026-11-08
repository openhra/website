#!/usr/bin/env python3
"""Loopback static preview with the site's extensionless HTML routing."""
import argparse
import functools
import http.server
import json
from pathlib import Path

PLANS = Path(__file__).resolve().parents[2] / 'plans'
CONFIG = json.loads((PLANS / 'vercel.json').read_text())


class Preview(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, request):
        target = Path(super().translate_path(request))
        if CONFIG.get('cleanUrls') and not target.exists() and not target.suffix:
            html = target.with_suffix('.html')
            if html.is_file():
                return str(html)
        return str(target)

    def end_headers(self):
        for rule in CONFIG['headers']:
            if rule['source'] == '/(.*)':
                for header in rule['headers']:
                    self.send_header(header['key'], header['value'])
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8779)
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), functools.partial(Preview, directory=str(PLANS)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
