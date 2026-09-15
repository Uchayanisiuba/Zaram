"""`draw_image` — a picture made *during* a task, and what it says when it cannot.

Before 15 September 2026 image generation was reachable only as an intent: the
planner matched "draw me a picture" and routed the whole request. One request,
one picture, nothing else — so a model could not decide that a step of its own
plan wanted an image, and *"write the proposal and put a cover on it"* was two
conversations.

The failure these tests exist for is the second one, not the first. Most
machines cannot draw, and a text model told only "that failed" will write
*"here is your cover image"* in prose — rule 9's failure in a new medium, and
worse than a refusal because it leaves the building inside a document. So the
unavailable answer has to carry the reason, the remedy, and the instruction.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from packs.draw import DRAW_IMAGE, SERVER_ID, DrawTools


class _Runtime:
    """Stands in for `ImagesRuntime`. Records what it was asked for."""

    def __init__(self, reply: Dict[str, Any]) -> None:
        self.reply = reply
        self.calls: list[tuple[str, Dict[str, Any]]] = []

    def __call__(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((capability, payload))
        return self.reply


DREW = {
    "success": True,
    "artifact": {"name": "a-blue-dog.png"},
    "artifacts": [{"name": "a-blue-dog.png"}],
}
CANNOT = {
    "success": False,
    "unavailable": True,
    "error": "No model on this machine can draw.",
    "remedy": "Add a cloud key for a provider that can.",
}


def _tools(reply: Dict[str, Any]) -> tuple[DrawTools, _Runtime]:
    runtime = _Runtime(reply)
    return DrawTools(runtime), runtime


def test_the_tool_is_offered_to_the_model_and_needs_no_confirmation() -> None:
    tools, _ = _tools(DREW)
    described = tools.list_tools()
    assert [t.name for t in described] == [DRAW_IMAGE]
    assert described[0].server_id == SERVER_ID
    # Generative tier: it writes a new file and can destroy nothing, so there
    # is nothing a confirmation would protect.
    assert tools.granted_tools() == {DRAW_IMAGE}


def test_a_drawing_goes_to_the_one_runtime_that_already_draws() -> None:
    tools, runtime = _tools(DREW)

    out = tools.call_tool(DRAW_IMAGE, {"prompt": "a blue dog, oil on canvas"})

    assert out == {"saved": "a-blue-dog.png", "prompt": "a blue dog, oil on canvas"}
    capability, payload = runtime.calls[0]
    # Not a second implementation: the same capability a directly-requested
    # picture uses, so the modality gate, the card check and the artifact
    # store are the ones already proven.
    assert capability == "image.generate"
    assert payload["prompt"] == "a blue dog, oil on canvas"


def test_a_machine_that_cannot_draw_says_so_with_the_remedy_and_the_instruction() -> None:
    """The one that matters. A model told only "failed" writes the picture in
    prose; this answer has to leave it nowhere to do that."""
    tools, _ = _tools(CANNOT)

    out = tools.call_tool(DRAW_IMAGE, {"prompt": "a cover image"})

    assert "saved" not in out
    message = out["error"]
    assert "No model on this machine can draw." in message
    assert "Add a cloud key" in message, "the remedy must travel with the refusal"
    assert "could not be made" in message, "the model must be told to admit it"


def test_an_empty_prompt_never_reaches_a_provider() -> None:
    tools, runtime = _tools(DREW)
    out = tools.draw("   ")
    assert "error" in out
    assert runtime.calls == [], "nothing should have been asked of the provider"


@pytest.mark.parametrize(
    ("asked", "expected"),
    [(None, 1024), (64, 256), (99999, 1536), ("768", 768), ("wide", 1024)],
)
def test_a_silly_size_is_brought_into_range_rather_than_refused(asked, expected) -> None:
    """A step lost over a width is a step lost for nothing."""
    tools, runtime = _tools(DREW)
    tools.draw("a cover", width=asked)
    assert runtime.calls[0][1]["width"] == expected


def test_an_unknown_tool_on_this_server_is_refused_by_name() -> None:
    tools, runtime = _tools(DREW)
    out = tools.call_tool("delete_image", {})
    assert "error" in out and "delete_image" in out["error"]
    assert runtime.calls == []
