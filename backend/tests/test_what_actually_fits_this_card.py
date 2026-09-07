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

import json
import os
import subprocess
import time
from typing import Any, Optional

import pytest
import requests

OLLAMA = "http://127.0.0.1:11434"
TABBY = "http://127.0.0.1:1234"

#: What to ask when the answer does not matter - the call whose only job is to
#: pay the load. Short, and deliberately not a question a model might refuse or
#: think about for a paragraph.
PROMPT = "Name three primary colours. Answer in one short line."

#: How long to wait for a model that has to page 18 GB through a 12 GB card.
LOAD_TIMEOUT = 900.0

#: What TabbyAPI actually takes off the card for `Qwen3.8-27B-exl3-2.20bpw`,
#: plus a margin. exllamav3 does **not** offload to system RAM the way Ollama
#: does - it either fits or it raises - so this is a floor below which a load is
#: not worth attempting.
#:
#: **Measured, and it had to be, because both guesses before it were wrong.** It
#: was 11,000 first, read off the config as 9.61 GiB of weights plus a 64K cache;
#: a Windows desktop holds ~1.3 GB of a 12 GB card for the compositor and the
#: browser, so the most this machine ever offers is ~10,750 MiB and the guard
#: skipped every single time. A threshold no machine can satisfy is not a strict
#: guard, it is a test that never runs - silently, which is the half worth
#: writing down.
#:
#: The real claim, once the load was allowed to happen, is **8.4-8.5 GiB**:
#: 8.41 and 8.48 across two clean runs. A third run, started while Coder was
#: still letting go of the card, read 10.17 GiB and ran at a quarter of the
#: speed - `gpu_split_auto` sizes the cache to whatever it finds, so a
#: contended load is bigger *and* slower. That run is why `SETTLE_TIMEOUT`
#: exists.
TABBY_NEEDS_MIB = 9_500

#: What every rate in the table is measured over, and why it counts so high.
#:
#: **A rate depends on how many tokens it was taken over, and this file found
#: that out the expensive way.** The short prompt above got 240 tokens out of
#: Gemma, 211 out of the 14B and *13* out of Coder, which is terse the way a
#: coding model is - and 18.9 tok/s over 13 tokens read as Coder beating Gemma.
#: Counting to sixty instead got 1,179 tokens out of Gemma and 199 out of
#: Coder, and the order reversed: Gemma 23.3, Coder 14.5. Neither pair was
#: wrong. Both were measurements of different things wearing one column
#: heading, because warm-up amortises over a long run and not over a short one.
#:
#: So the prompt is one no model finishes early and the budget below caps every
#: row at the same number of tokens. Same work, same length, same column.
LONG_PROMPT = "Count from one to two hundred in words, one number per line, nothing else."

#: How many tokens every rate is taken over. Fixed rather than left to the
#: model, which is the whole correction above: `num_predict` on the Ollama side
#: and `max_tokens` on Tabby's, so a terse model and a chatty one are timed
#: over identical output.
RATE_TOKENS = 300

#: Below this, the rate above it is arithmetic rather than a measurement, and
#: printing it beside a figure taken over three hundred tokens invites exactly
#: the comparison it cannot support. Asserted rather than noted, because a
#: caveat in a docstring is not a thing that fails.
MIN_TOKENS_FOR_A_RATE = 50

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


#: How long to wait for the previous row to let go of the card.
#:
#: **Unloading is acknowledged long before the memory comes back.** Ollama drops
#: a model from `/api/ps` and returns, while the `llama-server` process holding
#: the weights takes seconds more to exit - measured on 7 September, with
#: `/api/ps` answering `{"models":[]}` and Windows' counters showing
#: `llama-server` still holding 10.15 GB. The row that ran next loaded into a
#: card that was still occupied and was timed at a quarter of its real speed.
SETTLE_TIMEOUT = 120.0


def _the_card_is_clear_enough(needed_mib: int) -> tuple[bool, str]:
    """Wait for the card to be free, then say whether a measurement means anything.

    Written because the first run of this file measured a card that something
    else was holding. A number produced then is not a fact about the model, and
    the only safe thing to do with it is refuse to produce it.

    **It waits rather than judging instantly, and that is the second bug.** The
    first version read `nvidia-smi` once, the moment the previous test ended -
    which is exactly when the last model is still letting go. Two consecutive
    readings a couple of seconds apart is what tells a card that has settled from
    one that is halfway through freeing 20 GB.
    """
    deadline = time.time() + SETTLE_TIMEOUT
    free = _free_vram_mib()
    if free is None:
        return True, "no NVIDIA driver to ask; measuring anyway"

    while True:
        if free >= needed_mib:
            # Twice, because a card mid-release passes a single check on its way
            # past. The lower of the two is what gets reported, so the figure
            # beside the measurement is never the more flattering one.
            time.sleep(2.0)
            again = _free_vram_mib()
            if again is None or again >= needed_mib:
                return True, f"{min(free, again if again is not None else free)} MiB free"
            free = again
        if time.time() >= deadline:
            return False, (
                f"only {free} MiB free after waiting {SETTLE_TIMEOUT:.0f}s — something "
                "else is holding the card. Windows' own GPU counters name the "
                "process when nvidia-smi will not: "
                "Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage'"
            )
        time.sleep(3.0)
        free = _free_vram_mib()
        if free is None:
            return True, "no NVIDIA driver to ask; measuring anyway"


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


def _generate(model: str, prompt: str, tokens: int) -> dict:
    """Ask Ollama for a fixed number of tokens, with thinking switched off.

    **Thinking off is what makes the rows comparable, and two models failed two
    different ways before it was added.** Capped at 300 tokens,
    `qwen3-14b-16k` spent all of them reasoning about how to count and returned
    `response: ""` with the working in `thinking`. `gemma4-26b-32k` was worse and
    is the reason this helper exists: measured 7 September, `eval_count: 300`,
    `done_reason: "length"`, `response` of length **zero**, and **no `thinking`
    key in the body at all**. Ollama does not surface a thinking block until it
    closes, a block truncated by the budget never closes, and nothing else
    reports it. The tokens were not lost - they are visible in the `context`
    array the same response returns - but no text field carried them, so the
    table printed 22.7 tok/s beside an assertion that the model had said
    nothing. Both statements were true.

    The same request with `think: false` returns 781 characters of counting.
    That is the whole fix.

    None of this was a throughput error: 300 tokens are 300 tokens whichever
    field they land in, and the rates were right throughout. It is a
    *comparability* error - one model deliberating while another answers is two
    workloads under one column heading, which is the same mistake the prompt
    length made, arriving by a second route.

    A model with no thinking mode may reject the field, so it is dropped and the
    call retried rather than the row being lost.
    """
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": tokens},
    }
    answered = requests.post(f"{OLLAMA}/api/generate", json=body, timeout=LOAD_TIMEOUT)
    if answered.status_code >= 400:
        body.pop("think")
        answered = requests.post(f"{OLLAMA}/api/generate", json=body, timeout=LOAD_TIMEOUT)
    answered.raise_for_status()
    return answered.json()


def _resident_entry(model: str, attempts: int = 5) -> Optional[dict]:
    """What `/api/ps` says about a loaded model, or ``None``.

    **Asked more than once, because it has answered `{}` about a model that had
    just replied.** Measured on 7 September: `qwen3-coder-30b-32k` returned 300
    tokens and was absent from `/api/ps` immediately afterwards, so the row
    printed 0.00 GB and no context length beside a perfectly good rate. Ollama's
    bookkeeping and Ollama's answer are not written at the same instant, and one
    reading cannot tell a model that is not resident from one not yet recorded.
    """

    def norm(name: str) -> str:
        name = (name or "").strip().lower()
        return name[: -len(":latest")] if name.endswith(":latest") else name

    for attempt in range(attempts):
        try:
            loaded = requests.get(f"{OLLAMA}/api/ps", timeout=5).json().get("models")
        except Exception:
            loaded = None
        if isinstance(loaded, list):
            for entry in loaded:
                if isinstance(entry, dict) and norm(str(entry.get("name") or "")) == norm(model):
                    return entry
        if attempt + 1 < attempts:
            time.sleep(1.5)
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


def _tabby_model() -> Optional[str]:
    """The model TabbyAPI would serve, or ``None`` when it is not answering.

    `/v1/models` lists what the server *can* load, not what it holds -
    `inline_model_loading` means the first request is what puts it on the card.
    So this is an availability check and never a residency one.
    """
    try:
        listed = requests.get(f"{TABBY}/v1/models", timeout=5).json()
    except Exception:
        return None
    for entry in listed.get("data") or []:
        name = str((entry or {}).get("id") or "").strip()
        if name:
            return name
    return None


def _tabby_context() -> Optional[int]:
    """The window TabbyAPI loaded with, from `/v1/model`, or ``None``.

    The counterpart of the `context_length` the Ollama rows read off `/api/ps`.
    `MILESTONES` records that `context_budget` is Ollama-only and falls back to a
    conservative assumption for anything served here; this is the field that
    would end that, so the table is where it should first be seen to be real.
    """
    try:
        described = requests.get(f"{TABBY}/v1/model", timeout=5).json()
    except Exception:
        return None
    window = ((described or {}).get("parameters") or {}).get("max_seq_len")
    return window if isinstance(window, int) else None


def _tabby_chat(model: str, prompt: str, max_tokens: int = 64) -> dict:
    """One OpenAI-shaped completion. Raises, so a failure is not a slow zero.

    Used for the call that pays the load, where the answer does not matter. It
    is deliberately *not* what the rate is taken from: this server answers with
    ``"usage": null``, so there is no token count on this route at all - which
    the handoff for this work assumed there was, and there is not.
    """
    answered = requests.post(
        f"{TABBY}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": 0.0,
        },
        timeout=LOAD_TIMEOUT,
    )
    answered.raise_for_status()
    return answered.json()


def _tabby_token_count(text: str) -> Optional[int]:
    """How many tokens that text is, according to the model's own tokenizer.

    `/v1/token/encode` rather than a guess or a chunk count. **Counting stream
    chunks is the obvious shortcut and it is wrong**: this server batches, so a
    120-token answer arrived as 39 chunks and would have been reported at a
    third of its real speed. A tokenizer is the only thing that knows.
    """
    try:
        counted = requests.post(f"{TABBY}/v1/token/encode", json={"text": text}, timeout=60).json()
    except Exception:
        return None
    length = counted.get("length")
    return length if isinstance(length, int) and length > 0 else None


def _tabby_generation(model: str, prompt: str) -> tuple[str, float, float]:
    """Stream one answer back; return the text, the seconds spent generating, and
    the seconds spent before the first one arrived.

    **The split is what makes this number comparable to the Ollama rows.** Those
    come from `eval_duration`, which excludes loading the prompt into the cache;
    a wall-clock figure would include it and would be measuring something else
    under the same heading. Timing from the first content chunk to the last is
    the same quantity, obtained the only way this route allows.
    """
    started = time.time()
    first: Optional[float] = None
    last: Optional[float] = None
    text: list[str] = []

    answered = requests.post(
        f"{TABBY}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": RATE_TOKENS,
            "temperature": 0.0,
        },
        timeout=LOAD_TIMEOUT,
        stream=True,
    )
    answered.raise_for_status()
    for line in answered.iter_lines():
        if not line:
            continue
        payload = line.decode("utf-8")
        if not payload.startswith("data: "):
            continue
        body = payload[6:].strip()
        if body == "[DONE]":
            break
        try:
            delta = (json.loads(body).get("choices") or [{}])[0].get("delta") or {}
        except Exception:
            continue
        piece = delta.get("content")
        if piece:
            if first is None:
                first = time.time()
            last = time.time()
            text.append(piece)

    if first is None or last is None:
        return "", 0.0, time.time() - started
    return "".join(text), last - first, first - started


def _tabby_unload() -> None:
    """Put it down again - the same duty `_unload` has for Ollama.

    Swallows everything: the route depends on a loaded container, so calling it
    when nothing is loaded is an error rather than a problem, and a cleanup path
    that can fail a test is a cleanup path that hides the result.
    """
    try:
        requests.post(f"{TABBY}/v1/model/unload", timeout=60)
    except Exception:
        pass


def claimed_on_card_mib(free_before: Optional[int], free_after: Optional[int]) -> Optional[int]:
    """What loading took off the card, in MiB, or ``None`` when it cannot be told.

    No OpenAI-compatible route reports a memory figure - `providers/manager.py`
    calls that shape *"resident, size unknown"* and stores ``None`` for it. The
    driver still knows, though, so the size of the *claim* can be measured as the
    fall in free VRAM even when the share of the model that landed cannot be.

    Three-valued for the same reason `vram_bytes` is. A missing reading answers
    ``None``. So does a *rise* in free memory, which means something else let go
    of the card while the load was happening: the difference is then not this
    model's claim, and reporting 0 would be a confident wrong number where the
    honest one is that the instrument was disturbed.
    """
    if free_before is None or free_after is None:
        return None
    claimed = free_before - free_after
    return claimed if claimed >= 0 else None


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

    def test_a_load_that_takes_memory_reports_what_it_took(self):
        assert claimed_on_card_mib(11_800, 1_100) == 10_700

    def test_an_unreadable_card_gives_no_figure_rather_than_a_zero(self):
        assert claimed_on_card_mib(None, 1_100) is None
        assert claimed_on_card_mib(11_800, None) is None

    def test_memory_freed_during_the_load_invalidates_the_reading(self):
        """Free VRAM going *up* across a load means something else let go.

        The difference is then not this model's claim. Zero would read as "it
        loaded nothing", which is the confident wrong answer; ``None`` says the
        instrument was disturbed, which is what happened.
        """
        assert claimed_on_card_mib(1_100, 4_800) is None


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
            # Downloaded 7 September and never loaded. 30.5B in 128 experts
            # against Gemma's 26B, but only ~3B fire per token, so the
            # prediction on the record is ~50% resident and 18-22 tok/s. The
            # `-32k` suffix is not decoration: the bare `qwen3-coder:30b` has
            # no `num_ctx` and Ollama would serve it at 4,096.
            "qwen3-coder-30b-32k",
        ],
    )
    def test_a_model_loads_and_says_where_it_landed(self, model):
        if model not in _installed():
            pytest.skip(f"{model} is not installed")

        clear, why = _the_card_is_clear_enough(needed_mib=2000)
        if not clear:
            pytest.skip(f"the card is not clear enough to measure: {why}")

        started = time.time()
        body = _generate(model, LONG_PROMPT, RATE_TOKENS)
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

        # Where the tokens went, kept in the table even though `_generate` now
        # asks for all of them to go to the answer. It is the check on that flag
        # having been honoured: `thinking, not yet answering` means the request
        # was ignored, and `nothing` means Ollama is buffering a block that never
        # closed. Both were real on this machine before the flag existed, and a
        # row reporting 22.7 tok/s without saying what they bought is the sort of
        # number this file exists to stop.
        answer = (body.get("response") or "").strip()
        thinking = (body.get("thinking") or "").strip()
        where = "the answer" if answer else ("thinking, not yet answering" if thinking else "nothing")

        print(
            f"\n{model}\n"
            f"  card before      {why}\n"
            f"  size             {total / 1e9:5.2f} GB\n"
            f"  on the card      {vram / 1e9:5.2f} GB  ({share * 100:.0f}%)"
            f"{'  — fully resident' if share >= MOSTLY_RESIDENT else '  — partly in system RAM'}\n"
            f"  context          {entry.get('context_length')}\n"
            f"  load             {load_s:6.1f} s\n"
            f"  generation       {rate:6.1f} tok/s over {eval_count} tokens\n"
            f"  spent on         {where}\n"
            f"  wall clock       {wall:6.1f} s"
        )

        try:
            assert answer, (
                f"{eval_count} tokens generated and none of them reported as an "
                "answer. `think: false` is meant to prevent this: Ollama does "
                "not surface a thinking block until it closes, and one cut off "
                "by the token budget never does"
            )
            assert entry, "the model answered but /api/ps does not list it"
            assert eval_count >= MIN_TOKENS_FOR_A_RATE, (
                f"{rate:.1f} tok/s over {eval_count} tokens is not a rate this "
                "table can print beside one taken over three hundred"
            )
            assert vram <= total, "more on the card than the model is: a bad reading"
        finally:
            # In a `finally` because a failed assertion must not leave 18 GB
            # resident. That is the exact state this file was written to
            # diagnose, and reproducing it here would be its own joke.
            _unload(model)

    def test_tabby_loads_and_says_how_fast_it_runs(self):
        """The one model on this machine that had never been measured at all.

        Two calls, and the split is the point. The first pays the load - with
        `inline_model_loading` the request *is* the load - and the second is
        timed, because a rate taken across a cold start is a measurement of the
        disk. Ollama hands that split over in `load_duration` and
        `eval_duration`; the OpenAI route reports neither, so it has to be done
        by making the call twice.

        What cannot be had at all is the *share* that landed on the card, since
        no OpenAI-compatible route carries a size. The claim can still be
        measured from the driver, and that is what is printed: how much the card
        lost, with the share left explicitly unknown rather than assumed to be
        all of it.
        """
        model = _tabby_model()
        if model is None:
            pytest.skip("TabbyAPI is not answering on 1234")

        clear, why = _the_card_is_clear_enough(needed_mib=TABBY_NEEDS_MIB)
        if not clear:
            pytest.skip(f"the card is not clear enough to measure: {why}")

        free_before = _free_vram_mib()
        try:
            load_started = time.time()
            _tabby_chat(model, PROMPT)
            load_wall = time.time() - load_started
            free_after = _free_vram_mib()

            said, generating, prefill = _tabby_generation(model, LONG_PROMPT)
            tokens = _tabby_token_count(said) or 0
            rate = (tokens / generating) if tokens and generating > 0 else 0.0
            claimed = claimed_on_card_mib(free_before, free_after)
            took = f"{claimed / 1024:5.2f} GiB" if claimed is not None else "unreadable"

            print(
                f"\n{model}  (TabbyAPI)\n"
                f"  card before      {why}\n"
                f"  size             unknown - no OpenAI-compatible route reports one\n"
                f"  claimed off card {took}\n"
                f"  context          {_tabby_context()}\n"
                f"  load             {load_wall:6.1f} s  (first request, cold)\n"
                f"  first token      {prefill:6.1f} s\n"
                f"  generation       {rate:6.1f} tok/s over {tokens} tokens"
            )

            assert said.strip(), "the model loaded but said nothing"
            assert tokens >= MIN_TOKENS_FOR_A_RATE, (
                f"{rate:.1f} tok/s over {tokens} tokens is not a rate this table "
                "can print beside one taken over three hundred"
            )
            assert claimed is None or claimed > 1_000, (
                f"loading took only {claimed} MiB off the card - that is not a 27B "
                "landing, so whatever answered was not what this measured"
            )
        finally:
            _tabby_unload()
