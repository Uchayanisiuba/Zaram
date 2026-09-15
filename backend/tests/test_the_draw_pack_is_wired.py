"""`draw_image` exists in the running product, not only in its own test.

`test_a_picture_can_be_a_step.py` builds `DrawTools` by hand and proves its
rules. That is necessary and it is not sufficient — the same was true of the
MCP runtime for a fortnight while nothing could name `mcp.call`, of the library
tools that shipped measured and unregistered, and of fifteen other subsystems
here. `CLAUDE.md`: *assume unreachable until the caller is seen.*

So this asserts the link that turns a module into a feature: the bootstrapper
registers it, against the real boot path. Delete the registration line and this
fails while every other draw test still passes.
"""

from __future__ import annotations

import pytest

from packs.draw import DRAW_IMAGE, SERVER_ID


@pytest.mark.asyncio
async def test_the_bootstrapper_offers_the_drawing_tool_to_the_model() -> None:
    from core.bootstrapper import KernelBootstrapper

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        listed = await kernel.mcp_runtime.execute("mcp.list_tools", {"query": "draw a picture"})

        assert listed["success"] is True
        offered = {tool["name"] for tool in listed["tools"] if tool["server"] == SERVER_ID}
        assert DRAW_IMAGE in offered, (
            "the model is never handed a drawing verb, so a picture can only ever "
            "be a whole request again"
        )
    finally:
        await kernel.shutdown()


@pytest.mark.asyncio
async def test_it_is_offered_on_a_machine_that_cannot_draw_too() -> None:
    """Registered whether or not anything can draw, deliberately.

    Withholding the tool on a machine with no image provider would leave the
    model with no way to find out — and a model that cannot ask writes the
    picture in prose instead. The refusal *is* the feature there: it carries
    the reason, the remedy, and the instruction to admit the picture was not
    made. The runtime's own availability check is what decides, and it is the
    same one a directly-requested picture meets.
    """
    from core.bootstrapper import KernelBootstrapper

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        health = await kernel.images_runtime.health_check()
        listed = await kernel.mcp_runtime.execute("mcp.list_tools", {"query": "draw a picture"})
        offered = {tool["name"] for tool in listed["tools"] if tool["server"] == SERVER_ID}

        # True on this machine or not, the tool is there either way; what
        # changes is what it answers.
        assert DRAW_IMAGE in offered
        assert "can_draw" in health, "the runtime must say whether it can, rather than implying it"
    finally:
        await kernel.shutdown()
