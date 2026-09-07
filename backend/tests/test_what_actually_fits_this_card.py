"""What a model *actually* does when it lands, rather than what its size says.

`MILESTONES` has carried the line *"`gemma4-26b-32k` created, **unverified** — 17
GB exceeds the card by design"* since 6 September. This is the verification, and
it exists as a test rather than as a command somebody ran once because the
question comes back every time the model set changes.

**The number that matters is the split, not the size.** Ollama's `/api/ps`
reports `size` — what the model costs in total — and `size_vram` — how much of
that is on the card. The difference is what spilled into system RAM, and it is
the difference between a model that answers at bandwidth speed and one that
answers over PCIe. A file size cannot tell you which happened; this can.

**A mixture-of-experts model changes what offload costs.** `gemma4:26b-a4b` is
128 experts with 8 firing per token, so the weights that have to move for any
one token are a fraction of the file. A dense model of the same size pays for
all of it. Whether that makes offload survivable on a 12 GB card is exactly the
sort of thing this repository refuses to reason about and insists on measuring.

**Check the instrument before reading its output.** The first attempt at this
measurement, on 7 September, reported 193 MiB free on a card holding nothing
Ollama knew about: a Zaram backend left running from the day before was holding
9.09 GB, `nvidia-smi`'s process list did not show it, and Windows' own GPU
counters named it immediately. A measurement taken then would have recorded
thrashing and called it the model's fault. `_the_card_is_clear_enough` is the
guard that stops that number ever being printed as a result.

Run it with::

    pytest backend/tests/test_what_actually_fits_this_card.py -m measure -s

It skips when Ollama is absent, so the suite stays offline. Every model it
touches is unloaded afterwards — leaving one resident is the failure this file
was written in the middle of diagnosing.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Optional

import pytest
import requests

OLLAMA = "http://127.0.0.1:11434"

#: What to ask. Short, so the measurement is of the model loading and running
#: rather than of how long an answer is; deliberately not a question the model
#: might refuse or think about for a paragraph.
PROMPT = "Name three primary colours. Answer in one short line."

#: How long to wait for a model that has to page 18 GB through a 12 GB card.
LOAD_TIMEOUT = 900.0

#: Below this share of the model on the card, generation is running over PCIe
#: rather than over VRAM bandwidth, and the tokens-per-second figure beside it
#: is the thing that proves it. Not a threshold anything gates on — a label for
#: reading the table.
MOSTLY_RESIDENT = 0.9


def _installed() -> set[str]:
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=2.0).json()
    except Exception:
        return set()
    names: set[str] = set()
    for model in tags.get("models") or []:
        name = str(model.get("name") or "")
        names.add(name)
        names.add(name.removesuffix(":latest"))
    return names


def _free_vram_mib() -> Optional[int]:
    """Free VRAM according to the driver, or ``None`` when it cannot be read.

    From `nvidia-smi`, which ships with the driver — not from torch, which is a
    528 MB dependency that does not exist in a packaged build and which
    `CLAUDE.md` records making `vram_bytes` `None` for every real user.

    ``None`` is a third answer and not a zero: a machine with no NVIDIA card is
    not a machine with a full one, and the guard below treats the two
    differently.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return None
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


def _the_card_is_clear_enough(needed_mib: int) -> tuple[bool, str]:
    """Whether a measurement taken now would mean anything.

    Written because the first run of this file measured a card that something
    else was holding. A number produced then is not a fact about the model, and
    the only safe thing to do with it is refuse to produce it.
    """
    free = _free_vram_mib()
    if free is None:
        return True, "no NVIDIA driver to ask; measuring anyway"
    if free < needed_mib:
        return False, (
            f"only {free} MiB free — something else is holding the card. "
            "Windows' own GPU counters name the process when nvidia-smi will "
            "not: Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage'"
        )
    return True, f"{free} MiB free"


def _unload(model: str) -> None:
    """Put it down again. Leaving a model resident is the bug being diagnosed."""
    try:
        requests.post(
            f"{OLLAMA}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0},
            timeout=60,
        )
    except Exception:
        pass


def _resident_entry(model: str) -> Optional[dict]:
    """What `/api/ps` says about a loaded model, or ``None``."""
    try:
        loaded = requests.get(f"{OLLAMA}/api/ps", timeout=5).json().get("models")
    except Exception:
        return None
    if not isinstance(loaded, list):
        return None

    def norm(name: str) -> str:
        name = (name or "").strip().lower()
        return name[: -len(":latest")] if name.endswith(":latest") else name

    for entry in loaded:
        if isinstance(entry, dict) and norm(str(entry.get("name") or "")) == norm(model):
            return entry
    return None


def on_card(entry: dict) -> float:
    """The share of a loaded model that is on the GPU, 0..1.

    Pure, so the arithmetic that the printed table rests on is checkable without
    a GPU — which is the half of a measurement that survives the machine it was
    taken on. A missing or nonsensical pair answers ``0.0`` rather than raising:
    a model Ollama cannot describe is not a model that is resident, and an
    exception here would take down a measurement of everything else.
    """
    total = entry.get("size")
    vram = entry.get("size_vram")
    if not isinstance(total, int) or not isinstance(vram, int) or total <= 0:
        return 0.0
    return max(0.0, min(1.0, vram / total))


class TestTheArithmeticHolds:
    """The offline half. Asserted on every run, GPU or no GPU."""

    def test_a_fully_resident_model_reports_all_of_it(self):
        assert on_card({"size": 10_000, "size_vram": 10_000}) == 1.0

    def test_a_half_offloaded_model_says_so(self):
        assert on_card({"size": 18_000, "size_vram": 9_000}) == 0.5

    def test_a_model_ollama_cannot_describe_is_not_resident(self):
        """Never an exception, and never a confident zero-sized answer.

        The same three-valued care `vram_bytes` keeps by refusing to report 0
        for a card it cannot read: a missing figure is a missing figure.
        """
        assert on_card({}) == 0.0
        assert on_card({"size": 0, "size_vram": 0}) == 0.0
        assert on_card({"size": "big", "size_vram": None}) == 0.0

    def test_a_reported_overshoot_is_clamped_rather_than_believed(self):
        """`size_vram` above `size` is not 140% resident; it is a bad reading."""
        assert on_card({"size": 100, "size_vram": 140}) == 1.0


@pytest.mark.measure
class TestWhatHappensWhenItLands:
    """The live half. Prints a table; asserts only what is true of any machine."""

    @pytest.mark.parametrize(
        "model",
        [
            # The unverified one, and the reason this file exists.
            "gemma4-26b-32k",
            # The one measured fully resident on 6 September, as the control:
            # a table with one row in it cannot show a difference.
            "qwen3-14b-16k",
        ],
    )
    def test_a_model_loads_and_says_where_it_landed(self, model):
        if model not in _installed():
            pytest.skip(f"{model} is not installed")

        clear, why = _the_card_is_clear_enough(needed_mib=2000)
        if not clear:
            pytest.skip(f"the card is not clear enough to measure: {why}")

        started = time.time()
        answered = requests.post(
            f"{OLLAMA}/api/generate",
            json={"model": model, "prompt": PROMPT, "stream": False},
            timeout=LOAD_TIMEOUT,
        )
        answered.raise_for_status()
        body = answered.json()
        wall = time.time() - started

        entry = _resident_entry(model) or {}
        share = on_card(entry)
        total = entry.get("size") or 0
        vram = entry.get("size_vram") or 0

        # Ollama reports nanoseconds. A rate computed from the whole wall clock
        # would be a measurement of the load, not of the generation, and the two
        # differ by minutes on a model that does not fit.
        eval_count = body.get("eval_count") or 0
        eval_ns = body.get("eval_duration") or 0
        rate = (eval_count / (eval_ns / 1e9)) if eval_count and eval_ns else 0.0
        load_s = (body.get("load_duration") or 0) / 1e9

        print(
            f"\n{model}\n"
            f"  card before      {why}\n"
            f"  size             {total / 1e9:5.2f} GB\n"
            f"  on the card      {vram / 1e9:5.2f} GB  ({share * 100:.0f}%)"
            f"{'  — fully resident' if share >= MOSTLY_RESIDENT else '  — partly in system RAM'}\n"
            f"  context          {entry.get('context_length')}\n"
            f"  load             {load_s:6.1f} s\n"
            f"  generation       {rate:6.1f} tok/s over {eval_count} tokens\n"
            f"  wall clock       {wall:6.1f} s"
        )

        try:
            assert body.get("response", "").strip(), "the model loaded but said nothing"
            assert entry, "the model answered but /api/ps does not list it"
            assert vram <= total, "more on the card than the model is: a bad reading"
        finally:
            # In a `finally` because a failed assertion must not leave 18 GB
            # resident. That is the exact state this file was written to
            # diagnose, and reproducing it here would be its own joke.
            _unload(model)
