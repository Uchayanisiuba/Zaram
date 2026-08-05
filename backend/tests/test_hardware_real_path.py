"""The detection path that actually runs, exercised on the actual host.

Every other hardware test pins a profile or fakes a probe, which is right for
asserting behaviour that must hold on machines the maintainer does not have.
But it is exactly how the fit gate came to be dead code: `_vram_bytes` read
`torch.cuda.get_device_properties`, torch is not present in a packaged build, so
the real path returned None on every user's machine and the residency check
silently never engaged — while a full suite of tests passed against pinned
profiles, forever.

So these run the real profiler against the real machine and assert what must be
true *whatever* that machine is. They are written to be meaningful on a CUDA
box, a Mac, and a CI container with no GPU at all, without skipping — a skipped
test is indistinguishable from an absent one at the moment it matters.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from providers.contracts import DataPolicy, ModelCategory, ModelInfo
from providers.discoverers.hardware import HardwareProfiler
from providers.manager import ProviderManager

GB = 1024**3

HARDWARE_SOURCE = (
    Path(__file__).resolve().parents[1] / "providers" / "discoverers" / "hardware.py"
)


@pytest.fixture(scope="module")
def real_profile():
    """One real probe, shared. Shelling out per test is slow and pointless."""
    return HardwareProfiler().profile()


class TestTheRealPathDoesNotNeedTorch:
    """The regression that made every other hardware test meaningless.

    Asserting on the source rather than on behaviour, because the failure being
    guarded against is a dependency creeping back in — which behaviour cannot
    see when the dependency happens to be installed, as it is in this
    development environment.
    """

    def test_hardware_detection_never_imports_torch(self):
        tree = ast.parse(HARDWARE_SOURCE.read_text(encoding="utf-8"))

        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module.split(".")[0])

        assert "torch" not in imported, (
            "Hardware detection imported torch again. A 528 MB deep-learning "
            "framework must not be what stands between the product and knowing "
            "how much memory the card has — and it does not work in a packaged "
            "build, where the import fails and VRAM silently becomes unknown."
        )


class TestTheRealProbeOnThisMachine:
    def test_vram_is_a_real_number_or_genuinely_unknown(self, real_profile):
        """Never 0, never negative, never absurd."""
        vram = real_profile.vram_bytes

        if vram is None:
            # A legitimate answer: Metal, DirectML, or no accelerator.
            assert real_profile.vram_known is False
            return

        assert vram > 256 * 1024 * 1024, (
            f"Reported {vram} bytes of VRAM. Anything under 256 MB is a "
            "misparse, not a card."
        )
        assert real_profile.vram_known is True

    def test_sizeable_implies_available(self, real_profile):
        """`gpu_available` means "present and measurable", and must agree."""
        assert real_profile.gpu_available is (real_profile.vram_bytes is not None)

    def test_a_named_gpu_is_not_a_placeholder(self, real_profile):
        if real_profile.vram_bytes is None:
            return
        assert real_profile.gpu_name not in ("", "unknown"), (
            "A probe that established capacity should also have established a "
            "name; reporting 'unknown' alongside a real figure means the two "
            "came from different places and one of them is guessing."
        )

    def test_probing_twice_gives_the_same_answer(self):
        """Cached, and stable. A capacity that changes between calls would make
        a fit decision depend on when it was asked."""
        profiler = HardwareProfiler()
        assert profiler._vram_bytes() == profiler._vram_bytes()


class TestSelectionAgainstTheRealCard:
    """The acceptance criterion for M5, run against whatever this host is.

    Both branches assert something real, so the test cannot pass by doing
    nothing on a machine without a GPU.
    """

    def test_a_model_that_cannot_be_co_resident_is_refused(self, real_profile):
        manager = ProviderManager()
        manager._hardware = real_profile

        def model(mid, size, category=ModelCategory.LLM):
            return ModelInfo(
                id=mid,
                display_name=mid.split(":", 1)[-1],
                provider="ollama",
                category=category,
                size_bytes=size,
                available=True,
                data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
            )

        vram = real_profile.vram_bytes
        if vram is None:
            # Unknown capacity must skip the fit test, not fail it — inventing a
            # budget of zero would mean nothing ever fits and the machine gets
            # no default at all.
            manager.catalog.upsert_all([model("ollama:huge", 400 * GB)])
            assert manager.select_default_model() is not None, (
                "With VRAM unknown the fit gate must not run. Refusing here "
                "would be the false-zero bug wearing a different hat."
            )
            return

        # Known capacity: something larger than the whole card must be refused,
        # and a small model must still be chosen.
        oversized = vram + 4 * GB
        manager.catalog.upsert_all(
            [
                model("ollama:embed", 1 * GB, ModelCategory.EMBEDDING),
                model("ollama:oversized", oversized),
                model("ollama:modest", 2 * GB),
            ]
        )

        chosen = manager.select_default_model()
        assert chosen is not None and chosen.id == "ollama:modest"

        refusals = dict(
            (m.id, why) for m, why in manager.rejected_default_candidates()
        )
        assert "ollama:oversized" in refusals
        assert "fit" in refusals["ollama:oversized"]
