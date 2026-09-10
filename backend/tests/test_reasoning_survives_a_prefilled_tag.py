"""A closing tag nobody opened must never reach the reader.

**Corrected 10 September 2026, and the correction is the useful part.** This
file was written that morning claiming a live defect: that a reply whose
thinking arrives with only a closing tag -- Qwen3's template emits ``<think>``
into the *prompt*, so the model begins its output already inside the block --
was being filed as the answer and rendered on screen.

That case is real. It was **already handled**, one layer up, since 3 September.
``OpenAICompatibleEngine._template_opens_thinking`` asks ``/v1/model`` for the
chat template, reads what the template actually does, and supplies the opening
tag itself before the first frame reaches this splitter. It is called on the
live streaming path and cached, one request per engine.

The claim that nothing called it came from a truncated grep read as an absence
-- ``CLAUDE.md``'s *check the instrument before reading its output*, committed
by the session quoting that rule. A ``starts_in_reasoning`` flag was added here
on the strength of it and removed the same day: nothing called it either, so it
was a second answer to an answered question, set by a caller that knows less
than the engine does.

What survives is narrower and still worth having: a **floor** under the case
nothing upstream recognises. An engine with no template route, a provider that
prefills without saying so, a shape nobody has met yet. The classification is
lost there -- the monologue has already gone out as answer and a token stream
cannot be un-emitted -- but the reader never reads a raw tag, which is the part
that reads as the product being broken.
"""

from core.reasoning import ANSWER, REASONING, ReasoningSplitter


def drain(chunks):
    """Feed a stream one chunk at a time and flush, as a caller would."""
    splitter = ReasoningSplitter()
    events = []
    for chunk in chunks:
        events += splitter.feed(chunk)
    events += splitter.flush()
    return events


def text_of(events, kind):
    return "".join(body for seen, body in events if seen == kind)


def test_a_closing_tag_nobody_opened_is_never_rendered():
    """The floor. Not a classification fix -- a "no raw tags" guarantee.

    Reaching this means something upstream did not recognise a prefilled
    template. The thinking is already filed as answer and cannot be moved. The
    tag itself can be, and is, silently: there is nothing in it a reader could
    act on and the reply around it is intact.
    """
    events = drain(["Let me think.", "</think>", "Hello."])

    assert "</think>" not in text_of(events, ANSWER)
    assert "<think>" not in text_of(events, ANSWER)
    assert text_of(events, ANSWER) == "Let me think.Hello."


def test_a_closing_tag_split_across_chunks_does_not_leak():
    """Holding one tag and not its pair reintroduces the defect it prevents.

    ``<think>`` and ``</think>`` share a prefix, so a chunk ending in ``</thi``
    is a partial *closing* tag that the opening-tag hold does not recognise.
    Emitted, it reaches the reader as a tag split across two paints -- which is
    exactly what ``_partial_tag_suffix`` exists to stop.
    """
    events = drain(["Thinking", "</thi", "nk>", "Answer."])

    body = text_of(events, ANSWER)
    assert "</thi" not in body
    assert "nk>" not in body
    assert body == "ThinkingAnswer."


def test_the_engine_supplied_opening_tag_still_works():
    """What the live path actually sends.

    ``_tokens`` yields ``OPEN_TAG`` before the first frame when the template
    prefills, so by the time a stream reaches this splitter it is the ordinary
    tagged shape. This is that stream.
    """
    events = drain(["<think>", "the working out", "</think>", "the answer"])

    assert text_of(events, REASONING) == "the working out"
    assert text_of(events, ANSWER) == "the answer"


def test_a_reply_with_no_tags_at_all_is_untouched():
    """The common case pays nothing for any of the above.

    No holding beyond a partial tag, no reclassification, no delay to the
    first paint -- which ``docs/SPEECH.md`` is emphatic about, because
    synthesis starts on the first sentence that will not change again.
    """
    events = drain(["Just ", "an ordinary ", "answer."])

    assert text_of(events, ANSWER) == "Just an ordinary answer."
    assert text_of(events, REASONING) == ""
