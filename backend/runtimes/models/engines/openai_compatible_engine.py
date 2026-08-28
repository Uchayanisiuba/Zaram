# backend/runtimes/models/engines/openai_compatible_engine.py
"""Generation against any OpenAI-compatible endpoint — the cloud half of v1.

Zaram stays local-first. This exists because local-first is not local-only, and
the constraint is not capability but **who can run it**: a freelancer on a
laptop with no discrete GPU cannot serve a chat model at all, and `CLAUDE.md`
says plainly that the target user is not technical. An alpha recruited only
from people who can install Ollama and spare 8 GB of VRAM measures a different
market than the one the product is aimed at.

Rule 1 is not bent to do it. **Zaram never buys inference**: the user brings a
key, the key is theirs, and no key means no engine rather than a quiet fallback
to something we pay for.

Why one HTTP shape instead of a routing library
-----------------------------------------------
`CLAUDE.md`'s dependency table names LiteLLM for provider routing. This does
not use it, and the reason is the same one that makes packaging the stated
blocker: `/v1/chat/completions` is *already* the lingua franca. OpenAI,
OpenRouter, Groq, Together, DeepSeek, Mistral, Fireworks, vLLM, llama.cpp and
LM Studio all speak it, and OpenRouter fronts Anthropic and Gemini for the two
that do not. So the whole cloud surface is one POST and an SSE parser — no new
dependency at all — against a library that would add a substantial tree to the
installer that packaging worked to cut by 81%.

There is a second reason, and it turned out to be the stronger one. A routing
library brings its own HTTP client, and `test_egress_chokepoint.py` forbids any
shipped module from opening its own outbound connection. LiteLLM would have to
be exempted from the one scan that makes rule 3 enforceable rather than
aspirational — which is a high price for code that assembles a JSON body.

This is a deviation from a recorded decision, so it is recorded here rather
than made quietly, and it is **cheap to reverse**: this class satisfies
`LLMEngine` and nothing above it knows what is inside. Swapping in LiteLLM
later is the same move the TTS interface exists to allow. If a provider appears
that is worth supporting and does not speak this dialect, that is the evidence
to revisit it — not tidiness.

The part that actually matters: this is egress
-----------------------------------------------
`OllamaEngine` talks to loopback, so `system_prompt` has never left the
machine. **This engine changes that, and `system_prompt` is where recalled
facts live.** Every cloud generation therefore carries Spine content off-device
by design — `CLAUDE.md` intends exactly that, "carries project context into the
cloud request", and immediately follows it with "showing the user exactly what
leaves before it does".

So nothing here opens a socket at all. **This module has no HTTP client**: the
body is built, handed to :class:`EgressGate` in full, and the gate carries the
bytes. The gate consults per-host policy (rule 5, default deny), asks the user
when the policy says ask (M10), and writes the literal outbound text to the
append-only log *before* the request (rule 3).

The first draft did own a client — `check` the verdict, then `requests.post` —
which is a sanctioned pattern for async call sites and was still wrong here.
`test_egress_chokepoint.py` caught it on the first run, correctly: it scans
source rather than behaviour, so it fails on the commit that introduces a
bypass instead of in production when the path is first taken. The remedy it
insists on is the right one — `EgressGate.stream_lines` exists because this was
the first outbound call that had to be consumed as it arrived, and the gate was
missing that shape rather than the engine needing an exemption.

**With no confirmation handler installed, the gate refuses.** That is the
designed resting state, not an oversight: until M10's dialog exists, cloud
generation is reachable, tested, and declines to send. Rule 5 with the safety
removed would be the alternative.

The API key is deliberately not in the logged body
--------------------------------------------------
It travels in the `Authorization` header, which the gate does not record. The
egress log is append-only and tamper-evident by design, which makes it the
worst possible place to write a user's secret — a credential you cannot delete
is a credential you cannot rotate away from. What is logged is the destination
and the text, which is what the log exists to answer for.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
from urllib.parse import urlparse
from collections.abc import Iterator
from typing import Any, Dict, Optional

from core.egress import EgressDenied, get_gate
from core.reasoning import CLOSE_TAG, OPEN_TAG

from .base_engine import ERROR_PREFIX, LLMEngine

logger = logging.getLogger(__name__)

#: How long to wait for the first byte, and then between chunks. Generous
#: because a cold cloud model behind a queue can take a while to start, and a
#: timeout mid-answer is worse than a slow one.
DEFAULT_TIMEOUT = 120.0


#: OpenRouter's endpoint, used when `OPENROUTER_API_KEY` is set. Hardcoded
#: because it is the address of a specific service rather than a preference,
#: and the provider layer already registers OpenRouter from the same variable —
#: two places reading one key is fine; two places inventing two URLs is not.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


#: Generation settings for a **local** OpenAI-compatible server.
#:
#: **Sending nothing is not neutral, and that is the whole point.** This body
#: carried `model`, `messages` and `stream` and no sampling at all, so the
#: server's own factory default applied — and TabbyAPI's is temperature 1.0
#: with top-p 1.0, which is unconstrained sampling from the raw distribution.
#: The Ollama path does not have this problem because a Modelfile ships
#: per-model settings and Ollama applies them. So the two local engines
#: generated differently, nobody chose that, and nothing anywhere said so.
#:
#: Reported as *"talking weird"*, 28 August 2026, against Qwen3.8-27B at
#: **2.20bpw** — a quantisation aggressive enough that loose sampling shows up
#: as wandering answers and headings nobody asked for. The quantisation is the
#: user's choice and not this module's business; the missing dial was ours.
#:
#: The values are Qwen3's own published recommendation for thinking mode and
#: are conservative enough to suit a general assistant on any model. They are a
#: **default, not a setting** — `CLAUDE.md` forbids sampling controls in the
#: primary path, and this never appears in the interface.
#:
#: **`temperature` and `top_p` only.** Both are standard OpenAI fields that
#: every compatible server accepts. `top_k` is a local extension: TabbyAPI and
#: vLLM take it, OpenAI itself rejects unknown fields, and one dialect-specific
#: key would make this constant unsafe to reuse. The gain from the two standard
#: ones is most of the benefit at none of the risk.
LOCAL_SAMPLING: Dict[str, Any] = {"temperature": 0.6, "top_p": 0.95}


def from_environment(**kwargs: Any) -> "OpenAICompatibleEngine | None":
    """Build a cloud engine from configuration, or return ``None``.

    ``None`` is the ordinary answer, not a failure: a user who has not brought
    a key has no cloud engine, and rule 1 says Zaram never supplies one.

    Reads the variables the provider layer already uses, so a key configured
    once is discovered *and* callable rather than producing a catalogue of
    models that cannot be reached:

    * ``ZARAM_OPENAI_ENDPOINT`` + ``ZARAM_OPENAI_KEY`` — any compatible service
    * ``OPENROUTER_API_KEY`` — OpenRouter, whose endpoint is not a preference

    An explicit endpoint wins, because someone who set one meant it.

    **Nothing here touches the network.** Rule 7g: no network call occurs before
    the user has consented to one, and that includes checking whether a key
    works. A key is validated by being used, at which point the gate has already
    logged the attempt and asked.
    """
    endpoint = (os.getenv("ZARAM_OPENAI_ENDPOINT") or "").strip()
    key = (os.getenv("ZARAM_OPENAI_KEY") or "").strip()

    if not endpoint and (os.getenv("OPENROUTER_API_KEY") or "").strip():
        endpoint = OPENROUTER_BASE_URL
        key = os.getenv("OPENROUTER_API_KEY", "").strip()

    if not endpoint or not key:
        return None

    # The model is supplied per request by the router, so the default here is
    # only a fallback for a caller that names none. It is deliberately not
    # guessed from a hardcoded list of provider model names: those change
    # weekly and a stale guess is a confusing 404 rather than a helpful default.
    default_model = (os.getenv("ZARAM_CLOUD_MODEL") or "").strip()

    try:
        return OpenAICompatibleEngine(
            base_url=endpoint, api_key=key, default_model=default_model, **kwargs
        )
    except (MissingApiKey, ValueError) as exc:
        logger.warning("cloud engine not configured: %s", exc)
        return None


class MissingApiKey(ValueError):
    """No key, so no engine.

    Raised at construction rather than at the first request. Rule 1 says Zaram
    never buys inference, which means a keyless cloud engine has nothing it
    could legitimately fall back to — and an engine that constructs fine and
    fails on first use puts that discovery inside the user's first message.
    """


#: Hosts whose traffic cannot leave the machine. Duplicated from the discovery
#: adapter rather than imported: this module must not depend on `providers`,
#: which is the same layering constraint `ModelsRuntime` keeps by typing its
#: provider manager loosely.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0"})


def _is_loopback(base_url: str) -> bool:
    """True when the endpoint is on this machine, by address not by name."""
    try:
        host = urlparse((base_url or "").strip()).hostname
    except ValueError:
        return False
    return bool(host) and host.lower() in _LOOPBACK_HOSTS


class OpenAICompatibleEngine(LLMEngine):
    """Streams from an OpenAI-compatible `/v1/chat/completions`.

    ``base_url`` is the API root, with or without a trailing ``/v1`` — both are
    accepted because both are what providers print in their own documentation,
    and a user pasting the URL from a dashboard should not have to know which
    convention we chose.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        default_model: str,
        gate: Any = None,
        source: str = "chat",
        timeout: float = DEFAULT_TIMEOUT,
        sampling: Optional[Dict[str, Any]] = None,
    ) -> None:
        # A keyless endpoint is allowed **only on loopback**, and the test is
        # the address rather than the absence of a key.
        #
        # This class was written on the assumption that OpenAI-compatible means
        # cloud, which its own error message still says. It is not true here:
        # LM Studio ships auth-free on 127.0.0.1:1234 and TabbyAPI does the
        # same, and the `lm_studio` catalogue entry has declared
        # `AuthStyle.NONE` all along -- so that entry could be discovered,
        # listed in the picker, and never executed. Relaxing on emptiness
        # instead would let a *cloud* provider through with no key, turning a
        # clear "bring your own key" refusal into an opaque 401 from a
        # stranger's server. Loopback is structural: a request to 127.0.0.1
        # cannot leave, which is the same reasoning `_policy_for` uses in the
        # discovery adapter.
        if not (api_key or "").strip() and not _is_loopback(base_url):
            raise MissingApiKey(
                "A cloud model needs your own API key. Zaram does not provide one."
            )
        self.base_url = self._normalise(base_url)
        self.default_model = default_model
        self._api_key = api_key.strip()
        # Injectable so tests can supply a gate with a known policy and log.
        # Resolved lazily rather than captured at import, because the process
        # gate can be replaced during startup.
        self._gate = gate
        self._source = source
        self._timeout = timeout
        #: Extra generation parameters merged into every request body, or
        #: ``None`` for "send none and let the server decide". See
        #: `LOCAL_SAMPLING` for why the local path supplies these and the
        #: cloud path deliberately does not.
        self._sampling = dict(sampling) if sampling else None

    @staticmethod
    def _normalise(base_url: str) -> str:
        """Accept `https://host`, `https://host/`, and `https://host/v1`."""
        trimmed = (base_url or "").strip().rstrip("/")
        if not trimmed:
            raise ValueError("A cloud model needs a base URL.")
        return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _body(self, prompt: str, system_prompt: str, model: str | None) -> dict[str, Any]:
        """The exact object that will be sent, built before anything is checked.

        Built once and used for both the gate and the request. Building it
        twice would let the text the user was shown drift from the text that
        left, which is the one thing the confirmation dialog cannot survive.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
        }
        if self._sampling:
            body.update(self._sampling)
        return body

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        """Stream plain text tokens, per `LLMEngine`.

        The order is the whole design: **build, then hand the whole thing to
        the gate.** The body — including the system prompt, and therefore every
        recalled fact in it — is what the gate logs and what the confirmation
        shows.

        **The gate is asked exactly once.** An earlier draft called `check`
        here *and* let `stream_lines` check again, which on an approved host
        merely double-logged, and on an `ask` host would have put two
        confirmation dialogs in front of one message. A user shown the same
        request twice does not conclude the software is careful; they conclude
        it is broken, and they stop reading the dialog — which is the one
        outcome M10 cannot afford.
        """
        body = self._body(prompt, system_prompt, model)
        payload = json.dumps(body)

        gate = self._gate if self._gate is not None else get_gate()
        try:
            lines = gate.stream_lines(
                self.endpoint,
                method="POST",
                body=payload,
                # Sent, not logged. See `EgressGate.stream_lines` — the log is
                # append-only, and a token written into it is one the user can
                # never delete and therefore never rotate away from.
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
                source=self._source,
            )
            yield from self._tokens(lines)
        except EgressDenied as denied:
            # `stream_lines` checks inside the generator, so a denial can also
            # surface here rather than above — a generator body does not run
            # until it is iterated.
            logger.info("cloud generation refused: %s", denied)
            yield ERROR_PREFIX + str(denied)
        except urllib.error.HTTPError as http_error:
            yield ERROR_PREFIX + self._explain(http_error)
        except Exception as exc:
            logger.warning("cloud request failed: %s: %s", type(exc).__name__, exc)
            yield ERROR_PREFIX + f"Could not reach {self.base_url}: {exc}"

    @staticmethod
    def _explain(error: Any) -> str:
        """Turn an HTTP failure into something the user can act on.

        401 and 402 are the two a real person actually hits, and a bare "401"
        tells them nothing about which of their several keys is wrong or which
        account ran out of credit.
        """
        status = getattr(error, "code", 0)
        detail = ""
        try:
            body = error.read().decode("utf-8", "replace")
            parsed = json.loads(body)
            detail = (parsed.get("error") or {}).get("message") or body[:200]
        except Exception:
            detail = ""

        if status == 401:
            return f"That API key was rejected. {detail}".strip()
        if status == 402:
            return f"That account has no credit left. {detail}".strip()
        if status == 429:
            return f"Rate limited by the provider. {detail}".strip()
        return f"The provider returned {status}. {detail}".strip()

    @staticmethod
    def _tokens(lines: Any) -> Iterator[str]:
        """Parse SSE into plain text, per the engine contract.

        Frames are unwrapped here rather than passed upward. `OllamaEngine`
        used to yield SSE that `ModelsService` parsed straight back off, and
        the contract docstring is explicit that transport framing belongs to
        the transport.

        **`reasoning_content` is read as well as `content`, and re-tagged.**
        Providers that split a reasoning model's stream -- TabbyAPI with its
        parser on, DeepSeek, and others following the same OpenAI extension --
        put the thinking in a second delta field. This engine read only
        `content`, so on those providers the thinking was **dropped in
        silence**: not leaked into the answer, simply gone, with the panel that
        exists to show it left permanently empty.

        The tokens are wrapped back into `<think>` ... `</think>` rather than
        given a new channel, because `core.reasoning.ReasoningSplitter` already
        understands exactly that shape and everything downstream is built on
        it -- the reasoning event, the transcript, and the rule that thinking
        never reaches `pushSpeech`. A parallel path would have to re-earn all
        three.
        """
        in_reasoning = False
        #: Whether any answer text has been emitted yet. Gates the one-off
        #: leading-whitespace trim below; see the comment there.
        answer_started = False
        for raw in lines:
            if not raw:
                continue
            line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                # Close an open block before leaving. `[DONE]` returns early,
                # so the tidy-up after the loop never runs on the normal path --
                # and an unclosed `<think>` makes the splitter hold the entire
                # reply, showing the user nothing at all.
                if in_reasoning:
                    yield CLOSE_TAG
                return
            try:
                frame = json.loads(data)
            except json.JSONDecodeError:
                # A keep-alive or a comment. Skipping is right; failing here
                # would end a working stream over a blank frame.
                continue

            if "error" in frame:
                message = frame["error"]
                if isinstance(message, dict):
                    message = message.get("message") or str(message)
                yield ERROR_PREFIX + str(message)
                return

            for choice in frame.get("choices") or ():
                delta = choice.get("delta") or {}

                thinking = delta.get("reasoning_content")
                if thinking:
                    if not in_reasoning:
                        in_reasoning = True
                        yield OPEN_TAG
                    yield thinking

                text = delta.get("content")
                if text:
                    # The answer starting is what closes the block. A provider
                    # is not obliged to send a final empty reasoning delta, so
                    # waiting for one would leave the tag unclosed and the
                    # whole reply filed as thinking.
                    if in_reasoning:
                        in_reasoning = False
                        yield CLOSE_TAG

                    # **The answer never begins with blank lines.** A reasoning
                    # model's chat template puts a newline or two after the
                    # closing think tag, so the first content delta arrives as
                    # ``"\n\nI’m"`` — measured against TabbyAPI serving
                    # Qwen3.8-27B, 28 August 2026, on every reply. That gap is
                    # invisible in a raw stream and reads on screen as the
                    # answer starting late or the model having stalled.
                    #
                    # Only the leading edge, and only once: a blank line
                    # *inside* an answer is the author's paragraph break and
                    # stripping those would run the prose together. Nothing is
                    # yielded until there is something to yield, so a chunk
                    # that was entirely whitespace does not emit an empty one.
                    if not answer_started:
                        text = text.lstrip()
                        if not text:
                            continue
                        answer_started = True

                    yield text

        # A stream that ends mid-thought still has to close its tag, or the
        # splitter holds everything and the user sees nothing at all.
        if in_reasoning:
            yield CLOSE_TAG
