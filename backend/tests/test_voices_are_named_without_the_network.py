"""The voice list answered empty on every working install, and now does not.

`/voice/voices` asked HuggingFace to name the pack, rule 7g forbids a network
call nobody consented to, and discovery is therefore off — so the Settings
picker was drawn over nothing on a machine that was speaking. The pack is
fixed (Kokoro-82M v1.0 has 54 voices), so the names come from a dated file in
the bundle, as models do; *downloading* one stays a person pressing a button.

The shipped manifest is read directly in the first class, not a fixture, because
what could go wrong is the shipped file: a voice id that disagrees with its own
language or gender, or one that is listed twice.
"""

from __future__ import annotations

import json
import pytest

from voice import voice_manifest


def _shipped():
    with open(voice_manifest.MANIFEST_PATH, encoding="utf-8") as handle:
        return json.load(handle)


class TestTheShippedManifest:
    def test_it_names_the_whole_pack(self):
        voices = _shipped()["voices"]
        assert len(voices) == 54
        assert len({v["id"] for v in voices}) == 54

    def test_it_is_dated(self):
        """A list of things somebody might download is knowledge with a date
        on it, like the model manifest."""
        assert _shipped()["generated"]

    def test_an_id_agrees_with_its_own_language_and_gender(self):
        """Kokoro's prefix is `<language><gender>_<name>`. A row whose fields
        disagree with its id would pick the wrong front end."""
        for voice in _shipped()["voices"]:
            prefix, _, _ = voice["id"].partition("_")
            assert prefix[0] == voice["language_code"], voice["id"]
            assert {"f": "female", "m": "male"}[prefix[1]] == voice["gender"], voice["id"]

    def test_the_shipped_default_is_in_it(self):
        from voice.config import DEFAULT_VOICE

        assert DEFAULT_VOICE in voice_manifest.known_ids()

    def test_no_row_invents_a_grade(self):
        """`grade` is the upstream author's rating or nothing. Four languages
        were not rated at all, and a made-up letter would be a value nobody
        measured."""
        graded = [v for v in _shipped()["voices"] if v["grade"] is not None]
        ungraded = [v["id"] for v in _shipped()["voices"] if v["grade"] is None]
        assert graded and ungraded == ["ef_dora", "em_alex", "em_santa", "pf_dora", "pm_alex", "pm_santa"]


class TestTheCatalogue:
    def test_installed_is_measured_from_the_cache_not_assumed(self):
        found = voice_manifest.catalogue(cached=lambda vid, backend: vid == "am_michael")
        by_id = {v["id"]: v for v in found["voices"]}
        assert by_id["am_michael"]["installed"] is True
        assert by_id["af_heart"]["installed"] is False

    def test_a_voice_that_needs_an_extra_says_what(self):
        found = voice_manifest.catalogue(cached=lambda *_: False)
        by_id = {v["id"]: v for v in found["voices"]}
        assert by_id["af_heart"]["requires"] is None
        assert by_id["bf_emma"]["requires"] is None
        assert by_id["jf_alpha"]["requires"] == "misaki[ja]"
        assert by_id["ff_siwis"]["requires"] == "espeak-ng"

    def test_the_default_is_marked(self):
        found = voice_manifest.catalogue(default_voice="am_michael", cached=lambda *_: False)
        assert [v["id"] for v in found["voices"] if v["default"]] == ["am_michael"]

    def test_a_missing_manifest_is_an_empty_list_not_a_crash(self, tmp_path):
        found = voice_manifest.catalogue(path=str(tmp_path / "gone.json"))
        assert found["voices"] == []

    def test_naming_the_pack_makes_no_network_call(self, monkeypatch):
        """Rule 7g, asserted rather than described: any socket opened while
        the list is built fails the test."""
        import socket

        def boom(*a, **k):
            raise AssertionError("the voice list touched the network")

        monkeypatch.setattr(socket.socket, "connect", boom)
        voice_manifest.catalogue()


class _Gate:
    """Records what it was asked, and can refuse."""

    def __init__(self, deny: bool = False):
        self.asked = []
        self.deny = deny
        self.log = self

    def check(self, url, **kwargs):
        from core.egress import EgressDenied

        self.asked.append(url)
        if self.deny:
            raise EgressDenied("Zaram blocked a request to huggingface.co.", host="huggingface.co")

    def hosts(self):
        return []


@pytest.fixture
def gate(monkeypatch):
    import core.egress as egress_pkg

    g = _Gate()
    monkeypatch.setattr(egress_pkg, "get_gate", lambda: g, raising=False)
    return g


class TestFetching:
    def test_the_gate_is_asked_before_the_download_starts(self, gate, monkeypatch):
        import huggingface_hub

        def download(**kwargs):
            # By the time a byte moves the decision must already be on record.
            assert len(gate.asked) == 1
            return "path"

        monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
        voice_manifest.fetch_voice("af_heart")
        assert gate.asked == ["https://huggingface.co/hexgrad/Kokoro-82M"]

    def test_a_refusal_downloads_nothing(self, gate, monkeypatch):
        import huggingface_hub

        from core.egress import EgressDenied

        gate.deny = True
        monkeypatch.setattr(
            huggingface_hub, "hf_hub_download", lambda **k: pytest.fail("fetched after a refusal")
        )
        with pytest.raises(EgressDenied):
            voice_manifest.fetch_voice("af_heart")

    def test_a_name_the_manifest_never_listed_is_not_fetched(self, gate, monkeypatch):
        import huggingface_hub

        monkeypatch.setattr(
            huggingface_hub, "hf_hub_download",
            lambda **k: pytest.fail("fetched a voice nobody offered"),
        )
        with pytest.raises(KeyError):
            voice_manifest.fetch_voice("../../etc/passwd")
        assert gate.asked == []


class TestTheRoutesAreMounted:
    """A complete, tested, unreachable subsystem is this repository's most
    common defect."""

    @pytest.fixture
    def client(self, gate):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app), gate

    def test_the_list_is_no_longer_empty(self, client):
        http, _ = client
        body = http.get("/voice/voices").json()
        assert len(body["voices"]) == 54
        assert {"id", "installed", "grade", "requires"} <= set(body["voices"][0])

    def test_downloading_an_unlisted_voice_is_a_404_and_asks_nothing(self, client):
        http, g = client
        assert http.post("/voice/voices/not_a_voice/download").status_code == 404
        assert g.asked == []

    def test_downloading_a_listed_voice_goes_through_the_gate(self, client, monkeypatch):
        import huggingface_hub

        http, g = client
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda **k: "p")
        response = http.post("/voice/voices/af_heart/download")
        assert response.status_code == 200
        assert len(g.asked) == 1

    def test_a_blocked_host_is_a_403_with_the_gates_own_sentence(self, client, monkeypatch):
        import huggingface_hub

        http, g = client
        g.deny = True
        monkeypatch.setattr(
            huggingface_hub, "hf_hub_download", lambda **k: pytest.fail("fetched after a refusal")
        )
        response = http.post("/voice/voices/af_heart/download")
        assert response.status_code == 403
        assert "blocked a request to huggingface.co" in response.json()["detail"]
