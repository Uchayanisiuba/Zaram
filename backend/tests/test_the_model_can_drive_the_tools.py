"""Can a local model actually sequence two tool calls? Measured, not assumed.

**Nobody had watched this happen.** The code pack shipped retrieval, tools and a
sandbox on 6 September, and every one of them was verified by a test that called
it directly. Not one of them had been driven by a model, on any model, which is
the same gap `CLAUDE.md` records as this repository's base rate — a complete,
tested subsystem nobody has seen work end to end.

It matters more than a tick in a list, because the answer changes the design of
the loop it sits under. If a 14B cannot emit *search, then read what the search
returned*, then a token budget is generous to the point of irrelevance and the
work belongs somewhere else entirely.

The question is asked so that only a sequence can answer it. `search_code`
returns the matching **line**, so a match on a definition line tells the model
where the function is and nothing about what it returns; the value it is asked
for lives further down the body, reachable only through `read_lines`. A model
that answers after one call is either guessing or wrong, and the assertions can
tell those apart from the transcript.

Run it with::

    pytest backend/tests/test_the_model_can_drive_the_tools.py -m measure -s

It skips itself when Ollama or a suitable model is absent, so the suite stays
offline. `ZARAM_MEASURE_MODEL` names a different one.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import pytest
import requests

from core.context_budget import budget_for, estimate_tokens
from core.tool_loop import (
    TOOL_CALL_MARKER,
    ToolTurn,
    parse_call,
    render_result,
    result_prompt,
    strip_calls,
    tool_instructions,
)
from packs.code import CodeTools

OLLAMA = "http://127.0.0.1:11434"

#: The models this can be driven by, most capable first. Named rather than
#: discovered, because "the first installed model" would silently measure
#: `bge-m3` — an embedder — and report that tool use is impossible.
PREFERRED = ("qwen3-14b-16k", "qwen3-14b-8k", "gemma4-26b-32k")

#: The system prompt, shaped like the one the engine composes: a short identity
#: line and then the tools. Not `identity_preamble` itself — that pulls in user
#: settings, and what is being measured is the tool convention, not identity.
SYSTEM = (
    "You are Zaram, a local assistant. A coding project is open and you can "
    "read its files with the tools below."
)

QUESTION = (
    "In this project, what number does resident_budget_bytes return? "
    "Find it in the code and tell me the value and the file and line it is on."
)

#: The answer, which appears on no line that a search for the symbol matches.
THE_VALUE = "9137000000"


def _installed() -> set[str]:
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=2.0).json()
    except Exception:
        return set()
    names = set()
    for model in tags.get("models") or []:
        name = str(model.get("name") or "")
        names.add(name)
        names.add(name.removesuffix(":latest"))
    return names


def _model() -> Optional[str]:
    named = os.getenv("ZARAM_MEASURE_MODEL")
    installed = _installed()
    if named:
        return named if named in installed else None
    for candidate in PREFERRED:
        if candidate in installed:
            return candidate
    return None


@pytest.fixture
def project(tmp_path):
    """A repository small enough to be honest about what the model did.

    The value is deliberately not on the definition line and not in the file
    name, so `search_code` alone cannot answer the question — and there is a
    decoy carrying a different number, so a model that reads the first file it
    sees is caught rather than accidentally right.
    """
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "residency.py").write_text(
        "\n".join(
            [
                '"""What a chat model may claim beside the embedder."""',
                "",
                "",
                "def _reserve() -> int:",
                "    return 2580000000",
                "",
                "",
                "def resident_budget_bytes() -> int:",
                '    """The budget, in bytes."""',
                "    measured = 12_000_000_000",
                "    # The figure the gate hands a caller.",
                f"    return {THE_VALUE}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "core" / "notes.py").write_text(
        "\n".join(
            [
                "# resident_budget_bytes used to live here.",
                "OLD_BUDGET = 4400000000",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# A small project\n", encoding="utf-8")
    return tmp_path


def _generate(model: str, prompt: str, system: str) -> str:
    """One buffered generation, the way a tool round is buffered."""
    from runtimes.models.engines.ollama_engine import OllamaEngine

    return "".join(OllamaEngine(base_url=OLLAMA).stream_response(prompt, system, model))


@pytest.mark.measure
class TestALocalModelDrivesTheCodeTools:
    def test_it_searches_then_reads_what_it_found(self, project, capsys):
        model = _model()
        if model is None:
            pytest.skip("no suitable Ollama model installed")

        tools = CodeTools(lambda: project)
        offered = [
            {
                "server": "code",
                "name": descriptor.name,
                "description": descriptor.description,
                # Carried because `mcp.list_tools` carries it. Dropping it here
                # would measure a prompt the product does not send — and the
                # first run of this test, before `_argument_line` existed, is
                # what showed the model inventing parameter names without it.
                "input_schema": descriptor.input_schema,
            }
            for descriptor in tools.list_tools()
        ]
        system = SYSTEM + tool_instructions(offered)

        turns: list[ToolTurn] = []
        spent = 0
        prompt = QUESTION
        final = ""
        budget = None

        # The loop as `_run_tool_loop` runs it: buffer, parse, execute, ask
        # again with everything so far, and stop when the reading has spent its
        # share of the window.
        #
        # The budget is taken *after* the first generation on purpose.
        # `loaded_context_length` reads `/api/ps`, and a model that has not been
        # asked anything yet is not resident — measured here, asking first
        # returned the 4,096 fallback for a model loaded with 16,384. In the
        # engine the loop only ever runs after a generation, so this is the
        # order the product has anyway.
        for _ in range(4):
            working = estimate_tokens(system) + estimate_tokens(prompt)
            may_call_again = budget is None or working < budget.handoff_tokens
            text = _generate(model, prompt, system)
            if budget is None:
                budget = budget_for(model, base_url=OLLAMA)
            call = parse_call(text) if may_call_again else None
            if call is None:
                final = strip_calls(text)
                break
            result: Any = tools.call_tool(call.tool, call.arguments)
            turns.append(ToolTurn(call=call, result=result))
            spent += estimate_tokens(render_result(result))
            prompt = result_prompt(QUESTION, turns, may_call_again=True)

        print(f"\nmodel: {model}")
        print(
            f"loaded context: {budget.total_tokens} "
            f"({'measured' if budget.measured else 'assumed'}), "
            f"hands over at: {budget.handoff_tokens} tokens, "
            f"read so far: {spent}"
        )
        for index, turn in enumerate(turns, start=1):
            print(f"  {index}. {turn.call.tool} {turn.call.arguments}")
        print(f"answer: {final[:600]}")

        assert turns, "the model called no tool at all"
        rejected = [
            turn.call.tool
            for turn in turns
            if isinstance(turn.result, dict) and "does not take" in str(turn.result.get("error") or "")
        ]
        assert not rejected, (
            f"argument names were invented for {rejected}; the schema is in the "
            "prompt and should have been followed"
        )
        assert len(turns) >= 2, (
            "the model answered without sequencing: it called "
            f"{[t.call.tool for t in turns]}"
        )
        assert turns[0].call.tool in {"search_code", "list_files"}
        assert any(turn.call.tool == "read_lines" for turn in turns), (
            "nothing was read; the value is not on a line any search returns"
        )
        assert THE_VALUE in final.replace(",", "").replace("_", ""), (
            f"the answer does not contain the value: {final[:300]}"
        )

    def test_the_last_round_still_produces_an_answer_a_person_can_read(self, project):
        """Told not to call another tool, the model may call one anyway.

        **Measured, and it is why the terminal generation is buffered.** On the
        first run of this file `qwen3-14b` was given a failed search and told
        *"Do not call another tool"*, and it emitted
        ``[TOOL_CALL] {"server": "code", "tool": "list_files"…}`` regardless —
        reasonable behaviour from a model whose one tool had just failed, and a
        raw marker on the user's screen if the caller streams it.

        So what is asserted here is not obedience, which cannot be relied on. It
        is that the reply survives `strip_calls` with prose left in it, which is
        what the engine actually depends on.
        """
        model = _model()
        if model is None:
            pytest.skip("no suitable Ollama model installed")

        tools = CodeTools(lambda: project)
        offered = [
            {
                "server": "code",
                "name": d.name,
                "description": d.description,
                "input_schema": d.input_schema,
            }
            for d in tools.list_tools()
        ]
        system = SYSTEM + tool_instructions(offered)

        first = _generate(model, QUESTION, system)
        call = parse_call(first)
        assert call is not None, "the model called nothing on the first pass"

        turn = ToolTurn(call=call, result=tools.call_tool(call.tool, call.arguments))
        answer = _generate(
            model,
            result_prompt(QUESTION, [turn], may_call_again=False),
            system,
        )

        readable = strip_calls(answer)
        assert readable.strip(), "nothing was left once the markers came out"
        assert TOOL_CALL_MARKER not in readable
