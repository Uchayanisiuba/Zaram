"""OpenRouter — a router, so the data policy is per model, not per provider.

This exists mostly to refuse a mistake that is easy to make and hard to notice.
An audit of this repo proposed registering OpenRouter with
``data_policy=YOUR_KEY_NO_TRAINING``, which would have made every model it
returns ``selectable_by_default`` — including the ``:free`` variants, which are
free precisely because prompts are logged and may be trained on.

OpenRouter is not a provider. It is a router in front of dozens of them, and the
terms that apply to a prompt are the *downstream* provider's terms for the
*specific* model, mediated by account settings this API does not expose. There
is no single answer to "what happens to a prompt sent to OpenRouter", so the
provider-level policy is ``None`` — the absence of an answer, which
``selectable_by_default`` already treats as "do not route here on our own
initiative".

The asymmetry that makes this honest
------------------------------------
**We can sometimes prove a model logs. We can never prove one does not.**

A ``:free`` model is documented as the logged tier, so that is stated —
``LOGGED_AND_TRAINED_ON``, which excludes it from default routing and shows the
user the label if they pick it deliberately.

Everything else is ``None``. Not because it certainly logs, but because we have
no evidence either way, and a guess in the reassuring direction is a privacy
claim the user will act on. Rule: unknown is ``None``, never a guarantee.

This is the same shape as VRAM detection returning ``None`` rather than 0 — a
caller can check for ``None``; a confident wrong value is the worse failure.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..contracts import DataPolicy, ModelCategory, ModelInfo, ProviderKind
from .openai_compat import OpenAICompatibleAdapter

OPENROUTER_BASE_URL = "https://openrouter.ai/api"

#: OpenRouter's own marker for the logged tier. It is part of the model id, so
#: it survives without a second lookup.
_FREE_TIER_SUFFIX = ":free"


class OpenRouterAdapter(OpenAICompatibleAdapter):
    """Discovers OpenRouter models, and refuses to vouch for their terms.

    Registered only when a key is present. Without one, this would discover a
    catalogue of models that cannot be called — a list of things Zaram appears
    to offer and does not.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = OPENROUTER_BASE_URL,
    ) -> None:
        super().__init__(
            provider_id="openrouter",
            base_url=base_url,
            kind=ProviderKind.CLOUD_API,
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            # Explicitly None rather than omitted. The base class would infer
            # None for a non-loopback host anyway, but leaving it implicit
            # invites someone to "fill in the gap" later with a sensible-looking
            # guess. This is the gap being deliberate.
            data_policy=None,
        )

    def _to_model(self, model_id: str, entry: Dict[str, Any]) -> ModelInfo:
        model = super()._to_model(model_id, entry)
        _apply_modality(model, entry)

        if _is_free_tier(model_id, entry):
            # The one case we can state. Free is not a good enough reason to
            # route here on the user's behalf, and the label is what makes a
            # deliberate choice an informed one.
            model.data_policy = DataPolicy.LOGGED_AND_TRAINED_ON
            model.metadata["policy_source"] = (
                "OpenRouter free tier — prompts are logged and may be trained on"
            )
        else:
            model.metadata["policy_source"] = (
                "unknown — OpenRouter routes to downstream providers whose terms "
                "this API does not report. Set it per model once established."
            )

        return model



def _modalities(entry: Dict[str, Any], key: str) -> list[str]:
    """One side of `architecture`, lowercased, or an empty list.

    Empty means *not reported*, and every caller below treats it as "we do not
    know" rather than "text only". The base adapter's comment is right that
    OpenAI's `/v1/models` carries no metadata; OpenRouter's does, and an older
    or partial response must fall back to the base behaviour instead of
    inventing an answer from a missing field.
    """
    architecture = entry.get("architecture")
    if not isinstance(architecture, dict):
        return []
    values = architecture.get(key)
    if not isinstance(values, list):
        return []
    return [str(v).lower() for v in values if isinstance(v, (str, int, float))]


def _apply_modality(model: ModelInfo, entry: Dict[str, Any]) -> None:
    """What this model can accept and what it can emit.

    **It arrives in the response the pricing is already read from and was
    thrown away.** `OpenAICompatibleAdapter._to_model` hardcodes
    `ModelCategory.LLM` and never sets `supports_vision`, and its comment
    justifies that correctly for plain OpenAI — *"/v1/models exposes only an id
    + ownership; deeper metadata is not part of the spec"*. That reasoning does
    not carry here. OpenRouter returns `architecture` with `input_modalities`
    and `output_modalities`, in the same object `_is_free_tier` already opens.

    The consequence of discarding it was a refusal built on missing data. A
    user with a connected OpenRouter account and a dozen vision-capable models
    attaches a screenshot and is told *"No model on this machine can read
    images"* — which fails closed rather than open, and is the right refusal
    for the wrong reason. `select_model_for_task(requires_vision=True)` is the
    gate and it was reading a flag nothing ever set.

    **Input and output are two different questions and are answered
    separately.** `CLAUDE.md` is explicit that "can see" and "can draw" being
    one number is how a text model comes to be asked to draw. The deleted
    `orchestrator/capabilities.py` scored `ModelCategory.VISION`, `IMAGE` and
    `VIDEO` all as `Capability.VISION: 1.0` — one number for three questions,
    which is the whole error in four lines. So:

    - accepting images sets ``supports_vision``, and the model stays an
      ``LLM``, because a chat model that can also see is still a chat model.
      This is the same shape Ollama discovery already produces from
      ``/api/show``, which is what keeps one flag meaning one thing across
      providers.
    - emitting images **and not text** makes it a `ModelCategory.IMAGE`. That
      is not decoration: `select_model_for_task` filters by category, so
      without it a model that can only draw is a candidate for answering a
      question, and it would answer by not answering. A model that emits both
      is left an `LLM`, because it can still hold the conversation.

    Nothing here routes an image *request* anywhere. That needs a way to say
    "this reply should be a picture", which does not exist, and building the
    gate before the request would be scoring a decision nobody can make yet.
    The modalities are recorded on the model so the fact is not thrown away a
    second time.
    """
    accepts = _modalities(entry, "input_modalities")
    emits = _modalities(entry, "output_modalities")
    if not accepts and not emits:
        return

    if accepts:
        model.metadata["input_modalities"] = accepts
        if "image" in accepts:
            model.supports_vision = True
            model.capabilities.add("vision")

    if emits:
        model.metadata["output_modalities"] = emits
        if "image" in emits and "text" not in emits:
            model.category = ModelCategory.IMAGE


def _is_free_tier(model_id: str, entry: Dict[str, Any]) -> bool:
    """Whether this is the logged tier.

    Checked two ways because the id suffix is a convention rather than a
    contract, and pricing is the thing the suffix is a shorthand *for*. Either
    signal alone would miss a rename; requiring both would miss a model priced
    at zero without the suffix.
    """
    if model_id.lower().endswith(_FREE_TIER_SUFFIX):
        return True

    pricing = entry.get("pricing")
    if isinstance(pricing, dict):
        try:
            values = [float(pricing.get(k, 0) or 0) for k in ("prompt", "completion")]
        except (TypeError, ValueError):
            return False
        # All-zero pricing is the free tier. A model that is genuinely free and
        # *not* logged would be mislabelled here, which costs the user a
        # deliberate click — the opposite error costs them their data.
        return bool(values) and all(v == 0.0 for v in values)

    return False
