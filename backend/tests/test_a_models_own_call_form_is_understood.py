"""A model that writes its template's call form instead of the marker is
still calling a tool.

Watched on screen, 12 September 2026: `Qwen3.8-27B` on TabbyAPI, offered the
native function specs, answered *"I'll run the tests first to see what's
failing."* followed by

    <tool_call>
    <function=code__run_command>
    <parameter=runner>
    pytest
    </parameter>
    </function>
    </tool_call>

as text. The parser knew only `[TOOL_CALL] {…}`, so the reply rendered the
XML raw and nothing ran. A minute earlier the same model had used the marker
on the same question.
"""

from __future__ import annotations

from core.tool_loop import parse_call, strip_calls

XML = (
    "I'll run the tests first to see what's failing.\n"
    "<tool_call>\n<function=code__run_command>\n<parameter=runner>\npytest\n</parameter>\n"
    "</function>\n</tool_call>\n"
)


class TestTheQwenForm:
    def test_it_parses_to_the_same_call(self):
        call = parse_call(XML)
        assert call is not None
        assert (call.server, call.tool) == ("code", "run_command")
        assert call.arguments == {"runner": "pytest"}

    def test_typed_values_are_read_as_their_type(self):
        text = (
            "<tool_call><function=code__read_lines>"
            "<parameter=path>src/app.py</parameter>"
            "<parameter=start_line>1</parameter>"
            "<parameter=end_line>400</parameter>"
            "</function></tool_call>"
        )
        call = parse_call(text)
        assert call.arguments == {"path": "src/app.py", "start_line": 1, "end_line": 400}

    def test_a_multiline_value_survives_whole(self):
        text = (
            "<tool_call><function=code__edit_file>"
            "<parameter=path>calc.py</parameter>"
            "<parameter=find>\n    return a - b\n</parameter>"
            "<parameter=replace>\n    return a + b\n</parameter>"
            "</function></tool_call>"
        )
        call = parse_call(text)
        assert call.arguments["find"] == "return a - b"
        assert call.arguments["replace"] == "return a + b"

    def test_a_name_that_is_not_native_is_not_a_call(self):
        assert parse_call("<tool_call><function=run_command></function></tool_call>") is None

    def test_the_marker_still_wins_when_both_appear(self):
        both = '[TOOL_CALL] {"server": "code", "tool": "list_files", "arguments": {}}\n' + XML
        assert parse_call(both).tool == "list_files"

    def test_it_is_stripped_from_what_a_person_reads(self):
        assert strip_calls(XML) == "I'll run the tests first to see what's failing."

    def test_prose_alone_is_still_prose(self):
        assert parse_call("No tools needed; the answer is 4.") is None
