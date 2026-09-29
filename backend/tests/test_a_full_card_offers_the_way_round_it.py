"""A full card names the cheapest way round it, and ZCode says its own name.

Two things asked for on 29 September 2026, after a local draw failed on a card
holding a chat model.

**The offer.** `instead_of_the_card` already hands the request to a connected
provider when one exists. When none does, the refusal said *"or connect an
image provider"* — which names no provider, no cost and no screen, and so is
true and useless. Rule 7h is exactly this case: *offer at the moment of doubt,
never make the user choose in advance.* Somebody whose card is full has just
been told a picture is impossible, and that is the one moment naming the
alternative is help rather than an advertisement.

The ranking is the part worth asserting. It is by **what setting it up costs
the person** — a destination to allow, then a free key, then a paid one — and
never by picture quality, because an offer that names the paid provider first
reads as Zaram selling something.

**The name.** `cli.py` set `name="zaram"` on the Typer app and Click took its
usage line from ``sys.argv[0]``, so it introduced itself as `cli.py`. Worse,
`__main__` called `app()` directly and went around `main()` entirely, so the
fix would have applied on no path anybody uses. Two halves each correct alone
with nothing exercising the join — which is why this asserts the join.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from imaging.cloud import RoutedImageProvider
from imaging.contracts import AVAILABLE, Availability


class Cloud:
    """A cloud provider that is or is not set up, with its own remedy."""

    def __init__(self, provider_id: str, *, ok: bool, remedy: str = "") -> None:
        self.provider_id = provider_id
        self.name = f"{provider_id} images"
        self._ok = ok
        self._remedy = remedy

    def availability(self) -> Availability:
        if self._ok:
            return AVAILABLE
        return Availability(ok=False, reason=f"no {self.provider_id}", remedy=self._remedy)


class NoLocal:
    def availability(self) -> Availability:
        return Availability(ok=False, reason="no card")


def routed(*cloud: Cloud) -> RoutedImageProvider:
    return RoutedImageProvider(NoLocal(), list(cloud), prefer=lambda: "local")


class TestTheOfferIsRankedByWhatItCosts:
    def test_a_destination_to_allow_beats_a_free_key(self):
        """Pollinations needs no account at all. Together needs a signup. The
        cheaper one is named even though it is the worse picture."""
        answer = routed(
            Cloud("together", ok=False, remedy="Add a Together key."),
            Cloud("pollinations", ok=False, remedy="Allow images to it."),
        ).the_cloud_route()
        assert answer == "Allow images to it."

    def test_a_free_key_beats_a_paid_one(self):
        answer = routed(
            Cloud("fal", ok=False, remedy="Add a fal key. Paid per image."),
            Cloud("together", ok=False, remedy="Add a Together key. Free."),
        ).the_cloud_route()
        assert "Free" in answer

    def test_the_order_is_not_the_order_they_are_listed_in(self):
        """`CLOUD_PROVIDERS` is ordered by capability — Qwen first, because it
        is the one that edits. That is the right order for *drawing* and the
        wrong one for *offering*, and the two must not be the same list."""
        answer = routed(
            Cloud("fal", ok=False, remedy="paid"),
            Cloud("nvidia_nim", ok=False, remedy="a key"),
            Cloud("pollinations", ok=False, remedy="a click"),
        ).the_cloud_route()
        assert answer == "a click"

    def test_a_provider_nobody_ranked_is_offered_last_rather_than_dropped(self):
        answer = routed(Cloud("somebody_new", ok=False, remedy="the new one")).the_cloud_route()
        assert answer == "the new one"

    def test_nothing_is_offered_when_one_is_already_set_up(self):
        """It simply was not picked for this request. An offer here would be
        an advertisement for something the person already has."""
        answer = routed(
            Cloud("pollinations", ok=True),
            Cloud("together", ok=False, remedy="Add a Together key."),
        ).the_cloud_route()
        assert answer == ""

    def test_nothing_is_offered_when_there_is_nothing_to_offer(self):
        assert routed().the_cloud_route() == ""


class TestTheRefusalCarriesIt:
    def test_the_remedy_names_the_route(self):
        from runtimes.images.runtime import _with_the_cloud_route

        said = _with_the_cloud_route(
            routed(Cloud("pollinations", ok=False, remedy="Allow images to it, and ask again.")),
            "Unload it from that app.",
        )
        assert "Unload it from that app." in said
        assert "Allow images to it" in said

    def test_it_falls_back_to_the_general_sentence(self):
        from runtimes.images.runtime import _with_the_cloud_route

        said = _with_the_cloud_route(routed(), "Close what is using the card.")
        assert "Settings" in said
        assert "ask again" in said

    def test_a_provider_that_raises_does_not_turn_a_refusal_into_a_traceback(self):
        """An offer is the nice part. The refusal is the part that has to
        arrive."""
        from runtimes.images.runtime import _with_the_cloud_route

        class Broken:
            def the_cloud_route(self):
                raise RuntimeError("no")

        said = _with_the_cloud_route(Broken(), "Close what is using the card.")
        assert said.startswith("Close what is using the card.")

    def test_a_provider_with_no_such_method_is_fine(self):
        from runtimes.images.runtime import _with_the_cloud_route

        said = _with_the_cloud_route(object(), "Unload it.")
        assert said.startswith("Unload it.")


class TestZCodeSaysItsOwnName:
    """`python -m cli` is the only path anybody runs, so it is the path tested.

    Asserting on `main()` would have passed against the bug: `__main__` called
    `app()` directly and went round it.
    """

    def run(self, *args: str) -> str:
        backend = Path(__file__).resolve().parent.parent
        done = subprocess.run(
            [sys.executable, "-m", "cli", *args],
            cwd=backend,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        return (done.stdout or "") + (done.stderr or "")

    def test_the_usage_line_is_the_command_not_the_file(self):
        said = self.run("--help")
        assert "zcode" in said
        assert "cli.py" not in said

    def test_an_error_names_the_command_too(self):
        # Where a person actually reads the name: a typo, not `--help`.
        said = self.run("nonsense")
        assert "zcode" in said
        assert "cli.py" not in said


class TestTheLauncherExists:
    """The two-line launcher is the whole fix, so its absence is a failure.

    The reasoning against a `[project.scripts]` entry still holds — the root
    `pyproject.toml` has no `build-system` and Zaram is never `pip install`-ed.
    That is an argument about packaging, and treating it as an argument against
    a name at all is what left this unusable.
    """

    def root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def test_windows_gets_a_launcher(self):
        assert (self.root() / "zcode.cmd").is_file()

    def test_everybody_else_gets_one(self):
        assert (self.root() / "zcode").is_file()

    def test_the_posix_shebang_survives_a_crlf_checkout(self):
        """A shell refuses a script whose shebang line ends in CR, and this
        repository's checkout is CRLF. Written as bytes for that reason."""
        first = (self.root() / "zcode").read_bytes().split(b"\n", 1)[0]
        assert first == b"#!/usr/bin/env sh"
