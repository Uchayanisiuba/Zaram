"""What an exchange cost, counted where it is spent and reaching the stream.

Asked for on 7 September 2026: the green-plus / red-minus counter every agentic
tool now shows. The reference was a screenshot of Claude Code, whose header
reads `+8,507 -154` -- **a diff stat, which Zaram cannot produce.** The code
pack's tools are `list_files`, `read_lines` and `search_code`, all read-only,
and `CLAUDE.md` keeps every mutative tool out of scope until v1 ships. Nothing
edits a file. Borrowing the shape and inventing the quantity would be the
"status indicator over hardcoded data" the UI principles forbid, so this counts
the thing that is real and was invisible instead.

Two claims, and the second is the one this file exists for:

**The count comes from where every generation passes.** `execute_step` is the
one route to a model on both the plain and the tool-driven path, so nothing has
to estimate on another layer's behalf. A counter fed from the composer could
only have seen what the user typed -- and a Zaram prompt is mostly recall, so it
would have under-reported the cost by most of it, in the direction that reads as
headroom the user does not have.

**It reaches the stream.** Fifteen complete, tested, unreachable subsystems have
been found in this repository; a usage event that no reply carries would be the
sixteenth, and a factory test alone would pass against one. So these assert on
the events a real `ExecutionEngine.execute` yields.
"""

from __future__ import annotations

import pytest

from core.streaming_events import EventType, StreamEvent

# The doubles live with the tool-loop tests: one model runtime, one MCP double,
# one bootstrapped kernel. Reused rather than rebuilt so there is one definition
# of "a real engine" and these cannot drift apart from it.
from tests.test_the_tool_loop_is_bounded import (  # noqa: E402
    _McpDouble,
    _engine,
    _events,
)


class TestTheArithmeticHolds:
    """The pure half. No engine, no model, true on any machine."""

    def test_both_halves_are_reported_unsigned(self):
        """The sign lives in the field name, never in the value.

        A surface that had to test for a negative would render a minus in front
        of an addition the first time somebody passed the wrong argument, and
        the whole point of the indicator is that the colour is trustworthy.
        """
        event = StreamEvent.usage(added=-40, reclaimed=-9)
        assert event.data["added"] == 0
        assert event.data["reclaimed"] == 0

    def test_a_window_nobody_measured_is_not_quoted_as_one(self):
        """`measured` travels with `limit`, and defaults to not-measured.

        `ContextBudget` falls back to a constant when it cannot read a model's
        real `num_ctx`, and a surface quoting that constant would be stating a
        fallback as a fact about the user's machine -- the failure `vram_bytes`
        refuses by returning ``None`` rather than ``0``.
        """
        assert StreamEvent.usage(added=10).data["measured"] is False
        assert StreamEvent.usage(added=10).data["limit"] is None
        carried = StreamEvent.usage(added=10, limit=16384, measured=True)
        assert carried.data == {
            "added": 10,
            "reclaimed": 0,
            "limit": 16384,
            "measured": True,
        }

    def test_it_serialises_as_the_client_reads_it(self):
        import json

        sent = json.loads(StreamEvent.usage(added=7, reclaimed=3).to_ipc())
        assert sent["type"] == "usage"
        assert sent["data"]["added"] == 7
        assert sent["data"]["reclaimed"] == 3


class TestItReachesTheStream:
    """The half a factory test cannot make true."""

    def test_an_ordinary_reply_reports_what_it_cost(self):
        engine, _model = _engine(["Paris."], _McpDouble())
        out = list(engine.execute("What is the capital of France?"))

        usage = _events(out, EventType.USAGE)
        assert usage, (
            "no usage event reached the stream -- the counter would render "
            "nothing, which is the unreachable-subsystem failure this "
            "repository has found fifteen times"
        )
        assert sum(e.data["added"] for e in usage) > 0

    def test_the_count_includes_the_prompt_and_not_only_the_reply(self):
        """The prompt is most of the cost, and it is the half easily missed.

        A counter that only measured the reply would report a long question
        answered in one word as nearly free. Asserted by asking the same tiny
        question twice with a system prompt that differs only in length: the
        larger one must cost more, which is only true if the input is counted.
        """
        engine, _ = _engine(["ok"], _McpDouble())
        small = list(engine.execute("hi", system_prompt="short"))

        engine2, _ = _engine(["ok"], _McpDouble())
        large = list(engine2.execute("hi", system_prompt="verbose. " * 400))

        spent_small = sum(e.data["added"] for e in _events(small, EventType.USAGE))
        spent_large = sum(e.data["added"] for e in _events(large, EventType.USAGE))
        assert spent_large > spent_small, (
            f"{spent_large} is not more than {spent_small}: the system prompt "
            "is not being counted, so the figure is the reply alone"
        )

    def test_an_image_is_not_charged_as_a_million_tokens(self):
        """Base64 in `input_data` must not be estimated as text.

        `estimate_tokens` charges three characters a token, so a one-megabyte
        photograph would be reported as several hundred thousand tokens against
        a window of sixteen thousand -- a number so wrong it would read as a
        bug in the model rather than in the counter. There is no honest figure
        available here, so images are excluded rather than guessed at.
        """
        from core.execution_engine import _step_tokens

        class _Step:
            input_data = {"prompt": "hello", "images": ["A" * 1_000_000]}

        assert _step_tokens(_Step()) < 100
