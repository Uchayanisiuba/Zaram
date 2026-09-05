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

        # **An image is its own consent class, and the answer now lives where
        # every other egress decision does.** Rule 7j grants consent per
        # destination *and data class*: a chat message is a couple of kilobytes
        # and a photograph is a few megabytes of something far more personal,
        # so connecting a provider for text is not consent to send it a
        # picture.
        #
        # This used to refuse every cloud-bound image outright, with a comment
        # saying nothing asked that question yet. `EgressPolicy` could only
        # speak about hosts, so there was nowhere to put the answer, and a
        # blanket refusal was the only honest position available. Since 29
        # August 2026 the policy is keyed on `(host, DataClass)`, so the
        # question is asked properly: `OpenAICompatibleEngine` reads the class
        # off the body it is about to send, and the gate refuses, asks, or
        # allows — and logs whichever it did.
        #
        # **The check is not repeated here, and that is the point.** This
        # module deliberately holds no policy and no gate — it takes an
        # `is_remote` callable precisely so the chat path acquires no
        # dependency on the provider layer. A second copy of the rule here
        # would be a second implementation of one question, which is the defect
        # `_local_endpoint_for` shipped: four call sites resolving a model one
        # way and a fifth resolving it another. One chokepoint, asked once.
        logger.info("routing to cloud engine for model=%s images=%s", model, bool(images))
        yield from self._cloud.stream_response(prompt, system_prompt, model, images)
