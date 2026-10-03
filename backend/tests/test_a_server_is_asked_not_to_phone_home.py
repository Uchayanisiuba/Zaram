"""What Zaram asks of a tool server's process, and what it cannot make it do.

**The hole is real and this does not close it.** A stdio MCP server is a
separate program with its own sockets. `EgressGate` intercepts what *Zaram*
sends, so a server with an analytics SDK compiled into it can make a request
this process never sees — and rule 3, *every byte that leaves is logged*, is
unenforceable for that byte. No environment variable changes that.

What an environment variable does change is the SDKs that honour one, which
is most of the ones that end up embedded by accident: PostHog, Sentry, the
Next/Astro/Gatsby build telemetry, `uv`, Homebrew, the .NET CLI.
`DO_NOT_TRACK=1` is a cross-vendor convention rather than a standard, and it
is worth sending for the same reason a cookie banner gets the
privacy-preserving answer — it costs nothing and it is the correct one.

**Why not actually block it.** An outbound firewall rule per child needs
administrator rights on Windows, breaks every server that legitimately
fetches something, and fails *open* when it cannot be applied. That last part
is the disqualifying one: `electron-builder.yml` already records what this
codebase thinks of a guard that fails open — *"the next database somebody
adds is included by default and nobody finds out"* — which is why its payload
became an allow-list. A guard that silently does nothing is worse than a
limitation somebody can read, and so the limitation is written where servers
are attached rather than engineered around.

So these tests assert three things, and the third is the one that matters
most: the opt-outs are sent, the person can override them, and **the claim in
the interface is the narrow true one** rather than the broad false one.
"""

from __future__ import annotations

from runtimes.mcp.child_env import IMPOSED, PASSES, child_environment


class TestTheOptOutsAreSent:
    def test_do_not_track_crosses_on_every_spawn(self):
        child = child_environment({"PATH": "/bin"})
        assert child["DO_NOT_TRACK"] == "1"

    def test_the_vendor_specific_ones_too(self):
        """Because `DO_NOT_TRACK` is young and these are what SDKs read."""
        child = child_environment({})
        assert child["POSTHOG_DISABLED"] == "1"
        assert child["NEXT_TELEMETRY_DISABLED"] == "1"
        assert child["SENTRY_DSN"] == ""

    def test_they_do_not_depend_on_the_parent_having_them(self):
        """Imposed, not inherited.

        The distinction matters: inheriting would mean a machine where the
        maintainer happens to have set `DO_NOT_TRACK` protects its user and
        a machine where they have not does nothing — and the second is
        everybody else's machine.
        """
        assert "DO_NOT_TRACK" not in {name.upper() for name in PASSES}
        assert child_environment({})["DO_NOT_TRACK"] == "1"


class TestThePersonStillDecides:
    def test_a_declared_block_wins(self):
        """Somebody who writes `DO_NOT_TRACK=0` for a server that needs it
        gets what they asked for. Their block is the more specific claim, and
        that rule is unchanged from 15 September."""
        child = child_environment({}, {"DO_NOT_TRACK": "0"})
        assert child["DO_NOT_TRACK"] == "0"

    def test_and_can_restore_a_dsn(self):
        child = child_environment({}, {"SENTRY_DSN": "https://their-own-sentry"})
        assert child["SENTRY_DSN"] == "https://their-own-sentry"


class TestNothingElseChanged:
    """The allow-list is the part that keeps the Spine's key out of a
    stranger's process, and adding to the environment must not weaken it."""

    def test_the_credential_still_never_crosses(self):
        child = child_environment(
            {"PATH": "/bin", "ZARAM_API_SECRET": "the key to the Spine"}
        )
        assert "ZARAM_API_SECRET" not in child

    def test_no_zaram_variable_crosses(self):
        child = child_environment(
            {"ZARAM_DATA_DIR": "/home/u/.zaram", "ZARAM_TOOL_BUDGET": "8"}
        )
        assert not [name for name in child if name.upper().startswith("ZARAM_")]

    def test_what_crosses_is_the_allow_list_plus_exactly_these(self):
        """Whole-dict equality, so a new variable appearing here is a failure.

        A subset check would let the next addition cross unnoticed, which is
        the shape the allow-list exists to refuse.
        """
        child = child_environment({"PATH": "/bin", "OPENAI_API_KEY": "sk-whatever"})
        assert child == {"PATH": "/bin", **IMPOSED}

    def test_none_of_the_imposed_names_is_a_credential(self):
        """Read as a fact about the list rather than an intention about it.

        These are written into somebody else's process, so a value here is
        disclosed by construction. Every one is a flag or an empty string.
        """
        for name, value in IMPOSED.items():
            assert value in {"1", "0", "", "false", "true"}, (
                f"{name} carries {value!r}, which is data rather than a switch"
            )


class TestTheClaimIsTheNarrowTrueOne:
    """`CLAUDE.md`: *never claim absolute security. State what is verifiable.*

    The sentence shown where servers are attached is the one place somebody
    decides whether to trust a stranger's program, so it is the one place the
    limit has to be stated — and asserted, because copy drifts.
    """

    def test_the_interface_says_zaram_cannot_log_another_program(self):
        from pathlib import Path

        section = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "src"
            / "components"
            / "settings"
            / "ToolsSection.tsx"
        ).read_text(encoding="utf-8")
        assert "cannot log what another program sends" in section, (
            "the attach form no longer states the egress limit; a product "
            "that implies every byte is logged while a child process has its "
            "own socket is making the one claim it cannot keep"
        )

    def test_and_says_what_it_does_do(self):
        from pathlib import Path

        section = (
            Path(__file__).resolve().parents[2]
            / "frontend"
            / "src"
            / "components"
            / "settings"
            / "ToolsSection.tsx"
        ).read_text(encoding="utf-8")
        # Naming the limit without naming the mitigation reads as a shrug.
        assert "asks each not to send usage data" in section
