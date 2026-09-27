"""The tool budget can be varied on the machine that has to measure it.

`DEFAULT_TOOL_BUDGET`'s own comment calls eight "a starting number to be
re-measured, not a constant anybody proved" — and until now nothing could vary
it, which is the quiet way a provisional number becomes permanent. The cost was
real and observed on 27 September 2026: `comfy-mcp` offers 39 tools, eight
slots were already spoken for by the servers attached beside it, and the server
was **attached and invisible** — the model was never shown one of its tools and
so reported, truthfully from what it could see, that it had no way to reach
ComfyUI.

Three things asserted here, and the last two are the ones that matter. A
number is read. Nonsense is *ignored rather than fatal*, because an environment
variable must never be a way to stop the backend booting. And a value below one
is refused, because a budget of zero silently disables every attached server —
the same invisibility this override exists to let somebody measure their way
out of.
"""

from __future__ import annotations

import pytest

from runtimes.mcp.runtime import _budget_from_environment


def test_no_variable_leaves_the_measured_default(monkeypatch):
    monkeypatch.delenv("ZARAM_TOOL_BUDGET", raising=False)
    assert _budget_from_environment(8) == 8


def test_blank_is_the_same_as_unset(monkeypatch):
    monkeypatch.setenv("ZARAM_TOOL_BUDGET", "   ")
    assert _budget_from_environment(8) == 8


def test_a_number_is_read(monkeypatch):
    monkeypatch.setenv("ZARAM_TOOL_BUDGET", "24")
    assert _budget_from_environment(8) == 24


def test_surrounding_space_does_not_defeat_it(monkeypatch):
    monkeypatch.setenv("ZARAM_TOOL_BUDGET", " 40 ")
    assert _budget_from_environment(8) == 40


@pytest.mark.parametrize("nonsense", ["lots", "8.5", "--", "8 tools"])
def test_nonsense_is_ignored_rather_than_fatal(monkeypatch, nonsense):
    """A bad env var must not be a way to stop the backend starting."""
    monkeypatch.setenv("ZARAM_TOOL_BUDGET", nonsense)
    assert _budget_from_environment(8) == 8


@pytest.mark.parametrize("useless", ["0", "-1"])
def test_below_one_is_refused(monkeypatch, useless):
    """Zero is not a smaller budget, it is every attached server turned off."""
    monkeypatch.setenv("ZARAM_TOOL_BUDGET", useless)
    assert _budget_from_environment(8) == 8
