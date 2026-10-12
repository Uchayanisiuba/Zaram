"""The voice browser lists the whole Kokoro pack, with what is installed, offline.

10 October 2026. `/voice/voices/active` listed what the Kokoro provider "discovered",
and the provider's discovery asks Hugging Face, which rule 7g forbids doing unprompted.
On a working install it found nothing, so Settings showed an empty list: nothing to
scroll, nothing to test, nothing to download -- while the 54-voice manifest sat in the
bundle and `/voice/voices` answered from it. A provider that has nothing to download
still answers for itself.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from voice import voice_manifest

INSTALLED = {"am_michael", "af_bella", "bm_fable"}


class _Connector:
    """A speech engine as `SpeechRuntime` holds one. Only this is fake: the runtime is real.

    This file first faked the *runtime*, with a `manager` attribute the real one has
    never had -- so it passed while the route answered 500 in the running app.
    """

    def __init__(self, connector_id="kokoro", voices=()):
        self.connector_id = connector_id
        self.connector_type = "local"
        self._voices = list(voices)

    async def list_voices(self):
        return self._voices  # what Kokoro's discovery returns without asking Hugging Face

    async def health_check(self):
        return {"status": "healthy"}


def _speech(connector):
    from runtimes.speech.runtime import SpeechRuntime

    runtime = SpeechRuntime(SimpleNamespace(publish=lambda *a, **k: None))

    async def setup():
        await runtime.register_connector(connector)
        await runtime.set_active_connector(connector.connector_id)

    asyncio.run(setup())
    return SimpleNamespace(speech_runtime=runtime)


@pytest.fixture
def listing(monkeypatch):
    import main

    real = voice_manifest.catalogue
    monkeypatch.setattr(
        voice_manifest,
        "catalogue",
        lambda **kw: real(**{**kw, "cached": lambda voice, backend: voice in INSTALLED}),
    )

    def run(name="kokoro"):
        monkeypatch.setattr(main, "kernel", _speech(_Connector(name)))
        return asyncio.run(main.voice_list_active())

    return run


def test_kokoro_lists_the_whole_pack_even_when_its_own_discovery_found_nothing(listing):
    voices = listing()["voices"]
    assert len(voices) == len(voice_manifest.known_ids()) == 54


def test_each_row_says_whether_it_is_on_this_machine(listing):
    rows = {v["id"]: v for v in listing()["voices"]}
    assert {i for i, v in rows.items() if v["installed"]} == INSTALLED
    assert rows["af_heart"]["installed"] is False


def test_a_voice_behind_a_language_pack_is_listed_and_names_what_it_needs(listing):
    rows = {v["id"]: v for v in listing()["voices"]}
    assert rows["jf_alpha"]["available"] is False and rows["jf_alpha"]["requires"] == "misaki[ja]"
    assert rows["af_heart"]["available"] is True and rows["af_heart"]["requires"] is None


def test_each_row_carries_its_size_so_the_button_can_name_the_price(listing):
    assert all(v["size_bytes"] > 0 for v in listing()["voices"])


def test_the_default_voice_is_marked_so_the_browser_can_say_what_is_speaking(listing):
    defaults = [v["id"] for v in listing()["voices"] if v["default"]]
    assert defaults == ["am_michael"]


def test_a_provider_with_nothing_to_download_answers_for_itself(monkeypatch):
    import main
    from runtimes.speech.contracts import Voice, VoiceGender

    aria = Voice(id="aria", name="Aria", language="English", language_code="en",
                 gender=VoiceGender.FEMALE, provider="breeze_tts")
    monkeypatch.setattr(main, "kernel", _speech(_Connector("breeze_tts", [aria])))
    rows = asyncio.run(main.voice_list_active())["voices"]
    assert [r["id"] for r in rows] == ["aria"]
    assert rows[0]["installed"] is True and rows[0]["available"] is True and rows[0]["gender"] == "female"


def test_the_list_names_the_engine_and_tier_that_speak(listing):
    answer = listing()
    assert answer["provider"] == "kokoro" and answer["active_tier"] == "TIER_4_KOKORO"


def test_no_route_reaches_for_a_runtime_attribute_that_does_not_exist():
    """`SpeechRuntime` has no `manager`. Three routes called it and answered 500 live."""
    from pathlib import Path

    from runtimes.speech.runtime import SpeechRuntime

    assert not hasattr(SpeechRuntime, "manager")
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert "speech_runtime.manager." not in source
