"""The tool-choice eval — `docs/PLAN.md` D2 / G5: does the model choose right?

D1 puts the tool listing in front of every plain question on a model that
`ModelsRuntime.chooses_tools` says may choose, and lets the model decide.
Whether that is a good idea *for a given model* is a number, not a belief,
and this is the instrument. Twenty questions, each with the tool a careful
person would reach for first — or **none**, where the right answer is to
answer — put to the resident model with the same listing and convention the
product composes (`tool_instructions`), and scored the way the Berkeley
Function Calling Leaderboard scores: the called tool must match exactly,
its required arguments must be present and sane, and on the *relevance*
slice calling nothing is the only pass. Taken as a method, not as a
dependency: `bfcl-eval` brings its own harness and models, and what is
being measured is *this* listing on *this* machine.

**What the number decides.** `CHOOSES_TOOLS_MIN_BYTES` is provisional at
6 GB. The go/no-go from the plan: a model that over-calls (calls a tool on
a *none* question) on more than one question in five keeps the planner
primary; a model that under-calls badly (answers from memory where a page
had to be read) is not worse than the planner, which would not have called
either. Both rates are printed; `docs/CODE-PACK.md` slice 9 records them
per model and date.

**Text markers, not native calls.** The listing is the marker convention
every model gets; a model on TabbyAPI would also be offered native specs in
the product. The *choice* is the same question either way, and the marker
path is the one every model has.

Run with ``-m measure``; skipped without a model. ``ZARAM_MEASURE_MODEL``
pins one. ``ZARAM_EVAL_ONLY=name`` runs one question.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pytest

from core.tool_loop import ToolCall, parse_call, tool_instructions
from packs.code import CodeTools
from packs.web import READ_PAGE, SEARCH, WebTools
from tests.test_the_model_can_drive_the_tools import _generate, _model, _server_of

pytestmark = pytest.mark.measure


@dataclass
class Question:
    name: str
    text: str
    #: ``"server/tool"`` or ``None`` for the relevance slice.
    expect: Optional[str]
    #: Required arguments, each with a predicate on its value.
    arguments: Dict[str, Callable[[object], bool]] = field(default_factory=dict)
    #: Whether a coding project is "open" for this question — changes the
    #: identity line, as it does in the product.
    project: bool = False


def _nonempty(v: object) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _url_of(host: str) -> Callable[[object], bool]:
    return lambda v: isinstance(v, str) and host in v


QUESTIONS: List[Question] = [
    # --- web.search: current, changing, or outside what a model knows -----
    Question("current_event", "What did the Bank of England decide about rates at its meeting this week?", "web/search", {"query": _nonempty}),
    Question("recent_release", "What is in the latest version of Blender, released this month?", "web/search", {"query": _nonempty}),
    Question("price_today", "How much does a Steam Deck OLED cost right now?", "web/search", {"query": _nonempty}),
    Question("obscure_fact", "Who won the 2026 Booker Prize?", "web/search", {"query": _nonempty}),
    Question("local_business", "Is there a 24-hour pharmacy near Lekki Phase 1 in Lagos?", "web/search", {"query": _nonempty}),
    # --- web.read_page: the person named a page ------------------------
    Question("named_page", "Summarise https://docs.python.org/3/library/contextvars.html in three lines.", "web/read_page", {"url": _url_of("docs.python.org")}),
    Question("named_page_question", "On https://peps.python.org/pep-0567/ what does it say about asyncio tasks?", "web/read_page", {"url": _url_of("peps.python.org")}),
    Question("named_page_compare", "Read https://ollama.com/library/qwen3 and tell me which sizes are listed.", "web/read_page", {"url": _url_of("ollama.com")}),
    # --- code tools: a project is open and the question is about it ------
    Question("code_where_defined", "Where in this project is resident_budget_bytes defined?", "code/search_code", {"query": _nonempty}, project=True),
    Question("code_read_named", "Read core/residency.py and tell me what it returns.", "code/read_lines", {"path": _nonempty}, project=True),
    Question("code_what_files", "What files are in this project?", "code/list_files", {}, project=True),
    Question("code_find_symbol", "Find the class that handles egress policy in this project.", "code/search_code", {"query": _nonempty}, project=True),
    # --- none: the relevance slice — answer, call nothing ----------------
    Question("none_arithmetic", "What is 17 times 23?", None),
    Question("none_rewrite", "Rewrite this to sound friendlier: 'Your invoice is overdue. Pay it.'", None),
    Question("none_translate", "Translate 'the meeting is at ten tomorrow' into French.", None),
    Question("none_explain", "Explain what a context variable is in Python, in two sentences.", None),
    Question("none_stable_fact", "What is the capital of Australia?", None),
    Question("none_draft", "Draft a two-line reply thanking a client for paying early.", None),
    Question("none_opinion", "Which is better for a beginner, Python or JavaScript? One paragraph.", None),
    Question("none_project_general", "In general, what does a repo map do for a coding assistant?", None, project=True),
]


def _tools_listed(project: bool) -> list[dict]:
    """The listing the product would compose: the web pack always, the code
    pack when a project is open. Descriptors in the runtime's dict shape."""
    described: list[dict] = []
    web = WebTools(fetch=lambda *a, **k: b"", search=lambda q: {"results": []}, search_enabled=lambda: True)
    for tool in web.list_tools():
        described.append({"server": "web", "name": tool.name, "description": tool.description, "input_schema": tool.input_schema})
    if project:
        code = CodeTools(lambda: None)
        for tool in code.list_tools():
            if tool.name in ("search_code", "read_lines", "list_files", "find_symbol", "read_file"):
                described.append({"server": "code", "name": tool.name, "description": tool.description, "input_schema": tool.input_schema})
    return described


IDENTITY = "You are Zaram, a local assistant on this person's machine. Answer plainly."
IDENTITY_PROJECT = IDENTITY + " A coding project is open; its files can be read with the tools below."


def _first_call(reply: str) -> Optional[ToolCall]:
    return parse_call(reply)


def _score(q: Question, call: Optional[ToolCall]) -> str:
    """"" when it passed, else why not — BFCL's AST match, in words."""
    if q.expect is None:
        return "" if call is None else f"over-called {call.server}/{call.tool}"
    if call is None:
        return f"under-called: answered without {q.expect}"
    got = f"{call.server}/{call.tool}"
    if got != q.expect:
        return f"wrong tool: {got}, expected {q.expect}"
    for name, ok in q.arguments.items():
        if name not in call.arguments or not ok(call.arguments[name]):
            return f"argument {name} missing or wrong: {call.arguments.get(name)!r}"
    return ""


def test_the_model_chooses_its_tools(capsys):
    model = _model()
    if not model:
        pytest.skip("no model to measure with")
    only = os.getenv("ZARAM_EVAL_ONLY")
    questions = [q for q in QUESTIONS if not only or q.name == only]

    rows: list[tuple[str, str, str, float, str]] = []
    over = under = wrong = passed = 0
    none_count = sum(1 for q in questions if q.expect is None)
    for q in questions:
        system = (IDENTITY_PROJECT if q.project else IDENTITY) + "\n" + tool_instructions(_tools_listed(q.project))
        started = time.monotonic()
        reply = _generate(model, q.text, system)
        took = time.monotonic() - started
        call = _first_call(reply)
        verdict = _score(q, call)
        chose = f"{call.server}/{call.tool}" if call else "—"
        rows.append((q.name, q.expect or "none", chose, took, verdict))
        if not verdict:
            passed += 1
        elif verdict.startswith("over-called"):
            over += 1
        elif verdict.startswith("under-called"):
            under += 1
        else:
            wrong += 1

    lines = [
        "",
        f"tool choice — {model} on {_server_of(model)} — {passed}/{len(questions)} right",
        f"  over-called {over}/{none_count} of the none questions; under-called {under}; wrong tool or argument {wrong}",
        "",
        "| question | expected | chose | time | verdict |",
        "|---|---|---|---|---|",
    ]
    for name, expect, chose, took, verdict in rows:
        lines.append(f"| {name} | {expect} | {chose} | {took:.0f}s | {'PASS' if not verdict else verdict} |")
    with capsys.disabled():
        print("\n".join(lines))

    # The gate the plan names: over-calling more than one in five keeps the
    # planner primary on this model. Reported, never hidden in a green run.
    assert none_count == 0 or over <= max(1, none_count // 5), (
        f"{model} over-called on {over} of {none_count} none questions — "
        "chooses_tools should stay off for it; see the table above"
    )
