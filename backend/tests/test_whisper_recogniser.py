"""The local recogniser, and the one moment it can touch the network.

**Why this lives in ``backend/tests`` and not in ``voice/tests``.** That
directory's conftest skips every test beneath it when the *voice* extra is
absent, which is right for Kokoro and wrong for these: nothing here needs
faster-whisper installed, and the behaviour under test — that weights are never
fetched without the gate saying yes — is exactly the behaviour that must be
guarded on a machine where the extra was never installed.

Every test drives a fake model factory and a gate double. Nothing here opens a
socket, decodes audio, or loads a model. The two things that would be untestable
otherwise are the two that matter: which of the two load paths ran, and whether
the gate was asked before the downloading one.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

import pytest

from core.egress import EgressDenied
from voice.stt import whisper as whisper_module
from voice.stt.base import SpeechRecogniser
from voice.stt.whisper import WhisperConfig, WhisperRecogniser


# --------------------------------------------------------------------------- #
# Doubles
# --------------------------------------------------------------------------- #
class _DenyingGate:
    """Default deny — the product's actual posture on a fresh install."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def check(self, url: str, **kw: Any) -> None:
        self.asked.append(url)
        raise EgressDenied(
            f"Zaram blocked a request to {url}: no policy exists for this domain.",
            host="huggingface.co",
            entry_id="entry-1",
        )


class _AllowingGate:
    """The user has permitted huggingface.co for this."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def check(self, url: str, **kw: Any) -> None:
        self.asked.append(url)
        return None


class _ExplodingGate:
    """Asking it at all is the failure."""

    def check(self, url: str, **kw: Any) -> None:
        raise AssertionError(
            f"The gate was asked about {url}, but the weights were already on disk. "
            "Logging a decision about a request that was never going to happen "
            "fills the egress log with traffic that did not occur."
        )


class _FakeSegment:
    def __init__(self, text: str, start: float, end: float) -> None:
        self.text = text
        self.start = start
        self.end = end


class _FakeInfo:
    def __init__(self, language: Optional[str], duration: float) -> None:
        self.language = language
        self.language_probability = 0.99 if language else None
        self.duration = duration


class _FakeModel:
    """Stands in for ``WhisperModel``.

    ``transcribe`` returns a *generator* of segments, as the real one does.
    A fake returning a list would hide the fact that nothing is decoded until
    the caller consumes it — the property the provider's comment depends on.
    """

    def __init__(self, segments: Optional[list[_FakeSegment]] = None,
                 info: Optional[_FakeInfo] = None) -> None:
        self._segments = segments if segments is not None else [
            _FakeSegment(" Harbour Lane, four twenty five.", 0.0, 2.4)
        ]
        self._info = info or _FakeInfo("en", 2.5)
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, audio: Any, **kwargs: Any):
        self.calls.append({"audio": audio, **kwargs})
        return (s for s in self._segments), self._info


class _Factory:
    """Records which of the two load paths was taken.

    ``cached`` decides whether the offline attempt succeeds, which is the whole
    branch: with weights on disk the gate is never consulted, without them it
    always is.
    """

    def __init__(self, *, cached: bool, model: Optional[_FakeModel] = None) -> None:
        self.cached = cached
        self.model = model or _FakeModel()
        self.offline_attempts = 0
        self.download_attempts = 0

    def __call__(self, *, local_files_only: bool, **kwargs: Any) -> Any:
        if local_files_only:
            self.offline_attempts += 1
            if not self.cached:
                raise OSError("model not found locally; set local_files_only=False")
            return self.model
        self.download_attempts += 1
        return self.model


@pytest.fixture
def faster_whisper_installed(monkeypatch: pytest.MonkeyPatch):
    """Make ``import faster_whisper`` succeed without installing 81 MB.

    The provider's availability gate is that import, so it has to be
    controllable in both directions or half these paths are unreachable in a
    base-install test run.
    """
    monkeypatch.setitem(sys.modules, "faster_whisper", object())


@pytest.fixture
def faster_whisper_absent(monkeypatch: pytest.MonkeyPatch):
    """Make ``import faster_whisper`` fail even where it is installed.

    ``sys.modules[name] = None`` is the documented way to make an import raise;
    it is how the absence path stays testable on a developer machine that has
    the extra.
    """
    monkeypatch.setitem(sys.modules, "faster_whisper", None)


def _recogniser(factory: Any, **overrides: Any) -> WhisperRecogniser:
    config = WhisperConfig(**{"model_size": "base", **overrides})
    return WhisperRecogniser(config=config, model_factory=factory)


# --------------------------------------------------------------------------- #
# The contract it is an implementation of
# --------------------------------------------------------------------------- #
class TestItImplementsTheContract:
    def test_it_is_a_speech_recogniser(self):
        assert issubclass(WhisperRecogniser, SpeechRecogniser)

    def test_the_module_never_imports_faster_whisper_at_module_scope(self):
        """The Kokoro lesson, asserted rather than remembered.

        ``soundfile`` was imported at module scope in the Kokoro provider, so on
        a base install the module died three lines into its own imports and the
        provider could not be constructed even to report itself unavailable. The
        contract's docstring names this; here it is enforced.
        """
        source = (whisper_module.__file__ or "")
        assert source, "the module has no file to read"
        with open(source, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                stripped = line.strip()
                if stripped.startswith(("import faster_whisper", "from faster_whisper")):
                    assert line.startswith((" ", "\t")), (
                        f"{source}:{lineno} imports faster_whisper at module scope. "
                        "That makes the module unimportable on a base install, so "
                        "the recogniser cannot even report itself unavailable."
                    )


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #
class TestWhenTheExtraIsNotInstalled:
    async def test_initialize_does_not_raise(self, faster_whisper_absent):
        recogniser = _recogniser(_Factory(cached=True))
        await recogniser.initialize()  # must not raise
        assert recogniser.is_available() is False

    async def test_the_reason_names_the_install_and_its_size(self, faster_whisper_absent):
        recogniser = _recogniser(_Factory(cached=True))
        await recogniser.initialize()
        report = await recogniser.health_check()

        assert report["available"] is False
        reason = report["reason"]
        assert "zaram[mic]" in reason
        # The size, not just the command. Naming the fix without naming its cost
        # is not a choice a user on metered data can make.
        assert "81 MB" in reason

    async def test_it_never_reaches_the_model_factory(self, faster_whisper_absent):
        factory = _Factory(cached=True)
        recogniser = _recogniser(factory)
        await recogniser.initialize()

        assert factory.offline_attempts == 0
        assert factory.download_attempts == 0


# --------------------------------------------------------------------------- #
# The one moment it can touch the network
# --------------------------------------------------------------------------- #
class TestWeightsAlreadyOnDisk:
    async def test_the_gate_is_not_asked(self, faster_whisper_installed, monkeypatch):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        factory = _Factory(cached=True)
        recogniser = _recogniser(factory)

        await recogniser.initialize()

        assert recogniser.is_available() is True
        assert factory.offline_attempts == 1
        assert factory.download_attempts == 0

    async def test_health_says_nothing_was_downloaded(self, faster_whisper_installed, monkeypatch):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        recogniser = _recogniser(_Factory(cached=True))
        await recogniser.initialize()

        report = await recogniser.health_check()
        assert report["available"] is True
        assert report["weights_downloaded_this_run"] is False
        assert "reason" not in report


class TestWeightsMissing:
    async def test_default_deny_means_nothing_is_downloaded(
        self, faster_whisper_installed, monkeypatch
    ):
        """The whole point of the module, in one assertion.

        This is the trap ``test_egress_chokepoint.py`` documents: voice discovery
        contacted HuggingFace on every boot, unlogged, and the only reason anyone
        noticed was a timeout in the startup log. Here the refusal happens
        *before* the library that would open the socket is constructed.
        """
        gate = _DenyingGate()
        monkeypatch.setattr(whisper_module, "get_gate", lambda: gate)
        factory = _Factory(cached=False)
        recogniser = _recogniser(factory)

        await recogniser.initialize()

        assert gate.asked == ["https://huggingface.co/Systran/faster-whisper-base"]
        assert factory.download_attempts == 0
        assert recogniser.is_available() is False

    async def test_the_refusal_names_the_host_and_the_download_size(
        self, faster_whisper_installed, monkeypatch
    ):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _DenyingGate())
        recogniser = _recogniser(_Factory(cached=False))
        await recogniser.initialize()

        reason = (await recogniser.health_check())["reason"]
        assert "huggingface.co" in reason
        assert "141 MB" in reason  # weighed on disk after a real fetch

    async def test_an_unmeasured_model_says_so_rather_than_guessing(
        self, faster_whisper_installed, monkeypatch
    ):
        """A wrong number is worse than no number, and this is where one would
        be invented. Only tiny and base were measured."""
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _DenyingGate())
        recogniser = _recogniser(_Factory(cached=False), model_size="large-v3")
        await recogniser.initialize()

        reason = (await recogniser.health_check())["reason"]
        assert "MB" not in reason
        assert "size not recorded" in reason

    async def test_permission_lets_the_download_happen(
        self, faster_whisper_installed, monkeypatch
    ):
        gate = _AllowingGate()
        monkeypatch.setattr(whisper_module, "get_gate", lambda: gate)
        factory = _Factory(cached=False)
        recogniser = _recogniser(factory)

        await recogniser.initialize()

        assert gate.asked == ["https://huggingface.co/Systran/faster-whisper-base"]
        assert factory.download_attempts == 1
        assert recogniser.is_available() is True
        assert (await recogniser.health_check())["weights_downloaded_this_run"] is True

    async def test_a_broken_local_directory_is_not_reported_as_a_download(
        self, faster_whisper_installed, monkeypatch, tmp_path
    ):
        """A configured directory that exists cannot be fixed by downloading, so
        offering a download would be a wrong diagnosis rendered confidently."""
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        recogniser = _recogniser(_Factory(cached=False), model_size=str(tmp_path))

        await recogniser.initialize()

        reason = (await recogniser.health_check())["reason"]
        assert "huggingface.co" not in reason
        assert str(tmp_path) in reason


# --------------------------------------------------------------------------- #
# Transcription
# --------------------------------------------------------------------------- #
class TestTranscription:
    async def test_no_model_raises_rather_than_returning_empty_text(self, faster_whisper_absent):
        recogniser = _recogniser(_Factory(cached=True))
        await recogniser.initialize()

        # Silence and breakage produce the same empty string. A caller that
        # cannot tell them apart shows "" as though the user said nothing.
        with pytest.raises(RuntimeError, match="zaram\\[mic\\]"):
            await recogniser.transcribe(b"\x00\x01")

    async def test_empty_audio_is_an_empty_transcript_not_an_error(
        self, faster_whisper_installed, monkeypatch
    ):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        factory = _Factory(cached=True)
        recogniser = _recogniser(factory)
        await recogniser.initialize()

        transcript = await recogniser.transcribe(b"")

        assert transcript.text == ""
        assert transcript.metadata["reason"] == "empty_audio"
        assert factory.model.calls == []

    async def test_segments_carry_their_timings(self, faster_whisper_installed, monkeypatch):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        model = _FakeModel(
            segments=[
                _FakeSegment(" My day rate", 0.0, 1.2),
                _FakeSegment(" is four twenty five.", 1.2, 2.6),
            ],
            info=_FakeInfo("en", 2.6),
        )
        recogniser = _recogniser(_Factory(cached=True, model=model))
        await recogniser.initialize()

        transcript = await recogniser.transcribe(b"audio")

        assert transcript.text == "My day rate is four twenty five."
        assert [s.start_s for s in transcript.segments] == [0.0, 1.2]
        assert transcript.segments[1].end_s == 2.6
        assert transcript.duration_s == 2.6

    async def test_language_is_never_defaulted_to_english(
        self, faster_whisper_installed, monkeypatch
    ):
        """CLAUDE.md's ``vram_bytes`` rule, applied to language: a caller can
        check for None and cannot check for a plausible lie."""
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        model = _FakeModel(info=_FakeInfo(None, 1.0))
        recogniser = _recogniser(_Factory(cached=True, model=model))
        await recogniser.initialize()

        transcript = await recogniser.transcribe(b"audio")

        assert transcript.language is None

    async def test_an_explicit_language_is_passed_through_and_kept(
        self, faster_whisper_installed, monkeypatch
    ):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        model = _FakeModel(info=_FakeInfo(None, 1.0))
        factory = _Factory(cached=True, model=model)
        recogniser = _recogniser(factory)
        await recogniser.initialize()

        transcript = await recogniser.transcribe(b"audio", language="yo")

        assert model.calls[0]["language"] == "yo"
        assert transcript.language == "yo"

    async def test_silence_filtering_is_on(self, faster_whisper_installed, monkeypatch):
        """Whisper hallucinates on silence, and push-to-talk audio is mostly
        silence. Invented words would land in the user's own input box."""
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        factory = _Factory(cached=True)
        recogniser = _recogniser(factory)
        await recogniser.initialize()

        await recogniser.transcribe(b"audio")

        assert factory.model.calls[0]["vad_filter"] is True
        assert factory.model.calls[0]["word_timestamps"] is True

    async def test_the_audio_is_never_written_to_disk(
        self, faster_whisper_installed, monkeypatch
    ):
        """A file-like object reaches the model, not a path.

        Microphone audio is the most sensitive input Zaram takes; a temp file
        would leave it on disk for anything else on the machine to read.
        """
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        factory = _Factory(cached=True)
        recogniser = _recogniser(factory)
        await recogniser.initialize()

        await recogniser.transcribe(b"raw-bytes")

        passed = factory.model.calls[0]["audio"]
        assert hasattr(passed, "read")
        assert passed.read() == b"raw-bytes"


class TestTheHttpSurface:
    """What the microphone button actually talks to.

    Driven against a fake recogniser installed as the lazy singleton, so no
    model is built and the route is exercised on its own terms: what it does
    with an unavailable engine, an oversized body, and a transcript.
    """

    @pytest.fixture
    def client(self, monkeypatch):
        from fastapi.testclient import TestClient

        import main

        # Constructed rather than entered as a context manager, so the app's
        # startup event — which boots the whole kernel — does not run.
        return TestClient(main.app)

    @staticmethod
    def _install(monkeypatch, recogniser: Any) -> None:
        from voice.stt import service

        monkeypatch.setattr(service, "_recogniser", recogniser)

    class _Unavailable:
        def is_available(self) -> bool:
            return False

        async def health_check(self) -> dict:
            return {"available": False, "reason": whisper_module.INSTALL_HINT}

    class _Working:
        def is_available(self) -> bool:
            return True

        async def health_check(self) -> dict:
            return {"available": True}

        async def transcribe(self, audio: bytes, *, language: Optional[str] = None):
            from voice.stt.base import Transcript, TranscriptSegment

            self.audio = audio
            self.language = language
            return Transcript(
                text="Send Harbour Lane the invoice.",
                segments=[TranscriptSegment("Send Harbour Lane the invoice.", 0.0, 1.8)],
                language="en",
                duration_s=1.8,
            )

    def test_unavailable_returns_503_carrying_the_reason(self, client, monkeypatch):
        """The reason is written for a user and reaches them unedited.

        Replacing it with "unavailable" would strip the install command and its
        size, which is the only part of the message they can act on.
        """
        self._install(monkeypatch, self._Unavailable())

        response = client.post("/voice/transcribe", content=b"audio")

        assert response.status_code == 503
        assert "zaram[mic]" in response.json()["detail"]
        assert "81 MB" in response.json()["detail"]

    def test_a_transcript_comes_back_with_its_segments(self, client, monkeypatch):
        self._install(monkeypatch, self._Working())

        response = client.post("/voice/transcribe", content=b"audio-bytes")

        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "Send Harbour Lane the invoice."
        assert body["language"] == "en"
        assert body["segments"] == [
            {"text": "Send Harbour Lane the invoice.", "start_s": 0.0, "end_s": 1.8}
        ]

    def test_an_oversized_recording_is_refused_before_the_model_wakes(
        self, client, monkeypatch
    ):
        import main

        working = self._Working()
        self._install(monkeypatch, working)

        response = client.post(
            "/voice/transcribe", content=b"x" * (main.MAX_TRANSCRIBE_BYTES + 1)
        )

        assert response.status_code == 413
        assert not hasattr(working, "audio")

    def test_health_says_why_when_it_cannot_listen(self, client, monkeypatch):
        self._install(monkeypatch, self._Unavailable())

        body = client.get("/voice/stt/health").json()

        assert body["available"] is False
        assert "zaram[mic]" in body["reason"]


class TestLifecycle:
    async def test_shutdown_releases_the_model(self, faster_whisper_installed, monkeypatch):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        recogniser = _recogniser(_Factory(cached=True))
        await recogniser.initialize()
        assert recogniser.is_available() is True

        await recogniser.shutdown()

        assert recogniser.is_available() is False

    async def test_initialize_is_idempotent(self, faster_whisper_installed, monkeypatch):
        monkeypatch.setattr(whisper_module, "get_gate", lambda: _ExplodingGate())
        factory = _Factory(cached=True)
        recogniser = _recogniser(factory)

        await recogniser.initialize()
        await recogniser.initialize()

        assert factory.offline_attempts == 1
