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

    def __init__(self) -> None:
        self._buffer = ""
        self._in_reasoning = False

    @property
    def in_reasoning(self) -> bool:
        return self._in_reasoning

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
                    self._buffer = self._buffer[len(self._buffer) - hold :]
                    break
                if index:
                    out.append((REASONING, self._buffer[:index]))
                self._buffer = self._buffer[index + len(CLOSE_TAG) :]
                self._in_reasoning = False
                continue

            index = self._buffer.find(OPEN_TAG)
            if index == -1:
                hold = _partial_tag_suffix(self._buffer, OPEN_TAG)
                ready = self._buffer[: len(self._buffer) - hold]
                if ready:
                    out.append((ANSWER, ready))
                self._buffer = self._buffer[len(self._buffer) - hold :]
                break
            if index:
                out.append((ANSWER, self._buffer[:index]))
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
        if not self._buffer:
            return []
        kind = REASONING if self._in_reasoning else ANSWER
        out = [(kind, self._buffer)]
        self._buffer = ""
        return out


def split_events(splitter: ReasoningSplitter, chunk: str) -> Iterator[Tuple[str, str]]:
    """Convenience wrapper so every call site reads the same way.

    ``docs/SPEECH.md`` records the cost of the alternative: marker stripping
    existed in three copies and the one that had been missed was the one that
    spoke. There are four places in this backend that turn a string into a token
    event, so the splitting logic gets exactly one home and they all call it.
    """
    yield from splitter.feed(chunk)
