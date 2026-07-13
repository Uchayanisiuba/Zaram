"""Audio event contracts for the Voice Runtime.

These prepare the backend half of the future streaming protocol used by the
frontend SSE stream and (later) Unreal MetaHuman / Apple ARKit consumers. The
shapes are intentionally provider-agnostic and decoupled from any concrete
result type: builders accept duck-typed objects exposing the needed attributes.

Event shape (prepared for future use; frontend not modified yet):

    {
        "type": "audio",
        "audio_id": "<id>",
        "url": "/audio/<filename>.wav",
        "sequence": 0,
        "final": false,
        "voice": "<voice>"
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def to_audio_event(
    *,
    audio_id: str = "",
    url: str = "",
    sequence: int = 0,
    final: bool = False,
    voice: str = "",
    type_: str = "audio",
) -> Dict[str, Any]:
    """Build a provider-agnostic audio event dictionary."""
    return {
        "type": type_,
        "audio_id": audio_id,
        "url": url,
        "sequence": sequence,
        "final": final,
        "voice": voice,
    }


def _url_for(path: Optional[str], base_url: str) -> str:
    if not path:
        return ""
    filename = Path(path).name
    base = base_url.rstrip("/")
    if base:
        return f"{base}/audio/{filename}"
    return f"/audio/{filename}"


def audio_event_from_result(result: Any, *, sequence: int = 0, final: bool = True, base_url: str = "") -> Dict[str, Any]:
    """Build an audio event from a completed :class:`AudioResult`."""
    return to_audio_event(
        audio_id=getattr(result, "audio_id", "") or "",
        url=_url_for(getattr(result, "path", None), base_url),
        sequence=sequence,
        final=final,
        voice=getattr(result, "voice", ""),
    )


def audio_event_from_chunk(chunk: Any, *, base_url: str = "") -> Dict[str, Any]:
    """Build an audio event from a streamed :class:`AudioChunk`."""
    return to_audio_event(
        audio_id=getattr(chunk, "audio_id", "") or "",
        url=_url_for(getattr(chunk, "path", None), base_url),
        sequence=getattr(chunk, "index", 0),
        final=bool(getattr(chunk, "final", False)),
        voice=getattr(chunk, "voice", ""),
    )
