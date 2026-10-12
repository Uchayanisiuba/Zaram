"""A picture a tool returns is kept and shown, never pasted into the prompt as text.

10 October 2026, found by asking the resident model to "open google.com in your
browser" with computer use on. It launched the page, listed the windows, read one with
`get_window_state` -- and the run died: *"prompt length 1690633 exceeds the available
context size of 65536 tokens"*. Measured against the real driver, that tool returns
the window's text tree (about 4.7 KB) and a **2.2 MB base64 PNG**; Zaram wrote the
whole result into the prompt as text, where a picture is only noise.

The first fix dropped the picture, and the maintainer rejected it the same day: *"Don't
block images."* So the picture is saved, shown on the step card, and handed to a model
that can see through the channel an attached photo uses. A model that cannot see is
told a picture came back and works from the text.

The same run found the second half: `list_apps` said what was running in 554
characters and repeated it, with every installed app, in 98 KB of `structuredContent`.
A model is sent what the server wrote for a reader.
"""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from core.tool_loop import ToolCall, ToolTurn, bounded, render_result
from runtimes.mcp.client import ToolDescriptor
from runtimes.mcp.config import ServerConfig, ServerStore
from runtimes.mcp.policy import WriteMode
from runtimes.mcp import runtime as runtime_module
from runtimes.mcp.runtime import CALL, PICTURES_KEPT, McpRuntime, keep_media

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1_500_000  # the size the real driver sent, near enough
PICTURE = base64.b64encode(PNG).decode("ascii")


class _Driver:
    def list_tools(self):
        return [ToolDescriptor(server_id="cua-driver", name="get_window_state", description="read a window")]

    def call_tool(self, name, arguments):
        return {
            "content": [
                {"type": "text", "text": "window_id=1 pid=2 elements=47\n\n- Window \"Google\""},
                {"type": "image", "data": PICTURE, "mimeType": "image/png"},
            ],
            "structuredContent": {"tree_markdown": "- Window \"Google\"", "screenshot_width": 1920},
        }

    def close(self):
        pass


@pytest.fixture
def pictures(tmp_path, monkeypatch):
    folder = tmp_path / "pictures"
    monkeypatch.setattr(runtime_module, "pictures_dir", lambda: folder)
    return folder


@pytest.fixture
def runtime(tmp_path, pictures):
    store = ServerStore(tmp_path / "servers.json")
    store.save({"cua-driver": ServerConfig(server_id="cua-driver", command=["cua-driver", "mcp"], writes=WriteMode.HOST_UNDO)})
    rt = McpRuntime(store=store)
    rt._connections["cua-driver"] = _Driver()
    return rt


def _read_window(runtime):
    return asyncio.run(runtime.execute(CALL, {"server": "cua-driver", "tool": "get_window_state", "arguments": {}}))


def test_the_picture_is_kept_byte_for_byte_and_named_in_the_result(runtime, pictures):
    out = _read_window(runtime)
    assert out["success"] is True
    assert len(out["images"]) == 1
    kept = out["images"][0]
    assert open(kept, "rb").read() == PNG
    assert kept.startswith(str(pictures))
    note = out["result"]["content"][1]
    assert note["type"] == "text" and "a picture came back" in note["text"]


def test_the_prompt_carries_the_text_and_not_the_picture(runtime):
    out = _read_window(runtime)
    prompt_text = render_result(out["result"])
    assert PICTURE[:200] not in prompt_text
    assert "Window \"Google\"" in prompt_text
    assert len(prompt_text) < 1_000, len(prompt_text)


def test_the_text_a_server_wrote_is_sent_instead_of_its_structure():
    """`list_apps`: 554 characters of text, 98 KB of the same as data."""
    result = {
        "content": [{"type": "text", "text": "Found 259 app(s): 17 running.\n- Google Chrome (pid 1)"}],
        "structuredContent": {"apps": [{"name": f"app {i}", "running": False} for i in range(242)]},
    }
    rendered = render_result(result)
    assert rendered == "Found 259 app(s): 17 running.\n- Google Chrome (pid 1)"


def test_structure_is_still_sent_when_there_is_no_text():
    result = {"content": [], "structuredContent": {"apps": ["only here"]}}
    assert "only here" in render_result(result)


def test_an_error_result_says_it_was_one():
    rendered = render_result({"content": [{"type": "text", "text": "no such window"}], "isError": True})
    assert rendered.startswith("[the tool reported an error]")


def test_a_result_too_large_for_the_window_is_cut_and_says_so():
    huge = {"content": [{"type": "text", "text": "x" * 200_000}]}
    cut = bounded(huge, 1_000)
    assert isinstance(cut, str) and len(cut) < 5_000
    assert "were cut to fit" in cut
    small = {"content": [{"type": "text", "text": "fine"}]}
    assert bounded(small, 1_000) is small


def test_only_a_short_window_of_pictures_is_kept(pictures):
    for _ in range(PICTURES_KEPT + 5):
        keep_media({"type": "image", "data": base64.b64encode(b"\x89PNG tiny").decode(), "mimeType": "image/png"})
    assert len(list(pictures.iterdir())) == PICTURES_KEPT


def test_a_payload_that_is_not_a_picture_is_described_and_not_written(pictures):
    out, saved = keep_media({"content": [{"type": "image", "data": "AAAA", "mimeType": "application/x-msdownload"}]})
    assert saved == [] and not pictures.exists()
    assert "was not kept" in out["content"][0]["text"]
    audio, saved = keep_media({"type": "audio", "data": "A" * 2048, "mimeType": "audio/wav"})
    assert saved == [] and audio["type"] == "text"


def test_ordinary_data_is_not_mistaken_for_media(pictures):
    ordinary = {"type": "text", "text": "x", "data": ["not", "a", "payload"], "items": [{"type": "image", "name": "no data"}]}
    assert keep_media(ordinary) == (ordinary, [])


def test_the_servers_own_object_is_not_edited(pictures):
    original = {"content": [{"type": "image", "data": base64.b64encode(b"png").decode(), "mimeType": "image/png"}]}
    keep_media(original)
    assert original["content"][0]["type"] == "image"


# ---------------------------------------------------------------- who is shown it


def _engine_with(model_sees: bool):
    from core.execution_engine import ExecutionEngine

    engine = ExecutionEngine.__new__(ExecutionEngine)
    info = SimpleNamespace(display_name="m", supports_vision=model_sees)
    engine._provider_manager = SimpleNamespace(catalog=SimpleNamespace(all=lambda: [info]))
    engine._effective_model = lambda model: model
    return engine


def test_a_model_that_can_see_is_shown_the_newest_picture(tmp_path):
    older, newer = tmp_path / "a.png", tmp_path / "b.png"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    turns = [
        ToolTurn(call=ToolCall("cua-driver", "get_window_state", {}), result="", images=(str(older),)),
        ToolTurn(call=ToolCall("cua-driver", "list_windows", {}), result=""),
        ToolTurn(call=ToolCall("cua-driver", "get_window_state", {}), result="", images=(str(newer),)),
    ]
    sight = _engine_with(True)._sight(turns, "m")
    assert sight == {"images": [base64.b64encode(b"new").decode("ascii")]}


def test_a_model_that_cannot_see_is_not_sent_a_picture(tmp_path):
    shot = tmp_path / "a.png"
    shot.write_bytes(b"png")
    turns = [ToolTurn(call=ToolCall("cua-driver", "get_window_state", {}), result="", images=(str(shot),))]
    assert _engine_with(False)._sight(turns, "m") == {}
    # A model the catalogue does not know is treated as unable to see.
    assert _engine_with(True)._sight(turns, "unknown") == {}


def test_the_picture_is_served_by_name_only(tmp_path, pictures):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from runtimes.mcp import api

    pictures.mkdir()
    (pictures / "shot.png").write_bytes(PNG[:100])
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    ok = client.get("/tools/pictures/shot.png")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png" and ok.content == PNG[:100]
    assert client.get("/tools/pictures/..%2Fservers.json").status_code == 404
    assert client.get("/tools/pictures/shot.exe").status_code == 404
    assert client.get("/tools/pictures/missing.png").status_code == 404
