"""Voice provider registry.

Maps provider names to provider classes/instances and validates them. Works
with any future provider (Kokoro, XTTS, ElevenLabs, OpenAI, Unreal, custom)
without changes here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from .exceptions import DuplicateProviderError, ProviderNotFoundError
from .providers.base import VoiceProvider


class VoiceRegistry:
    def __init__(self) -> None:
        # name -> provider class or instance
        self._providers: Dict[str, Union[Type[VoiceProvider], VoiceProvider]] = {}

    # --- registration ---
    def register(self, name: str, provider: Union[Type[VoiceProvider], VoiceProvider]) -> None:
        """Register a provider under ``name``.

        ``provider`` may be a :class:`VoiceProvider` subclass or an instance.
        Raises :class:`DuplicateProviderError` if ``name`` is taken, and
        :class:`ValueError` if the object is not a valid provider.
        """
        if name in self._providers:
            raise DuplicateProviderError(f"Provider '{name}' is already registered")

        self._validate(provider)
        self._providers[name] = provider

    def _validate(self, provider: Union[Type[VoiceProvider], VoiceProvider]) -> None:
        if isinstance(provider, VoiceProvider):
            return
        if isinstance(provider, type) and issubclass(provider, VoiceProvider):
            return
        raise ValueError(
            f"'{provider!r}' is not a VoiceProvider subclass or instance"
        )

    # --- retrieval ---
    def is_registered(self, name: str) -> bool:
        return name in self._providers

    def get(self, name: str) -> Union[Type[VoiceProvider], VoiceProvider]:
        """Return the registered class or instance (no instantiation)."""
        if name not in self._providers:
            raise ProviderNotFoundError(f"Provider '{name}' is not registered")
        return self._providers[name]

    def get_instance(self, name: str, *args: Any, **kwargs: Any) -> VoiceProvider:
        """Return a provider *instance* for ``name`` (lazily instantiated)."""
        obj = self.get(name)
        if isinstance(obj, VoiceProvider):
            return obj
        return obj(*args, **kwargs)  # type: ignore[call-arg]

    def list_providers(self) -> List[str]:
        return list(self._providers)

    def count(self) -> int:
        return len(self._providers)
