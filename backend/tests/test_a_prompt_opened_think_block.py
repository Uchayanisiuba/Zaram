"""The third shape of reasoning output, and the one that leaked.

Reported by the maintainer on 3 September 2026: *"it seems to be putting
thinking in answer and reading it aloud."*

Two shapes were already handled, and both put the thinking somewhere of its
own — Ollama in a `thinking` field, an OpenAI-compatible server with a
reasoning parser in `reasoning_content`. This is the third: the thinking
arrives in **`content`, with only a closing tag**, because the chat template
emitted the opening one into the *prompt*. The model therefore begins its
output already inside the block and never writes `<think>` itself.

`ReasoningSplitter` switches into reasoning mode on an opening tag. There is
none, so the whole monologue is filed as the answer — rendered on screen,
committed to the transcript, and read aloud by Kokoro. That last part is what
made it worth stopping everything for: `core/reasoning.py` was written to close
exactly that hole, and this route walked around it.

Measured against the running TabbyAPI serving `Qwen3.8-27B-exl3-2.20bpw`:

    reasoning_content: null
    content: "The user is asking for 17 times 23. Let me calculate: …
              </think>\\n\\n17 × 23 = **391**"

and the server's own template ends with `{{- '<think>\\n' }}` under
`add_generation_prompt`.

**It is established from the server, never from the model's name** — the same
discipline `OllamaEngine` uses when it asks `/api/show` whether a model can
think. `/v1/model` reports the template and the template says what it does.
"""

from __future__ import annotations

import json

import pytest

from core.reasoning import ANSWER, CLOSE_TAG, OPEN_TAG, REASONING, ReasoningSplitter
from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine


def sse(*deltas: dict) -> list[str]:
    frames = ["data: " + json.dumps({"choices": [{"delta": d}]}) for d in deltas]
    return frames + ["data: [DONE]"]


def run(*deltas: dict, opened: bool = True) -> str:
    return "".join(OpenAICompatibleEngine._tokens(sse(*deltas), opened))


def split(stream: str) -> dict[str, str]:
    """What the user would actually see, through the real splitter.

    Asserting on the tags alone would pass for a stream the splitter cannot
    sort — which is precisely the state the product was in.
    """
    splitter = ReasoningSplitter()
    out = {ANSWER: "", REASONING: ""}
    for kind, text in splitter.feed(stream) + splitter.flush():
        out[kind] += text
    return out


#: The observed template's generation-prompt branch, in the shape that opens
#: a block and leaves the model to close it.
TEMPLATE_THAT_OPENS = "{{- '<think>\n' }}"

#: The observed reply, trimmed. One content stream, no opening tag.
THINKING = "The user is asking for 17 times 23. Let me calculate: 391.\n"
ANSWER_TEXT = "\n\n17 × 23 = **391**"


class TestTheThinkingReachesThePanelAndNotTheAnswer:
    def test_the_monologue_is_not_the_answer(self):
        seen = split(run({"content": THINKING + CLOSE_TAG + ANSWER_TEXT}))

        assert "Let me calculate" in seen[REASONING]
        assert "Let me calculate" not in seen[ANSWER], (
            "the model's working was filed as the answer — this is what gets "
            "rendered, transcribed and spoken"
        )
        assert "391" in seen[ANSWER]

    def test_it_survives_arriving_a_token_at_a_time(self):
        """The tag comes through split, as `[M1]` does. The splitter buffers
        for that reason; this asserts the engine does not defeat it."""
        pieces = [THINKING, "</", "think", ">", "\n\n17 × 23 = ", "**391**"]
        seen = split(run(*({"content": p} for p in pieces)))

        assert "Let me calculate" in seen[REASONING]
        assert "391" in seen[ANSWER]
        assert "think" not in seen[ANSWER]

    def test_the_opening_tag_is_supplied_before_any_content(self):
        stream = run({"content": THINKING + CLOSE_TAG + ANSWER_TEXT})
        assert stream.startswith(OPEN_TAG)

    def test_the_block_is_closed_once_and_not_twice(self):
        """The auto-close fires when content arrives, and here the first
        content *is* the thinking. Left in place it would close the block
        immediately and put the monologue straight back in the answer."""
        stream = run({"content": THINKING + CLOSE_TAG + ANSWER_TEXT})
        assert stream.count(CLOSE_TAG) == 1
        assert stream.count(OPEN_TAG) == 1


class TestTheFailuresAreTheVisibleOnes:
    def test_a_model_that_never_closes_still_shows_something(self):
        """The honest failure rather than the silent one.

        An unclosed `<think>` makes the splitter hold the entire reply and the
        user sees nothing at all. Closing it at end of stream puts the reply in
        the working panel with an empty answer — wrong, and visible, which is
        the one that gets reported instead of shrugged at.
        """
        stream = run({"content": "thinking with no end"})

        assert stream.endswith(CLOSE_TAG)
        assert "thinking with no end" in split(stream)[REASONING]

    def test_nothing_changes_for_a_server_that_does_not_do_this(self):
        """The regression guard. Every other provider must be untouched."""
        seen = split(
            run({"reasoning_content": "weighing it up"}, {"content": "the answer"}, opened=False)
        )

        assert seen[REASONING] == "weighing it up"
        assert seen[ANSWER] == "the answer"

    def test_a_plain_reply_is_still_a_plain_reply(self):
        seen = split(run({"content": "391"}, opened=False))

        assert seen[ANSWER] == "391"
        assert seen[REASONING] == ""


class TestWhetherTheTemplateOpensOneIsReadFromTheServer:
    """Not guessed from the model name — that is the mistake the VRAM figure
    already cost this codebase, in a different field."""

    def _engine(self, template: str | None) -> OpenAICompatibleEngine:
        engine = OpenAICompatibleEngine(
            base_url="http://127.0.0.1:1234", api_key="", default_model="m"
        )

        class _Gate:
            def request(self, url, **_kw):
                if template is None:
                    raise OSError("no such route")
                return json.dumps(
                    {"id": "m", "parameters": {"prompt_template_content": template}}
                ).encode()

        engine._gate = _Gate()
        return engine

    #: The observed template's generation-prompt branch, verbatim in shape.
    QWEN3 = (
        "{%- if add_generation_prompt %}\n"
        "    {{- '<|im_start|>assistant\\n' }}\n"
        "    {%- if enable_thinking is defined and enable_thinking is false %}\n"
        "        {{- '<think>\\n\\n</think>\\n\\n' }}\n"
        "    {%- else %}\n"
        "        {{- '<think>\\n' }}\n"
        "    {%- endif %}\n"
        "{%- endif %}"
    )

    def test_an_unclosed_open_tag_in_the_template_is_the_signal(self):
        assert self._engine(self.QWEN3)._template_opens_thinking() is True

    def test_a_template_that_only_ever_closes_what_it_opens_is_not(self):
        """The disabled branch on its own emits a *complete* empty block, so
        the model starts after it rather than inside it. Telling those two
        apart is the whole reason this reads literals rather than searching for
        the substring."""
        closed_only = "{{- '<think>\\n\\n</think>\\n\\n' }}"
        assert self._engine(closed_only)._template_opens_thinking() is False

    def test_a_template_with_no_thinking_at_all_is_not(self):
        assert self._engine("{{- '<|im_start|>assistant\\n' }}")._template_opens_thinking() is False

    def test_a_server_that_cannot_be_asked_claims_nothing(self):
        """Only TabbyAPI serves `/v1/model`. Everything else is the ordinary
        case, and the answer is no — a wrong yes would file a whole reply into
        the panel and show an empty answer."""
        assert self._engine(None)._template_opens_thinking() is False

    def test_it_is_asked_once_and_remembered(self):
        engine = self._engine(self.QWEN3)
        calls = {"n": 0}
        inner = engine._gate.request

        def counted(url, **kw):
            calls["n"] += 1
            return inner(url, **kw)

        engine._gate.request = counted

        assert engine._template_opens_thinking() is True
        assert engine._template_opens_thinking() is True
        assert calls["n"] == 1, "this runs before every reply; it must not ask every time"


class TestAskingTooEarlyIsNotAnAnswer:
    """The regression that put the leak back, and the reason it looked fixed.

    TabbyAPI answers `/v1/model` with **503 until its model has finished
    loading**, and an exl3 takes minutes — `scripts/dev-app.ps1` says so and
    deliberately does not wait for it, because blocking the launcher on a
    model load would cost a minute every time.

    So Zaram's first reply of a session asks too early. The old code wrote
    `False` into the cache *before* issuing the request, so a 503 latched it
    for the life of the engine and every later reply filed the whole monologue
    as the answer — with the fix above present, correct, and never consulted
    again. Measured 4 September 2026: TabbyAPI listening on 1234 and
    `GET /v1/model` returning 503 while the maintainer's app was already up.

    Could not ask is not the answer no. The same distinction `vram_bytes`
    keeps by returning `None` rather than `0`.
    """

    def _engine(self, responder) -> OpenAICompatibleEngine:
        engine = OpenAICompatibleEngine(
            base_url="http://127.0.0.1:1234", api_key="", default_model="m"
        )

        class _Gate:
            def request(self, url, **_kw):
                return responder()

        engine._gate = _Gate()
        return engine

    @staticmethod
    def _http_error(code: int):
        import urllib.error

        def raise_it():
            raise urllib.error.HTTPError("http://x/v1/model", code, "no", {}, None)

        return raise_it

    def test_a_model_still_loading_is_asked_again_next_reply(self):
        """The whole bug in one assertion: 503 first, then the real template."""
        state = {"calls": 0}

        def responder():
            state["calls"] += 1
            if state["calls"] == 1:
                self._http_error(503)()
            return json.dumps(
                {"id": "m", "parameters": {"prompt_template_content": TEMPLATE_THAT_OPENS}}
            ).encode()

        engine = self._engine(responder)

        assert engine._template_opens_thinking() is False, "nothing is known yet"
        assert engine._template_opens_thinking() is True, (
            "the 503 was cached as a definite no, so the model's whole "
            "monologue goes on being filed as the answer for the session"
        )

    def test_a_timeout_is_not_an_answer_either(self):
        state = {"calls": 0}

        def responder():
            state["calls"] += 1
            if state["calls"] == 1:
                raise TimeoutError("timed out")
            return json.dumps(
                {"id": "m", "parameters": {"prompt_template_content": TEMPLATE_THAT_OPENS}}
            ).encode()

        engine = self._engine(responder)
        assert engine._template_opens_thinking() is False
        assert engine._template_opens_thinking() is True

    def test_a_server_without_the_route_is_asked_once_and_never_again(self):
        """The other half. Every provider but TabbyAPI 404s here, and asking a
        *cloud* one before every reply is an egress per reply for an answer
        that cannot change."""
        state = {"calls": 0}

        def responder():
            state["calls"] += 1
            self._http_error(404)()

        engine = self._engine(responder)

        assert engine._template_opens_thinking() is False
        assert engine._template_opens_thinking() is False
        assert state["calls"] == 1, "a missing route was asked for twice"

    def test_a_definite_yes_is_still_asked_only_once(self):
        state = {"calls": 0}

        def responder():
            state["calls"] += 1
            return json.dumps(
                {"id": "m", "parameters": {"prompt_template_content": TEMPLATE_THAT_OPENS}}
            ).encode()

        engine = self._engine(responder)

        assert engine._template_opens_thinking() is True
        assert engine._template_opens_thinking() is True
        assert state["calls"] == 1


@pytest.mark.measure
class TestAgainstTheServerOnThisMachine:
    """The half a fake cannot assert: that a real server does this at all.

    Every test above would pass against a provider that never produces the
    shape — which is exactly how the shape went unnoticed. Skips when nothing
    is listening, because a skip says "not measured here" and a fake reporting
    success says something false.
    """

    def _engine(self):
        import socket

        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", 1234)) != 0:
                pytest.skip("no OpenAI-compatible server on 127.0.0.1:1234")
        return OpenAICompatibleEngine(
            base_url="http://127.0.0.1:1234", api_key="", default_model=""
        )

    def test_the_running_model_is_recognised(self):
        engine = self._engine()
        if not engine._template_opens_thinking():
            pytest.skip("the loaded model's template does not open a think block")

    def test_its_thinking_lands_in_the_panel(self):
        engine = self._engine()
        if not engine._template_opens_thinking():
            pytest.skip("the loaded model's template does not open a think block")

        stream = "".join(
            engine.stream_response("What is 17 times 23? Answer briefly.", "")
        )
        seen = split(stream)

        assert seen[ANSWER].strip(), f"no answer came out at all: {stream[:200]!r}"
        assert "391" in seen[ANSWER]
        assert seen[REASONING].strip(), (
            "the model thought and none of it reached the panel"
        )
        # The failure as reported: the working shown as the reply.
        assert "</think>" not in seen[ANSWER]
        assert len(seen[ANSWER]) < len(stream) / 2, (
            "the answer is most of the stream, which means the monologue is "
            f"still in it: {seen[ANSWER][:200]!r}"
        )
