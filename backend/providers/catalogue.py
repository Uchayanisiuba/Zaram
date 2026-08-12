"""The cloud providers a person can pick from, and an honest grade for each.

Configuring a cloud model today means knowing that ``ZARAM_OPENAI_ENDPOINT``
exists, knowing that Groq's root is ``https://api.groq.com/openai/v1`` and not
``https://api.groq.com/v1``, and setting both by hand before anything works.
`CLAUDE.md` says the target user is not technical; an environment variable is
the least technical-user-facing configuration surface there is. This module is
the data a picker reads instead — a list of the services people actually have
keys for, each with the one URL that matters and a plain statement of whether
Zaram can call it today.

Why a dated manifest rather than a lookup
-----------------------------------------
Same shape, and the same reason, as the model recommendations: **a dated local
manifest, with the date visible.** These are third-party facts that change on
someone else's schedule — a base URL moves, a console moves, a provider adds a
compatibility layer — and there are exactly two honest ways to handle that.
Fetch it, which is a network call before the user has consented to one and
therefore forbidden by rule 7g. Or write it down, say when it was written down,
and let the reader judge staleness themselves. This is the second.

So: **nothing here is confirmed by a live request.** Every URL is transcribed
from the provider's own documentation on the date in :data:`GENERATED`. What
*is* verified, in this repo, by tests, is the narrower and more useful claim —
that the base URL in an entry marked available, put through the same
normalisation the engine and the discoverer use, arrives at the endpoint the
entry says it should. That is a property of our code, and our code is the thing
that breaks.

Graded, not advertised
----------------------
`CLAUDE.md` settles the shape with the pack catalogue: unavailable entries are
**shown greyed out and honestly graded**, not hidden and not quietly listed as
working. A provider Zaram cannot reach today still appears — someone looking
for Gemini should find out that it is known about and why it does not work yet,
rather than conclude the product has never heard of it — and it appears with
:data:`Support.UNAVAILABLE` and a note naming the obstacle.

Three obstacles are represented here, and they are genuinely different things:

* **A different wire format.** Anthropic's API is ``/v1/messages`` with an
  ``x-api-key`` header, not ``/v1/chat/completions`` with a bearer token. It
  needs an adapter that does not exist.
* **A base URL our normalisation cannot express.** Gemini's OpenAI-compatible
  root ends in ``/openai``, and its chat path hangs directly off that. Both
  halves of Zaram's cloud path assume ``<root>/v1/...`` — the engine appends
  ``/v1`` when it is missing, the discoverer strips it and re-adds it — so a
  Gemini root would be sent to ``.../openai/v1/chat/completions``, which is not
  where Gemini listens. The wire format is fine; the assumption is not.
* **A URL nobody here has confirmed.** Qwen and Kimi are documented as
  OpenAI-compatible and both publish regional roots. Which root a given account
  uses is not something this file can know, and shipping the wrong one produces
  a DNS failure the user has no way to interpret. That is the same failure as a
  confident wrong ``vram_bytes``: a caller can handle "unknown", and cannot
  handle a plausible wrong answer.

Only the first is "needs an adapter". Collapsing them into one label would lose
the fact that two of the three are a small change to code we already own.

This module holds no secrets
----------------------------
It describes providers. It names the *variable* a chosen provider's key lands
in — ``ZARAM_OPENAI_KEY`` is a name, not a value — and never the key itself.
Nothing here reads a key either: what a key is worth is decided at the moment
it is used, by the engine, behind the egress gate.

It is not a gate
----------------
The catalogue is a convenience over configuration that already works. Setting
``ZARAM_OPENAI_ENDPOINT`` to something that appears nowhere in this file
configures a working cloud engine exactly as it did before, and an empty or
truncated catalogue takes nothing away — which is what "never fail closed"
means for a manifest whose job is to save typing. There is a test for that,
because it is the property most easily lost by someone later making the picker
the only route.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .contracts import ProviderKind

__all__ = [
    "GENERATED",
    "AuthStyle",
    "Compatibility",
    "Support",
    "ProviderEntry",
    "PROVIDERS",
    "GENERIC_ENDPOINT_ENV",
    "GENERIC_KEY_ENV",
    "list_providers",
    "get",
    "to_payload",
]


#: The date every URL below was read from provider documentation, ISO-8601.
#:
#: Visible in the payload, deliberately. A manifest without a date is a claim
#: about the present that quietly becomes a claim about the past, and the user
#: has no way to tell which they are looking at. Bump it when an entry is
#: re-checked, not when an unrelated entry is added.
GENERATED = "2026-08-12"


#: The variables the existing cloud path already reads. Named here so a picker
#: can say what it is about to set, rather than setting something invisible.
#: Kept as constants because the engine and the provider runtime both read
#: these exact strings, and a third spelling of them is a bug waiting to be
#: written — see ``test_provider_catalogue.py``, which checks the round trip
#: through the real engine rather than trusting the match by eye.
GENERIC_ENDPOINT_ENV = "ZARAM_OPENAI_ENDPOINT"
GENERIC_KEY_ENV = "ZARAM_OPENAI_KEY"


class Compatibility(str, Enum):
    """Which wire format a provider speaks, or the admission that we do not know.

    ``UNVERIFIED`` is not a hedge for tidiness. It is the value for a provider
    whose documentation says "OpenAI-compatible" while the specific root this
    file would have to ship has not been confirmed from here — and a wrong root
    is worse than no entry, because it fails as an unexplained network error
    inside the user's first cloud message.
    """

    #: Speaks ``/v1/chat/completions`` with a bearer token.
    OPENAI = "openai"
    #: Its own request shape. Needs an adapter Zaram does not have.
    NATIVE = "native"
    #: Documented as compatible; the exact root has not been confirmed here.
    UNVERIFIED = "unverified"


class AuthStyle(str, Enum):
    """How the key is presented, for the entries that need one.

    Recorded rather than assumed because it is the difference between an
    adapter existing and not existing. It never travels in a request body and
    is never logged: the egress log is append-only, which makes it the worst
    possible place to write a credential.
    """

    #: ``Authorization: Bearer <key>`` — what the OpenAI-compatible engine sends.
    BEARER = "bearer"
    #: ``x-api-key: <key>`` plus an ``anthropic-version`` header.
    X_API_KEY = "x_api_key"
    #: A local server on loopback. No key, and nothing leaves the machine.
    NONE = "none"


class Support(str, Enum):
    """Whether Zaram can call this provider today.

    Two states and a mandatory reason, rather than a boolean. The reason is the
    point: "greyed out" without "and here is why" is the same as missing.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderEntry:
    """One provider, as a person choosing between them needs to see it."""

    #: Stable identifier. Matches the adapter's ``provider_id`` where one
    #: exists, so a catalogue pick and a discovered provider are the same thing
    #: rather than two records that have to be reconciled later.
    id: str
    display_name: str
    kind: ProviderKind
    #: The API root, exactly as the provider prints it in its own dashboard.
    #: Written that way on purpose — a user comparing this against the page
    #: they copied their key from should see the same string.
    base_url: str
    #: The URL a chat request actually goes to, per the provider's docs.
    #:
    #: Redundant-looking and load-bearing. This is what makes the grade
    #: checkable: a test puts ``base_url`` through the real engine and asserts
    #: the result equals this, so an entry claiming to be available is claiming
    #: something a machine can disagree with.
    chat_endpoint: str
    compatibility: Compatibility
    auth: AuthStyle
    #: Where a person goes to get a key. Never fetched — see the module
    #: docstring; it is displayed and opened by the user, if at all.
    key_url: str
    support: Support
    #: Why, in one sentence a non-technical user can act on. Required for
    #: anything unavailable, and used for caveats on the rest.
    note: str = ""
    #: The variable a picker would set. A name, never a value.
    key_env: str = ""
    endpoint_env: str = ""

    @property
    def available(self) -> bool:
        return self.support is Support.AVAILABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "kind": self.kind.value,
            "base_url": self.base_url,
            "chat_endpoint": self.chat_endpoint,
            "compatibility": self.compatibility.value,
            "openai_compatible": self.compatibility is Compatibility.OPENAI,
            "auth": self.auth.value,
            "key_url": self.key_url,
            "support": self.support.value,
            "available": self.available,
            "note": self.note,
            "key_env": self.key_env,
            "endpoint_env": self.endpoint_env,
        }


def _openai_compatible(
    provider_id: str,
    display_name: str,
    base_url: str,
    key_url: str,
    *,
    note: str = "",
) -> ProviderEntry:
    """An entry for a service reachable through the existing engine.

    A helper rather than twelve near-identical literals, because the thing that
    must not drift between them is the relationship between ``base_url`` and
    ``chat_endpoint`` — and deriving it here means an entry cannot claim a root
    and an endpoint that disagree. Providers whose endpoint is *not*
    ``<root>/chat/completions`` are written out in full below, which is exactly
    the visibility they deserve.
    """
    return ProviderEntry(
        id=provider_id,
        display_name=display_name,
        kind=ProviderKind.CLOUD_API,
        base_url=base_url,
        chat_endpoint=f"{base_url.rstrip('/')}/chat/completions",
        compatibility=Compatibility.OPENAI,
        auth=AuthStyle.BEARER,
        key_url=key_url,
        support=Support.AVAILABLE,
        note=note,
        key_env=GENERIC_KEY_ENV,
        endpoint_env=GENERIC_ENDPOINT_ENV,
    )


#: The manifest. Ordered roughly by how likely a first-time user already holds a
#: key, not by preference — Zaram does not rank providers, and an order that
#: looked like a recommendation would be a recommendation.
PROVIDERS: Tuple[ProviderEntry, ...] = (
    _openai_compatible(
        "openai",
        "OpenAI",
        "https://api.openai.com/v1",
        "https://platform.openai.com/api-keys",
    ),
    ProviderEntry(
        id="anthropic",
        display_name="Claude (Anthropic)",
        kind=ProviderKind.CLOUD_API,
        base_url="https://api.anthropic.com",
        # Not chat/completions. The request shape differs too: system text is a
        # top-level field rather than a message, which is the part that matters
        # here, because the system prompt is where recalled facts live.
        chat_endpoint="https://api.anthropic.com/v1/messages",
        compatibility=Compatibility.NATIVE,
        auth=AuthStyle.X_API_KEY,
        key_url="https://console.anthropic.com/settings/keys",
        support=Support.UNAVAILABLE,
        note=(
            "Zaram cannot call Claude directly yet — it uses a different request "
            "format from the one Zaram speaks. An OpenAI-compatible route is "
            "documented by Anthropic but has not been confirmed here, so it is "
            "not offered. OpenRouter reaches Claude today."
        ),
    ),
    ProviderEntry(
        id="google_gemini",
        display_name="Gemini (Google)",
        kind=ProviderKind.CLOUD_API,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        # The obstacle, in one line: the path hangs off `/openai`, with no `/v1`
        # under it. Zaram's normalisation would send this to
        # `.../openai/v1/chat/completions`.
        chat_endpoint=(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        ),
        compatibility=Compatibility.OPENAI,
        auth=AuthStyle.BEARER,
        key_url="https://aistudio.google.com/apikey",
        support=Support.UNAVAILABLE,
        note=(
            "Gemini speaks the format Zaram speaks, but its address does not fit "
            "the pattern Zaram assumes, so it would be called at the wrong URL. "
            "A small change to how endpoints are built would fix it. OpenRouter "
            "reaches Gemini today."
        ),
    ),
    _openai_compatible(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "https://openrouter.ai/keys",
        note=(
            "One key for models from many providers. What happens to a prompt "
            "depends on the model you pick, not on OpenRouter, so Zaram will not "
            "route here on its own — free models in particular are logged and may "
            "be trained on."
        ),
    ),
    _openai_compatible(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com/v1",
        "https://platform.deepseek.com/api_keys",
    ),
    _openai_compatible(
        "groq",
        "Groq",
        "https://api.groq.com/openai/v1",
        "https://console.groq.com/keys",
    ),
    _openai_compatible(
        "mistral",
        "Mistral",
        "https://api.mistral.ai/v1",
        "https://console.mistral.ai/api-keys/",
    ),
    _openai_compatible(
        "xai",
        "Grok (xAI)",
        "https://api.x.ai/v1",
        "https://console.x.ai/",
    ),
    _openai_compatible(
        "together",
        "Together AI",
        "https://api.together.xyz/v1",
        "https://api.together.xyz/settings/api-keys",
    ),
    ProviderEntry(
        id="qwen",
        display_name="Qwen (Alibaba Model Studio)",
        kind=ProviderKind.CLOUD_API,
        # The international root. There is a separate mainland-China one, and
        # which applies depends on where the account was opened — which this
        # file cannot know, which is the whole reason it is not offered.
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        chat_endpoint=(
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
        ),
        compatibility=Compatibility.UNVERIFIED,
        auth=AuthStyle.BEARER,
        key_url="https://www.alibabacloud.com/help/en/model-studio/",
        support=Support.UNAVAILABLE,
        note=(
            "Documented as compatible with the format Zaram speaks, but the "
            "address differs by region and has not been confirmed here. Paste "
            "the base URL from your own console to use it anyway."
        ),
    ),
    ProviderEntry(
        id="moonshot",
        display_name="Kimi (Moonshot AI)",
        kind=ProviderKind.CLOUD_API,
        base_url="https://api.moonshot.ai/v1",
        chat_endpoint="https://api.moonshot.ai/v1/chat/completions",
        compatibility=Compatibility.UNVERIFIED,
        auth=AuthStyle.BEARER,
        key_url="https://platform.moonshot.ai/",
        support=Support.UNAVAILABLE,
        note=(
            "Documented as compatible with the format Zaram speaks, but Moonshot "
            "publishes separate international and mainland-China addresses and "
            "neither has been confirmed here. Paste the base URL from your own "
            "console to use it anyway."
        ),
    ),
    ProviderEntry(
        id="lm_studio",
        display_name="LM Studio (on this machine)",
        kind=ProviderKind.LOCAL_AI_SERVER,
        # Deliberately without `/v1`, matching what LM Studio shows in its own
        # server panel — and it exercises the other half of the engine's
        # normalisation, which is worth having in the manifest rather than only
        # in a test fixture.
        base_url="http://127.0.0.1:1234",
        chat_endpoint="http://127.0.0.1:1234/v1/chat/completions",
        compatibility=Compatibility.OPENAI,
        auth=AuthStyle.NONE,
        key_url="https://lmstudio.ai/",
        support=Support.AVAILABLE,
        note=(
            "Runs on your own machine. Nothing you type leaves the device, and "
            "Zaram finds it on its own when the LM Studio server is running — no "
            "key and no setup."
        ),
    ),
)


def list_providers(*, available_only: bool = False) -> Tuple[ProviderEntry, ...]:
    """The catalogue, in manifest order.

    ``available_only`` exists for callers that are about to *act* — a routing
    fallback, say. It is the wrong argument for a picker: the whole point of
    the grading is that the unavailable ones are seen, greyed out, with their
    reason.

    Reads no files, opens no sockets, and returns the same tuple every time.
    """
    if available_only:
        return tuple(entry for entry in PROVIDERS if entry.available)
    return PROVIDERS


def get(provider_id: str) -> Optional[ProviderEntry]:
    """One entry by id, or ``None`` when the catalogue has never heard of it.

    ``None`` rather than a raise, and rather than a synthesised placeholder: an
    id that is not in the manifest is the ordinary case for a user who
    configured an endpoint by hand, and that must keep working. See the module
    docstring — this is a convenience, not a gate.
    """
    for entry in PROVIDERS:
        if entry.id == provider_id:
            return entry
    return None


def to_payload() -> Dict[str, Any]:
    """The whole catalogue as plain data, with its date attached.

    The date travels with the list rather than being available from a separate
    call, because a surface that renders the providers and forgets the date is
    the exact failure the date exists to prevent.
    """
    return {
        "generated": GENERATED,
        "providers": [entry.to_dict() for entry in PROVIDERS],
    }
