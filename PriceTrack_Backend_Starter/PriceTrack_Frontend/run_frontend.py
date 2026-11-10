"""Serve Price Track UI on :5500 and forward read-only /api requests to :3000.
Python standard library only. Keep your existing backend running separately.
Run: py run_frontend.py
Optional: py run_frontend.py --port 5501 --backend http://127.0.0.1:3000
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import argparse
import json
import re
import mimetypes

PUBLIC = Path(__file__).resolve().parent / 'public'
BACKEND = 'http://127.0.0.1:3000'
ALLOWED = {
    '/api/health', '/api/overview', '/api/dashboard', '/api/opportunities',
    '/api/opportunities/stages', '/api/users',
    '/api/mappings/business-units', '/api/mappings/capabilities',
    '/api/rates/client', '/api/rates/standard', '/api/workflow-config',
    '/api/pricing-cases', '/api/workbook-reference', '/api/approval-inbox', '/api/auth/me',
}

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, content_type='application/json; charset=utf-8',set_cookie=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if set_cookie:self.send_header('Set-Cookie',set_cookie)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def error_json(self, status, message):
        self.reply(status, json.dumps({'error': message}).encode())

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        if urlsplit('http://'+self.headers.get('Host','')).hostname not in ('localhost','127.0.0.1'):
            return self.error_json(403,'Use a localhost address.')
        requested = urlsplit(self.path)
        if not (self.command == 'POST' and requested.path in ('/api/pricing-cases','/api/auth/login','/api/auth/logout')) and not (self.command == 'PUT' and re.fullmatch(r'/api/pricing-cases/[A-Za-z0-9-]+/(resources|workbook-calculation|versions|approvals|negotiation)', requested.path)):
            return self.error_json(404, 'Unknown write API route')
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
            if content_length < 1 or content_length > 262144:
                return self.error_json(413, 'Invalid request size')
            payload = self.rfile.read(content_length)
            target = BACKEND + requested.path
            request = Request(target, data=payload, method=self.command, headers={
                'Accept': 'application/json',
                'Content-Type': self.headers.get('Content-Type', 'application/json'),
                **{key:self.headers[key] for key in ('Cookie','X-CSRF-Token','X-PriceTrack-Request','Origin','Sec-Fetch-Site') if self.headers.get(key)},
            })
            with urlopen(request, timeout=10) as upstream:
                payload = upstream.read(10 * 1024 * 1024 + 1)
                if len(payload) > 10 * 1024 * 1024:
                    return self.error_json(502, 'Backend response too large')
                return self.reply(upstream.status, payload, 'application/json; charset=utf-8',upstream.headers.get('Set-Cookie'))
        except HTTPError as error:
            return self.reply(error.code, error.read(65536), 'application/json; charset=utf-8',error.headers.get('Set-Cookie'))
        except (URLError, TimeoutError, OSError, ValueError):
            return self.error_json(503, 'Backend request failed; check that the Python backend is running')

    def do_PUT(self):
        self.do_POST()

    def do_GET(self):
        if urlsplit('http://'+self.headers.get('Host','')).hostname not in ('localhost','127.0.0.1'):
            return self.error_json(403,'Use a localhost address.')
        requested = urlsplit(self.path)
        if requested.path.startswith('/api/'):
            if requested.path not in ALLOWED and not requested.path.startswith('/api/opportunities/') and not re.fullmatch(r'/api/pricing-cases/[A-Za-z0-9-]+/(resources|workbook-calculation|versions|approvals|negotiation|activity|readiness)', requested.path):
                return self.error_json(404, 'Unknown read-only API route')
            try:
                target = BACKEND + requested.path + ('?' + requested.query if requested.query else '')
                with urlopen(Request(target, headers={'Accept': 'application/json',**({'Cookie':self.headers['Cookie']} if self.headers.get('Cookie') else {})}), timeout=9) as upstream:
                    payload = upstream.read(10 * 1024 * 1024 + 1)
                    if len(payload) > 10 * 1024 * 1024:
                        return self.error_json(502, 'Backend response too large')
                    return self.reply(upstream.status, payload, 'application/json; charset=utf-8',upstream.headers.get('Set-Cookie'))
            except HTTPError as error:
                return self.reply(error.code,error.read(65536),'application/json; charset=utf-8',error.headers.get('Set-Cookie'))
            except (URLError, TimeoutError, OSError):
                return self.error_json(503, 'Start your existing Python backend on localhost:3000')
        relative = unquote(requested.path).lstrip('/') or 'index.html'
        try:
            file = (PUBLIC / relative).resolve()
            if not file.is_relative_to(PUBLIC.resolve()) or not file.is_file():
                return self.error_json(404, 'File not found')
            content_type = mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
            if file.suffix == '.js':
                content_type = 'text/javascript; charset=utf-8'
            elif file.suffix in {'.css', '.html'}:
                content_type += '; charset=utf-8'
            self.reply(200, file.read_bytes(), content_type)
        except (OSError, ValueError):
            self.error_json(404, 'File not found')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5500)
    parser.add_argument('--backend', default=BACKEND)
    args = parser.parse_args()
    parsed = urlsplit(args.backend)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1'} or parsed.path not in {'', '/'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error('--backend must be an HTTP localhost address, such as http://127.0.0.1:3000')
    if not PUBLIC.joinpath('index.html').is_file():
        parser.error('public/index.html is missing. Keep the public folder beside run_frontend.py.')
    BACKEND = args.backend.rstrip('/')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Price Track frontend running at http://localhost:{args.port}', flush=True)
    print(f'Read-only API proxy: {BACKEND}', flush=True)
    print('Keep your existing Python backend running. Press Ctrl+C to stop the frontend.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nFrontend stopped.')
    finally:
        server.server_close()
