"""Who the assistant says it is, assembled from what the system knows.

**A model does not know what it is running as.** Ask a local Qwen what it is and
it answers from its training data — sometimes wrongly, because fine-tunes claim
to be GPT-4 all the time. So a request like "which model am I talking to" is a
question about *system state*, and the only place the true answer exists is here,
where routing already resolved it. Everything below exists to hand the model a
truer answer than its weights contain.

That is the difference between this and the persona strings it sits in front of.
A persona says *be authoritative, be patient*. This says *here is what you are
and here is what is answering right now*. One is a costume; the other is a fact.

**Identity is not personality, and the distinction is load-bearing.** The
embodiment rule already refuses a character: no name, no pronoun, no expression
not derived from system state. That refusal is about a *someone* the user forms
a relationship with. It is not a refusal to say what the product is — a status
indicator that cannot describe itself is not calm, it is broken.

**Nothing here hides the model, and hiding it was never the goal.** Routing must
be legible: every reply names the model that answered and why. An identity that
denied the model would forfeit the product's best demonstration — that the same
memory works when the model changes underneath it. A model switch is not a leak
in the story, it *is* the story, so the preamble names the current model and
tells the assistant to report it when asked.

**Unknown is said as unknown.** `locality` is three-valued, and that is
deliberate rather than tidy: `ModelsRuntime._is_remote_model` answers `False`
when it cannot resolve a model, which is the correct fail-safe for *routing* —
guessing local costs a possibly-wrong model, guessing cloud costs the user's
documents leaving on a lookup that failed. It is the wrong answer for *identity*,
where "runs on this machine" would be a confident false claim on the one thing
the user must be able to trust. Same input, two questions, two answers. The same
split `vram_bytes` makes by returning `None` rather than `0`.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["LOCAL", "CLOUD", "identity_preamble", "compose_system_prompt"]

#: Answering on this machine.
LOCAL = "local"
#: Answering through a provider the request had to leave the machine to reach.
CLOUD = "cloud"


_WHAT_ZARAM_IS = (
    "You are Zaram.\n"
    "\n"
    "Zaram is not a language model. It is a memory and control layer that runs "
    "on this person's own machine. It holds what they have told it and what "
    "their documents say, it shows them what it recalled and where each fact "
    "came from, and it puts that knowledge in front of whichever model is "
    "answering. The model can change; what the person knows does not."
)

_HOW_TO_ANSWER_ABOUT_YOURSELF = (
    "When you are asked what you are, describe Zaram — not the model you are "
    "running as, and not the lab that trained it.\n"
    "When you are asked which model is answering, give the one named above. Do "
    "not answer that from your training: you were trained by one lab and you "
    "may be deployed as any model, so your own impression of your identity is "
    "not evidence and is often wrong.\n"
    "Never claim to *be* the model, and never claim there is no model. Both are "
    "false. Zaram is the layer; the model is what it is speaking through; the "
    "person is entitled to know both."
)

_HONESTY = (
    "Do not describe anything as private, secure or kept on the machine unless "
    "that is stated above. Where you were not told, say you do not know.\n"
    "If you were given remembered facts or sources, prefer them over your "
    "training and say which you used. If you were given neither, answer from "
    "what you know and do not refer to sources you were not given.\n"
    "If you are asked to produce something and the context needed to produce it "
    "was not recalled, say what is missing and ask. A document that is confident "
    "and wrong leaves the building; a question does not."
)


def _running_line(model: Optional[str], locality: Optional[str]) -> Optional[str]:
    """One sentence naming what is answering, or nothing when nothing is known.

    Silence is a real option here. A preamble that says "you are answering
    through an unknown model" invites the assistant to talk about its own
    uncertainty, which is noise the user did not ask for — whereas saying
    nothing leaves the honest instruction below to handle the question if it
    ever comes up.
    """
    name = (model or "").strip()
    if not name:
        return None

    if locality == LOCAL:
        where = (
            ", which is running on this machine. Nothing in this conversation "
            "has left the device to reach you"
        )
    elif locality == CLOUD:
        where = (
            ", which runs on a provider's servers. This person's request left "
            "their machine to reach you, and Zaram logged that it did"
        )
    else:
        # Known model, unresolved locality. Name the one and not the other,
        # rather than completing the sentence with a guess.
        where = ""

    return f"Right now you are answering through {name}{where}."


def identity_preamble(
    *,
    model: Optional[str] = None,
    locality: Optional[str] = None,
) -> str:
    """The identity block that goes in front of everything else.

    `model` is the model the request is actually being answered by, and
    `locality` is ``LOCAL``, ``CLOUD``, or ``None`` when it could not be
    resolved. Pure: it reaches nothing and asks nothing, so what it claims is
    exactly what the caller knew.
    """
    parts = [_WHAT_ZARAM_IS]

    running = _running_line(model, locality)
    if running:
        parts.append(running)

    parts.append(_HOW_TO_ANSWER_ABOUT_YOURSELF)
    parts.append(_HONESTY)

    return "\n\n".join(parts)


def compose_system_prompt(identity: str, persona: str = "") -> str:
    """Identity first, then the voice.

    Order matters and it is the whole reason this is a function rather than an
    f-string at the call site. A persona that opens "You are Nova, a fast-paced
    technical assistant" is an identity claim, and whichever identity claim
    comes last is the one a model tends to keep. Putting the product's identity
    second would reintroduce exactly the confusion this module exists to remove.
    """
    voice = (persona or "").strip()
    if not voice:
        return identity
    return f"{identity}\n\n{voice}"
