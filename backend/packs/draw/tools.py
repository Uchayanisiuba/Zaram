"""`draw_image`: a picture as a **step**, not as a whole request.

Zaram could already draw. What it could not do was draw *inside a task*.
Generation was reached only by `IntentPlanner` spotting "draw me a picture" and
routing the entire request to an image-capable model — one request, one intent
— so *"write the proposal and put a cover image on it"* had to be two
conversations, and the model could never decide for itself that a step wanted a
picture. Built 15 September 2026 to close that, on the same day the plan card
learned to let a run finish.

**It is the same runtime underneath.** Nothing about routing, consent, the
provider choice or the egress log is re-implemented here: this is a tool
descriptor and a call into `ImagesRuntime`, which already owns the modality
gate, the card check, the refusal with its remedy, and `ArtifactService` — so a
picture drawn from a task lands in the one output directory with the one
record and the one download route, exactly like a picture somebody asked for
directly. A second path to the same capability would be a second
no-overwrite guarantee nobody had proved.

**Generative tier, so it needs no undo, sandbox or confirmation.** It creates a
new artifact and changes nothing that exists; `ArtifactStore` has no capability
to delete or overwrite, and a name collision increments. That is why this tool
is granted rather than gated — see `granted_tools` — and it is the same
reasoning that lets the documents runtime ship in v1.

**The refusal matters more here than the drawing.** Most machines cannot draw:
there is no local image model, and a cloud provider that can is the usual
answer. When that is the state, the tool says so *with the remedy*, and the
model is told plainly not to describe a picture it did not make. A text model
answering "here is your cover image" in prose is rule 9's failure in a new
medium, and it is the one thing this tool must never invite.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

logger = logging.getLogger(__name__)

__all__ = ["DrawTools", "DRAW_IMAGE", "SERVER_ID"]

SERVER_ID = "draw"
DRAW_IMAGE = "draw_image"

#: Both bounded well inside what every provider accepts. A model that asks for
#: something silly gets the nearest sane size rather than an error, because a
#: refusal over a width is a step lost for nothing.
_MIN_SIDE = 256
_MAX_SIDE = 1536
_DEFAULT_SIDE = 1024


def _side(value: Any, fallback: int = _DEFAULT_SIDE) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(_MIN_SIDE, min(_MAX_SIDE, n))


class DrawTools:
    """Zaram's built-in drawing server: one tool, `draw_image`."""

    def __init__(self, run: Callable[[str, Dict[str, Any]], Dict[str, Any]]) -> None:
        # The synchronous bridge into `ImagesRuntime.execute`, supplied at
        # registration. Injected rather than imported so this module holds no
        # opinion about how the runtime is reached, and so a test can exercise
        # the tool's own rules — the refusal wording, the bounds, the shape of
        # what comes back — without a provider or a card.
        self._run = run

    # -- the built-in server surface ------------------------------------------ #

    def connect(self) -> None:
        """Nothing to start. Present because the runtime calls it."""

    def close(self) -> None:
        """Nothing to stop."""

    def granted_tools(self) -> set:
        """Always offered.

        Generative tier: it writes a new file and can destroy nothing, so there
        is nothing for a confirmation to protect. The consent that *does* apply
        is about the destination — an image is its own data class and a
        provider must have been permitted for it — and that gate lives in the
        runtime and the egress gate, where it governs a picture asked for
        directly in exactly the same way.
        """
        return {DRAW_IMAGE}

    def list_tools(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=SERVER_ID,
                name=DRAW_IMAGE,
                description=(
                    "Draw a picture from a description, and save it. Use it when a step of "
                    "the work needs an image made — a cover, a diagram's illustration, a "
                    "mock-up, a logo — rather than when the person is asking about a "
                    "picture they already have. Returns the saved file's name. "
                    "If it answers that drawing is unavailable, say so plainly and carry "
                    "on without the picture: never describe an image as though it was made."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "What the picture should be of. Describe the subject, style and mood.",
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "What to keep out of it, if anything.",
                        },
                        "width": {"type": "integer", "description": "Pixels across. 1024 by default."},
                        "height": {"type": "integer", "description": "Pixels down. 1024 by default."},
                    },
                    "required": ["prompt"],
                },
            )
        ]

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        if name != DRAW_IMAGE:
            return {"error": f"the drawing server has no tool called {name!r}"}
        return self.draw(
            str(arguments.get("prompt") or ""),
            negative_prompt=str(arguments.get("negative_prompt") or ""),
            width=arguments.get("width"),
            height=arguments.get("height"),
        )

    # -- the tool ------------------------------------------------------------- #

    def draw(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        width: Any = None,
        height: Any = None,
    ) -> Dict[str, Any]:
        if not prompt.strip():
            return {"error": "there was nothing to draw — say what the picture should be of"}

        result = self._run(
            "image.generate",
            {
                "prompt": prompt.strip(),
                "negative_prompt": negative_prompt.strip(),
                "width": _side(width),
                "height": _side(height),
                "count": 1,
            },
        )

        if not isinstance(result, dict) or not result.get("success"):
            reason = ""
            if isinstance(result, dict):
                reason = str(result.get("error") or "")
                remedy = str(result.get("remedy") or "")
                if remedy:
                    reason = f"{reason} {remedy}".strip()
            # Returned as an `error`, which is the loop's ordinary "that did
            # not work" and is handed back to the model to account for. The
            # instruction is in the wording rather than in a flag: the one
            # failure that matters is a model that narrates a picture nobody
            # drew.
            return {
                "error": (
                    f"{reason or 'drawing is not available on this machine'} "
                    "— carry on without the picture and say it could not be made."
                )
            }

        card = result.get("artifact") or {}
        name = str(card.get("name") or card.get("filename") or "")
        logger.info("draw_image saved %s", name or "an image")
        return {
            # What the model needs and nothing more: a file exists and this is
            # what it is called. The picture itself reaches the person through
            # the card the runtime already emits, not through the transcript.
            "saved": name,
            "prompt": prompt.strip(),
        }
