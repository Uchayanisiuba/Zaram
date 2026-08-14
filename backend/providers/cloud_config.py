"""The cloud providers Zaram is connected to, and the keys that reach them.

Until now the only way to reach a cloud model was to set
``ZARAM_OPENAI_ENDPOINT`` and ``ZARAM_OPENAI_KEY`` *before* the process
started. `CLAUDE.md` says the target user is not technical, and an environment
variable that must be exported before launch is the least approachable
configuration surface there is — it also means the answer to "am I connected?"
lives nowhere a screen can read it.

**Several at once, not one.** The environment-variable design could express
exactly one endpoint and one key, which is not the shape people hold keys in: a
user signed in to two services expects to send one kind of work to one and
another kind to the other. So this holds a *set* of connections keyed by
provider id, and the engine side resolves per model — see
:class:`runtimes.models.engines.cloud_fanout.CloudFanout`. Building the single
version first and generalising later would have meant re-plumbing the engine,
which is the expensive half.

Where a key lives
-----------------
In memory, and in the environment for the one legacy connection, and nowhere
else this module writes. Persistence is Electron's `safeStorage`, which hands
keys back as environment variables at launch — the shape `CLAUDE.md` names, and
the reason there is no file path in here.

The environment is still read at startup, so a key exported before launch keeps
working exactly as it did. It is a *seed*, not the store: once there can be
more than one connection, a pair of variables cannot represent the state, and
pretending otherwise is how two halves of a system come to disagree about one
value. The provider layer already carries a scar from precisely that — the
engine and the discoverer reading ``ZARAM_OPENAI_ENDPOINT`` differently
produced a working chat beside a discovery asking for ``/v1/v1/models``.

What it will not do
-------------------
**It does not test the key.** Rule 7g: no network call occurs before the user
has consented to one, and "let me just check the key works" is a network call.
A key is validated by being used, at which point the egress gate has already
logged the attempt and asked. Connecting is a local state change and nothing
else.

**It does not return a key.** :func:`status` reports the last four characters,
which is enough to tell one key from another and is not a credential.
`CLAUDE.md` forbids an endpoint that returns a key, and the local API has no
authentication, so this is the line: enough to identify, never enough to use.

**It refuses a provider the catalogue grades as unreachable**, quoting the
catalogue's own reason. Anthropic speaks a different wire format and Gemini's
address does not fit the shape Zaram builds — connecting either would produce
an unexplained network error inside the user's first message, which is exactly
what the grading exists to prevent. The two entries marked *unverified* are
different: their format is right and only the regional root is unknown, so they
connect when the user supplies the root themselves, which is what their note
already tells them to do.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from . import catalogue
from .catalogue import Compatibility, GENERIC_ENDPOINT_ENV, GENERIC_KEY_ENV
from .contracts import ProviderKind
from .discoverers.openai_compat import OpenAICompatibleAdapter

logger = logging.getLogger(__name__)

__all__ = [
    "CloudConnection",
    "CloudConfigError",
    "LEGACY_PROVIDER_ID",
    "attach_runtimes",
    "connect",
    "disconnect",
    "resolve_for_model",
    "seed_from_environment",
    "status",
]

#: The id an environment-configured connection registers under.
#:
#: Matches what ``_register_default_providers`` already used, so a key exported
#: before launch and the same key set from Settings produce one registration
#: rather than two that shadow each other.
LEGACY_PROVIDER_ID = "openai_cloud"

#: Hosts where a missing key is normal rather than a mistake. LM Studio and
#: Ollama's OpenAI mode want no credential at all, and demanding one would make
#: the picker refuse the one catalogue entry that is not egress.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0"}


class CloudConfigError(ValueError):
    """The connection was refused, with a reason a person can act on."""


@dataclass(frozen=True)
class CloudConnection:
    """One provider Zaram may call, and the credential that reaches it."""

    provider_id: str
    base_url: str
    api_key: str
    display_name: str

    @property
    def is_loopback(self) -> bool:
        return (urlparse(self.base_url).hostname or "").lower() in _LOOPBACK_HOSTS

    def to_dict(self) -> Dict[str, Any]:
        """Safe to serve. The key is reduced to four characters — see the module docstring.

        Four rather than eight, and the tail rather than the head: ``sk-proj-``
        is identical on every OpenAI key and identifies nothing, while the last
        four are what a person compares against the row in their provider's
        dashboard.
        """
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "base_url": self.base_url,
            "key_tail": self.api_key[-4:] if len(self.api_key) >= 4 else None,
            "needs_key": not self.is_loopback,
            "locality": "local" if self.is_loopback else "cloud",
        }


_connections: Dict[str, CloudConnection] = {}
_providers_runtime: Any = None
_models_runtime: Any = None


def attach_runtimes(providers_runtime: Any, models_runtime: Any) -> None:
    """Give this module the two runtimes it has to keep in step.

    Called from the bootstrapper. Passed in rather than imported so this module
    does not reach across into ``runtimes.models`` — the same direction of
    dependency the rest of the provider layer keeps.
    """
    global _providers_runtime, _models_runtime
    _providers_runtime = providers_runtime
    _models_runtime = models_runtime

    setter = getattr(models_runtime, "set_cloud_engine_factory", None)
    if callable(setter):
        setter(_build_fanout)


# --------------------------------------------------------------------- read


def _is_loopback(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() in _LOOPBACK_HOSTS


def connections() -> Dict[str, CloudConnection]:
    return dict(_connections)


def status() -> Dict[str, Any]:
    """Everything connected, without any credential.

    The catalogue's ``generated`` date travels with it for the same reason it
    travels with the catalogue itself: a surface that renders providers and
    forgets when the list was written is the failure the date exists to
    prevent.
    """
    return {
        "connections": [c.to_dict() for c in _connections.values()],
        "configured": bool(_connections),
        "generated": catalogue.GENERATED,
        "endpoint_env": GENERIC_ENDPOINT_ENV,
        "key_env": GENERIC_KEY_ENV,
    }


# -------------------------------------------------------------------- write


def _resolve_endpoint(provider_id: Optional[str], base_url: Optional[str]) -> Tuple[str, str]:
    """The URL to call and a name to show, or a refusal in the catalogue's words."""
    supplied = (base_url or "").strip()

    if not provider_id:
        if not supplied:
            raise CloudConfigError(
                "Choose a provider, or paste the API address from your provider's console."
            )
        return supplied, urlparse(supplied).hostname or supplied

    entry = catalogue.get(provider_id)
    if entry is None:
        # Not in the manifest is not an error — the catalogue is a convenience
        # over configuration that already works, and says so. A caller naming an
        # unknown id and supplying a URL meant the URL.
        if not supplied:
            raise CloudConfigError(
                f"Zaram has no entry for {provider_id!r}. Paste the API address instead."
            )
        return supplied, provider_id

    if not entry.available:
        # An unverified entry is unavailable only because *which* regional root
        # applies is unknowable from here. Supplying the root answers the one
        # open question, which is what the entry's own note asks the user to do.
        if entry.compatibility is Compatibility.UNVERIFIED and supplied:
            return supplied, entry.display_name
        raise CloudConfigError(entry.note or f"Zaram cannot call {entry.display_name} yet.")

    return (supplied or entry.base_url), entry.display_name


async def connect(
    *,
    provider_id: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Add or replace a cloud connection, effective without a restart.

    No network call happens here — see the module docstring. Which models the
    provider offers is not known until something asks, and asking is a separate,
    explicit action because it is egress.
    """
    endpoint, display_name = _resolve_endpoint(provider_id, base_url)
    key = (api_key or "").strip()

    if not key and not _is_loopback(endpoint):
        raise CloudConfigError(
            "That provider needs an API key. Zaram never supplies one — bring your own."
        )

    connection_id = provider_id or (urlparse(endpoint).hostname or "custom")
    _connections[connection_id] = CloudConnection(
        provider_id=connection_id,
        base_url=endpoint,
        api_key=key,
        display_name=display_name,
    )

    # The legacy variables track whichever connection registered under the
    # legacy id, and only that one. They exist so a key exported before launch
    # keeps behaving as it did; they are not the store, and a second connection
    # deliberately does not touch them rather than overwriting a value the user
    # set outside the app.
    if connection_id == LEGACY_PROVIDER_ID:
        os.environ[GENERIC_ENDPOINT_ENV] = endpoint
        if key:
            os.environ[GENERIC_KEY_ENV] = key

    _register_adapter(_connections[connection_id])
    _reload_engine()

    logger.info("cloud provider connected: %s (%s)", connection_id, endpoint)
    return status()


def disconnect(provider_id: str) -> Dict[str, Any]:
    """Forget one connection. Local answering, and every other connection, are unaffected.

    The adapter is removed as well as the credential dropped, because leaving it
    registered would keep a catalogue of models Zaram can no longer call — the
    same "list of things Zaram appears to offer and does not" the provider
    runtime already refuses to create for a keyless OpenRouter.
    """
    _connections.pop(provider_id, None)

    if provider_id == LEGACY_PROVIDER_ID:
        os.environ.pop(GENERIC_ENDPOINT_ENV, None)
        os.environ.pop(GENERIC_KEY_ENV, None)

    if _providers_runtime is not None:
        try:
            _providers_runtime.registry.remove_model_provider(provider_id)
        except Exception:  # pragma: no cover - registry shapes vary in tests
            logger.debug("no adapter registered for %s", provider_id, exc_info=True)
        _forget_scan()

    _reload_engine()
    logger.info("cloud provider disconnected: %s", provider_id)
    return status()


def seed_from_environment() -> None:
    """Adopt a key exported before launch as an ordinary connection.

    Called once, from the bootstrapper. Everything set this way behaves exactly
    as a connection made in Settings, which is the point: there is one code path
    for a configured provider, and the environment is an input to it rather than
    a parallel mechanism with its own bugs.
    """
    endpoint = (os.getenv(GENERIC_ENDPOINT_ENV) or "").strip()
    key = (os.getenv(GENERIC_KEY_ENV) or "").strip()
    if endpoint and (key or _is_loopback(endpoint)):
        _connections[LEGACY_PROVIDER_ID] = CloudConnection(
            provider_id=LEGACY_PROVIDER_ID,
            base_url=endpoint,
            api_key=key,
            display_name=urlparse(endpoint).hostname or endpoint,
        )

    router_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if router_key:
        entry = catalogue.get("openrouter")
        _connections["openrouter"] = CloudConnection(
            provider_id="openrouter",
            base_url=entry.base_url if entry else "https://openrouter.ai/api/v1",
            api_key=router_key,
            display_name=entry.display_name if entry else "OpenRouter",
        )

    for connection in _connections.values():
        _register_adapter(connection)
    if _connections:
        _reload_engine()


# ------------------------------------------------------------------ internals


def _register_adapter(connection: CloudConnection) -> None:
    """Replace the discovery adapter so it points at this connection.

    Removed and re-added rather than mutated: the adapter derives its data
    policy and its stripped base URL in ``__init__``, so mutating ``base_url``
    in place would leave a policy inferred from the *previous* address. That is
    a privacy claim about the wrong destination, which is the one kind of stale
    value this codebase treats as worse than an error.
    """
    if _providers_runtime is None:
        return

    registry = _providers_runtime.registry
    try:
        registry.remove_model_provider(connection.provider_id)
    except Exception:  # pragma: no cover
        logger.debug("no previous adapter for %s", connection.provider_id, exc_info=True)

    registry.register_model_provider(
        OpenAICompatibleAdapter(
            provider_id=connection.provider_id,
            base_url=connection.base_url,
            kind=(
                ProviderKind.LOCAL_AI_SERVER
                if connection.is_loopback
                else ProviderKind.CLOUD_API
            ),
            api_key=connection.api_key or None,
        )
    )
    _forget_scan()


def _forget_scan() -> None:
    """Mark discovery stale so the next read re-scans.

    Deliberately not a scan. ``ensure_scanned`` reaches every registered
    provider, and for a cloud one that is egress — it belongs behind a
    deliberate action by the user, not behind a settings save.
    """
    manager = getattr(_providers_runtime, "manager", None)
    if manager is not None:
        manager._scanned = False  # noqa: SLF001 - the manager has no public invalidate


def resolve_for_model(model: Optional[str]) -> Optional[Tuple[Any, str]]:
    """Which connection serves ``model``, and what to call it on the wire.

    The provider layer records models as ``<provider_id>:<name>``, and the wire
    wants the bare name — see `CloudFanout`, which is the only caller and whose
    docstring carries the reasoning.

    A bare name with no prefix is resolved only when exactly one connection
    exists. With two, a bare name is genuinely ambiguous, and picking one would
    send a prompt to a provider the user did not choose.
    """
    if not model:
        return None

    provider_id, _, bare = model.partition(":")
    if bare and provider_id in _connections:
        return _engine_for(_connections[provider_id]), bare

    if len(_connections) == 1:
        only = next(iter(_connections.values()))
        return _engine_for(only), model

    return None


def _engine_for(connection: CloudConnection) -> Any:
    """A cloud engine pointed at one connection.

    Built per call rather than cached. The cost is an object with three
    strings in it; the alternative is a cache that has to be invalidated when a
    key changes, and a stale entry there would send the user's prompt with a
    credential they had already revoked.
    """
    from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

    return OpenAICompatibleEngine(
        base_url=connection.base_url,
        api_key=connection.api_key,
        default_model="",
    )


def _build_fanout() -> Any:
    """The engine `ModelsRuntime` uses for everything cloud, or ``None``.

    ``None`` when nothing is connected, which is the ordinary state and not a
    failure: `RoutedEngine` already says out loud that a cloud model was asked
    for and no key exists, rather than quietly answering from a local one.
    """
    if not _connections:
        return None

    from runtimes.models.engines.cloud_fanout import CloudFanout

    return CloudFanout(resolve_for_model)


def _reload_engine() -> None:
    """Rebuild the answering engine so a change applies without a restart.

    Without this the process keeps the engine it built at boot: a key entered in
    Settings would appear connected, discovery would find the models, and every
    message would still be answered locally with nothing saying why.
    """
    if _models_runtime is None:
        return
    try:
        _models_runtime.reload_engine()
    except Exception:  # pragma: no cover - never take chat down for a settings change
        logger.warning("could not rebuild the model engine", exc_info=True)
