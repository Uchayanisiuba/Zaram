"""A reply can be reasoning without ever saying so.

Qwen3's chat template emits ``<think>`` itself, before the model writes a
token. What arrives over the wire is the working-out, a bare ``</think>``, and
then the answer -- with no opening tag anywhere in the stream.

Measured 10 September 2026 against TabbyAPI serving ``Qwen3.8-27B-exl3-2.20bpw``:
``reasoning_content`` came back ``null`` and the whole monologue sat in
``content``. Tabby's own ``reasoning: true`` splitter fails for the same reason
this one did, so there is no upstream to defer to.

Before the fix the splitter found no ``<think>``, emitted the entire monologue
**as the answer**, and rendered the stray closing tag in the middle of it. On
screen that is the model talking to itself where the reply should be, which
reads as the product being broken rather than as a model that thinks out loud.
"""

from core.reasoning import ANSWER, REASONING, ReasoningSplitter


def drain(chunks, **kwargs):
    """Feed a stream one chunk at a time and flush, as a caller would."""
    splitter = ReasoningSplitter(**kwargs)
    events = []
    for chunk in chunks:
        events += splitter.feed(chunk)
    events += splitter.flush()
    return events


def text_of(events, kind):
    return "".join(body for seen, body in events if seen == kind)


def test_a_declared_prefill_puts_the_monologue_under_reasoning():
    """The case Zaram can predict: it asked for thinking, so thinking may open.

    This is the whole point of the flag. The caller that enabled thinking is
    the only party that knows the reply may begin mid-block, and it cannot be
    inferred from the stream -- by the time the closing tag arrives, the text
    before it has already gone out.
    """
    events = drain(
        ["The user wants a comment line.", " Let me check the file.", "</think>", "\n\nDone."],
        starts_in_reasoning=True,
    )

    assert text_of(events, REASONING) == (
        "The user wants a comment line. Let me check the file."
    )
    assert text_of(events, ANSWER).strip() == "Done."


def test_an_undeclared_prefill_never_renders_a_raw_tag():
    """The floor under the case Zaram cannot predict.

    An unexpected model, or a prefill nobody declared. The classification is
    already lost -- the monologue went out as answer and a token stream cannot
    be un-emitted. What is still recoverable is that the reader never sees
    ``</think>`` sitting in the middle of their reply.
    """
    events = drain(["Let me think.", "</think>", "Hello."])

    assert "</think>" not in text_of(events, ANSWER)
    assert "<think>" not in text_of(events, ANSWER)
    assert text_of(events, ANSWER) == "Let me think.Hello."


def test_a_closing_tag_split_across_chunks_does_not_leak():
    """Holding one tag and not its pair reintroduces the defect it prevents.

    ``<think>`` and ``</think>`` share a prefix, so a chunk ending in ``</thi``
    is a partial *closing* tag that the opening-tag hold does not recognise.
    Emitted, it reaches the reader as a tag split across two paints.
    """
    events = drain(["Thinking", "</thi", "nk>", "Answer."])

    body = text_of(events, ANSWER)
    assert "</thi" not in body
    assert "nk>" not in body
    assert body == "ThinkingAnswer."


def test_the_ordinary_tagged_form_is_unchanged():
    """The convention still works, and the flag defaults to off."""
    events = drain(["<think>", "working it out", "</think>", "the answer"])

    assert text_of(events, REASONING) == "working it out"
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


def test_a_declared_prefill_that_thinks_and_stops_still_says_so():
    """`NO_ANSWER` must survive the new entry path.

    A model that thinks at length and never gets to the point is the failure
    this splitter already names in words. Starting mid-block must not turn
    that into a blank bubble again.
    """
    events = drain(["thinking, at length, forever"], starts_in_reasoning=True)

    assert text_of(events, REASONING) == "thinking, at length, forever"
    assert text_of(events, ANSWER) == ReasoningSplitter.NO_ANSWER
