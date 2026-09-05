"""Does the residency check see the *whole* card, or only the first server?

CLAUDE.md: *"a route that requires a swap must be visible in the orb's state.
An invisible swap reads as a broken product"* — and, underneath that, *"a score
built for ranking is not a score for deciding"*, whose general form is that a
number gating a decision has to be the quantity it claims to be.

`ProviderManager._resident_models` asked each registered adapter in turn and
**returned on the first non-``None`` answer**. On a one-server machine that is
indistinguishable from correct. On the maintainer's machine, 28 August 2026, it
was a ten-gigabyte lie:

    nvidia-smi          -> 12288 MiB total, 9493 MiB used, 2623 MiB free
    Ollama /api/ps      -> {"models": []}          <- answered first, so this won
    TabbyAPI /v1/model  -> Qwen3.8-27B-exl3-2.20bpw, holding ~9.5 GB

so `swap_preflight` planned against an empty card and graded a cold start onto
2.6 GB of real headroom as *"fits, just a cold start"*. Every residency
decision on a two-server machine was taken on an input that was wrong by most
of the card.

Two halves to the fix and both are tested here. The map is **merged** rather
than first-wins, and an OpenAI-compatible server can **report at all** — it
could not, which is why merging alone would have changed nothing.

The third thing these pin is the honest treatment of a size nobody knows.
`/v1/model` names the loaded model and carries no memory figure, because the
OpenAI contract has no field for one. That is reported as ``None`` and never as
``0``: a zero is a measurement meaning "holds nothing", which is exactly the
false zero `vram_bytes` already cost this codebase once.
"""
from __future__ import annotations

import io
import urllib.error
from typing import Optional

import pytest

from providers.contracts import (
    CapabilityLocality,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
    ProviderKind,
)
from providers.discoverers.openai_compat import OpenAICompatibleAdapter
from providers.manager import ProviderManager

GB = 1024 ** 3
MIB = 1024 ** 2


class _Server:
    """A local model server that reports what it is holding.

    ``kind`` is absent on purpose in the tests that do not need it: the
    production `_resident_models` treats a provider that does not say what kind
    it is as local, because that is the assumption that fails safe, and the
    fakes should exercise the same path the Ollama adapter does.
    """

    def __init__(self, provider_id: str, resident: Optional[dict]):
        self.provider_id = provider_id
        self._resident = resident
        self.calls = 0

    def resident_models(self, *, timeout: float = 1.0):
        self.calls += 1
        return self._resident


class _Driver:
    """A hardware profiler that can read occupancy off the card."""

    def __init__(self, used_bytes: Optional[int]):
        self._used = used_bytes
        self.calls = 0

    def vram_used_bytes(self) -> Optional[int]:
        self.calls += 1
        return self._used


def _catalogued(
    model_id: str,
    display_name: str,
    provider: str,
    size_gb: Optional[float],
    category=ModelCategory.LLM,
) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=display_name,
        provider=provider,
        category=category,
        locality=CapabilityLocality.LOCAL,
        size_bytes=None if size_gb is None else int(size_gb * GB),
        available=True,
    )


@pytest.fixture
def two_server_machine():
    """The maintainer's machine, in miniature: 12 GB, Ollama and TabbyAPI.

    Budget: 12 GB less the 1.16 GB embedder = ~10.84 GB, with each model
    charged its own weights plus a 20% KV allowance. Re-pinned 31 August 2026
    when that allowance moved off the card and onto the model; see the fixture
    in `test_swap_preflight.py` for why.

    TabbyAPI is discovered under the `lm_studio` provider id, which is a
    historical label rather than a claim about the program: nothing in the
    `/v1/models` contract says which server is on the port. The interface names
    the port. This fixture is the case that proved it — the maintainer runs
    TabbyAPI here and has never installed LM Studio.
    """
    mgr = ProviderManager()
    mgr.catalog.upsert_all([
        _catalogued("ollama:bge-m3:latest", "bge-m3:latest", "ollama", 1.16,
                    ModelCategory.EMBEDDING),
        _catalogued("ollama:gemma3:latest", "gemma3:latest", "ollama", 3.3),
        _catalogued("ollama:qwen3:latest", "qwen3:latest", "ollama", 8.0),
        _catalogued("ollama:llama3.2:latest", "llama3.2:latest", "ollama", 2.0),
        # Discovery cannot size a model served over the OpenAI contract, so the
        # catalog carries no size for it either. That is the real shape.
        _catalogued(
            "lm_studio:Qwen3.8-27B-exl3-2.20bpw",
            "Qwen3.8-27B-exl3-2.20bpw",
            "lm_studio",
            None,
        ),
        _catalogued("lm_studio:small-exl3", "small-exl3", "lm_studio", 3.0),
    ])
    mgr._hardware = HardwareProfile(vram_bytes=12 * GB, gpu_available=True)
    return mgr


class TestTheMapCoversEveryServer:
    def test_a_second_server_is_not_lost_behind_the_first(self, two_server_machine):
        """The defect itself, at the smallest scale that shows it.

        Ollama answers first and answers "nothing loaded". Under the old
        first-wins loop that ended the search, and the 9.5 GB TabbyAPI was
        holding never entered the map at all.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"Qwen3.8-27B-exl3-2.20bpw": None})
        )

        resident = two_server_machine._resident_models()

        assert resident is not None
        assert "Qwen3.8-27B-exl3-2.20bpw" in resident, (
            "the second server's model is what the whole fix is about; an "
            "empty answer from the first server must not end the search"
        )

    def test_a_size_nobody_knows_is_none_and_never_zero(self, two_server_machine):
        """`None` means "resident, size unknown". `0` would mean "holds nothing".

        Collapsing them is the false zero this codebase already paid for in
        `vram_bytes`, and here it points the same way: a tenant recorded as
        zero bytes makes the card look emptier than it is, which is the
        direction that invents room.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"Qwen3.8-27B-exl3-2.20bpw": None})
        )

        resident = two_server_machine._resident_models()

        assert resident["Qwen3.8-27B-exl3-2.20bpw"] is None

    def test_a_local_server_that_cannot_answer_makes_the_whole_map_unknown(
        self, two_server_machine
    ):
        """Partial knowledge is not knowledge for this decision.

        Merging whatever happened to be reachable would report a partial
        picture as a complete one — the same defect, smaller, and pointing the
        same dangerous way. Unknown is a supported answer downstream; a
        confident undercount is not.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(_Server("lm_studio", None))

        assert two_server_machine._resident_models() is None

    def test_a_local_provider_with_no_probe_at_all_is_unknown_not_empty(
        self, two_server_machine
    ):
        """The hole, reopened by a quieter route.

        The old loop `continue`d past a provider with no `resident_models`,
        which is how a local server contributes nothing and nobody is told.
        Skipping it silently is the same invisibility the merge was written to
        end, so it counts as "cannot tell".
        """
        class _Mute:
            provider_id = "lm_studio"

        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(_Mute())

        assert two_server_machine._resident_models() is None

    def test_a_cloud_provider_holds_no_vram_and_is_not_asked(
        self, two_server_machine
    ):
        """A cloud provider cannot occupy this card, so it cannot make the
        answer unknown — and it must not be reached over the network on the
        reply path to establish something already known."""
        class _Cloud:
            provider_id = "openrouter"
            kind = ProviderKind.CLOUD_API

        two_server_machine.registry.register_model_provider(
            _Server("ollama", {"gemma3:latest": int(3.3 * GB)})
        )
        two_server_machine.registry.register_model_provider(_Cloud())

        resident = two_server_machine._resident_models()

        assert resident == {"gemma3:latest": int(3.3 * GB)}


class TestTheDecisionThatWasWrong:
    def test_the_reported_failure_no_longer_grades_a_full_card_as_a_cold_start(
        self, two_server_machine
    ):
        """The measurement from 28 August, replayed.

        12288 MiB total, 9493 MiB used by a TabbyAPI model whose size nothing
        reports, 2623 MiB actually free. Asked to route to a 3.3 GB Ollama
        model, the old code said `load` — "a cold start with room to spare" —
        because the sum it added up contained nothing at all.

        The answer now is silence, and silence is the designed outcome rather
        than a shortfall. It does not fit; nothing Ollama would unload is what
        is in the way, because the occupant belongs to another server that will
        not step aside; and `SwapPlan` has no honest word for that. It is not
        `oversized`, the model is far smaller than the card, and it is not a
        `swap`, because nothing is displaced. Saying the nearest wrong thing is
        what trains a user to stop believing the indicator.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"Qwen3.8-27B-exl3-2.20bpw": None})
        )
        two_server_machine.registry.set_hardware_profiler(_Driver(9493 * MIB))

        plan = two_server_machine.swap_preflight("gemma3:latest")

        assert plan is None, (
            "9.5 GB of a 12 GB card was in use and this reported "
            f"{plan.to_dict() if plan else None}"
        )

    def test_a_second_servers_weights_are_counted_against_the_budget(
        self, two_server_machine
    ):
        """Both servers report sizes, so the attributable sum can answer.

        3.0 GB held by the second server against an ~10.84 GB budget leaves
        ~7.84 GB, and the 8 GB model costs 9.6 with its cache, so it does not
        fit in it. The old code counted only Ollama's empty map and graded this
        `load`.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"small-exl3": int(3.0 * GB)})
        )

        plan = two_server_machine.swap_preflight("qwen3:latest")

        assert plan is None or plan.kind != "load", (
            "3 GB is held by the other server; a 6 GB model does not have "
            f"room to spare: {plan.to_dict() if plan else None}"
        )

    def test_a_swap_names_only_what_this_models_own_server_would_unload(
        self, two_server_machine
    ):
        """Ollama evicts Ollama's tenants and nobody else's.

        It has no way to unload what a second server on the same card is
        holding and does not try — it loads anyway and spills to system RAM.
        Naming a cross-server model here would be the indicator claiming a
        displacement that never happens, which is the same failure the
        `oversized` branch exists to avoid.

        This would have passed before the fix, because the residency map it was
        given never contained the other server's model to name. It is a guard
        on the contract now that the map does contain it.
        """
        two_server_machine.registry.register_model_provider(
            _Server("ollama", {"gemma3:latest": int(3.3 * GB)})
        )
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"small-exl3": int(3.0 * GB)})
        )

        plan = two_server_machine.swap_preflight("qwen3:latest")

        assert plan is not None and plan.kind == "swap"
        assert plan.evicts == ["gemma3:latest"], plan.to_dict()

    def test_the_driver_is_not_consulted_while_the_sum_can_be_made(
        self, two_server_machine
    ):
        """The two sources are alternatives, and the order matters.

        The sum is attributable — it counts Zaram's own tenants and nothing
        else — so an answer does not start moving because an unrelated program
        took a slice of the card. The driver is the fallback for the case the
        sum cannot answer at all, not a second opinion on the case it can.
        """
        driver = _Driver(9493 * MIB)
        two_server_machine.registry.register_model_provider(
            _Server("ollama", {"gemma3:latest": int(3.3 * GB)})
        )
        two_server_machine.registry.set_hardware_profiler(driver)

        assert two_server_machine.swap_preflight("llama3.2:latest").kind == "load"
        assert driver.calls == 0

    def test_an_unsizeable_tenant_cannot_suppress_the_oversized_verdict(
        self, two_server_machine
    ):
        """Whether a model is too big for the card is decidable from capacity.

        It has nothing to do with what is currently loaded, so a tenant whose
        size nobody knows — and with no driver to fall back to — must not
        silence it. The ordering inside `swap_preflight` is what guarantees
        that, which is why it is asserted rather than assumed.
        """
        two_server_machine.catalog.upsert_all([
            _catalogued("ollama:huge:latest", "huge:latest", "ollama", 11.0),
        ])
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"Qwen3.8-27B-exl3-2.20bpw": None})
        )

        plan = two_server_machine.swap_preflight("huge:latest")

        assert plan is not None and plan.kind == "oversized", (
            plan.to_dict() if plan else None
        )

    def test_no_driver_and_no_sum_is_silence_rather_than_a_guess(
        self, two_server_machine
    ):
        """A Mac, or any machine whose occupancy nothing can read.

        Neither source can answer, so there is no answer. The reply is
        unaffected either way; only the indicator is.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"Qwen3.8-27B-exl3-2.20bpw": None})
        )

        assert two_server_machine.swap_preflight("gemma3:latest") is None


class TestAnIdleServerDoesNotBlindTheWholeMachine:
    """The reported symptom: **"Warming up" on every question, still.**

    Reported by the maintainer on 3 September 2026, after the 31 August session
    fixed three other causes of the same label. The state of the machine when
    it was measured: Ollama running and holding the chat model, TabbyAPI
    running on 127.0.0.1:1234 with **nothing loaded**.

    `_resident_models` merges every local provider and one unknown makes the
    merge unknown — deliberately, because a partial picture reported as a
    complete one is the 28 August defect. TabbyAPI's idle 503 was read as
    unknown, so residency was unknowable while a model sat plainly loaded in
    Ollama, `swap_preflight` returned None, no `model_load` event was emitted,
    and the interface's 2.5-second timer guessed a cold model on every single
    message. The `resident` event whose whole job is to cancel that guess was
    never sent at all.

    The LM Studio adapter is registered at that address on every machine, so
    any idle OpenAI-compatible server anywhere on the box was enough to do it.
    """

    def _idle_openai_server(self) -> OpenAICompatibleAdapter:
        adapter = OpenAICompatibleAdapter(
            provider_id="lm_studio",
            base_url="http://127.0.0.1:1234",
            kind=ProviderKind.LOCAL_AI_SERVER,
        )

        def _idle(path, *, timeout):
            raise urllib.error.HTTPError(
                "http://127.0.0.1:1234/v1/model",
                503,
                "Service Unavailable",
                {},
                io.BytesIO(b'{"detail": "No models are currently loaded."}'),
            )

        adapter._get = _idle
        return adapter

    def test_a_resident_model_is_still_reported_resident(self, two_server_machine):
        """The one that matters: the orb can say "Thinking" again."""
        two_server_machine.registry.register_model_provider(
            _Server("ollama", {"qwen3:latest": 9 * GB})
        )
        two_server_machine.registry.register_model_provider(self._idle_openai_server())

        plan = two_server_machine.swap_preflight("qwen3:latest")

        assert plan is not None, (
            "an idle second server made residency unknown, which is what puts "
            "'Warming up' under a model that has not moved"
        )
        assert plan.kind == "resident"

    def test_the_idle_server_contributes_nothing_rather_than_hiding_everything(
        self, two_server_machine
    ):
        two_server_machine.registry.register_model_provider(
            _Server("ollama", {"qwen3:latest": 9 * GB})
        )
        two_server_machine.registry.register_model_provider(self._idle_openai_server())

        assert two_server_machine._resident_models() == {"qwen3:latest": 9 * GB}


class TestTheOpenAICompatibleServerCanReportAtAll:
    """Merging alone would have changed nothing: there was nothing to merge.

    `OpenAICompatibleAdapter` had no `resident_models` at all, so the second
    local server on the machine could not have contributed to the map however
    the map was built.
    """

    def _adapter(self, kind=ProviderKind.LOCAL_AI_SERVER):
        return OpenAICompatibleAdapter(
            provider_id="lm_studio",
            base_url="http://127.0.0.1:1234",
            kind=kind,
        )

    def test_a_loaded_model_is_reported_with_an_unknown_size(self):
        """What TabbyAPI actually returns, trimmed to the field that matters.

        Its `/v1/model` carries the id, the context and cache settings and the
        chat template. There is no memory figure anywhere in it, so the size is
        unknown and says so.
        """
        adapter = self._adapter()
        adapter._get = lambda path, *, timeout: {
            "id": "Qwen3.8-27B-exl3-2.20bpw",
            "object": "model",
            "owned_by": "tabbyAPI",
            "parameters": {"max_seq_len": 16384, "cache_size": 16384},
        }

        assert adapter.resident_models() == {"Qwen3.8-27B-exl3-2.20bpw": None}

    def test_a_refused_connection_means_that_server_holds_nothing(self):
        """The LM Studio adapter is registered whether or not anything runs
        behind it. Treating an absent server as unknowable would silence the
        swap indicator on every Ollama-only machine — so a refused connection
        on a local port is read as the fact it is: nothing is listening.
        """
        adapter = self._adapter()

        def _refuse(path, *, timeout):
            raise urllib.error.URLError(ConnectionRefusedError(10061, "refused"))

        adapter._get = _refuse

        assert adapter.resident_models() == {}

    def test_a_server_that_declines_the_route_is_unknown_not_empty(self):
        """An HTTP error is the server answering, and answering "not here".

        `/v1/model` is TabbyAPI's; a different OpenAI-compatible server may not
        serve it. That is "we cannot read what this one is holding", which is
        not the same as "it is holding nothing" — and the two differ by the
        whole card.
        """
        adapter = self._adapter()

        def _decline(path, *, timeout):
            raise urllib.error.HTTPError(
                "http://127.0.0.1:1234/v1/model", 404, "Not Found", {}, None
            )

        adapter._get = _decline

        assert adapter.resident_models() is None

    def test_an_idle_server_says_so_with_a_status_code_and_is_believed(self):
        """503 plus *"No models are currently loaded"* is an empty card.

        Measured against the running TabbyAPI on 127.0.0.1:1234, 3 September
        2026: with nothing loaded it answers `/v1/model` with **503** and
        ``{"detail": "No models are currently loaded."}``. That is the same
        fact the null-id branch above reports, arriving as a status rather than
        as a field — and reading it as "cannot tell" made residency unknown for
        the whole machine, because one unknown provider makes the merge
        unknown. See `TestAnIdleServerDoesNotBlindTheWholeMachine`.
        """
        adapter = self._adapter()

        def _idle(path, *, timeout):
            raise urllib.error.HTTPError(
                "http://127.0.0.1:1234/v1/model",
                503,
                "Service Unavailable",
                {},
                io.BytesIO(b'{"detail": "No models are currently loaded."}'),
            )

        adapter._get = _idle

        assert adapter.resident_models() == {}

    def test_a_503_that_does_not_say_that_is_still_unknown(self):
        """Busy is not empty, and busy is when a model is most likely loaded.

        503 alone means "not right now" — overloaded, starting up, behind a
        proxy that is between backends. Reading any of those as an empty card
        undercounts the card, which is the error that runs in the dangerous
        direction: an unseen tenant makes a cold start look like it fits.
        """
        adapter = self._adapter()

        def _busy(path, *, timeout):
            raise urllib.error.HTTPError(
                "http://127.0.0.1:1234/v1/model",
                503,
                "Service Unavailable",
                {},
                io.BytesIO(b'{"detail": "Server is warming up, try again."}'),
            )

        adapter._get = _busy

        assert adapter.resident_models() is None

    def test_a_timeout_is_unknown_because_busy_is_when_it_is_most_likely_loaded(
        self,
    ):
        adapter = self._adapter()

        def _hang(path, *, timeout):
            raise TimeoutError("timed out")

        adapter._get = _hang

        assert adapter.resident_models() is None

    def test_a_cloud_provider_answers_without_a_request(self):
        """It holds no VRAM on this machine, and the reply path is not the
        place to establish something already known — nor to make a network
        call for it."""
        adapter = self._adapter(kind=ProviderKind.CLOUD_API)

        def _boom(path, *, timeout):  # pragma: no cover - must not be reached
            raise AssertionError("a cloud provider was asked about local VRAM")

        adapter._get = _boom

        assert adapter.resident_models() == {}


class TestAgainstTheRealServersOnThisMachine:
    """The same claims, measured rather than traced.

    Every test above builds the machine out of fakes, and fakes are how this
    defect survived: `test_local_dispatch.py` stubbed the resolver it was
    testing, and `test_swap_preflight.py` registered exactly one adapter, so
    neither could see a shape with two servers in it. `CLAUDE.md` is explicit
    that "tests green" has repeatedly meant nothing here and that the evidence
    that counts is having watched it work.

    So these run against whatever is actually listening on this machine and
    **skip** when nothing is. A skip says "not measured here", which is a true
    statement; a fake reporting success would be a false one.
    """

    def _tabby(self):
        import socket

        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", 1234)) != 0:
                pytest.skip("no OpenAI-compatible server on 127.0.0.1:1234")
        return OpenAICompatibleAdapter(
            provider_id="lm_studio",
            base_url="http://127.0.0.1:1234",
            kind=ProviderKind.LOCAL_AI_SERVER,
        )

    def test_the_running_server_reports_what_it_is_holding(self):
        """A listening server answers, whether or not it holds anything.

        **This asserted `assert resident` until 3 September 2026, and the
        assumption underneath it — listening implies loaded — was the bug.**
        TabbyAPI idle answers `/v1/model` with 503 and *"No models are
        currently loaded"*, which was read as "cannot tell" and made residency
        unknown for the whole machine. The test passed for as long as the
        maintainer happened to have a model loaded, and went red the moment the
        real state it was blind to was the state of the machine.

        The contract is: a reachable server is never unknown, and any model it
        names carries an unknown size, because no OpenAI-compatible route has a
        field for one.
        """
        resident = self._tabby().resident_models()

        assert resident is not None, (
            "a server is listening, so what it holds is knowable — including "
            "when the answer is nothing"
        )
        for name, size in resident.items():
            assert size is None, (
                "no OpenAI-compatible route carries a memory figure; a number "
                f"here would be an invention: {name} -> {size}"
            )

    def test_both_servers_appear_in_one_map(self):
        from providers.discoverers.ollama import OllamaAdapter

        tabby = self._tabby()
        mgr = ProviderManager()
        mgr.registry.register_model_provider(OllamaAdapter())
        mgr.registry.register_model_provider(tabby)

        resident = mgr._resident_models()

        assert resident is not None, (
            "both servers are reachable, so residency is knowable"
        )
        assert set(resident) >= set(tabby.resident_models() or {}), (
            "the second server's model was dropped from the merged map: "
            f"{resident}"
        )

    def test_the_driver_can_be_read_when_the_sum_cannot(self):
        """The fallback the unsizeable tenant depends on, on real hardware.

        `None` here is a legitimate answer on a Mac or an AMD card, and this
        asserts only that a machine reporting a VRAM *capacity* can also report
        its *occupancy* — the two come from the same driver, and a capacity
        without an occupancy would leave every two-server verdict silent.
        """
        from providers.discoverers.hardware import HardwareProfiler

        profiler = HardwareProfiler()
        if profiler.profile().vram_bytes is None:
            pytest.skip("no card whose capacity can be read")

        assert profiler.vram_used_bytes() is not None


class TestASizelessModelIsStillKnownToBeResident:
    """Warming up on every message, reported by the maintainer 31 August 2026.

    `swap_preflight` asked for the model's size before it asked whether the
    model was already loaded, and returned "cannot determine" when the size was
    unknown. No OpenAI-compatible server reports a size, so for every TabbyAPI
    model that was always: no `model_load` event reached the interface, the
    frontend fell back to its timer, and the orb read **Warming up** on replies
    that arrived in under a second from weights that had not moved.

    Residency is answerable from the residency map alone. It needs no budget
    and no size, and asking the unanswerable question first is what made the
    answerable one unreachable.
    """

    def test_a_resident_model_with_no_size_reports_resident(
        self, two_server_machine
    ):
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {"Qwen3.8-27B-exl3-2.20bpw": None})
        )

        plan = two_server_machine.swap_preflight(
            "lm_studio:Qwen3.8-27B-exl3-2.20bpw"
        )

        assert plan is not None, (
            "returning None here emits no model_load event, and the interface "
            "then guesses that silence means a cold model"
        )
        assert plan.kind == "resident"
        assert plan.requires_swap is False

    def test_a_sizeless_model_that_is_not_loaded_still_says_nothing(
        self, two_server_machine
    ):
        """The guard against fixing this by inventing a verdict.

        Not resident and no size is genuinely undecidable: we cannot say
        whether loading it would displace anything. Silence is correct there,
        and it is a different answer from the one above.
        """
        two_server_machine.registry.register_model_provider(_Server("ollama", {}))
        two_server_machine.registry.register_model_provider(
            _Server("lm_studio", {})
        )

        assert two_server_machine.swap_preflight(
            "lm_studio:Qwen3.8-27B-exl3-2.20bpw"
        ) is None
