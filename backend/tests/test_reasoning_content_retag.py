"""A provider that splits thinking into its own field, read and re-tagged.

**This path shipped with no tests.** `OpenAICompatibleEngine._tokens` gained
`reasoning_content` handling last session — the OpenAI extension TabbyAPI,
DeepSeek and others use to put a reasoning model's monologue in a second delta
field. Before it, this engine read only `content`, so on those providers the
thinking was dropped in silence and the panel built to show it stayed
permanently empty. Nothing asserted any of that.

The second half is the leading-whitespace trim, and it is here rather than in
`test_reasoning_split.py` because it is a property of *this* parser and not of
`ReasoningSplitter`. A reasoning model's chat template puts a newline or two
after the closing tag, so the first content delta arrives as ``"\n\nI’m"`` —
measured against TabbyAPI serving Qwen3.8-27B, 28 August 2026, on every reply.
On screen that reads as the answer starting late.
"""

from __future__ import annotations

import json

import pytest

from runtimes.models.engines.openai_compatible_engine import (
    LOCAL_SAMPLING,
    OpenAICompatibleEngine,
)


def sse(*deltas: dict) -> list[str]:
    """The wire, as the provider sends it."""
    frames = [
        "data: " + json.dumps({"choices": [{"delta": d}]}) for d in deltas
    ]
    return frames + ["data: [DONE]"]


def run(*deltas: dict) -> str:
    return "".join(OpenAICompatibleEngine._tokens(sse(*deltas)))


class TestReasoningContentIsReadAndRetagged:
    def test_thinking_in_its_own_field_is_not_dropped(self):
        out = run({"reasoning_content": "weighing it up"}, {"content": "the answer"})

        assert "weighing it up" in out, "the monologue was dropped in silence"
        assert "the answer" in out

    def test_it_arrives_wrapped_for_the_existing_splitter(self):
        """`ReasoningSplitter` already understands this shape; a parallel
        channel would have to re-earn the reasoning event, the transcript, and
        the rule that thinking never reaches speech."""
        out = run({"reasoning_content": "hmm"}, {"content": "answer"})

        assert out == "<think>hmm</think>answer"

    def test_the_tag_opens_once_across_several_thinking_deltas(self):
        out = run(
            {"reasoning_content": "one "},
            {"reasoning_content": "two"},
            {"content": "answer"},
        )

        assert out.count("<think>") == 1
        assert out.count("</think>") == 1

    def test_thinking_that_never_reaches_an_answer_still_closes(self):
        """An unclosed tag makes the splitter hold the whole reply, and the
        user sees nothing at all."""
        out = run({"reasoning_content": "cut off mid-"})

        assert out.endswith("</think>")

    def test_a_reply_with_no_thinking_gets_no_tags(self):
        assert run({"content": "just an answer"}) == "just an answer"


class TestTheAnswerNeverStartsWithBlankLines:
    """The measured symptom: every reply opened with a gap."""

    def test_the_template_newlines_after_the_close_tag_are_dropped(self):
        out = run({"reasoning_content": "hmm"}, {"content": "\n\nI’m Zaram"})

        assert out == "<think>hmm</think>I’m Zaram"

    def test_it_applies_without_any_thinking_too(self):
        assert run({"content": "\n  Hello"}) == "Hello"

    def test_a_wholly_blank_first_chunk_emits_nothing_and_does_not_arm(self):
        """Trimming must survive the whitespace arriving in its own delta,
        which is how a token-by-token stream actually delivers it."""
        out = run({"content": "\n\n"}, {"content": "  Hello"}, {"content": " there"})

        assert out == "Hello there"

    def test_only_the_leading_edge_is_touched(self):
        """A blank line inside an answer is the author's paragraph break.
        Stripping those would run the prose together."""
        out = run({"content": "First para.\n\nSecond para.\n\n"})

        assert out == "First para.\n\nSecond para.\n\n"

    def test_interior_whitespace_chunks_survive_once_the_answer_has_started(self):
        out = run({"content": "one"}, {"content": "\n\n"}, {"content": "two"})

        assert out == "one\n\ntwo"

    def test_an_answer_that_is_only_whitespace_yields_nothing(self):
        assert run({"reasoning_content": "hmm"}, {"content": "   "}) == "<think>hmm</think>"


class TestTheThinkingItselfIsNotTrimmed:
    """The trim is about the answer. Thinking is shown verbatim in a panel of
    its own, and reshaping it there would misrepresent what the model did."""

    def test_leading_whitespace_in_thinking_is_kept(self):
        out = run({"reasoning_content": "\n\nlet me see"}, {"content": "yes"})

        assert out == "<think>\n\nlet me see</think>yes"


class TestSamplingIsSentToLocalServers:
    """Sending nothing is not neutral.

    The body carried `model`, `messages` and `stream` and no sampling at all,
    so the server's factory default applied -- TabbyAPI's is temperature 1.0
    with top-p 1.0, unconstrained sampling from the raw distribution. Ollama
    does not have this problem because a Modelfile ships per-model settings and
    Ollama applies them, so the two local engines generated differently and
    nothing said so. Reported as "talking weird", 28 August 2026.
    """

    def _engine(self, **kwargs):
        return OpenAICompatibleEngine(
            base_url="http://127.0.0.1:1234", api_key="", default_model="m", **kwargs
        )

    def test_none_by_default_so_the_cloud_path_is_unchanged(self):
        """A provider's own default is part of what the user chose when they
        connected it. Only the local path overrides."""
        body = self._engine()._body("hi", "", None)

        assert "temperature" not in body
        assert "top_p" not in body

    def test_supplied_sampling_reaches_the_body(self):
        body = self._engine(sampling=LOCAL_SAMPLING)._body("hi", "", None)

        assert body["temperature"] == LOCAL_SAMPLING["temperature"]
        assert body["top_p"] == LOCAL_SAMPLING["top_p"]

    def test_the_shape_of_the_request_is_otherwise_untouched(self):
        body = self._engine(sampling=LOCAL_SAMPLING)._body("hi", "sys", None)

        assert body["model"] == "m"
        assert body["stream"] is True
        assert body["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
        ]

    def test_only_standard_openai_fields(self):
        """`top_k` is a local dialect extension. One dialect-specific key would
        make this constant unsafe to reuse against a strict server."""
        assert set(LOCAL_SAMPLING) == {"temperature", "top_p"}

    def test_the_defaults_are_conservative(self):
        """The failure was looseness. A default at or above 1.0 would not fix
        anything, and this test is what stops it drifting back."""
        assert 0 < LOCAL_SAMPLING["temperature"] < 1.0
        assert 0 < LOCAL_SAMPLING["top_p"] <= 1.0

    def test_the_caller_cannot_mutate_the_shared_constant(self):
        engine = self._engine(sampling=LOCAL_SAMPLING)
        engine._body("hi", "", None)["temperature"] = 99

        assert LOCAL_SAMPLING["temperature"] != 99
