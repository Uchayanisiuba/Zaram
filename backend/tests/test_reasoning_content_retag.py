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


class TestOpenRouterCallsTheFieldSomethingElse:
    """The third name one defect has arrived under, and the third provider.

    `reasoning_content` was read for TabbyAPI. Then `ollama_engine` had to
    learn `thinking`, and its own comment records what that cost — *"the
    maintainer saw thinking on TabbyAPI and lost it on switching to Ollama,
    and read that as Zaram breaking."* OpenRouter is the third: it normalises
    a reasoning model's monologue into `delta.reasoning`, nothing here looked
    for that name, and every cloud reasoning model therefore lost its working
    in silence.

    Reported by the maintainer on 4 September 2026, on a machine whose recent
    traffic is entirely OpenRouter — `openai/gpt-5.6-sol-pro`,
    `qwen/qwen3.8-27b`, `google/gemini-3.7-flash`.
    """

    def test_openrouters_field_is_not_dropped(self):
        out = run({"reasoning": "weighing it up"}, {"content": "the answer"})

        assert "weighing it up" in out, (
            "OpenRouter puts the thinking in `reasoning`; unread, it vanishes "
            "and the panel stays empty for every cloud reasoning model"
        )
        assert out == "<think>weighing it up</think>the answer"

    def test_it_opens_once_across_several_deltas(self):
        out = run(
            {"reasoning": "one "},
            {"reasoning": "two"},
            {"content": "answer"},
        )

        assert out == "<think>one two</think>answer"

    def test_a_provider_sending_both_names_is_not_doubled(self):
        """Some gateways echo the OpenAI field alongside their own. Taking one
        keeps the monologue from arriving twice in the panel."""
        out = run({"reasoning_content": "hmm", "reasoning": "hmm"}, {"content": "a"})

        assert out == "<think>hmm</think>a"

    def test_a_structure_rather_than_text_is_ignored_not_stringified(self):
        """OpenRouter also sends `reasoning_details` as objects, and some
        gateways put a dict in `reasoning` itself. `str(dict)` in the working
        panel is worse than an empty one — it is indistinguishable from
        something the model wrote."""
        out = run({"reasoning": {"summary": "hmm"}}, {"content": "the answer"})

        assert "summary" not in out
        assert "{" not in out
        assert out == "the answer"

    def test_a_plain_reply_is_untouched(self):
        """The regression guard: no tag appears where no thinking was sent."""
        assert run({"content": "391"}) == "391"


class TestOpenRouterStreamsAListOfObjects:
    """`reasoning_details` is the field OpenRouter's own docs name for
    streaming — *"in streaming responses, `reasoning_details` appears in
    `choices[].delta.reasoning_details` for each chunk"* — and it is a list of
    objects rather than a string.

    Read on 4 September 2026 from openrouter.ai/docs/use-cases/reasoning-tokens
    rather than from memory, because the shape decides the parser: a list
    handled as a string yields `str(list)` in the working panel.

    Reasoning is returned **by default** when a model produces it, which is
    why nothing is added to the request. Sending an unknown `reasoning`
    parameter to the other servers this engine talks to — TabbyAPI, LM Studio,
    llama.cpp — would risk breaking them to ask for something already on.
    """

    def test_the_documented_streaming_shape_is_read(self):
        out = run(
            {"reasoning_details": [
                {"type": "reasoning.text", "text": "step by step", "index": 0}
            ]},
            {"content": "the answer"},
        )

        assert out == "<think>step by step</think>the answer"

    def test_a_summary_entry_is_read_too(self):
        out = run(
            {"reasoning_details": [
                {"type": "reasoning.summary", "summary": "weighed it up", "index": 0}
            ]},
            {"content": "a"},
        )

        assert out == "<think>weighed it up</think>a"

    def test_raw_working_is_preferred_over_a_precis_of_it(self):
        """An entry carrying both is the working plus a summary of the
        working, and the panel exists for the working."""
        out = run(
            {"reasoning_details": [
                {"type": "reasoning.text", "text": "the working", "summary": "a precis"}
            ]},
            {"content": "a"},
        )

        assert "the working" in out
        assert "a precis" not in out

    def test_encrypted_reasoning_is_skipped_rather_than_shown(self):
        """`reasoning.encrypted` is a base64 blob that streams as
        "[REDACTED]". There is nothing in it to read, and putting it in the
        panel is noise the model did not write."""
        out = run(
            {"reasoning_details": [
                {"type": "reasoning.encrypted", "data": "S2V5Ym9hcmQ=", "index": 0}
            ]},
            {"content": "the answer"},
        )

        assert out == "the answer"
        assert "S2V5" not in out

    def test_a_list_is_never_stringified(self):
        """The failure this shape invites: `str(list)` in the working panel,
        indistinguishable from something the model wrote."""
        out = run(
            {"reasoning_details": [{"type": "reasoning.text", "text": "hmm"}]},
            {"content": "a"},
        )

        assert "[{" not in out
        assert "'type'" not in out

    def test_several_entries_join_in_order(self):
        out = run(
            {"reasoning_details": [
                {"type": "reasoning.text", "text": "one ", "index": 0},
                {"type": "reasoning.text", "text": "two", "index": 1},
            ]},
            {"content": "a"},
        )

        assert out == "<think>one two</think>a"


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
