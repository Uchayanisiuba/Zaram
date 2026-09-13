"""Claude, spoken to in its own wire format.

`providers/catalogue.py` has carried an entry for Anthropic since the
catalogue existed, greyed out with the honest note that Zaram *"uses a
different request format from the one Zaram speaks"*. This is the adapter
that note was waiting for. The Messages API is not chat-completions with
the names changed: the system prompt is a top-level field rather than a
message, images and tool calls are typed content blocks rather than
`image_url` parts and `tool_calls` deltas, and the stream is a sequence of
named events — `content_block_start`, `content_block_delta`,
`content_block_stop` — rather than one `choices[0].delta` per frame. A
shim over the OpenAI engine would have to lie about all four, so this is a
second engine rather than a flag on the first.

**Raw HTTP through the gate, not the SDK — and that is a rule, not a
shortcut.** Rule 3 says every byte that leaves is logged, and
`tests/test_egress_chokepoint.py` enforces it by refusing any shipped
module that opens its own connection. An SDK is a module that opens its own
connection. So this engine builds the exact body, hands it to
`EgressGate.stream_lines` — which is what logs it, what shows it in a
confirmation, and what refuses it on a host with no policy — and parses
what comes back. The same shape as `OpenAICompatibleEngine`, whose docstring
carries the reasoning about building the body once and asking the gate
exactly once; both hold here unchanged.

What is deliberately not sent: a `thinking` block. Current Claude models
reason adaptively when the parameter is omitted, and the one that does not
(Haiku 4.5) rejects the adaptive form — so omitting it is the one request
every current model accepts. The cost is that the reasoning panel stays
empty on this path; the reply is unaffected. Recorded rather than hidden.
"""

from __future__ import annotations

import json
import logging
import urllib.error
from collections.abc import Iterator
from typing import Any, Dict, Optional

from core.egress import DataClass, EgressDenied, get_gate
from core.reasoning import CLOSE_TAG, OPEN_TAG
from core.tool_loop import marker_for_native_call

from .base_engine import ERROR_PREFIX, LLMEngine
from .openai_compatible_engine import _data_uri

logger = logging.getLogger(__name__)

__all__ = ["AnthropicEngine", "ANTHROPIC_VERSION", "DEFAULT_BASE_URL", "to_anthropic_tools"]

DEFAULT_BASE_URL = "https://api.anthropic.com"
#: The API version header every request carries. Pinned, because the wire
#: shape parsed below is the one this date names.
ANTHROPIC_VERSION = "2023-06-01"
#: Required by the Messages API on every request. Streaming, so a large value
#: costs nothing until the model uses it; sized so a long answer is not cut
#: mid-sentence and a runaway one still ends.
MAX_TOKENS = 16000


def to_anthropic_tools(tools: list[dict] | None) -> list[dict[str, Any]]:
    """OpenAI's ``tools`` array — what `native_tool_specs` emits — as Anthropic
    tool definitions. Same schema underneath: ``parameters`` *is* JSON Schema
    and travels as ``input_schema``. A tool with no name is left out rather
    than sent nameless, which the API would refuse for the whole request."""
    out: list[dict[str, Any]] = []
    for tool in tools or []:
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict) or not function.get("name"):
            continue
        out.append({
            "name": str(function["name"]),
            "description": str(function.get("description") or ""),
            "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


def _image_block(image: str) -> dict[str, Any]:
    """One attached image as a typed content block.

    `_data_uri` is reused for the one thing it knows — reading the format off
    the picture's own signature, and refusing when it cannot — and the URI it
    returns is split back into the pieces this API wants. Refusing is the
    point, as it is there: an image Zaram cannot name is one it does not send.
    """
    uri = _data_uri(image)
    header, _, data = uri.partition(",")
    media_type = header[len("data:"):].split(";", 1)[0]
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


class AnthropicEngine(LLMEngine):
    """Streams from ``/v1/messages`` on api.anthropic.com, or a host the user names."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "",
        default_model: str = "",
        timeout: float = 120.0,
        gate: Any = None,
        source: str = "cloud.anthropic",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.default_model = default_model
        self._timeout = timeout
        self._gate = gate
        self._source = source

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/v1/messages"

    # -- the request ---------------------------------------------------------- #

    def _body(
        self,
        prompt: str,
        system_prompt: str,
        model: str | None,
        images: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> Dict[str, Any]:
        """The exact object that will be sent, built once for the gate and the
        wire. The system prompt — and so every recalled fact — is a top-level
        field here, which is the difference that made this engine necessary
        and is also what the confirmation dialog shows verbatim."""
        attached = [image for image in (images or []) if image and image.strip()]
        if attached:
            content: list[dict[str, Any]] = [_image_block(image) for image in attached]
            content.append({"type": "text", "text": prompt})
            user: dict[str, Any] = {"role": "user", "content": content}
        else:
            user = {"role": "user", "content": prompt}

        body: Dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": MAX_TOKENS,
            "stream": True,
            "messages": [user],
        }
        if system_prompt:
            body["system"] = system_prompt
        converted = to_anthropic_tools(tools)
        if converted:
            body["tools"] = converted
        return body

    @staticmethod
    def _body_carries_images(body: Dict[str, Any]) -> bool:
        for message in body.get("messages") or []:
            content = message.get("content")
            if isinstance(content, list) and any(
                isinstance(part, dict) and part.get("type") == "image" for part in content
            ):
                return True
        return False

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> Iterator[str]:
        """Stream plain text tokens, per `LLMEngine`. Build, then the gate, once."""
        try:
            body = self._body(prompt, system_prompt, model, images, tools)
        except ValueError as unreadable:
            logger.info("refusing to send an unidentifiable image: %s", unreadable)
            yield ERROR_PREFIX + str(unreadable)
            return
        payload = json.dumps(body)

        gate = self._gate if self._gate is not None else get_gate()
        try:
            lines = gate.stream_lines(
                self.endpoint,
                method="POST",
                body=payload,
                # Sent, never logged — the log is append-only and a key written
                # into it is one the user can never rotate away from.
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
                source=self._source,
                data_class=(
                    DataClass.IMAGE if self._body_carries_images(body) else DataClass.PROMPT
                ),
            )
            yield from self._tokens(lines)
        except EgressDenied as denied:
            logger.info("cloud generation refused: %s", denied)
            yield ERROR_PREFIX + str(denied)
        except urllib.error.HTTPError as http_error:
            yield ERROR_PREFIX + self._explain(http_error)
        except Exception as exc:  # noqa: BLE001 - reported in-band, per the engine contract
            logger.warning("cloud request failed: %s: %s", type(exc).__name__, exc)
            yield ERROR_PREFIX + f"Could not reach {self.base_url}: {exc}"

    # -- the response --------------------------------------------------------- #

    @staticmethod
    def _tokens(lines: Any) -> Iterator[str]:
        """Parse the Messages API's SSE into the engine's plain-text contract.

        Only ``data:`` lines carry anything; the event name is repeated inside
        the JSON as ``type``, so the ``event:`` lines are not needed. Three
        block kinds matter. *Text* is yielded as it arrives. *Thinking* is
        wrapped in the same ``<think>`` tags the OpenAI engine emits, so
        `core.reasoning.ReasoningSplitter` and everything behind it — the
        panel, the transcript, the rule that thinking is never spoken — work
        unchanged; the opening tag is held until the first non-empty delta,
        because by default the API streams thinking blocks with empty text and
        an empty pair of tags would read as a reply that was all thinking.
        *Tool use* arrives as a name in ``content_block_start`` and its
        arguments in ``input_json_delta`` pieces, assembled per block index
        and emitted once, as the marker the loop already reads.
        """
        tool_blocks: dict[int, dict[str, str]] = {}
        thinking_open: set[int] = set()
        for raw in lines:
            if not raw:
                continue
            line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[len("data:"):].strip())
            except ValueError:
                continue
            kind = event.get("type")
            index = event.get("index")

            if kind == "content_block_start":
                block = event.get("content_block") or {}
                if block.get("type") == "tool_use" and isinstance(index, int):
                    tool_blocks[index] = {"name": str(block.get("name") or ""), "json": ""}
            elif kind == "content_block_delta":
                delta = event.get("delta") or {}
                delta_type = delta.get("type")
                if delta_type == "text_delta":
                    text = delta.get("text")
                    if text:
                        yield str(text)
                elif delta_type == "thinking_delta":
                    thought = delta.get("thinking")
                    if thought and isinstance(index, int):
                        if index not in thinking_open:
                            thinking_open.add(index)
                            yield OPEN_TAG
                        yield str(thought)
                elif delta_type == "input_json_delta" and isinstance(index, int):
                    slot = tool_blocks.get(index)
                    if slot is not None:
                        slot["json"] += str(delta.get("partial_json") or "")
            elif kind == "content_block_stop" and isinstance(index, int):
                if index in thinking_open:
                    thinking_open.discard(index)
                    yield CLOSE_TAG
                slot = tool_blocks.pop(index, None)
                if slot is not None:
                    marker = marker_for_native_call(slot["name"], slot["json"] or "{}")
                    if marker:
                        yield marker
            elif kind == "error":
                error = event.get("error") or {}
                yield ERROR_PREFIX + str(error.get("message") or "the provider reported an error")
                return
        # A stream that ended mid-block: close what was opened rather than
        # leave a tag dangling, and emit a call whose arguments had finished.
        for index in sorted(thinking_open):
            yield CLOSE_TAG
        for index in sorted(tool_blocks):
            slot = tool_blocks[index]
            marker = marker_for_native_call(slot["name"], slot["json"] or "{}")
            if marker:
                yield marker

    @staticmethod
    def _explain(error: Any) -> str:
        """An HTTP failure as a sentence the person can act on."""
        status = getattr(error, "code", 0)
        detail = ""
        try:
            body = error.read().decode("utf-8", "replace")
            parsed = json.loads(body)
            detail = (parsed.get("error") or {}).get("message") or body[:200]
        except Exception:  # noqa: BLE001
            detail = ""
        if status == 401:
            return f"That API key was rejected. {detail}".strip()
        if status == 402:
            return f"That account has no credit left. {detail}".strip()
        if status == 429:
            return f"Rate limited by the provider. {detail}".strip()
        return f"The provider returned {status}. {detail}".strip()
