# backend/core/query_classifier.py
import re

_TIME_RE = re.compile(
    r'\b(today|now|current|right now|this week|this month|this year|latest|breaking|just happened|recent|recently)\b',
    re.IGNORECASE
)
_FACTUAL_RE = re.compile(
    r'\b(who is|who was|who are|what is the|what are the|when did|where is|how many|how much|how long|when was)\b',
    re.IGNORECASE
)
_REALTIME_RE = re.compile(
    r'\b(weather|temperature|forecast|stock|price|market|bitcoin|crypto|nasdaq|dow|news|headlines|traffic|score|election|president|ceo|founder|released|launch|update)\b',
    re.IGNORECASE
)
_YEAR_RE = re.compile(r'\b20(2[5-9]|3[0-9])\b')

_TOPIC_RE = re.compile(
    r'\b(OpenAI|Gemini|Claude|Qwen|Llama|Unreal Engine|Blender|AI model|announcement|release|version)\b',
    re.IGNORECASE
)

_SEARCH_MARKER = "=== INTERNET SEARCH RESULTS ==="

#: Questions the system already answers from a fact it supplies, so wanting
#: search for them is wrong rather than merely unnecessary.
#:
#: **Zaram puts today's date in the system prompt** — `core.identity._today_line`,
#: added because a model asked outright answered `04-07-2026` from training
#: data. So "what is today's date" is not a question about the world; it is a
#: question about something the system stated as a fact one paragraph earlier.
#:
#: Measured 28 August 2026. Asked *"What is today's date?"* Zaram answered
#: **"Today's date is 28 August 2026"** — correct, from the supplied fact — and
#: rendered the amber card underneath it saying *"this answer comes only from
#: what the model already knows."* The reply and the warning about the reply
#: contradicted each other on screen, and the warning was the one that was
#: wrong: the answer came from Zaram, not from the weights.
#:
#: **Anchored, and that is the whole discipline.** `_TIME_RE` matches the bare
#: word "today" anywhere in a prompt, which is exactly how this broke — so the
#: exemption must match the *entire* question or it will start swallowing
#: "what happened today" and suppress a search that was genuinely wanted. An
#: unanchored exemption would be the same defect with the sign reversed, and
#: the sign reversed is the worse direction: a missing warning is quieter than
#: a false one.
#:
#: **Scoped to the date, because the date is what is supplied.** Not the time
#: of day — `_today_line` carries a date and nothing finer, so "what time is
#: it" is still not answered here and must not be exempted. If `identity.py`
#: ever stops supplying the date, this goes with it;
#: `test_query_classifier.py` asserts the coupling so the two cannot drift.
#:
#: One fact, one narrow pattern. A general "is this answerable from supplied
#: facts" mechanism is not built, because there is one supplied fact and
#: designing the abstraction from a single example is how the pack system was
#: explicitly told not to be built.
_ANSWERED_BY_SUPPLIED_DATE = re.compile(
    r"""^\W*
        (?:hi|hey|hello|ok|okay)?\W*
        (?:can\s+you\s+|could\s+you\s+|please\s+|do\s+you\s+know\s+|tell\s+me\s+)*
        (?:what(?:'|’)?s|what\s+is|what\s+was|what|which)?\s*
        (?:the\s+)?
        (?:current\s+|today(?:'|’)?s\s+)?
        (?:date|day|year|month)
        (?:\s+(?:is\s+it|it\s+is|today|of\s+the\s+week|are\s+we\s+in|is\s+today))?
        (?:\s+today)?
        \W*$""",
    re.IGNORECASE | re.VERBOSE,
)


def needs_search(prompt: str) -> bool:
    if not prompt or len(prompt.strip()) < 3:
        return False
    if _SEARCH_MARKER in prompt:
        return False
    # Before every pattern below, because several of them match a date
    # question — "today" on `_TIME_RE`, "what is the" on `_FACTUAL_RE` — and
    # the answer is already in the prompt. See `_ANSWERED_BY_SUPPLIED_DATE`.
    if _ANSWERED_BY_SUPPLIED_DATE.match(prompt.strip()):
        return False
    if _YEAR_RE.search(prompt):
        return True
    if _TIME_RE.search(prompt):
        return True
    if _FACTUAL_RE.search(prompt):
        return True
    if _REALTIME_RE.search(prompt):
        return True
    if _TOPIC_RE.search(prompt):
        return True
    return False


SEARCH_MARKER = _SEARCH_MARKER
