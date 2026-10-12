"""The model on TabbyAPI is on the card before the first message.

**Reported 12 October 2026:** *"I set Zaram up to start warming the local LLM
after loading its dependencies on launch. It still seems to warm up after my
first prompt."*

The setup that made it true: the maintainer's TabbyAPI has `model_name:` empty
and `inline_model_loading: true` on purpose, so nothing is on the card until a
request names a model. Zaram's boot preload warmed Ollama's model and
*refused* anything served by another local server, on the reasoning that an
OpenAI-compatible server has no way to load without generating. TabbyAPI does:
`POST /v1/model/load`, the twin of the unload route Zaram already calls. So the
chosen default -- the one that actually answers -- was never loaded, and the
first message of every session paid for it.

Three things are pinned, each against a real HTTP server on loopback rather
than a fake engine (a fake with a `load` method is the scaffolding the
`CLAUDE.md` working agreement says passes while the shipped path is dead):

* an empty server is asked to load, and the model name travels in the body;
* a server that already holds a model is never asked to swap -- loading on
  TabbyAPI unloads what is there, and a preload is the wrong reason to evict;
* a server without the route, or an answer Zaram cannot read, is left alone.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

MODEL = "Qwen3.8-27B-exl3-2.20bpw"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.server.requests.append(("GET", self.path, None))
        if not self.server.has_routes:
            return self._send(404, {"detail": "Not Found"})
        if self.path == "/v1/model":
            if self.server.busy:
                return self._send(503, {"detail": "Model is loading."})
            if self.server.loaded:
                return self._send(200, {"id": self.server.loaded})
            return self._send(503, {"detail": "No models are currently loaded."})
        self._send(404, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append(("POST", self.path, body))
        if self.path == "/v1/model/load" and self.server.has_routes:
            if self.server.load_status == 200:
                self.server.loaded = body.get("model_name")
            return self._send(self.server.load_status, {"module": 1, "status": "finished"})
        self._send(404, {})


class _Tabby(ThreadingHTTPServer):
    """TabbyAPI's two routes that matter here, and a log of what was asked."""

    def __init__(self, *, loaded=None, has_routes=True, load_status=200, busy=False):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.loaded = loaded
        self.has_routes = has_routes
        self.load_status = load_status
        self.busy = busy
        self.requests: list = []
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def stop(self) -> None:
        self.shutdown()
        self.server_close()


@pytest.fixture
def tabby():
    made: list = []

    def make(**kw):
        server = _Tabby(**kw)
        made.append(server)
        return server

    yield make
    for server in made:
        try:
            server.stop()
        except Exception:  # already stopped by the test
            pass


def _engine(server) -> OpenAICompatibleEngine:
    return OpenAICompatibleEngine(base_url=server.url, api_key="", default_model=MODEL)


def _posts(server):
    return [r for r in server.requests if r[0] == "POST"]


def test_an_empty_server_is_asked_to_load_the_model_by_name(tabby):
    server = tabby()

    assert _engine(server).load(MODEL) is True
    assert _posts(server) == [("POST", "/v1/model/load", {"model_name": MODEL})]
    assert server.loaded == MODEL


def test_a_server_already_holding_the_model_is_warm_and_is_not_reloaded(tabby):
    server = tabby(loaded=MODEL)

    assert _engine(server).load(MODEL) is True
    assert _posts(server) == [], "a load on TabbyAPI unloads what is there first"


def test_a_server_holding_a_different_model_is_left_alone(tabby):
    server = tabby(loaded="something-the-person-loaded-by-hand")

    assert _engine(server).load(MODEL) is False
    assert _posts(server) == []
    assert server.loaded == "something-the-person-loaded-by-hand"


def test_a_server_without_the_route_is_not_made_to_generate(tabby):
    server = tabby(has_routes=False)

    assert _engine(server).load(MODEL) is False
    assert _posts(server) == []
    assert not any("chat" in path for _, path, _ in server.requests)


def test_a_load_the_server_refuses_is_reported_as_not_warm(tabby):
    server = tabby(load_status=401)

    assert _engine(server).load(MODEL) is False


def test_a_server_that_is_not_running_costs_nothing(tabby):
    server = tabby()
    engine = _engine(server)
    server.stop()

    assert engine.load(MODEL) is False


def test_a_busy_503_is_not_read_as_an_empty_card(tabby):
    """503 also means 'busy'. Only the sentence says nothing is loaded."""
    server = tabby(busy=True)

    assert _engine(server).load(MODEL) is False
    assert _posts(server) == []


def test_a_model_is_never_loaded_on_a_remote_host():
    engine = OpenAICompatibleEngine(base_url="https://api.example.com", api_key="k", default_model=MODEL)

    assert engine.load(MODEL) is False


def test_the_load_logic_names_no_model():
    """Build for the set of models: the route is asked, the name is not read."""
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(OpenAICompatibleEngine.load)))
    function = tree.body[0]
    function.body = function.body[1:]  # the docstring is prose, and may say what it likes
    code = ast.unparse(function).lower()
    assert "qwen" not in code and "gemma" not in code and "llama" not in code and "tabby" not in code


# ------------------------------------------------------- through the real stack


def test_the_dispatch_engine_reaches_the_load_route_for_a_model_on_another_server(tabby):
    """The guard the fakes above could not be: `LocalDispatchEngine.warm` builds
    the real `OpenAICompatibleEngine` for the endpoint and the request lands."""
    from runtimes.models.engines.local_dispatch_engine import LocalDispatchEngine

    server = tabby()

    class _Ollama:
        def warm(self, *a, **k):  # pragma: no cover - must not be reached
            raise AssertionError("a model on another server was warmed on Ollama")

    engine = LocalDispatchEngine(
        ollama=_Ollama(),
        resolve_endpoint=lambda mid: server.url if mid == f"lm_studio:{MODEL}" else None,
        wire_name=lambda mid: mid.split(":", 1)[-1],
    )

    assert engine.warm(f"lm_studio:{MODEL}") is True
    assert _posts(server) == [("POST", "/v1/model/load", {"model_name": MODEL})]


# ------------------------------------------- the server Zaram itself started


@pytest.mark.asyncio
async def test_a_server_zaram_started_is_warmed_once_it_answers(monkeypatch):
    """The boot preload runs before a server Zaram started has answered, so the
    chosen model was not in the catalogue and nothing was loaded. Coming up is
    the moment to try again -- and only when it did come up."""
    import asyncio

    import main
    from providers import model_servers

    warmed: list = []

    async def fake_warm():
        warmed.append(True)

    class _Runtime:
        class manager:
            @staticmethod
            def refresh():
                return None

    monkeypatch.setattr(main, "_warm_local_model", fake_warm)
    monkeypatch.setattr(model_servers, "SERVERS", {"tabbyapi": object()})
    monkeypatch.setattr(model_servers, "ensure_started", lambda server_id, **kw: {"state": "starting"})

    async def came_up(server_id, refresh, **kw):
        return True

    monkeypatch.setattr(model_servers, "refresh_when_up", came_up)
    main._bring_up_model_servers(_Runtime)
    await asyncio.gather(*list(main._model_server_tasks))
    assert warmed == [True]

    warmed.clear()

    async def never_came_up(server_id, refresh, **kw):
        return False

    monkeypatch.setattr(model_servers, "refresh_when_up", never_came_up)
    main._bring_up_model_servers(_Runtime)
    await asyncio.gather(*list(main._model_server_tasks))
    assert warmed == []
