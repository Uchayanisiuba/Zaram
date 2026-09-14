"""One key, the right model for each job — offered, never assumed.

A provider like NVIDIA NIM, OpenRouter or Groq puts dozens of models behind
one key and one endpoint, and the person who pasted the key is not going to
read the list. Per-task assignment already exists — `default_model` for
chat, `TaskSlot.CODE` for coding chains, `TaskSlot.VISION` for pictures —
so what was missing was the *offer*: after a key is connected, one tap that
fills those slots from a dated recommendation.

Three things make it safe rather than presumptuous.

**It is an offer, not a default.** Every free tier here is
``LOGGED_AND_TRAINED_ON``, and `selectable_by_default` refuses to route
there on Zaram's own initiative. Nothing in this module runs unless the
person presses the button; what it writes is exactly what the picker under
Advanced would have written by hand.

**Only models the key can actually see are ever assigned.** The manifest
lists candidates in order of preference; `recommend` walks them against
what discovery returned for that provider and takes the first that exists.
A renamed or withdrawn model is skipped, and a slot with no surviving
candidate is left alone — an assignment to a model that is not there would
be worse than none, because the router would try it and fail on every
message of that kind.

**It is dated, per provider, and scales by adding an entry.** The same
four slots for every provider; OpenRouter and Groq are entries, not code.
Candidate names are what the provider published on the date written here,
and the date travels to the interface so a stale list is visible as stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

#: When the candidate lists below were last read off the providers' catalogues.
GENERATED = "2026-09-14"


@dataclass(frozen=True)
class Pick:
    """One recommended model and the one-line reason it is recommended."""

    model: str
    why: str


@dataclass(frozen=True)
class Pairing:
    """Candidates per slot, in order of preference, for one provider."""

    provider_id: str
    #: The chat model — `default_model`, the answer for a request with no task.
    chat: Tuple[Pick, ...]
    #: `TaskSlot.CODE`.
    code: Tuple[Pick, ...]
    #: `TaskSlot.VISION`.
    vision: Tuple[Pick, ...]
    #: `TaskSlot.DOCUMENT` — the strongest writer with a long window, since a
    #: proposal is the one job worth waiting for the best model on.
    document: Tuple[Pick, ...] = ()


PAIRINGS: Dict[str, Pairing] = {
    "nvidia_nim": Pairing(
        provider_id="nvidia_nim",
        chat=(
            Pick("nvidia/nemotron-3.5-lightning-30b-a3b", "fast — a small set of experts answers each token"),
            Pick("nvidia/llama-3.3-nemotron-super-49b-v1.5", "NVIDIA's tuned Llama; quick and steady"),
            Pick("meta/llama-3.3-70b-instruct", "a strong general model"),
        ),
        code=(
            Pick("qwen/qwen3-coder-480b-a35b-instruct", "trained for multi-step tool use; finishes long chains"),
            Pick("moonshotai/kimi-k2-instruct", "agentic and long-context; slower on the free tier"),
            Pick("deepseek-ai/deepseek-v3.1", "strong single-turn code"),
            Pick("qwen/qwen2.5-coder-32b-instruct", "a solid coder at a fraction of the size"),
        ),
        vision=(
            Pick("meta/llama-3.2-90b-vision-instruct", "reads screenshots and documents well"),
            Pick("nvidia/llama-3.1-nemotron-nano-vl-8b-v1", "small and quick for receipts and screens"),
            Pick("meta/llama-3.2-11b-vision-instruct", "a lighter reader"),
        ),
        document=(
            Pick("moonshotai/kimi-k2-instruct", "writes long, structured documents well; holds the whole conversation"),
            Pick("deepseek-ai/deepseek-v3.1", "a strong writer with a long window"),
            Pick("meta/llama-3.3-70b-instruct", "a strong general writer"),
        ),
    ),
    "openrouter": Pairing(
        provider_id="openrouter",
        chat=(
            Pick("meta-llama/llama-3.3-70b-instruct:free", "a strong general model on the free route"),
            Pick("google/gemma-3-27b-it:free", "quick and capable"),
            Pick("qwen/qwen3-30b-a3b:free", "fast — few experts per token"),
        ),
        code=(
            Pick("qwen/qwen3-coder:free", "trained for multi-step tool use"),
            Pick("moonshotai/kimi-k2:free", "agentic and long-context"),
            Pick("deepseek/deepseek-chat-v3-0324:free", "strong single-turn code"),
        ),
        vision=(
            Pick("qwen/qwen2.5-vl-72b-instruct:free", "reads screenshots and documents well"),
            Pick("google/gemma-3-27b-it:free", "sees images; quick"),
            Pick("meta-llama/llama-3.2-11b-vision-instruct:free", "a lighter reader"),
        ),
        document=(
            Pick("moonshotai/kimi-k2:free", "writes long, structured documents well"),
            Pick("deepseek/deepseek-chat-v3-0324:free", "a strong writer with a long window"),
            Pick("meta-llama/llama-3.3-70b-instruct:free", "a strong general writer"),
        ),
    ),
    "groq": Pairing(
        provider_id="groq",
        chat=(
            Pick("llama-3.3-70b-versatile", "the fastest strong general model anywhere"),
            Pick("llama-3.1-8b-instant", "instant; fine for short answers"),
        ),
        code=(
            Pick("moonshotai/kimi-k2-instruct", "agentic and long-context, at Groq's speed"),
            Pick("qwen/qwen3-32b", "a capable coder"),
            Pick("llama-3.3-70b-versatile", "a strong general model"),
        ),
        vision=(
            Pick("meta-llama/llama-4-scout-17b-16e-instruct", "sees images; fast"),
            Pick("meta-llama/llama-4-maverick-17b-128e-instruct", "sees images; larger"),
        ),
        document=(
            Pick("moonshotai/kimi-k2-instruct", "writes long, structured documents well"),
            Pick("llama-3.3-70b-versatile", "a strong general writer"),
        ),
    ),
}

#: The slots, in the order the interface shows them.
SLOTS: Tuple[str, ...] = ("chat", "code", "vision", "document")


def _seen(model: str, seen: Iterable[str]) -> Optional[str]:
    """The discovered id that names this candidate, or ``None``.

    Adapters may prefix an id with the provider (``nvidia_nim/meta/...``) or
    hand it through as published; either is the same model. Matched exactly
    first, then by suffix after a slash, never by substring — ``llama-3.3-70b``
    must not match ``llama-3.3-70b-vision``.
    """
    for candidate in seen:
        if candidate == model or candidate.endswith("/" + model):
            return candidate
    return None


def recommend(provider_id: str, seen_models: Iterable[str]) -> Dict[str, Dict[str, str]]:
    """What would be assigned, slot by slot, from what the key can see.

    Returns only slots with a surviving candidate. An empty dict means the
    provider is not paired here or none of its listed models were found —
    both are "nothing to offer", and the interface shows no card.
    """
    pairing = PAIRINGS.get(provider_id)
    if pairing is None:
        return {}
    seen = list(seen_models)
    out: Dict[str, Dict[str, str]] = {}
    for slot in SLOTS:
        for pick in getattr(pairing, slot):
            found = _seen(pick.model, seen)
            if found is not None:
                out[slot] = {"model": found, "why": pick.why}
                break
    return out


def apply(settings, picks: Dict[str, Dict[str, str]]) -> Dict[str, Optional[str]]:
    """Write the picks into the same fields the Advanced picker writes.

    Chat is `default_model`; the others are task slots. Slots not in
    ``picks`` are left exactly as they were — an offer fills gaps and
    overrides what it names, and touches nothing else.
    """
    from core.user_settings import TaskSlot

    if "chat" in picks:
        settings.set_default_model(picks["chat"]["model"])
    if "code" in picks:
        settings.set_task_model(TaskSlot.CODE, picks["code"]["model"])
    if "vision" in picks:
        settings.set_task_model(TaskSlot.VISION, picks["vision"]["model"])
    if "document" in picks:
        settings.set_task_model(TaskSlot.DOCUMENT, picks["document"]["model"])
    return {
        "chat": settings.default_model,
        **{slot.value: model for slot, model in ((s, settings.task_models.get(s.value)) for s in TaskSlot)},
    }


def paired_providers() -> List[str]:
    return list(PAIRINGS)
