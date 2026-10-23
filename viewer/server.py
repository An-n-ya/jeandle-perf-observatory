#!/usr/bin/env python3
"""Serve local Jeandle perf data. Python standard library only."""
import argparse
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, urlsplit

from perfview.data import catalog, NotReady, discover
from perfview.stacks import speedscope

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    server_version = 'JeandlePerf/1.0'

    def log_message(self, format, *args):
        if self.path != '/api/status':
            super().log_message(format, *args)

    def respond(self, data, mime='application/json; charset=utf-8', status=200, download=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
        compressed = 'gzip' in self.headers.get('Accept-Encoding', '') and len(data) > 2048
        if compressed:
            data = gzip.compress(data, compresslevel=3)
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if compressed:
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Vary', 'Accept-Encoding')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # Loopback plus Host / Origin checks prevent browser DNS rebinding.
        authority = self.headers.get('Host', '')
        allowed = {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
        if authority not in allowed or self.headers.get('Origin', 'http://' + authority) != 'http://' + authority:
            return self.respond({'error': 'Local requests only'}, status=403)
        url = urlsplit(self.path)
        args = parse_qs(url.query)
        def param(key, default=None):
            return args.get(key, [default])[0]
        try:
            if url.path == '/api/datasets':
                return self.respond([catalog(d) for d in self.server.datasets.values()])
            if url.path.startswith('/api/'):
                dataset = self.server.datasets[param('dataset', next(iter(self.server.datasets)))]
                if url.path == '/api/status':
                    return self.respond(dataset.status())
                if url.path == '/api/overview':
                    return self.respond(dataset.overview)
                if url.path == '/api/raw':
                    p = dataset.raw(param('file'))
                    return self.respond(p.read_bytes(), 'text/plain; charset=utf-8')
                if url.path == '/api/record':
                    return self.respond(dataset.record(param('case'), param('mode'), param('run'), param('kind')),
                                        'text/plain; charset=utf-8')
                if url.path in ('/api/profile', '/api/speedscope'):
                    profile = dataset.profile(param('case'), param('mode'), param('run', 'all'))
                    if url.path == '/api/profile':
                        return self.respond(profile)
                    name = f"{profile['case']} {profile['mode']}"
                    filename = re.sub(r'[^A-Za-z0-9_.-]', '-',
                                      f"{profile['case']}-{profile['mode']}-{profile['run']}")
                    return self.respond(speedscope(profile, name),
                                        download=filename + '.speedscope.json')
                raise KeyError('Unknown endpoint')
            static = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if url.path not in static:
                raise KeyError('Not found')
            name, mime = static[url.path]
            self.respond((ROOT / 'web' / name).read_bytes(), mime)
        except NotReady:
            self.respond({'indexing': True, 'status': dataset.status()}, status=202)
        except (KeyError, ValueError) as exc:
            self.respond({'error': str(exc)}, status=404)
        except (BrokenPipeError, ConnectionResetError):
            pass


def create_server(datasets, port):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.datasets = datasets
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', action='append', type=Path, help='Dataset directory; repeat for multiple datasets')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache')
    args = parser.parse_args()
    paths = args.data or sorted((ROOT.parent / 'jeandle-develop-log/artifacts').glob('java-type-perf-*')) + sorted((ROOT.parent / 'jeandle-develop-log/artifacts').glob('context-cache-reuse-*'))
    if not paths:
        parser.error('No datasets found. Specify --data /path/to/artifacts')
    datasets = discover(paths, args.cache)
    try:
        server = create_server(datasets, args.port)
    except OSError as exc:
        parser.error(f'Cannot listen on 127.0.0.1:{args.port}: {exc}. Try --port with another port.')
    for dataset in datasets.values():
        threading.Thread(target=dataset.index, daemon=True).start()
    print(f'Jeandle Perf Observatory: http://127.0.0.1:{server.server_port}', flush=True)
    print('Read-only data. Stack indexes are disposable; Ctrl-C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
