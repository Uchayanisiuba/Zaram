"""Ask the running app one question the way a person would — in process.

A trigger's run **is `POST /chat`**, so it gets recall, the planner, the
tools, the gate, the egress log and a transcript exactly as a typed question
does, and nothing becomes a second engine (`core/triggers.py`). The request
is dispatched through `httpx.ASGITransport`, which calls this process's own
ASGI app directly: **no socket is opened, nothing is bound and nothing can
leave the machine by this path.** The `base_url` is a loopback address only
so the `Host` header guard sees the name it expects.

Its own module because `tests/test_egress_chokepoint.py` scans every product
file for a client that opens its own connection, and `httpx.AsyncClient(`
is one of the shapes it looks for. Exempting `main.py` would exempt every
future call in six thousand lines; exempting a module whose whole text is
this one function is a fact the test can keep checking.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Sequence, Tuple


async def ask_in_process(
    app: Any,
    *,
    question: str,
    session_id: str,
    project_id: str,
    secret: str,
    outcome_of: Callable[[Sequence[dict]], Tuple[str, str]],
) -> Tuple[str, str, str]:
    """``(outcome, conversation_id, note)`` for one unattended question.

    The session id is minted by the caller and nothing ever grants to it,
    which is what "never self-approves" means in code: `_approved`,
    `_uninterrupted` and the conversation rung are all keyed on a session a
    person is in.
    """
    import httpx

    events: list[dict] = []
    conversation_id = ""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8420") as client:
        async with client.stream(
            "POST",
            "/chat",
            json={"text": question, "session_id": session_id, "project_id": project_id},
            headers={"X-Zaram-Auth": secret, "Host": "127.0.0.1:8420"},
            timeout=None,
        ) as response:
            if response.status_code != 200:
                return "failed", "", f"the chat route answered {response.status_code}"
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(event)
                if event.get("type") == "conversation":
                    data = event.get("data", {})
                    conversation_id = str(data.get("id") or data.get("conversation_id") or "")
    outcome, note = outcome_of(events)
    return outcome, conversation_id, note
