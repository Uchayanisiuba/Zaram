"""Pictures drawn somewhere else, with the user's own key.

Three providers behind the one seam ``contracts.ImageProvider`` already draws
around :mod:`local_flux`, built 14 September 2026 because a machine with no
card for Flux still has a person on it who wants a picture:

* **NVIDIA NIM** — free tier, the key most users already pasted for text.
  Flux is hosted on it.
* **Together AI** — a standing free Flux schnell endpoint beside its paid
  models; a second route for someone without an NVIDIA account.
* **fal.ai** — paid, cents per image, no training on API data; the rung for
  "it must work every time".

What every one of them shares, and what this module is really about:

**The key is the connection the user already made.** Nothing here asks for a
second credential. ``providers.cloud_config`` holds what was pasted in
Settings, and a provider is *available* exactly when its key is there —
rule 1, the user brings the key; Zaram never holds an account on their
behalf.

**An image is its own consent.** Connecting a provider for text grants
``DataClass.PROMPT`` to its host and nothing else (rule 7j). A picture is
megabytes and far more personal, so the first one is a separate decision:
``availability()`` asks the policy about ``DataClass.IMAGE`` and, when the
class has no grant, says so *before* anything is sent — with the fix named —
rather than failing in the middle of a request. Once granted it is
remembered, like every other rule.

**Every byte goes through the gate.** The request is sent with
``EgressGate.request(..., data_class=DataClass.IMAGE)``, which checks, logs
the prompt as what left, and only then sends. There is no second HTTP path.

**Nothing is estimated.** A cloud endpoint reports no denoising steps, so the
progress callback is never called and the card shows an indeterminate wait —
the contract's own words for this case. The seed is the one the provider
reports, or the one we sent; a provider that reports none gets the one we
chose, so the picture can still be asked for again.

**Shapes are read defensively, never assumed.** The three providers return
three different JSON shapes and any of them may change; each parser looks
for the fields it knows and refuses with the provider's name when none are
there, so a changed API is a sentence in the notice rather than a stack
trace.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from .contracts import (
    AVAILABLE,
    Availability,
    GeneratedImage,
    ImageProgress,
    ImageRequest,
)

logger = logging.getLogger(__name__)

#: How long to wait for a picture. Free tiers queue; a minute is not unusual.
TIMEOUT_SECONDS = 180.0

#: What the log names as the sender.
SOURCE = "images"


def _connection(provider_id: str):
    """The stored connection for a catalogue id, or ``None``."""
    from providers import cloud_config

    return cloud_config.connections().get(provider_id)


def _image_grant(host: str) -> Availability:
    """Whether a picture may go to ``host`` right now, and if not, why.

    Asked of the policy, not guessed: the same ``decide`` the gate will run.
    ``ASK`` is fine — the gate will confirm at send time — and ``ALLOW`` is
    fine; only ``DENY`` is reported here, with the policy's own reason, which
    already says whether the host was blocked or the image class simply has
    not been decided.
    """
    try:
        from core.egress import DataClass, Mode, get_gate

        decision = get_gate().policy.decide(host, DataClass.IMAGE)
    except Exception:  # noqa: BLE001 - no gate means no cloud, and that is said
        return Availability(
            ok=False,
            reason="Zaram's egress gate is not running, so nothing can be sent.",
        )
    if decision.mode is Mode.DENY:
        return Availability(
            ok=False,
            reason=f"Pictures may not go to {host} yet: {decision.reason}.",
            remedy=f"Allow images to {host} under Activity → Destinations, and ask again.",
        )
    return AVAILABLE


def _send_json(url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Any:
    """POST through the gate as an image, and parse the JSON that comes back."""
    from core.egress import DataClass, get_gate

    raw = get_gate().request(
        url,
        method="POST",
        body=json.dumps(body),
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        timeout=TIMEOUT_SECONDS,
        source=SOURCE,
        data_class=DataClass.IMAGE,
    )
    return json.loads(raw.decode("utf-8"))


def _png_from_data_uri_or_b64(value: str) -> bytes:
    """A base64 body, with or without a ``data:`` prefix."""
    if value.startswith("data:"):
        value = value.split(",", 1)[1]
    return base64.b64decode(value)


def _image(png: bytes, seed: int) -> GeneratedImage:
    """A picture with its size read off its own header, never off the request.

    The record says how big the image *is*; a provider that rounded the size
    would otherwise be recorded at the size that was asked for.
    """
    width = height = 0
    if png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) >= 24:
        width = int.from_bytes(png[16:20], "big")
        height = int.from_bytes(png[20:24], "big")
    return GeneratedImage(png=png, width=width, height=height, seed=seed)


class CloudImageProvider:
    """What the three share. Subclasses say where and in what shape."""

    #: Catalogue id whose stored key this provider uses.
    provider_id: str = ""
    name: str = ""
    #: Where the picture request goes. The host is what the policy is asked about.
    endpoint: str = ""
    #: What Settings should say when the key is missing.
    key_hint: str = ""

    @property
    def host(self) -> str:
        return (urlparse(self.endpoint).hostname or "").lower()

    def availability(self) -> Availability:
        conn = _connection(self.provider_id)
        if conn is None or not conn.api_key:
            return Availability(
                ok=False,
                reason=f"No {self.name} key is connected.",
                remedy=self.key_hint,
            )
        return _image_grant(self.host)

    def describe(self) -> str:
        return f"{self.name} · cloud · {self.host}"

    # ----------------------------------------------------------- the request

    def _headers(self, api_key: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def _body(self, request: ImageRequest, seed: int) -> Dict[str, Any]:
        raise NotImplementedError

    def _parse(self, payload: Any, seed: int) -> List[GeneratedImage]:
        raise NotImplementedError

    def generate(
        self,
        request: ImageRequest,
        on_progress: Optional[Callable[[ImageProgress], None]] = None,
    ) -> List[GeneratedImage]:
        conn = _connection(self.provider_id)
        if conn is None or not conn.api_key:
            raise RuntimeError(f"no {self.name} key is connected")
        # A seed is chosen here when the caller left it open, so the picture
        # is reproducible even from a provider that reports none back.
        seed = request.seed if request.seed is not None else secrets.randbelow(2**31)
        out: List[GeneratedImage] = []
        # One request per image rather than a batch: the three providers
        # disagree about batching and a loop is the same on all of them.
        for i in range(request.count):
            payload = _send_json(self.endpoint, self._body(request, seed + i), self._headers(conn.api_key))
            images = self._parse(payload, seed + i)
            if not images:
                raise RuntimeError(f"{self.name} answered without a picture")
            out.extend(images)
        return out[: request.count]


class NimImages(CloudImageProvider):
    """Flux schnell on NVIDIA's free tier, with the key already in Settings."""

    provider_id = "nvidia_nim"
    name = "flux-schnell · NVIDIA NIM"
    endpoint = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell"
    key_hint = "Add your NVIDIA key under Settings → Providers; the same key draws pictures."

    def _body(self, request: ImageRequest, seed: int) -> Dict[str, Any]:
        return {
            "prompt": request.prompt,
            "width": request.width,
            "height": request.height,
            "seed": seed,
            "steps": request.steps,
        }

    def _parse(self, payload: Any, seed: int) -> List[GeneratedImage]:
        # NIM has answered in two shapes across its image models: a bare
        # `{"image": <b64>}` and Stability's `{"artifacts": [{"base64", "seed"}]}`.
        items: List[Dict[str, Any]] = []
        if isinstance(payload, dict) and isinstance(payload.get("artifacts"), list):
            items = [a for a in payload["artifacts"] if isinstance(a, dict) and a.get("base64")]
        elif isinstance(payload, dict) and payload.get("image"):
            items = [{"base64": payload["image"], "seed": payload.get("seed")}]
        return [_image(_png_from_data_uri_or_b64(a["base64"]), int(a.get("seed") or seed)) for a in items]


class TogetherImages(CloudImageProvider):
    """Together's standing free Flux schnell endpoint. OpenAI-shaped."""

    provider_id = "together"
    name = "flux-schnell · Together"
    endpoint = "https://api.together.xyz/v1/images/generations"
    key_hint = "Add a Together key under Settings → Providers; FLUX.1 schnell is free there."
    model = "black-forest-labs/FLUX.1-schnell-Free"

    def _body(self, request: ImageRequest, seed: int) -> Dict[str, Any]:
        return {
            "model": self.model,
            "prompt": request.prompt,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "n": 1,
            "seed": seed,
            "response_format": "b64_json",
        }

    def _parse(self, payload: Any, seed: int) -> List[GeneratedImage]:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        return [
            _image(_png_from_data_uri_or_b64(d["b64_json"]), seed)
            for d in data
            if isinstance(d, dict) and d.get("b64_json")
        ]


class FalImages(CloudImageProvider):
    """fal.ai — paid, per image, no training on API data. The reliable rung."""

    provider_id = "fal"
    name = "flux-schnell · fal.ai"
    endpoint = "https://fal.run/fal-ai/flux/schnell"
    key_hint = "Add a fal.ai key under Settings → Providers. Paid per image; nothing is trained on."

    def _headers(self, api_key: str) -> Dict[str, str]:
        return {"Authorization": f"Key {api_key}"}

    def _body(self, request: ImageRequest, seed: int) -> Dict[str, Any]:
        return {
            "prompt": request.prompt,
            "image_size": {"width": request.width, "height": request.height},
            "num_inference_steps": request.steps,
            "num_images": 1,
            "seed": seed,
            # Data URIs in the answer, so the picture arrives in this one
            # gated request rather than through a second fetch the log would
            # have to explain.
            "sync_mode": True,
        }

    def _parse(self, payload: Any, seed: int) -> List[GeneratedImage]:
        images = payload.get("images") if isinstance(payload, dict) else None
        if not isinstance(images, list):
            return []
        out: List[GeneratedImage] = []
        for im in images:
            url = im.get("url") if isinstance(im, dict) else None
            if isinstance(url, str) and url.startswith("data:"):
                out.append(_image(_png_from_data_uri_or_b64(url), int(payload.get("seed") or seed)))
        return out


#: Every cloud provider, in the order they are tried after local.
CLOUD_PROVIDERS: List[CloudImageProvider] = [NimImages(), TogetherImages(), FalImages()]


class RoutedImageProvider:
    """Local first; then whichever cloud provider has a key and a grant.

    The routing claim CLAUDE.md makes for text, made for pictures: *local is
    the fallback for everything, and the fallback is exercised.* If Flux is on
    this machine it draws, every time, and no key changes that. Only when it
    cannot — no card, no weights — does a cloud provider the user connected
    take the request, and only one the user has allowed pictures to.

    Attributes the runtime reads off a provider (`vram_needed_bytes`, `loaded`,
    `unload`) are delegated to the *local* one only, because a cloud provider
    holds no card and must not be preflighted as if it did.
    """

    def __init__(self, local: Any, cloud: Optional[List[CloudImageProvider]] = None) -> None:
        self._local = local
        self._cloud = list(CLOUD_PROVIDERS if cloud is None else cloud)

    # The provider that will draw the next picture, decided fresh each time —
    # a key can be added between two requests.
    def _pick(self) -> Any:
        if self._local is not None and self._local.availability().ok:
            return self._local
        for provider in self._cloud:
            if provider.availability().ok:
                return provider
        return None

    @property
    def name(self) -> str:
        chosen = self._pick()
        return chosen.name if chosen is not None else getattr(self._local, "name", "images")

    def describe(self) -> str:
        chosen = self._pick()
        if chosen is None:
            return "nothing can draw"
        describe = getattr(chosen, "describe", None)
        return describe() if callable(describe) else chosen.name

    def availability(self) -> Availability:
        if self._pick() is not None:
            return AVAILABLE
        # Nothing can draw. Say what local needs and what cloud needs, each
        # with its cost, so the person can choose between installing weights
        # and pasting a key — and, for a connected provider, that a picture
        # is a separate permission from a prompt.
        reasons: List[str] = []
        remedies: List[str] = []
        if self._local is not None:
            local = self._local.availability()
            reasons.append(local.reason)
            if local.remedy:
                remedies.append(local.remedy)
        for provider in self._cloud:
            a = provider.availability()
            if _connection(provider.provider_id) is not None:
                # A key exists; the obstacle is the grant, and that is the
                # more useful sentence.
                reasons.append(a.reason)
                if a.remedy:
                    remedies.append(a.remedy)
        if not remedies:
            remedies.append(
                "Add a key for NVIDIA NIM or Together (free) or fal.ai (paid) under "
                "Settings → Providers, then allow images to it under Activity → Destinations."
            )
        return Availability(ok=False, reason=" ".join(r for r in reasons if r), remedy=" ".join(remedies))

    @property
    def vram_needed_bytes(self) -> Optional[int]:
        chosen = self._pick()
        if chosen is not self._local:
            return None
        return getattr(self._local, "vram_needed_bytes", None)

    @property
    def loaded(self) -> bool:
        return bool(getattr(self._local, "loaded", False))

    def unload(self) -> None:
        unload = getattr(self._local, "unload", None)
        if callable(unload):
            unload()

    def generate(
        self,
        request: ImageRequest,
        on_progress: Optional[Callable[[ImageProgress], None]] = None,
    ) -> List[GeneratedImage]:
        chosen = self._pick()
        if chosen is None:
            raise RuntimeError("nothing can draw")
        return chosen.generate(request, on_progress)
