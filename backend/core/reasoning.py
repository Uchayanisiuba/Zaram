"""Separate a model's thinking from its answer, as both arrive.

Why this exists
---------------
Reasoning models — Qwen3, DeepSeek-R1 and the rest of the ``<think>`` convention
— emit their working before their answer, in the same token stream, wrapped in a
tag. Asked for on 19 August 2026: show the thinking, the way Claude does.

**It is also a defect fix, and that is the part worth stating first.** Nothing in
this codebase looked for those tags, so on a reasoning model the working was
already reaching the user *as the answer*: rendered as the reply, committed to
the transcript, handed to ``pushSpeech`` — which means Kokoro read the model's
internal monologue aloud, in avatar mode, before it got to the point. Splitting
the stream fixes the display and closes that at the same time, because reasoning
never becomes a ``token`` event and therefore never enters ``streamingText``,
which is the single thing speech reads.

Why it buffers
--------------
**A tag arrives split across tokens.** This repository already learned that from
citation markers — ``[M1]`` comes through as ``[M`` then ``1]`` — and the fix
there was to strip on *accumulated* text rather than per token. The same hazard
applies here and is worse, because a half-recognised ``<think>`` does not merely
render wrong, it puts the splitter in the wrong state for the rest of the reply.

So text that could still turn out to be the start of a tag is held back rather
than emitted, and released the moment it is proved not to be. The buffer is
bounded by the longest tag, so the delay is a few characters and never a clause
— which matters, because ``pushSpeech`` is downstream and speech is supposed to
keep pace with the text.

What it deliberately does not do
--------------------------------
It does not try to *detect* whether a model reasons. There is no reliable signal
short of running it, the tag is the signal, and a model that never emits one
simply never produces a reasoning event. Guessing from a model name would be the
same class of mistake as sizing a model against a VRAM figure of ``0``.
"""

from __future__ import annotations

from typing import Iterator, List, Tuple

#: The convention, and the only one. ``<think>`` is what Qwen3, DeepSeek-R1 and
#: the models that copied them emit. Others are added here when a model that
#: uses them is actually installed and observed — a speculative list of tags is
#: a list of guesses about text that will be shown to a user as an answer.
OPEN_TAG = "<think>"
CLOSE_TAG = "</think>"

#: Kind markers for what :meth:`ReasoningSplitter.feed` returns.
ANSWER = "answer"
REASONING = "reasoning"

_MAX_HOLD = max(len(OPEN_TAG), len(CLOSE_TAG))


def _partial_tag_suffix(text: str, tag: str) -> int:
    """Length of the longest suffix of ``text`` that is a proper prefix of ``tag``.

    This is the whole trick. ``"...and <thi"`` ends in something that might
    become ``<think>`` on the next token, so those four characters are held; a
    text ending in ``"...and <t h"`` holds nothing, because no prefix of the tag
    matches. Proper prefix only — a complete tag is not held, it is consumed.
    """
    limit = min(len(text), len(tag) - 1)
    for size in range(limit, 0, -1):
        if text[-size:] == tag[:size]:
            return size
    return 0


class ReasoningSplitter:
    """Turns a token stream into ``(kind, text)`` pairs, tags removed.

    Stateful across calls by necessity: whether a given chunk is thinking or
    answer depends on a tag that may have arrived several tokens ago.

    One instance per reply. Reusing one across replies would carry an unclosed
    ``<think>`` from a truncated answer into the next question, and the next
    answer would silently vanish into the thinking panel.
    """

    #: What is said when a reply is all thinking and no answer.
    #:
    #: Not an error, and deliberately not phrased as one — nothing failed, the
    #: model simply stopped before it got to the point. Observed on the
    #: maintainer's machine on 3 September 2026 with a 27B model at 2.2 bits
    #: per weight, asked to build a portfolio site from a CV: it thought at
    #: length, twice, and the reply came back **empty**. On screen that is a
    #: blank bubble with a collapsed *Thought process* beside it and nothing at
    #: all saying what happened, which reads as the product being broken rather
    #: than as a generation that ran out.
    #:
    #: `CLAUDE.md`: *generation must fail rather than invent* — and a silent
    #: failure is the half of that rule which is easy to miss, since inventing
    #: nothing at all still leaves the user with no idea why. It names where
    #: the working went, because that panel is genuinely worth opening here.
    NO_ANSWER = (
        "The model stopped before writing an answer — everything it produced is "
        "under Thought process. Ask again, or try a shorter question."
    )

    def __init__(self) -> None:
        self._buffer = ""
        self._in_reasoning = False
        #: Whether anything has ever been emitted as answer.
        #:
        #: Tracked rather than derived at the end from `_in_reasoning`, because
        #: by flush time that flag says nothing useful: `OpenAICompatibleEngine`
        #: closes an unterminated block itself before the stream ends, so the
        #: splitter is out of reasoning mode with an empty answer — the exact
        #: case being caught. What matters is not who closed the tag; it is
        #: that no answer was ever produced.
        self._answered = False
        #: And whether there was any thinking to attribute the silence to. An
        #: empty reply with no reasoning is a different failure — a refused
        #: request, a dropped connection — which the error path already reports
        #: in its own words, and speaking over it here would replace a specific
        #: message with a vaguer one.
        self._reasoned = False

    @property
    def in_reasoning(self) -> bool:
        return self._in_reasoning

    def _saw(self, kind: str, text: str) -> None:
        """Record that real content of ``kind`` was emitted.

        **Whitespace does not count, and that is not tidiness.** A reasoning
        model's chat template puts a newline or two after the closing tag, so a
        reply truncated immediately afterwards emits `"

"` as its entire
        answer — measured against TabbyAPI serving Qwen3.8-27B, where every
        reply's first content delta arrives that way. Counted, that blank line
        would mark the reply as answered and put the empty bubble back, hiding
        the one case `NO_ANSWER` exists for behind two characters nobody can
        see.
        """
        if not text.strip():
            return
        if kind == ANSWER:
            self._answered = True
        else:
            self._reasoned = True

    def feed(self, chunk: str) -> List[Tuple[str, str]]:
        """Consume one token; return whatever can now be emitted safely."""
        self._buffer += chunk
        out: List[Tuple[str, str]] = []

        while self._buffer:
            if self._in_reasoning:
                index = self._buffer.find(CLOSE_TAG)
                if index == -1:
                    hold = _partial_tag_suffix(self._buffer, CLOSE_TAG)
                    ready = self._buffer[: len(self._buffer) - hold]
                    if ready:
                        out.append((REASONING, ready))
                        self._saw(REASONING, ready)
                    self._buffer = self._buffer[len(self._buffer) - hold :]
                    break
                if index:
                    out.append((REASONING, self._buffer[:index]))
                    self._saw(REASONING, self._buffer[:index])
                self._buffer = self._buffer[index + len(CLOSE_TAG) :]
                self._in_reasoning = False
                continue

            index = self._buffer.find(OPEN_TAG)
            if index == -1:
                hold = _partial_tag_suffix(self._buffer, OPEN_TAG)
                ready = self._buffer[: len(self._buffer) - hold]
                if ready:
                    out.append((ANSWER, ready))
                    self._saw(ANSWER, ready)
                self._buffer = self._buffer[len(self._buffer) - hold :]
                break
            if index:
                out.append((ANSWER, self._buffer[:index]))
                self._saw(ANSWER, self._buffer[:index])
            self._buffer = self._buffer[index + len(OPEN_TAG) :]
            self._in_reasoning = True

        return out

    def flush(self) -> List[Tuple[str, str]]:
        """Release whatever is still held, at end of stream.

        **Held text must never be dropped.** A reply ending in a literal ``<`` —
        or in ``<thin``, from a model that got cut off — would otherwise lose its
        last characters, and a truncated final word is exactly the kind of defect
        that gets blamed on the model. Whatever is in the buffer is emitted as
        whichever side of the tag the stream was on when it ended.
        """
        out: List[Tuple[str, str]] = []
        if self._buffer:
            kind = REASONING if self._in_reasoning else ANSWER
            out.append((kind, self._buffer))
            self._saw(kind, self._buffer)
            self._buffer = ""

        # All working, no answer. See `NO_ANSWER` for what was measured.
        if self._reasoned and not self._answered:
            self._answered = True
            out.append((ANSWER, self.NO_ANSWER))

        return out


def split_events(splitter: ReasoningSplitter, chunk: str) -> Iterator[Tuple[str, str]]:
    """Convenience wrapper so every call site reads the same way.

    ``docs/SPEECH.md`` records the cost of the alternative: marker stripping
    existed in three copies and the one that had been missed was the one that
    spoke. There are four places in this backend that turn a string into a token
    event, so the splitting logic gets exactly one home and they all call it.
    """
    yield from splitter.feed(chunk)
