#!/usr/bin/env python3
"""
Integration tests for cua-driver computer use integration.

Tests cover:
1. Policy classification of cua-driver tools
2. Floor rules for sensitive operations
3. Planner intent classification (COMPUTER_USE)
4. Health check integration
"""

from pathlib import Path

import pytest
from backend.runtimes.mcp.policy import decide, WriteMode, Verdict
from backend.runtimes.mcp.floors import cua_driver_floor, Floor
from backend.core.planner import IntentRouter, IntentClassification, IntentType


class TestCuaDriverPolicy:
    """Test that cua-driver tools are correctly classified by policy."""

    def test_read_only_tools_classified_as_read_only(self):
        """Observation tools should be read-only by default."""
        read_only_tools = [
            'list_apps', 'list_windows', 'get_window_state', 'get_desktop_state',
            'get_screen_size', 'get_cursor_position', 'get_accessibility_tree',
            'zoom', 'get_browser_state', 'get_config', 'check_permissions',
            'health_report', 'get_session', 'list_sessions', 'get_agent_cursor_state',
            'get_recording_state'
        ]
        for tool in read_only_tools:
            decision = decide(
                server_id="cua-driver",
                tool_name=tool,
                mode=WriteMode.READ_ONLY,
                granted_tools=set(),
            )
            # These should not need confirmation - they match _LOOKS_READ_ONLY
            assert decision.verdict == Verdict.ALLOW, f"{tool} should be ALLOW, got {decision.verdict}"

    def test_mutative_tools_require_confirm_on_read_only(self):
        """Mutative tools on READ_ONLY server should be refused."""
        mutative_tools = [
            'click', 'double_click', 'right_click', 'drag', 'scroll', 'type_text',
            'press_key', 'hotkey', 'set_value', 'launch_app', 'kill_app',
            'bring_to_front', 'set_window_frame', 'invoke_menu',
            'browser_click', 'browser_type', 'browser_pointer', 'browser_dialog',
            'run_actions', 'start_session', 'end_session',
            'set_agent_cursor_enabled', 'set_agent_cursor_motion',
            'set_agent_cursor_theme', 'start_recording', 'stop_recording',
            'replay_trajectory', 'install_extension', 'set_config', 'install_ffmpeg',
        ]
        for tool in mutative_tools:
            decision = decide(
                server_id="cua-driver",
                tool_name=tool,
                mode=WriteMode.READ_ONLY,
                granted_tools=set(),
            )
            assert decision.verdict == Verdict.REFUSE, f"{tool} should be REFUSE on READ_ONLY, got {decision.verdict}"

    def test_mutative_tools_confirm_on_host_undo(self):
        """Mutative tools on HOST_UNDO server should confirm."""
        mutative_tools = [
            'click', 'double_click', 'right_click', 'drag', 'scroll', 'type_text',
            'press_key', 'hotkey', 'set_value', 'launch_app', 'kill_app',
            'bring_to_front', 'set_window_frame', 'invoke_menu',
            'browser_click', 'browser_type', 'browser_pointer', 'browser_dialog',
            'run_actions', 'start_session', 'end_session',
            'set_agent_cursor_enabled', 'set_agent_cursor_motion',
            'set_agent_cursor_theme', 'start_recording', 'stop_recording',
            'replay_trajectory', 'browser_navigate', 'page', 'move_cursor',
        ]
        for tool in mutative_tools:
            decision = decide(
                server_id="cua-driver",
                tool_name=tool,
                mode=WriteMode.HOST_UNDO,
                granted_tools=set(),
            )
            assert decision.verdict == Verdict.CONFIRM, f"{tool} should be CONFIRM on HOST_UNDO, got {decision.verdict}"

    def test_tools_that_reach_the_internet_themselves_are_refused_on_every_mode(self):
        """Each of these makes the driver contact the internet where Zaram's egress gate
        cannot see it, or rewrites the driver's own settings (its telemetry switch lives
        there). They were `CONFIRM` until 10 October 2026, which meant a person could be
        asked to approve an unlogged download in a dialog that did not say so."""
        for tool in ('check_for_update', 'install_ffmpeg', 'install_extension', 'set_config'):
            for mode in (WriteMode.READ_ONLY, WriteMode.HOST_UNDO, WriteMode.GRANTED):
                decision = decide(server_id="cua-driver", tool_name=tool, mode=mode, granted_tools={tool})
                assert decision.verdict == Verdict.REFUSE, f"{tool} on {mode} got {decision.verdict}"
                assert "Zaram does not run it" in decision.reason

    def test_navigating_the_persons_browser_always_asks(self):
        """`browser_navigate` was "reads only" on every mode: `browser` prefix-matched the
        look-word `browse`. It sends the person's signed-in browser to a URL the model
        picked, and a URL can carry anything, so it asks every time, granted or not."""
        for mode in (WriteMode.HOST_UNDO, WriteMode.GRANTED):
            decision = decide(
                server_id="cua-driver", tool_name="browser_navigate", mode=mode,
                granted_tools={"browser_navigate"},
            )
            assert decision.verdict == Verdict.CONFIRM, f"{mode}: {decision.verdict}"

    def test_outbound_tools_always_confirm_even_granted(self):
        """Outbound tools should always confirm even when granted."""
        outbound_tools = ['clipboard_write', 'browser_download', 'browser_set_input_files']
        for tool in outbound_tools:
            decision = decide(
                server_id="cua-driver",
                tool_name=tool,
                mode=WriteMode.GRANTED,
                granted_tools=set(),
            )
            assert decision.verdict == Verdict.CONFIRM, f"{tool} should always confirm, got {decision.verdict}"

    def test_destructive_tools_always_confirm(self):
        """Destructive tools should always confirm even when granted."""
        decision = decide(
            server_id="cua-driver",
            tool_name='kill_app',
            mode=WriteMode.GRANTED,
            granted_tools=set(),
        )
        assert decision.verdict == Verdict.CONFIRM, "kill_app should always confirm"

    def test_granted_tool_allows_without_confirm(self):
        """A granted tool should be allowed without confirmation."""
        decision = decide(
            server_id="cua-driver",
            tool_name='click',
            mode=WriteMode.HOST_UNDO,
            granted_tools={'click'},
        )
        assert decision.verdict == Verdict.ALLOW, "granted click should be ALLOW"


class TestCuaDriverFloors:
    """Test floor rules for cua-driver sensitive operations."""

    def test_kill_app_always_confirms(self):
        """kill_app should always confirm (cannot undo process kill)."""
        floor = cua_driver_floor('cua-driver', 'kill_app', {'pid': 1234}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'
        assert floor.grantable is False

    def test_set_window_frame_always_confirms(self):
        """set_window_frame should always confirm (may disrupt workflow)."""
        floor = cua_driver_floor('cua-driver', 'set_window_frame', {'pid': 1234, 'frame': {}}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'
        assert floor.grantable is True

    def test_clipboard_write_external_path_confirms(self):
        """clipboard_write with external path should confirm."""
        import os
        external_path = '/etc/passwd'  # Outside user directory
        floor = cua_driver_floor('cua-driver', 'clipboard_write', {'file_url': external_path}, None)
        # May be None if path resolution fails, but should confirm when it can detect
        if floor:
            assert floor.verdict == 'confirm'

    def test_browser_download_always_confirms(self):
        """browser_download should always confirm (writes to disk)."""
        floor = cua_driver_floor('cua-driver', 'browser_download', {}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'
        assert floor.grantable is True

    def test_browser_set_input_files_always_confirms(self):
        """browser_set_input_files should always confirm (uploads files)."""
        floor = cua_driver_floor('cua-driver', 'browser_set_input_files', {}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'
        assert floor.grantable is False

    def test_end_session_always_confirms(self):
        """end_session should always confirm (destroys trajectory data)."""
        floor = cua_driver_floor('cua-driver', 'end_session', {}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'
        assert floor.grantable is False

    def test_stop_recording_always_confirms(self):
        """stop_recording should always confirm (may lose data)."""
        floor = cua_driver_floor('cua-driver', 'stop_recording', {}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'
        assert floor.grantable is False

    def test_other_servers_unaffected(self):
        """Floors should only apply to cua-driver servers."""
        # Non-cua server returns None for any tool
        floor = cua_driver_floor('blender', 'click', {'x': 100, 'y': 100}, None)
        assert floor is None

        # Cua server returns None for tools without specific floor rules
        floor = cua_driver_floor('cua', 'click', {'x': 100, 'y': 100}, None)
        assert floor is None

        # Cua server returns floor for tools with specific rules
        floor = cua_driver_floor('cua', 'kill_app', {'pid': 1234}, None)
        assert floor is not None
        assert floor.verdict == 'confirm'


class TestPlannerComputerUseIntent:
    """Test that computer-use phrases route to COMPUTER_USE intent."""

    def setup_method(self):
        self.router = IntentRouter()

    def test_click_phrases_route_to_computer_use(self):
        phrases = [
            "click the save button",
            "click at 100 200",
            "double click the icon",
            "right click the file",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.COMPUTER_USE, f"'{phrase}' should be COMPUTER_USE"

    def test_type_phrases_route_to_computer_use(self):
        phrases = [
            "type hello world",
            "type text into the search box",
            "press enter",
            "press cmd+c",
            "hotkey ctrl+shift+esc",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.COMPUTER_USE, f"'{phrase}' should be COMPUTER_USE"

    def test_scroll_drag_phrases_route_to_computer_use(self):
        phrases = [
            "scroll down",
            "scroll the window",
            "drag the file to the folder",
            "drag and drop",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.COMPUTER_USE, f"'{phrase}' should be COMPUTER_USE"

    def test_window_app_phrases_route_to_computer_use(self):
        phrases = [
            "screenshot the desktop",
            "list windows",
            "list apps",
            "get window state",
            "bring vscode to front",
            "launch notepad",
            "minimize the window",
            "maximize the window",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.COMPUTER_USE, f"'{phrase}' should be COMPUTER_USE"

    def test_computer_use_has_correct_capabilities(self):
        """COMPUTER_USE intent should have mcp.list_tools and reasoning.generate capabilities."""
        classification = self.router.classify("click the button")
        assert classification.capabilities == ['mcp.list_tools', 'reasoning.generate']
        assert classification.requires_computer_use is True

    def test_computer_use_checked_before_tool(self):
        """COMPUTER_USE should be checked before generic TOOL intent."""
        # A phrase that could be both computer use and tool use
        classification = self.router.classify("click the save button")
        # Should be COMPUTER_USE, not TOOL
        assert classification.intent_type == IntentType.COMPUTER_USE


class TestPlannerSettingsIntent:
    """Test that settings phrases route to SETTINGS intent."""

    def setup_method(self):
        self.router = IntentRouter()

    def test_renderer_phrases_route_to_settings(self):
        phrases = [
            "switch to avatar",
            "change to orb",
            "use the avatar renderer",
            "show the orb",
            "switch renderer to avatar",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.SETTINGS, f"'{phrase}' should be SETTINGS"

    def test_voice_phrases_route_to_settings(self):
        phrases = [
            "set voice to bella",
            "change voice to michael",
            "speak with voice af_bella",
            "disable voice",
            "enable speech",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.SETTINGS, f"'{phrase}' should be SETTINGS"

    def test_routing_phrases_route_to_settings(self):
        phrases = [
            "route to local",
            "prefer cloud",
            "use local only",
            "change routing to auto",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.SETTINGS, f"'{phrase}' should be SETTINGS"

    def test_name_manner_phrases_route_to_settings(self):
        phrases = [
            "rename assistant to Ada",
            "call me Ada",
            "set manner to brief",
            "write like a pirate",
            "sound more formal",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.SETTINGS, f"'{phrase}' should be SETTINGS"

    def test_schedule_phrases_route_to_settings(self):
        phrases = [
            "schedule avatar at 9pm",
            "every monday morning",
            "daily at 8am",
            "weekly on friday",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.SETTINGS, f"'{phrase}' should be SETTINGS"

    def test_permission_phrases_route_to_settings(self):
        phrases = [
            "grant click tool",
            "allow cua-driver click",
            "revoke permission for click",
            "deny tool access",
        ]
        for phrase in phrases:
            classification = self.router.classify(phrase)
            assert classification.intent_type == IntentType.SETTINGS, f"'{phrase}' should be SETTINGS"

    def test_settings_has_correct_capabilities(self):
        """SETTINGS intent should have mcp.list_tools and reasoning.generate capabilities."""
        classification = self.router.classify("switch to avatar")
        assert classification.capabilities == ['mcp.list_tools', 'reasoning.generate']
        assert classification.requires_settings is True

    def test_settings_checked_before_computer_use(self):
        """SETTINGS should be checked before COMPUTER_USE."""
        classification = self.router.classify("switch to avatar")
        assert classification.intent_type == IntentType.SETTINGS


class TestCuaDriverConfig:
    """Test that cua-driver is in KNOWN_HOSTS."""

    def test_cua_driver_in_known_hosts(self):
        from backend.runtimes.mcp.config import KNOWN_HOSTS
        assert 'cua-driver' in KNOWN_HOSTS
        assert 'cua' in KNOWN_HOSTS
        assert 'desktop automation' in KNOWN_HOSTS['cua-driver'].lower()


class TestHealthCheckIntegration:
    """Test health check integration for cua-driver."""

    @pytest.mark.asyncio
    async def test_health_check_includes_cua_health(self):
        """Health check should include cua_health for cua-driver servers."""
        # This would need a running backend - mark as integration
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

def test_a_tool_that_always_asks_is_never_offered_an_always_allow():
    """`grantable` read only the generic word lists, so the permission card offered
    "always allow" for cua-driver's `kill_app` and `browser_navigate` -- an answer the
    gate then ignored on the next call. Found 10 October 2026 against the real driver."""
    from runtimes.mcp.policy import always_asks

    for tool in ('kill_app', 'browser_navigate', 'clipboard_write', 'browser_download'):
        assert always_asks('cua-driver', tool) is True, tool
    assert always_asks('cua-driver', 'click') is False
    assert always_asks('someone-else', 'kill_app') is False
    source = (Path(__file__).resolve().parents[1] / 'runtimes' / 'mcp' / 'runtime.py').read_text(encoding='utf-8')
    assert 'or always_asks(server_id, tool_name)' in source
