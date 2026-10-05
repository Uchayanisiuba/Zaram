"""The voices Zaram can speak with, named without asking the network.

`/voice/voices` answered an empty list on every working install, because the
only way the provider knew to name the pack was to list a HuggingFace repo, and
rule 7g forbids a network call nobody consented to. The pack is not a secret and
does not change between releases — Kokoro-82M v1.0 has 54 voices — so the answer
is the one `providers/models.manifest.json` already gives for models: a dated
file in the bundle. Naming a voice needs no network; *fetching* one is a
separate act and is only ever a person pressing a button.

Three things are kept apart, as they are for models:

* **What exists** — the manifest. Dated, falls back to an empty catalogue
  rather than failing the launch.
* **What is on this machine** — read from the HuggingFace cache offline
  (`try_to_load_from_cache` never touches the network), so "downloaded" is a
  measurement and not a claim.
* **What can speak** — `requires`: a voice outside American and British English
  needs a language front end that is not in the base install. Those voices are
  listed and marked, not hidden and not offered as if they worked.

Nothing in the catalogue is a Zaram-authored opinion of how a voice sounds.
`grade` is the upstream author's own rating of how well it was trained, and is
`None` where he gave none; inventing a description for the other fifty would be
rendering values nobody measured.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["MANIFEST_PATH", "VoiceRow", "catalogue", "fetch_voice", "is_cached", "voice_url"]

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices.manifest.json")

#: Where the torch pipeline's voices live. The ONNX pipeline reads the same
#: voices from a different repo as raw `.bin`, so the repo, the filename and the
#: pinned revision all depend on the backend — resolved together in `_location`.
_TORCH_REPO = "hexgrad/Kokoro-82M"


@dataclass(frozen=True)
class VoiceRow:
    id: str
    name: str
    language: str
    language_code: str
    gender: str
    grade: Optional[str]
    size_bytes: int
    #: On this machine now. A measurement of the cache, never a default.
    installed: bool
    #: What the voice needs that the base install lacks, or None when nothing.
    requires: Optional[str]
    #: The voice that speaks when the user has not chosen one.
    default: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "language_code": self.language_code,
            "gender": self.gender,
            "grade": self.grade,
            "size_bytes": self.size_bytes,
            "installed": self.installed,
            "requires": self.requires,
            "default": self.default,
        }


def _load(path: str = MANIFEST_PATH) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        # Logged rather than raised: a packaging mistake costs the list of
        # voices, never the launch.
        logger.warning("voice manifest unreadable at %s: %s", path, error)
        return None
    return data if isinstance(data, dict) else None


def _location(voice_id: str, backend: str) -> tuple[str, str, Optional[str]]:
    """(repo, filename, revision) for one voice under `backend`."""
    if backend == "onnx":
        from voice.providers.kokoro_onnx import ONNX_REPO_ID, ONNX_REVISION

        return ONNX_REPO_ID, f"voices/{voice_id}.bin", ONNX_REVISION
    return _TORCH_REPO, f"voices/{voice_id}.pt", None


def voice_url(voice_id: str, backend: str = "torch") -> str:
    repo, _, _ = _location(voice_id, backend)
    return f"https://huggingface.co/{repo}"


def is_cached(voice_id: str, backend: str = "torch") -> bool:
    """Whether this voice's file is already on the machine. Offline by construction."""
    try:
        from huggingface_hub import try_to_load_from_cache

        repo, filename, revision = _location(voice_id, backend)
        found = try_to_load_from_cache(repo_id=repo, filename=filename, revision=revision)
    except Exception:
        return False
    return isinstance(found, str)


def catalogue(
    *,
    backend: str = "torch",
    default_voice: str = "",
    path: str = MANIFEST_PATH,
    cached=is_cached,
) -> Dict[str, Any]:
    """Every voice in the pack, with what this machine knows about each.

    `cached` is injectable so the shape can be tested without a HuggingFace
    cache on the machine running the test.
    """
    data = _load(path)
    if data is None:
        return {"generated": None, "source": None, "voices": []}

    front_ends = data.get("front_ends") or {}
    size = int(data.get("voice_bytes") or 0)
    rows: List[VoiceRow] = []
    for raw in data.get("voices") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        code = str(raw.get("language_code") or "")
        requires = (front_ends.get(code) or {}).get("requires")
        rows.append(
            VoiceRow(
                id=str(raw["id"]),
                name=str(raw.get("name") or raw["id"]),
                language=str(raw.get("language") or "unknown"),
                language_code=code,
                gender=str(raw.get("gender") or "unknown"),
                grade=raw.get("grade") or None,
                size_bytes=size,
                installed=bool(cached(str(raw["id"]), backend)),
                requires=requires,
                default=str(raw["id"]) == default_voice,
            )
        )
    return {
        "generated": data.get("generated"),
        "source": data.get("source"),
        "note": data.get("note"),
        "voices": [row.to_dict() for row in rows],
    }


def known_ids(path: str = MANIFEST_PATH) -> set[str]:
    data = _load(path) or {}
    return {str(v["id"]) for v in data.get("voices") or [] if isinstance(v, dict) and v.get("id")}


def fetch_voice(voice_id: str, *, backend: str = "torch", source: str = "voices") -> str:
    """Download one voice, having asked the gate first.

    **Gated, like the model itself.** The Kokoro weights already need
    huggingface.co to be allowed before they arrive, so a voice from the same
    host asks the same question and gets the same answer: allowed means the
    entry is written before the first byte and the file is fetched; default
    deny raises :class:`EgressDenied` for the caller to say in a sentence. An
    earlier version recorded the request and skipped the policy, on the
    reasoning that pressing a button which names the file is the explicit
    decision rule 7j asks for — true, but it made this module the one place a
    deliberate-looking exception sat beside a rule the model download obeys,
    and `test_egress_chokepoint` is right to want one answer for the host.

    The id must be in the manifest. A name arriving in a request body that the
    user was never shown is not a thing to fetch.
    """
    from core.egress import EgressDenied, get_gate

    if voice_id not in known_ids():
        raise KeyError(voice_id)
    repo, filename, revision = _location(voice_id, backend)
    try:
        get_gate().check(f"https://huggingface.co/{repo}", source=source)
    except EgressDenied as denied:
        # Refusal is the ordinary answer on a machine that has not allowed the
        # host, so it is named and handled here rather than left to surface as
        # whatever the caller happens to catch. Worded by the caller: the route
        # returns it as a 403, the provider as "unavailable, and here is why".
        logger.info("voice %s not fetched: %s", voice_id, denied)
        raise

    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo_id=repo, filename=filename, revision=revision)
