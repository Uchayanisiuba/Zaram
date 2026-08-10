# backend/tests/test_query_classifier.py
from core.query_classifier import needs_search, SEARCH_MARKER


def test_rejects_too_short():
    assert needs_search("") is False
    assert needs_search("ab") is False
    assert needs_search("   ") is False


def test_rejects_already_augmented_prompt():
    prompt = f"{SEARCH_MARKER}\nSource:\nTitle: Foo"
    assert needs_search(prompt) is False


def test_time_signals_trigger_search():
    assert needs_search("Latest news about AI") is True
    assert needs_search("What is the current weather?") is True
    assert needs_search("Breaking changes in React today") is True
    assert needs_search("Recent updates to Kubernetes") is True


def test_factual_signals_trigger_search():
    assert needs_search("Who is the current CEO of OpenAI?") is True
    assert needs_search("What is the price of Bitcoin?") is True
    assert needs_search("When was Python 3.14 released?") is True
    assert needs_search("How many people live in Tokyo?") is True


def test_realtime_keywords_trigger_search():
    assert needs_search("NASDAQ closes at record high") is True
    assert needs_search("Will there be an election next month?") is True
    assert needs_search("Local traffic on I-95") is True
    assert needs_search("Market analysis for semiconductor stocks") is True


def test_year_references_trigger_search():
    assert needs_search("What happened in 2026?") is True
    assert needs_search("Future of AI in 2030") is True


def test_timeless_questions_do_not_trigger_search():
    assert needs_search("Explain recursion") is False
    assert needs_search("How does Python work?") is False
    assert needs_search("What is polymorphism?") is False
    assert needs_search("Describe the water cycle") is False
