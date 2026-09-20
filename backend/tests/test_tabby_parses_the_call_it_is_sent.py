"""TabbyAPI returns a tool call as a *call*, not as text — measured, `-m measure`.

Found 20 September 2026, by the tool-calling issue on the server's own
tracker (theroyallab/tabbyAPI #479) and then measured here. With no
`tool_format` in Tabby's config, a call the 27B makes comes back with
`finish_reason: stop`, `tool_calls: null`, and the call itself as
`<tool_call><function=get_weather>...` text in `content` — and the thinking
unsplit in front of it. Nothing on either side warns.

Two keys fixed it, and the second is the one that was missed: `tool_format:
qwen3_5` under `model:`, **and both `tool_format` and `reasoning` named in
`use_as_default`**, because with `inline_model_loading` an API-driven load
honours only the keys in that list. `reasoning: true` had been silently
ignored on every real load the same way; Zaram's engine covered for it with
`starts_in_reasoning`, which is why nobody noticed.

Before: 61.7 s (with the load), `stop`, null. After: 3.4 s, `tool_calls`,
`get_weather({"city": "Lagos"})`, thinking in `reasoning`, content empty.

This pins the *server* half. `test_native_tool_calls_reach_the_loop.py` pins
what the engine does with a parsed call; the two together are the claim that
a native call on the maintainer's own server reaches the loop as one.

Runs only with ``-m measure``: it loads a 27B on the card.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.measure

TABBY = "http://127.0.0.1:1234/v1"

_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}


def _served_model() -> str:
    try:
        with urllib.request.urlopen(f"{TABBY}/models", timeout=3) as r:
            listed = json.load(r).get("data") or []
    except (urllib.error.URLError, OSError, ValueError) as exc:
        pytest.skip(f"TabbyAPI is not answering on 1234: {exc}")
    if not listed:
        pytest.skip("TabbyAPI lists no models")
    return str(listed[0]["id"])


def test_a_tool_call_arrives_as_a_call_with_its_thinking_apart():
    body = {
        "model": _served_model(),
        "messages": [
            {"role": "user", "content": "What is the weather in Lagos right now? Use the tool."}
        ],
        "tools": [_TOOL],
        "stream": False,
        "max_tokens": 400,
    }
    req = urllib.request.Request(
        f"{TABBY}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        reply = json.load(r)

    choice = reply["choices"][0]
    message = choice["message"]

    # The call is a call. `stop` with the call in `content` is the
    # misconfiguration, and it is what an unset `tool_format` produces.
    assert choice["finish_reason"] == "tool_calls", (
        f"finish_reason={choice['finish_reason']!r}; content={message.get('content')!r} — "
        "is `tool_format` set, and named in `use_as_default`?"
    )
    calls = message.get("tool_calls") or []
    assert calls, "tool_calls is empty"
    assert calls[0]["function"]["name"] == "get_weather"
    assert json.loads(calls[0]["function"]["arguments"])["city"].lower() == "lagos"

    # The thinking is apart from the answer, not in front of it. `reasoning`
    # is applied on the same inline load as `tool_format`; if one is honoured
    # the other is, and this is the cheaper thing to assert.
    assert "<tool_call>" not in (message.get("content") or "")
    assert "</think>" not in (message.get("content") or "")
