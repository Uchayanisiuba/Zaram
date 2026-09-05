"""The recogniser this process listens with.

One lazily-built instance, for two reasons that pull the same way.

**Loading is expensive and optional.** A CT2 model takes seconds to load and
holds a few hundred megabytes of RAM. Building it during startup would charge
every user for a feature most of them will not touch in a given session, and
would put a slow step in front of the first question. It is built on the first
transcription request instead, which is the first moment anyone has asked for
it.

**Boot must stay quiet.** ``voice/stt/whisper.py`` can ask the egress gate about
huggingface.co. That decision belongs to a user pressing a microphone button,
not to a process starting up — rule 7g: no network call occurs before the user
has consented to one, and a startup that asks is a startup that has already
decided to.

The lock matters. Two requests arriving together would otherwise each build a
model, and the second would win while the first sat resident and unreferenced.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from .whisper import WhisperRecogniser

_lock = asyncio.Lock()
_recogniser: Optional[WhisperRecogniser] = None


async def get_recogniser() -> WhisperRecogniser:
    """The initialised recogniser. Never raises; ask it whether it is available.

    An unavailable recogniser is still returned, because it is the thing that
    knows *why* — and "why" is what a caller has to show the user.
    """
    global _recogniser
    async with _lock:
        if _recogniser is None:
            recogniser = WhisperRecogniser()
            await recogniser.initialize()
            _recogniser = recogniser
        return _recogniser


async def shutdown_recogniser() -> None:
    """Release the model. Safe to call when nothing was ever built."""
    global _recogniser
    async with _lock:
        if _recogniser is not None:
            await _recogniser.shutdown()
            _recogniser = None
