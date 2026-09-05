"""The residency gate, pinned to the machine it was measured wrong on.

On 31 August 2026 `/providers/models` reported ``fits_resident: false`` for
**every** chat model installed on the 12 GB card — including one that was, at
that moment, answering questions perfectly well beside the embedder. With every
candidate excluded, auto-routing had an empty field, and the user was told:

    "No model was selected for this request."

Three models installed, one of them running. The gate that exists to keep a
thrashing model from becoming the default had instead rejected everything.

**One charge in two places.** A flat 20% of *card* capacity was held back for
KV cache while models were compared as bare on-disk weights, which exclude that
cache. So the allowance was deducted from the budget and never added to the
model, and the deduction was a constant unrelated to whichever model was being
tested. `qwen3:14b` missed the resulting budget by 0.13 GB.

The allowance now travels with the model — `resident_cost_bytes` — and the
budget is capacity less the embedder. Same two quantities, each counted once.

Every number below is measured, not estimated. Sizes are the exact byte counts
from Ollama's `/api/tags`; residency figures are from `/api/ps` and
`nvidia-smi` on an RTX 3060 12 GB reporting 12288 MiB.

`CLAUDE.md` has warned about the substitution this file guards since before it
happened: *"a download size is not a residency measurement"*, and *"a constant
in a document that a gate reads is the same failure as a wrong `vram_bytes`,
only quieter."*
"""
from __future__ import annotations

import pytest

from providers.contracts import (
    CapabilityLocality,
    DataPolicy,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
)
from providers.manager import ProviderManager

#: nvidia-smi, 31 August 2026: `NVIDIA GeForce RTX 3060, 12288 MiB`.
CARD_BYTES = 12288 * 1024 * 1024

#: `/api/tags`, same day. On-disk weights, which is all discovery ever sees.
BGE_M3 = 1_157_672_605           # 1.16 GB
QWEN3_14B_8K = 9_276_198_244     # 9.28 GB
GEMMA4_26B = 17_987_581_215      # 17.99 GB

#: `/api/ps`. What the card actually held, which discovery never sees.
#:
#: `qwen3-14b-8k` at `num_ctx 8192` is 10.32 GB resident and runs at 31.6 tok/s
#: warm — with `bge-m3` at 0.66 GB beside it, 10.98 GB of 12.88. It fits, and
#: the gate said it did not.
QWEN3_RESIDENT = 10_320_000_000
BGE_M3_RESIDENT = 660_000_000

#: `gemma4` in the same reading: `size` 18_246_617_003 against `size_vram`
#: 9_304_287_476 — Ollama holding half of it and streaming the rest from system
#: RAM. This one genuinely does not fit, and the gate has to keep saying so.
GEMMA4_RESIDENT_TOTAL = 18_246_617_003
GEMMA4_ON_CARD = 9_304_287_476


def _local(model_id: str, size: int, category=ModelCategory.LLM) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=model_id.split(":", 1)[-1],
        provider="ollama",
        category=category,
        locality=CapabilityLocality.LOCAL,
        size_bytes=size,
        available=True,
        data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
    )


def _machine(*models: ModelInfo) -> ProviderManager:
    mgr = ProviderManager()
    mgr.catalog.upsert_all(list(models))
    mgr._hardware = HardwareProfile(vram_bytes=CARD_BYTES, gpu_available=True)
    return mgr


@pytest.fixture
def measured() -> ProviderManager:
    """The machine as it actually was when the gate got it wrong."""
    return _machine(
        _local("ollama:bge-m3:latest", BGE_M3, category=ModelCategory.EMBEDDING),
        _local("ollama:qwen3-14b-8k:latest", QWEN3_14B_8K),
        _local("ollama:gemma4:26b-a4b-it-q4_K_M", GEMMA4_26B),
    )


class TestTheVerdictMatchesTheMeasurement:
    def test_the_model_that_runs_is_reported_as_fitting(self, measured):
        """The defect itself, at the size it actually occurred."""
        model = measured.get_model("ollama:qwen3-14b-8k:latest")

        assert measured.model_fits_resident(model) is True, (
            "this model was measured resident at 10.32 GB beside a 0.66 GB "
            "embedder on a 12.88 GB card, answering at 31.6 tok/s. A gate that "
            "excludes it is not being cautious, it is wrong"
        )

    def test_the_model_that_spills_is_still_reported_as_not_fitting(self, measured):
        """The guard against fixing the gate by disabling it.

        `gemma4:26b-a4b` was measured with 9.30 GB of its 18.25 GB on the card
        and the rest streaming from system RAM. Loosening the budget until
        everything fits would make the verdict useless in the other direction.
        """
        model = measured.get_model("ollama:gemma4:26b-a4b-it-q4_K_M")

        assert measured.model_fits_resident(model) is False
        assert GEMMA4_ON_CARD < GEMMA4_RESIDENT_TOTAL, (
            "the measurement this assertion rests on: Ollama held half of it"
        )

    def test_the_estimate_never_undercuts_the_measurement(self, measured):
        """The allowance must cover the cache it stands in for.

        An allowance smaller than the real cache readmits exactly the model
        that thrashes, which is the failure the gate exists to prevent — and it
        would do it while reporting a confident `fits: true`. Charged against
        the measured resident figure rather than against the on-disk size,
        because the on-disk size is the quantity that was wrong.
        """
        cost = measured.resident_cost_bytes(
            measured.get_model("ollama:qwen3-14b-8k:latest")
        )

        assert cost >= QWEN3_RESIDENT, (
            f"estimated {cost} bytes for a model measured at {QWEN3_RESIDENT}; "
            "the KV allowance is under-charging"
        )

    def test_the_budget_leaves_room_for_the_embedder(self, measured):
        """Recall runs on every exchange, so the embedder is a permanent tenant.

        Still charged on-disk (1.16 GB) rather than resident (0.66 GB), which
        over-reserves by half a gigabyte. That is a known imprecision and it
        errs in the safe direction; it is recorded in `CLAUDE.md` and it is not
        what broke the gate.
        """
        assert measured.resident_budget_bytes() == CARD_BYTES - BGE_M3
        assert BGE_M3_RESIDENT < BGE_M3


class TestAutoRoutingIsNeverEmptyForVram:
    def test_a_model_is_selected_on_the_measured_machine(self, measured):
        """"No model was selected for this request", which is what was seen."""
        chosen = measured.select_default_model()

        assert chosen is not None
        assert chosen.id == "ollama:qwen3-14b-8k:latest", (
            "the model that fits beside the embedder is the one that should "
            "answer, ahead of the larger one that spills"
        )

    def test_the_oversized_model_still_answers_when_it_is_the_only_one(self):
        """Warn, never block.

        `CLAUDE.md`: *"VRAM limits route a task; they do not reject a
        vertical."* A machine holding nothing but an oversized model gets a
        slow answer, not a refusal — and `gemma4` is the only model here that
        can read an image, so refusing would also take vision with it.
        """
        machine = _machine(
            _local("ollama:bge-m3:latest", BGE_M3, category=ModelCategory.EMBEDDING),
            _local("ollama:gemma4:26b-a4b-it-q4_K_M", GEMMA4_26B),
        )

        chosen = machine.select_default_model()

        assert chosen is not None, (
            "residency is a speed judgement and must not produce a refusal; "
            "only consent may do that"
        )
        assert chosen.id == "ollama:gemma4:26b-a4b-it-q4_K_M"
        assert machine.model_fits_resident(chosen) is False, (
            "and it is still honestly reported as not fitting — the relaxation "
            "changes what is offered, never what is claimed about it"
        )

    def test_consent_is_not_relaxed_along_with_residency(self):
        """The escape hatch must not become a route around rule 5.

        A model that does not fit *and* whose provider trains on prompts is
        still refused: the residency retry re-applies `selectable_by_default`
        rather than skipping it. If this ever passes by returning a model, the
        relaxation has become a consent bypass.
        """
        machine = _machine(
            _local("ollama:bge-m3:latest", BGE_M3, category=ModelCategory.EMBEDDING),
            ModelInfo(
                id="freetier:huge",
                display_name="huge",
                provider="freetier",
                category=ModelCategory.LLM,
                locality=CapabilityLocality.CLOUD,
                size_bytes=GEMMA4_26B,
                available=True,
                data_policy=DataPolicy.LOGGED_AND_TRAINED_ON,
            ),
        )

        assert machine.select_default_model() is None
