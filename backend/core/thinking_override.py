"""Thinking, for one message, without touching the setting.

Settings has a *Thinking* switch, on by default: a model that can think is asked
to, because that is where a 27B earns its keep on a hard question. The comment
beside the default predicted the cost as "10-40 s". **Measured 4 October 2026
against the resident 27B: 870 seconds** for a looping CSS animation -- 3,956
frames of reasoning against 542 of answer, so 87% of the generation was the
model talking to itself about a bouncing ball.

The switch is the right *control* and the wrong *moment*. Rule 7h: offer at the
moment of doubt, never make the user choose in advance. Nobody knows before
asking whether a question will make the model think for fourteen minutes; they
know eighty seconds in. So the conversation offers "answer without thinking"
once thinking has run long, and that sends the same question again with this
override set for that one request.

**A `ContextVar`, not the setting.** Flipping the global would change the next
question too, and the one after it, for a decision about one. And two requests in
flight must not decide each other's thinking -- the same reason
`set_search_locality` is a `ContextVar` and not a module global.

``None`` means no opinion, and then the setting decides. That is the ordinary
case and it is the default: nothing here changes a request that did not ask.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Optional

_OVERRIDE: ContextVar[Optional[bool]] = ContextVar("zaram_thinking_override", default=None)

__all__ = [
    "decide_thinking",
    "is_code_request",
    "set_thinking_override",
    "thinking_override",
    "thinking_wanted",
]


def set_thinking_override(value: Optional[bool]) -> None:
    """For the request in flight. Called on every chat request, including the
    ones that pass ``None``, so a previous request's choice cannot leak."""
    _OVERRIDE.set(value if isinstance(value, bool) else None)


#: Words that mean the request is for code or for a page, matched as whole words.
#: Deliberately plain and short: a false positive costs thinking time for
#: someone who chose "for code", a false negative costs the setting doing
#: nothing for a request that was code.
_CODE_WORDS = re.compile(
    r"\b(code|coding|function|script|bug|debug|refactor|implement|algorithm|program|"
    r"python|javascript|typescript|react|css|html|backend|frontend|compile|regex|sql|"
    r"webpage|web ?page|website|game|app|three\.?js|webgl|canvas)\b",
    re.IGNORECASE,
)


def is_code_request(text: str, last_answer: str = "") -> bool:
    """Whether this request is for code or a page, or a follow-up to one."""
    return bool(
        _CODE_WORDS.search(text or "")
        or "```" in (text or "")
        or "```" in (last_answer or "")
    )


def decide_thinking(asked: Optional[bool], *, code: bool, for_code: bool) -> Optional[bool]:
    """The override for one request.

    What the message itself asked for wins. Otherwise a code request with
    *thinking for code* on thinks, whatever the everyday setting is. ``None``
    leaves the person's setting to decide, which is the ordinary case.
    """
    if asked is not None:
        return asked
    if code and for_code:
        return True
    return None


def thinking_override() -> Optional[bool]:
    return _OVERRIDE.get()


def thinking_wanted() -> bool:
    """Whether a model that can think is asked to, for this request.

    The override first; otherwise the person's setting; *on* when the settings
    store cannot be reached -- the direction that costs a wait and not an answer.
    """
    chosen = _OVERRIDE.get()
    if chosen is not None:
        return chosen
    try:
        from core.user_settings import get_user_settings

        return bool(get_user_settings().thinking)
    except Exception:
        return True
