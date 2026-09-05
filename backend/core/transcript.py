"""One canonical transcript, projected into whatever a provider speaks.

**The rule this module exists to enforce:** the transcript is canonical and a
provider's format is a projection of it. Never the other way round. The moment
a transcript is stored in the shape one vendor's API wanted, it belongs to that
vendor, and switching model stops being free — which is the whole product.

Same discipline as *"HTML is the source of truth for every generated
document"*: one form, N conversions, and the conversions are where the
per-vendor mess is allowed to live.

Two providers, two genuinely different shapes:

- Ollama's ``/api/generate`` takes a single ``prompt`` string. History has to be
  flattened into it, which means the roles become text and the model reads them
  as convention rather than as structure.
- An OpenAI-compatible ``/v1/chat/completions`` takes a list of role-tagged
  messages, where the structure is real.

Fitting is the other half, and it is not the same question as projecting. A
local model is loaded with 4,096 tokens and Claude has 200,000, so *the same
transcript* has to arrive whole at one and trimmed at the other. That trimming
happens here, against the target's real budget, and it **drops whole turns**.

Why whole turns and never a partial one
---------------------------------------
Half a message attributed to a person is a fabrication. A transcript that says
the user asked *"what is the rate for"* is worse than one that does not mention
the exchange at all, because the model will answer the truncated question. Rule
9's failure, arriving through the context window instead of through recall.

Why dropping and not summarising
--------------------------------
Everybody else compacts aggressively because the transcript is their only
memory. Zaram has a second store: facts from an old turn are in the Spine, with
provenance, and recall brings them back when they are relevant. So the default
here is to **evict**, which is deterministic, rather than to summarise, which is
a generation — and rule 9 exists because generations invent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Literal, Sequence

from core.context_budget import estimate_tokens

Role = Literal["user", "assistant"]

USER: Role = "user"
ASSISTANT: Role = "assistant"

#: What a flattened transcript labels each side as.
#:
#: Text, because a completion endpoint has nowhere structural to put a role.
#: Deliberately not the assistant's *name*: the user may have called it Ada, and
#: a transcript that says "Ada:" teaches the model that the name is part of the
#: format rather than a fact about this person. Identity is supplied by
#: `core/identity.py`, in front, once.
_PROMPT_LABELS = {USER: "User", ASSISTANT: "Assistant"}


@dataclass(frozen=True)
class Turn:
    """One thing that was said. Provider-neutral by construction.

    Deliberately smaller than `conversations.Message`: no id, no timestamp, no
    model. Those are facts about the *record*, and a projection that carried
    them would tempt a caller into putting them on the wire — where they are
    noise at best and, in the case of which model answered, a claim the next
    model has no reason to trust.
    """

    role: Role
    text: str

    @property
    def tokens(self) -> int:
        # The label and separator ride along, because they are sent too. A fit
        # computed on the bare text overflows by a few tokens per turn, which
        # on a 4,096 window and a long conversation is not a rounding error.
        return estimate_tokens(f"{_PROMPT_LABELS[self.role]}: {self.text}\n\n")


def from_messages(messages: Iterable) -> List[Turn]:
    """Turns from stored `conversations.Message` records, in order.

    Anything without one of the two roles is dropped rather than coerced. The
    store already refuses a `system` role; this is the second gate, for a row
    that arrived some other way.
    """
    turns: List[Turn] = []
    for message in messages:
        role = getattr(message, "role", None)
        text = (getattr(message, "text", "") or "").strip()
        if role in (USER, ASSISTANT) and text:
            turns.append(Turn(role=role, text=text))
    return turns


def fit(turns: Sequence[Turn], budget_tokens: int) -> tuple[List[Turn], int]:
    """The most recent turns that fit, and how many were dropped.

    Oldest first, whole turns only. Returns ``([], len(turns))`` when even the
    last turn does not fit — which is a real answer and must not be softened
    into a truncated one. A caller that receives it should say the conversation
    is too long for this model, not send half a sentence.

    **The kept transcript never begins with an assistant turn.** A reply whose
    question has been dropped reads as context from nowhere, and a model handed
    one will answer as though it had already been asked something. Dropping the
    orphan costs one turn and removes a whole class of confusion.
    """
    if budget_tokens <= 0 or not turns:
        return [], len(turns)

    kept: List[Turn] = []
    spent = 0
    # Backwards: the recent end is the part that matters, so it is the part
    # that gets the budget.
    for turn in reversed(turns):
        cost = turn.tokens
        if spent + cost > budget_tokens:
            break
        kept.append(turn)
        spent += cost
    kept.reverse()

    while kept and kept[0].role == ASSISTANT:
        kept.pop(0)

    return kept, len(turns) - len(kept)


def as_prompt(turns: Sequence[Turn]) -> str:
    """A completion-style flattening, for Ollama's ``/api/generate``.

    Roles become labels because the endpoint has nowhere else to put them.
    Empty for an empty transcript rather than a header with nothing under it —
    a caller concatenating this onto a question must not get a stray "User:"
    with no exchange behind it.
    """
    if not turns:
        return ""
    return "\n\n".join(f"{_PROMPT_LABELS[t.role]}: {t.text}" for t in turns)


def as_messages(turns: Sequence[Turn]) -> List[dict]:
    """Role-tagged messages, for an OpenAI-compatible ``/v1/chat/completions``.

    No ``system`` entry. The system prompt is composed per request from
    identity, the user's character settings and the date, and it is the
    caller's to place — putting one here would let a stored transcript carry a
    preamble that was true when it was written and is false now.
    """
    return [{"role": t.role, "content": t.text} for t in turns]
