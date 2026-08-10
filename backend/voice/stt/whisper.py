"""faster-whisper, the first :class:`SpeechRecogniser`.

Chosen on the constraints that chose Kokoro for speaking, not on benchmark
scores: MIT licence, runs on CPU so it never competes with a resident local
model for VRAM, and works on Macs and AMD. ``zaram[mic]`` is 81 MB measured —
an order of magnitude under ``zaram[voice]``'s 905 MB, which is the argument for
splitting them rather than shipping one extra that speaks and listens.

**Transcription happens on this machine.** The audio never leaves. What *can*
leave is the first-run weight fetch, and that is the whole subtlety of this
module: ``WhisperModel("base")`` resolves through ``huggingface_hub`` and
downloads 141 MB from huggingface.co without asking anyone. The library opens
its own socket, so the gate cannot carry those bytes — exactly as it cannot
carry DuckDuckGo's. It can still own the **decision**, which is the property
that matters, so this module does what the DuckDuckGo provider does:

1. try the weights **offline** first (``local_files_only=True``). Cached weights
   are the ordinary case after the first run, and that path touches nothing;
2. only when they are absent, ask ``get_gate().check()`` for huggingface.co.
   Under default deny the answer is no, the library is never constructed, and
   the recogniser reports itself unavailable with the download size named —
   the same shape as the OCR extra naming its 321 MB.

That ordering is deliberate. Asking the gate unconditionally would log a
decision about a request that was never going to happen, and a log full of
entries for traffic that did not occur is worth less than no log.

``voice/stt/whisper.py`` is listed in ``NETWORK_LIBRARY_GATED`` in
``test_egress_chokepoint.py``, which asserts both halves of that claim in the
AST rather than trusting the sentence next to the entry.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.egress import EgressDenied, get_gate

from .base import SpeechRecogniser, Transcript, TranscriptSegment

ENV_PREFIX = "ZARAM_STT_"

#: Where faster-whisper's own model names resolve to. Kept here rather than
#: imported from ``faster_whisper.utils`` so the destination can be named in a
#: refusal on a machine where the package is not installed — which is precisely
#: the machine where the user needs to be told what the download would be.
HF_REPO_TEMPLATE = "Systran/faster-whisper-{size}"

#: Download size per model, for the reason attached to a refusal. Only the two
#: that were actually measured are here. An unmeasured size is left out rather
#: than guessed: a wrong number on a metered connection is worse than no number,
#: and ``_download_note`` says so in words instead of inventing one.
#:
#: ``base`` is 141 MB weighed on disk after a real fetch on 10 August 2026 —
#: 138.5 MB of ``model.bin`` plus the tokenizer and vocabulary. The 145 MB
#: carried in from the packaging notes was close, and is corrected here rather
#: than left standing, because the whole point of the number is that someone on
#: metered data can trust it.
MEASURED_MODEL_MB = {
    "tiny": 75,
    "base": 141,
}

#: What to install, with what it costs. CLAUDE.md: naming the fix without naming
#: its cost is not a choice the user can make on a metered connection.
INSTALL_HINT = "Listening needs the mic extra: pip install zaram[mic] (81 MB, one time)"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class WhisperConfig:
    """Settings for the local recogniser.

    ``device`` and ``compute_type`` default to CPU int8 and that is a product
    decision, not a performance oversight. Speech must not take VRAM away from
    the chat model — the constraint that chose Kokoro — and ``base`` on int8
    transcribes a push-to-talk utterance in well under the time it takes to read
    the reply it produces.
    """

    model_size: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"
    #: Where weights live. ``None`` means faster-whisper's own default, which is
    #: the HuggingFace cache — shared with anything else on the machine that has
    #: already fetched the same model, so the offline path succeeds more often
    #: than a private directory would.
    download_root: Optional[str] = None
    beam_size: int = 5
    #: On, because the segments are what let a caller show *when* something was
    #: heard, and the contract mirrors ``SpeechTiming`` for that reason.
    word_timestamps: bool = True
    #: On, because Whisper hallucinates on silence — "Thank you.", subtitle
    #: credits — and push-to-talk audio is mostly leading and trailing silence.
    #: Inventing words into the user's own input box is the failure rule 9 is
    #: about, one surface earlier.
    vad_filter: bool = True

    @classmethod
    def load(cls, **overrides: object) -> "WhisperConfig":
        config = cls(
            model_size=os.getenv(f"{ENV_PREFIX}MODEL", cls.model_size),
            device=os.getenv(f"{ENV_PREFIX}DEVICE", cls.device),
            compute_type=os.getenv(f"{ENV_PREFIX}COMPUTE_TYPE", cls.compute_type),
            download_root=os.getenv(f"{ENV_PREFIX}DOWNLOAD_ROOT") or None,
            beam_size=int(os.getenv(f"{ENV_PREFIX}BEAM_SIZE", cls.beam_size)),
            word_timestamps=_env_bool(f"{ENV_PREFIX}WORD_TIMESTAMPS", cls.word_timestamps),
            vad_filter=_env_bool(f"{ENV_PREFIX}VAD", cls.vad_filter),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        return config


def _default_model_factory(
    *,
    model_size_or_path: str,
    device: str,
    compute_type: str,
    download_root: Optional[str],
    local_files_only: bool,
) -> Any:
    """Build a real ``WhisperModel``. Lazy import keeps faster-whisper optional.

    A top-level import here would make the module unimportable on a base
    install, so the recogniser could not be constructed even to report itself
    unavailable — the exact failure the Kokoro provider hit with ``soundfile``,
    written into the contract's docstring and worth not repeating.
    """
    from faster_whisper import WhisperModel

    return WhisperModel(
        model_size_or_path,
        device=device,
        compute_type=compute_type,
        download_root=download_root,
        local_files_only=local_files_only,
    )


def _download_note(model_size: str) -> str:
    """How big the fetch would be, or an honest admission that we do not know."""
    megabytes = MEASURED_MODEL_MB.get(model_size)
    if megabytes is not None:
        return f"about {megabytes} MB, one time"
    return "size not recorded for this model, one time"


class WhisperRecogniser(SpeechRecogniser):
    """Local speech-to-text. Never reaches the network to transcribe."""

    name = "faster-whisper"

    def __init__(
        self,
        config: Optional[WhisperConfig] = None,
        *,
        model_factory: Optional[Callable[..., Any]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config or WhisperConfig.load()
        self._model_factory = model_factory or _default_model_factory
        self._model: Any = None
        self._initialized = False
        #: Why it is not available, when it is not. Named, never silent — a
        #: caller renders this, so it is written for the user rather than for a
        #: log line.
        self._reason: Optional[str] = None
        self._weights_were_downloaded = False
        self._lock = asyncio.Lock()
        self._log = logger or logging.getLogger(f"voice.stt.{self.name}")

    # ------------------------------------------------------------------ paths
    def _repo_id(self) -> Optional[str]:
        """The HuggingFace repo the weights would come from.

        ``None`` when the configured value is a directory that already exists,
        because then there is nothing to fetch and nothing to ask about.
        """
        configured = self.config.model_size
        if Path(configured).expanduser().is_dir():
            return None
        if "/" in configured:
            return configured
        return HF_REPO_TEMPLATE.format(size=configured)

    # ------------------------------------------------------------- model load
    def _load_offline(self) -> Any:
        """Load weights that are already on this machine. Touches no network."""
        return self._model_factory(
            model_size_or_path=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            download_root=self.config.download_root,
            local_files_only=True,
        )

    def _load_downloading(self) -> Any:
        """Load weights, fetching them if absent. Only ever called after the
        gate has said yes."""
        return self._model_factory(
            model_size_or_path=self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
            download_root=self.config.download_root,
            local_files_only=False,
        )

    def _load(self) -> None:
        """Resolve a model, or set ``_reason`` to something a user can act on.

        Blocking, and run in a worker thread by :meth:`initialize`. Loading a
        CT2 model takes seconds and would otherwise stall the event loop that
        the rest of the app answers on.
        """
        try:
            self._model = self._load_offline()
            self._reason = None
            self._log.info(
                "Whisper weights loaded from disk; nothing left the machine",
                extra={"provider": self.name, "model": self.config.model_size},
            )
            return
        except Exception as exc:  # weights absent, or the package is broken
            offline_failure = exc

        repo = self._repo_id()
        if repo is None:
            # A local directory was configured and the load still failed, so
            # there is nothing to download and the failure is about the files
            # themselves. Reporting a download would be a wrong diagnosis.
            self._reason = f"Whisper weights at {self.config.model_size} could not be read: {offline_failure}"
            self._log.warning(self._reason, extra={"provider": self.name})
            return

        url = f"https://huggingface.co/{repo}"
        try:
            get_gate().check(url, source="speech-to-text")
        except EgressDenied as denied:
            # Default deny is the *ordinary* answer here, not an error. The
            # recogniser is unavailable and the user is told what it would cost
            # to make it available, which is a choice they can act on.
            self._reason = (
                f"Speech recognition needs the Whisper weights, which are not on this "
                f"machine yet. Downloading them from huggingface.co ({_download_note(self.config.model_size)}) "
                f"was blocked: {denied}"
            )
            self._log.info(
                "Whisper weight download refused by policy",
                extra={"provider": self.name, "host": denied.host, "entry": denied.entry_id},
            )
            return

        try:
            self._model = self._load_downloading()
            self._weights_were_downloaded = True
            self._reason = None
            self._log.info(
                "Whisper weights downloaded and loaded",
                extra={"provider": self.name, "repo": repo},
            )
        except Exception as exc:
            self._reason = f"Whisper weights could not be loaded: {exc}"
            self._log.warning(self._reason, extra={"provider": self.name})

    # -------------------------------------------------- SpeechRecogniser API
    async def initialize(self) -> None:
        """Load the model, or record why it could not be loaded. Never raises."""
        async with self._lock:
            if self._initialized:
                return
            self._initialized = True

            try:
                import faster_whisper  # noqa: F401
            except Exception as exc:
                self._reason = f"{INSTALL_HINT} ({exc})"
                self._log.info(
                    "faster-whisper is not installed; listening disabled, chat unaffected",
                    extra={"provider": self.name},
                )
                return

            await asyncio.to_thread(self._load)

    async def transcribe(
        self, audio: bytes, *, language: Optional[str] = None
    ) -> Transcript:
        """Turn an audio buffer into text. Never leaves the device.

        Raises :class:`RuntimeError` when there is no model, rather than
        returning an empty transcript. Silence and breakage produce the same
        empty string, and a caller that cannot tell them apart will show "" as
        though the user said nothing.
        """
        if self._model is None:
            raise RuntimeError(self._reason or "Speech recognition is not available.")
        if not audio:
            # Genuinely nothing to hear. Distinct from a failure, and cheap to
            # answer without waking the model.
            return Transcript(text="", metadata={"reason": "empty_audio"})

        return await asyncio.to_thread(self._transcribe, audio, language)

    def _transcribe(self, audio: bytes, language: Optional[str]) -> Transcript:
        # A file-like object, not a path: the audio arrives from a microphone
        # over HTTP and writing it to disk to read it straight back would leave
        # the most sensitive input Zaram takes lying in a temp directory.
        segments_iter, info = self._model.transcribe(
            io.BytesIO(audio),
            language=language,
            beam_size=self.config.beam_size,
            word_timestamps=self.config.word_timestamps,
            vad_filter=self.config.vad_filter,
        )

        # faster-whisper returns a generator: nothing is decoded until it is
        # consumed, so `info` is available before any work has happened and the
        # list() below is where the transcription actually runs.
        segments: List[TranscriptSegment] = [
            TranscriptSegment(
                text=(segment.text or "").strip(),
                start_s=float(segment.start),
                end_s=float(segment.end),
            )
            for segment in segments_iter
        ]

        detected = getattr(info, "language", None)
        probability = getattr(info, "language_probability", None)

        return Transcript(
            text=" ".join(s.text for s in segments if s.text).strip(),
            segments=segments,
            # Never defaulted to "en". The engine says or it does not, and a
            # guessed language is a wrong value rendered confidently.
            language=language or detected or None,
            duration_s=float(getattr(info, "duration", 0.0) or 0.0),
            metadata={
                "model": self.config.model_size,
                "language_probability": probability,
            },
        )

    def is_available(self) -> bool:
        return self._model is not None

    async def health_check(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "provider": self.name,
            "available": self._model is not None,
            "model": self.config.model_size,
            "device": self.config.device,
            "compute_type": self.config.compute_type,
            "initialized": self._initialized,
            #: True only when *this process* fetched them. Useful in the egress
            #: log's neighbourhood: it says whether the one network-touching
            #: moment in this module has happened.
            "weights_downloaded_this_run": self._weights_were_downloaded,
        }
        if self._model is None:
            report["reason"] = self._reason or "Speech recognition has not been initialised."
        return report

    async def shutdown(self) -> None:
        async with self._lock:
            self._model = None
            self._initialized = False
        self._log.info("Whisper recogniser shut down", extra={"provider": self.name})
