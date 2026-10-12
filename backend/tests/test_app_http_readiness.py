from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from packs.code.readiness import probe_app


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status = 302 if self.path == '/redirect' else 500 if self.path == '/error' else 200
            self.send_response(status)
            if status == 302:
                self.send_header('Location', 'https://example.com/private')
            self.end_headers()
            self.wfile.write(b'controlled app')

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{http.server_port}'
    http.shutdown()
    http.server_close()
    thread.join()


def test_real_http_response_is_ready(server):
    assert probe_app(server)['ready'] is True
    assert probe_app(server)['http_status'] == 200


def test_http_errors_and_redirects_are_not_ready(server):
    assert probe_app(server + '/error')['ready'] is False
    result = probe_app(server + '/redirect')
    assert result['ready'] is False
    assert result['http_status'] == 302


@pytest.mark.parametrize('url', ['https://example.com', 'http://user:secret@localhost', 'file:///tmp/a'])
def test_unapproved_destinations_are_never_probed(url):
    assert 'Only credential-free loopback' in probe_app(url)['readiness_error']


def test_closed_port_is_not_ready():
    import socket
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    assert probe_app(f'http://127.0.0.1:{port}', timeout=0.1)['ready'] is False


def test_a_printed_url_is_starting_until_http_answers(tmp_path):
    from collections import deque
    from types import SimpleNamespace
    from packs.code.apps import AppProcess, AppTools
    process = SimpleNamespace(poll=lambda: None, pid=123)
    app = AppProcess('dev', 'dev', process, 0, deque(), url='http://localhost:3000')
    tools = AppTools(probe=lambda *a, **kw: {'ready': False, 'readiness_error': 'not listening'})
    tools._apps[str(tmp_path.resolve())] = {'default': app}
    try:
        assert tools.status(tmp_path)['state'] == 'starting'
        tools._probe = lambda *a, **kw: {'ready': True, 'http_status': 200}
        assert tools.status(tmp_path)['state'] == 'ready'
        process.poll = lambda: 1
        process.returncode = 1
        assert tools.status(tmp_path)['ready'] is False
        assert tools.status(tmp_path)['state'] == 'stopped'
    finally:
        tools._apps.clear()
