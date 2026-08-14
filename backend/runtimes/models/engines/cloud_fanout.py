"""One engine standing in for several cloud providers at once.

`RoutedEngine` decides *local or cloud*. It has always been handed a single
cloud engine, because a single endpoint and a single key were the only cloud
configuration that existed. That stops being enough the moment someone is
signed in to two services and wants a coding question answered by one and
something else by the other — which is the shape a person actually holds keys
in, not a special case.

So the split is: `RoutedEngine` answers "may this leave the machine?", and this
answers "whose machine does it go to?". Two questions, two classes, and neither
learns the other's job. It satisfies the same `LLMEngine` contract, so it drops
into the slot the single cloud engine occupied and nothing above it changes.

**The provider prefix has to come off, and that is a bug this class fixes.**
The provider layer records every discovered model as ``<provider_id>:<model>``
— ``openai_cloud:gpt-4o`` — because two providers can offer models with the
same name and the ids have to be distinct. The cloud engine puts whatever it is
handed straight into the request body's ``model`` field. So selecting a
discovered cloud model by its real id would have sent ``openai_cloud:gpt-4o``
to OpenAI, which does not exist, and the failure would have arrived as a
provider error message about an unknown model rather than as anything pointing
at Zaram. Resolution and stripping are the same lookup, so they belong in the
same place.

**A model this cannot place is refused out loud, never sent anywhere.** Falling
back to "the first connection" would mean a prompt going to a provider the user
did not choose, which is a rule 5 failure that looks like a working feature —
the exact phrasing `ModelInfo.selectable_by_default` already uses for the same
hazard one layer down.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Callable, Optional, Tuple

from .base_engine import ERROR_PREFIX, LLMEngine

logger = logging.getLogger(__name__)

#: Given a model id, return the engine to send it to and the name to send.
#:
#: A callable rather than a dictionary of connections, for the same reason
#: `RoutedEngine` takes `IsRemote` as a callable: this module must not import
#: `providers`, and the mapping from a model to a provider is knowledge that
#: belongs where the connections live.
#:
#: ``None`` means "no connection can serve this", which is a refusal and never
#: a licence to pick something.
ResolveCloud = Callable[[Optional[str]], Optional[Tuple[LLMEngine, str]]]


class CloudFanout(LLMEngine):
    """Delegates to whichever connected provider owns the requested model."""

    def __init__(self, resolve: ResolveCloud) -> None:
        self._resolve = resolve
        self._default_model: Optional[str] = None

    @property
    def default_model(self) -> Optional[str]:
        """Held, not proxied.

        There is no sensible single default across several providers, and
        picking one would be Zaram choosing a destination for the user's data.
        `RoutedEngine` only ever reaches this class with an explicit model, so
        the value exists to satisfy the contract rather than to be used.
        """
        return self._default_model

    @default_model.setter
    def default_model(self, value: Optional[str]) -> None:
        self._default_model = value

    def stream_response(
        self, prompt: str, system_prompt: str = "", model: str | None = None
    ) -> Iterator[str]:
        try:
            resolved = self._resolve(model)
        except Exception as exc:
            # A lookup failure is never a reason to send data to a guess.
            logger.warning("cloud lookup failed for %r: %s", model, exc)
            resolved = None

        if resolved is None:
            yield ERROR_PREFIX + (
                f"{model or 'That model'} is a cloud model and no connected provider "
                f"offers it. Connect the provider in Settings, or choose a different model."
            )
            return

        engine, wire_name = resolved
        logger.info("cloud fanout: %s -> %s as %r", model, type(engine).__name__, wire_name)
        yield from engine.stream_response(prompt, system_prompt, wire_name)
