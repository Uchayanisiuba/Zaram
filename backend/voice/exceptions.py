"""Exceptions for the Voice Runtime subsystem."""

from __future__ import annotations


class VoiceRuntimeError(Exception):
    """Base class for all voice runtime errors."""


class ProviderNotFoundError(VoiceRuntimeError):
    """Raised when a requested provider is not registered."""


class DuplicateProviderError(VoiceRuntimeError):
    """Raised when registering a provider name that already exists."""


class ProviderUnavailableError(VoiceRuntimeError):
    """Raised when a provider cannot serve a request (not initialized, etc.)."""
