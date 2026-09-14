"""The optional packs, installed from inside Zaram — one button, the cost named.

**Why this exists.** Speaking, listening and reading scans are optional
extras, and until 14 September 2026 every one of them was offered to the
user as a `pip install` line in Settings. A packaged install has a real,
relocatable CPython with `pip` in it (`scripts/build-python-runtime.mjs`
chose that over PyInstaller for exactly this reason) — but no user of a
packaged app has a terminal open, and the line was a remedy nobody could
take. The maintainer's words: *"Zaram shouldn't be too technical … or make
users think a lot."*

So a pack is a row: what it turns on, in plain words; what it costs, once;
and a button. Pressing the button is the consent (rule 7g — discovery on a
button), the download is recorded in the egress log **before the first
byte moves** (the same discipline `providers.pull` keeps for a model), and
pip runs in the interpreter Zaram is running in, so what it installs is
what Zaram will import.

**Never on the first run, never a prompt.** `CLAUDE.md`: *never block on a
download*, and *offer at the moment of doubt; never make the user choose in
advance*. Nobody is asked about packs when Zaram is installed. The avatar
works silently until the person turns it on and is then, once, offered the
voice pack; the microphone button offers the mic pack; a scan in Knowledge
offers OCR. Settings → Packs lists all of them for whoever wants to look.

**Sizes are measured, dated, and say which measurement.** A wrong size on a
metered connection is the one lie this screen cannot afford.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parent.parent

#: Where pip fetches from. Recorded on the egress log as the download's
#: destination; pip's own connections cannot pass through the gate's socket,
#: so the decision is the person's press and the record is written here.
PYPI_HOST = "files.pythonhosted.org"


@dataclass(frozen=True)
class Extra:
    id: str
    #: The pack's name, as a person would say it.
    name: str
    #: What it turns on — each a sentence the row shows.
    enables: Tuple[str, ...]
    #: The download, in MB, and how it was measured.
    size_mb: int
    measured: str
    #: Commands run in order, each as pip/python arguments after the interpreter.
    commands: Tuple[Tuple[str, ...], ...]
    #: A module whose presence means the pack is installed.
    probe: str
    #: Whether Zaram has to be restarted before the pack takes effect.
    restart: bool = False
    #: Hosts the commands fetch from, for the log.
    hosts: Tuple[str, ...] = (PYPI_HOST,)


EXTRAS: Dict[str, Extra] = {
    "voice": Extra(
        id="voice",
        name="Speaking",
        enables=(
            "The avatar speaks its replies, with its mouth in time.",
            "Any reply can be read aloud.",
        ),
        size_mb=290,
        measured="on disk after install, 14 September 2026 — the ONNX build, without torch",
        commands=(
            ("-m", "pip", "install", "--disable-pip-version-check", "--no-input",
             "-r", str(BACKEND / "requirements-voice-onnx.txt")),
            ("-m", "spacy", "download", "en_core_web_sm"),
        ),
        probe="kokoro",
        restart=True,
        hosts=(PYPI_HOST, "github.com"),
    ),
    "mic": Extra(
        id="mic",
        name="Listening",
        enables=(
            "Push-to-talk and hands-free listening, transcribed on this machine.",
        ),
        size_mb=81,
        measured="wheels downloaded, 10 August 2026",
        commands=(
            ("-m", "pip", "install", "--disable-pip-version-check", "--no-input",
             "-r", str(BACKEND / "requirements-mic.txt")),
        ),
        probe="faster_whisper",
    ),
    "ingest": Extra(
        id="ingest",
        name="Reading scans",
        enables=(
            "Scanned PDFs and photographed pages in Knowledge are read, not skipped.",
        ),
        size_mb=321,
        measured="wheels downloaded, 25 August 2026",
        commands=(
            ("-m", "pip", "install", "--disable-pip-version-check", "--no-input",
             "docling>=2.118.1"),
        ),
        probe="docling",
    ),
}


def installed(extra: Extra) -> bool:
    """Whether the pack's probe module can be imported here. Answered without
    importing it — a probe that loaded torch to say yes would cost seconds."""
    try:
        return importlib.util.find_spec(extra.probe) is not None
    except (ImportError, ValueError):
        return False


def describe(extra: Extra) -> Dict[str, Any]:
    return {
        "id": extra.id,
        "name": extra.name,
        "enables": list(extra.enables),
        "size_mb": extra.size_mb,
        "measured": extra.measured,
        "installed": installed(extra),
        "restart": extra.restart,
        "python": sys.executable,
    }


def catalogue() -> List[Dict[str, Any]]:
    return [describe(e) for e in EXTRAS.values()]


Runner = Callable[[List[str]], Iterator[str]]


def _run(argv: List[str]) -> Iterator[str]:
    """Run one command in Zaram's own interpreter, yielding its output lines."""
    proc = subprocess.Popen(
        [sys.executable, *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line.rstrip("\n")
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"exited with {code}")


def install(
    extra: Extra,
    *,
    log: Any = None,
    run: Runner = _run,
    source: str = "packs",
) -> Iterator[Dict[str, Any]]:
    """Install the pack, yielding what a screen can render.

    Events: ``{"line": ...}`` for each line the installer prints, then one
    terminal event — ``{"done": True, "restart": bool}`` or
    ``{"error": "..."}``. The egress record is written before anything runs.
    ``log`` is the egress log, or ``None`` in a test not asserting on it;
    ``run`` is how a command is executed, injectable for the same reason.
    """
    if log is not None:
        for host in extra.hosts:
            log.append(
                host=host,
                method="GET",
                url=f"https://{host}",
                body=extra.id,
                decision="allowed",
                reason=f"you pressed Get it for the {extra.name} pack ({extra.size_mb} MB)",
                source=source,
                meta={"expected_bytes": extra.size_mb * 1_000_000, "direction": "download"},
            )
    started = time.time()
    yield {"stage": f"Getting the {extra.name} pack — about {extra.size_mb} MB, one time."}
    try:
        for argv in extra.commands:
            for line in run(list(argv)):
                if line.strip():
                    yield {"line": line}
    except Exception as exc:  # noqa: BLE001 - the screen needs the sentence, not a trace
        yield {"error": f"The {extra.name} pack did not install: {exc}"}
        return
    if not installed(extra):
        yield {"error": f"The installer finished but {extra.probe} still cannot be imported."}
        return
    _forget_probes(extra)
    yield {"done": True, "restart": extra.restart, "seconds": round(time.time() - started)}


def _forget_probes(extra: Extra) -> None:
    """Let a service that reported the pack missing look again.

    The recogniser is cached once it has answered; installed under it, the
    pack would go unnoticed until a restart the person was never told about.
    Speaking is bootstrapped at start and genuinely needs one — `restart`
    says so on the row.
    """
    if extra.id == "mic":
        try:
            from voice.stt import service

            service._recogniser = None  # noqa: SLF001 - the seam is the cache itself
        except Exception:  # noqa: BLE001
            pass
