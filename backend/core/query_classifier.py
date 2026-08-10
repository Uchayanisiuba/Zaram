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


def needs_search(prompt: str) -> bool:
    if not prompt or len(prompt.strip()) < 3:
        return False
    if _SEARCH_MARKER in prompt:
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
