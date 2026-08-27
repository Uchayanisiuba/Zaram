# backend/runtimes/models/engines/routed_engine.py
"""Local or cloud, decided per message.

`ModelsService` holds one engine, and until now there was only one to hold.
With a cloud engine in the picture the choice has to be made somewhere, and the
`LLMEngine` contract already carries the only input it needs: `stream_response`
takes a `model`. So this satisfies the same contract, sits where the single
engine used to, and delegates. Nothing above it changes.

**Locality is asked, never guessed.** The provider layer discovered each model
and recorded its `locality`, so that is what decides. The alternative — matching
on the name, `"gpt"` or `"claude"` or a `/` in it — would be a guess about
whether the user's private documents are about to cross the internet, made by
string comparison against a list nobody maintains. A local model called
`gpt-oss` is not a hypothetical; it is on Ollama today.

**An unresolvable model routes local.** That is the fail-safe direction and it
is the only defensible one: local costs a possibly-wrong model, cloud costs the
user's data leaving the machine on the strength of a lookup that failed. The
asymmetry decides it. The gate would still refuse an unapproved host, but a
design that leans on the last line of defence for its ordinary behaviour has
one line of defence.

**Cloud requested and unavailable is said out loud.** `CLAUDE.md`: "Disabled
capabilities are visible, not silent. If a question would have used search and
search is off, say so rather than answering quietly without it." Quietly
answering from a small local model when the user picked a large cloud one is
the same failure — the answer is worse and nothing indicates why.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Callable, Optional

from .base_engine import ERROR_PREFIX, LLMEngine

logger = logging.getLogger(__name__)

#: Answers the question "would this model name send data off the machine?".
#: A callable rather than a `ProviderManager` because this module must not
#: import `providers` — `ModelsRuntime` is explicit that the chat path may not
#: acquire a hard dependency on a layer that is still being connected.
IsRemote = Callable[[Optional[str]], bool]


class RoutedEngine(LLMEngine):
    """Delegates to a local or cloud engine, per call, by the model's locality."""

    def __init__(
        self,
        *,
        local: LLMEngine,
        cloud: Optional[LLMEngine],
        is_remote: IsRemote,
    ) -> None:
        self._local = local
        self._cloud = cloud
        self._is_remote = is_remote

    @property
    def default_model(self) -> Optional[str]:
        """Proxied so `ModelsRuntime` can keep setting it on one object.

        The runtime assigns `engine.default_model` after asking the provider
        layer. That attribute belongs to whichever engine actually answers, and
        today the default is always local — a cloud default would mean Zaram
        chose to send data off-device without being asked, which rule 5 forbids
        as a default and rule 7g forbids at startup.
        """
        return getattr(self._local, "default_model", None)

    @default_model.setter
    def default_model(self, value: Optional[str]) -> None:
        self._local.default_model = value  # type: ignore[attr-defined]

    def stream_vision_response(self, prompt: str, images, system_prompt: str = ""):
        """Vision goes local. Forwarded so the wrapper does not swallow it.

        `Dispatcher` looks this up by attribute, so a wrapper that does not
        name it fails with `AttributeError` rather than falling back -- which
        is what "Can you see images" produced once a cloud key was configured.

        Local rather than cloud, deliberately: the cloud engine has no vision
        path today, and rule 5's default-deny means an image -- far more
        personal than a chat message, and its own consent class under rule 7j
        -- must not start leaving the device because a wrapper picked the
        nearest available method.
        """
        return self._local.stream_vision_response(prompt, images, system_prompt)

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        try:
            remote = bool(model) and self._is_remote(model)
        except Exception as exc:
            # A resolver failure is not a reason to send anything anywhere.
            logger.warning("locality lookup failed for %r, routing local: %s", model, exc)
            remote = False

        if not remote:
            yield from self._local.stream_response(prompt, system_prompt, model, images)
            return

        if self._cloud is None:
            yield ERROR_PREFIX + (
                f"{model} is a cloud model and no API key is configured, so it "
                f"cannot be used. Add a key in Settings, or choose a local model."
            )
            return

        # **An image does not go to a cloud provider yet, and that is a
        # consent decision rather than a missing feature.** Rule 7j grants
        # consent per destination *and data class*: a chat message is a couple
        # of kilobytes and a photograph is a few megabytes of something far
        # more personal, so connecting a provider for text is not consent to
        # send it a picture. Nothing asks that question yet, so nothing may
        # assume the answer.
        #
        # Refused rather than stripped, because an answer built from the prompt
        # with the image quietly removed is confident prose about a picture
        # nobody looked at — the same failure the local gate exists to stop,
        # arriving by the cloud route.
        if images:
            yield ERROR_PREFIX + (
                f"{model} is a cloud model, and Zaram does not send images off "
                "this device yet. Choose a local model that can see, or remove "
                "the picture."
            )
            return

        logger.info("routing to cloud engine for model=%s", model)
        yield from self._cloud.stream_response(prompt, system_prompt, model)
