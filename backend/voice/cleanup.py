"""Automated local asset cleanup for Kokoro voice models.

Removes unused downloaded voice files from HuggingFace cache while preserving
the active voice and all configuration/model files.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _scan_cache_dir(cache_dir: str):
    """Lazy import of huggingface_hub.scan_cache_dir.

    The bundled runtime Python may not have huggingface_hub installed — it is
    an optional dependency for asset cleanup only, and importing it at module
    scope crashed the entire voice subsystem on startup. The cleanup functions
    are optional utilities; they must not block the voice pipeline from loading.
    """
    from huggingface_hub import scan_cache_dir as _scan
    return _scan(cache_dir)


def _hf_hub_cache() -> str:
    """Lazy resolution of the HuggingFace cache directory."""
    from huggingface_hub.constants import HF_HUB_CACHE
    return HF_HUB_CACHE


def resolve_keep_voice(requested: Optional[str], current: Optional[str], default: str) -> str:
    """The voice a cleanup keeps: what was asked, else what speaks now, else the default.

    It used to be a literal in the route, in two callers and in the button's own
    sentence -- one person's favourite, deleted around for everybody else.
    """
    for name in (requested, current, default):
        if name and name.strip():
            return name.strip()
    raise ValueError("there is no voice to keep")


@dataclass
class CleanupReport:
    """Report of cleanup operation."""
    deleted_files: List[str] = field(default_factory=list)
    deleted_count: int = 0
    freed_bytes: int = 0
    kept_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deleted_count": self.deleted_count,
            "freed_bytes": self.freed_bytes,
            "freed_mb": round(self.freed_bytes / (1024 * 1024), 2),
            "kept_count": len(self.kept_files),
            "dry_run": self.dry_run,
            "errors": self.errors,
        }


@dataclass
class VoiceCacheInfo:
    """Information about a voice file in cache."""
    voice_id: str
    file_path: Path
    size_bytes: int
    repo_id: str
    revision: str
    backend: str  # "torch" or "onnx"
    #: Where the bytes actually live. The same file as `file_path` on a cache without
    #: symlinks (Windows, usually); a separate blob on one with them.
    blob_path: Optional[Path] = None


def _get_kokoro_repo_ids() -> Dict[str, str]:
    """Get the HuggingFace repo IDs for Kokoro (torch and ONNX)."""
    return {
        "torch": "hexgrad/Kokoro-82M",
        "onnx": "onnx-community/Kokoro-82M-v1.0-ONNX",
    }


def _get_voice_filename(voice_id: str, backend: str) -> str:
    """Get the filename for a voice in the given backend."""
    if backend == "onnx":
        return f"voices/{voice_id}.bin"
    return f"voices/{voice_id}.pt"


def scan_kokoro_cache() -> Dict[str, List[VoiceCacheInfo]]:
    """
    Scan HuggingFace cache for Kokoro voice files.

    Returns a dict mapping backend -> list of VoiceCacheInfo.
    """
    result: Dict[str, List[VoiceCacheInfo]] = {"torch": [], "onnx": []}
    repo_ids = _get_kokoro_repo_ids()

    try:
        cache_info = _scan_cache_dir(_hf_hub_cache())
    except Exception as exc:
        logger.warning("Failed to scan HuggingFace cache: %s", exc)
        return result

    for repo in cache_info.repos:
        repo_id = repo.repo_id
        backend = None
        if repo_id == repo_ids["torch"]:
            backend = "torch"
        elif repo_id == repo_ids["onnx"]:
            backend = "onnx"
        else:
            continue

        for revision in repo.revisions:
            snapshot = Path(revision.snapshot_path)
            for file in revision.files:
                path = Path(file.file_path)
                try:
                    inside = path.relative_to(snapshot).as_posix()
                except ValueError:
                    continue
                if not inside.startswith("voices/"):
                    continue

                filename = path.name
                if backend == "onnx":
                    if not filename.endswith(".bin"):
                        continue
                    voice_id = filename[:-4]  # Remove .bin
                else:
                    if not filename.endswith(".pt"):
                        continue
                    voice_id = filename[:-3]  # Remove .pt

                blob = getattr(file, "blob_path", None)
                result[backend].append(VoiceCacheInfo(
                    voice_id=voice_id,
                    file_path=path,
                    size_bytes=file.size_on_disk,
                    repo_id=repo_id,
                    revision=revision.commit_hash,
                    backend=backend,
                    blob_path=Path(blob) if blob else None,
                ))

    return result


def find_voice_files(
    voice_id: str,
    backend: str = "torch",
    cache_dir: Optional[str] = None,
) -> List[Path]:
    """Find all cache files for a specific voice."""
    repo_ids = _get_kokoro_repo_ids()
    repo_id = repo_ids.get(backend)
    if not repo_id:
        return []

    cache_path = Path(cache_dir) if cache_dir else Path(_hf_hub_cache())
    voice_filename = _get_voice_filename(voice_id, backend)

    matches = []
    repo_cache = cache_path / f"models--{repo_id.replace('/', '--')}"
    if repo_cache.exists():
        for revision_dir in repo_cache.iterdir():
            if not revision_dir.is_dir():
                continue
            voice_file = revision_dir / "snapshots" / revision_dir.name / voice_filename
            if voice_file.exists():
                matches.append(voice_file)
            # Also check blobs
            blob_file = revision_dir / "blobs" / voice_filename
            if blob_file.exists():
                matches.append(blob_file)

    return matches


def cleanup_unused_voices(
    keep_voice: str = "am_michael",
    backends: Optional[List[str]] = None,
    dry_run: bool = False,
    cache_dir: Optional[str] = None,
) -> CleanupReport:
    """
    Delete all downloaded Kokoro voice files except the active one.

    Args:
        keep_voice: Voice ID to preserve (default: "am_michael")
        backends: List of backends to clean ["torch", "onnx"] (default: both)
        dry_run: If True, only report what would be deleted
        cache_dir: Custom HuggingFace cache directory

    Returns:
        CleanupReport with details of deleted/kept files
    """
    if backends is None:
        backends = ["torch", "onnx"]

    report = CleanupReport(dry_run=dry_run)
    cache_info = scan_kokoro_cache()

    # What a kept voice stands on, so a blob shared with one is never deleted.
    kept_blobs = set()
    for backend in backends:
        for voice_info in cache_info.get(backend, []):
            if voice_info.voice_id == keep_voice:
                kept_blobs.add(voice_info.blob_path or voice_info.file_path)

    for backend in backends:
        voices = cache_info.get(backend, [])
        for voice_info in voices:
            if voice_info.voice_id == keep_voice:
                report.kept_files.append(str(voice_info.file_path))
                continue

            # This voice should be deleted
            full_path = voice_info.file_path
            if cache_dir and not full_path.is_absolute():
                full_path = Path(cache_dir) / full_path

            if not full_path.exists():
                # Try alternative locations
                found = find_voice_files(voice_info.voice_id, backend, cache_dir)
                if found:
                    full_path = found[0]

            if not full_path.exists():
                logger.debug("Voice file not found (already cleaned?): %s", full_path)
                continue

            blob = voice_info.blob_path
            has_own_blob = (
                blob is not None and blob != full_path and blob.exists() and blob not in kept_blobs
            )
            try:
                size = blob.stat().st_size if has_own_blob else full_path.stat().st_size
                if not dry_run:
                    full_path.unlink()
                    if has_own_blob:
                        blob.unlink()
                    logger.info("Deleted voice file: %s (%d bytes)", full_path, size)
                report.deleted_files.append(str(full_path))
                report.deleted_count += 1
                report.freed_bytes += size
            except Exception as exc:
                error_msg = f"Failed to delete {full_path}: {exc}"
                logger.error(error_msg)
                report.errors.append(error_msg)

    # Also clean up ONNX patched models if they exist (separate cache)
    if not dry_run:
        _cleanup_onnx_patched_models(cache_dir)

    logger.info(
        "Cleanup complete: deleted=%d, freed=%d bytes, kept=%d, errors=%d",
        report.deleted_count, report.freed_bytes, len(report.kept_files), len(report.errors)
    )
    return report


def _cleanup_onnx_patched_models(cache_dir: Optional[str] = None) -> int:
    """Clean up ONNX patched model copies (created by kokoro_onnx.py)."""
    base = Path(cache_dir) if cache_dir else Path(_hf_hub_cache())
    onnx_patch_dir = base / "zaram-kokoro-onnx"
    removed = 0

    if onnx_patch_dir.exists():
        try:
            for file in onnx_patch_dir.glob("*.onnx"):
                size = file.stat().st_size
                file.unlink()
                logger.info("Deleted ONNX patched model: %s (%d bytes)", file, size)
                removed += 1
            # Remove directory if empty
            if not any(onnx_patch_dir.iterdir()):
                onnx_patch_dir.rmdir()
        except Exception as exc:
            logger.warning("Failed to clean ONNX patched models: %s", exc)

    return removed


async def cleanup_unused_voices_async(
    keep_voice: str = "am_michael",
    backends: Optional[List[str]] = None,
    dry_run: bool = False,
    cache_dir: Optional[str] = None,
) -> CleanupReport:
    """Async wrapper for cleanup_unused_voices (runs in thread pool)."""
    import asyncio
    return await asyncio.to_thread(
        cleanup_unused_voices,
        keep_voice=keep_voice,
        backends=backends,
        dry_run=dry_run,
        cache_dir=cache_dir,
    )


def get_cache_status(keep_voice: str = "am_michael") -> Dict[str, Any]:
    """Get status of Kokoro voice cache without modifying anything."""
    cache_info = scan_kokoro_cache()
    total_voices = sum(len(v) for v in cache_info.values())
    total_size = sum(v.size_bytes for voices in cache_info.values() for v in voices)

    keep_size = 0
    keep_count = 0
    for voices in cache_info.values():
        for v in voices:
            if v.voice_id == keep_voice:
                keep_size += v.size_bytes
                keep_count += 1

    deletable_size = total_size - keep_size
    deletable_count = total_voices - keep_count

    return {
        "total_voices_cached": total_voices,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "keep_voice": keep_voice,
        "keep_voice_size_bytes": keep_size,
        "deletable_voices": deletable_count,
        "deletable_size_bytes": deletable_size,
        "deletable_size_mb": round(deletable_size / (1024 * 1024), 2),
        "by_backend": {
            backend: {
                "count": len(voices),
                "size_bytes": sum(v.size_bytes for v in voices),
                "voices": [v.voice_id for v in voices],
            }
            for backend, voices in cache_info.items()
        },
    }


# Module exports
__all__ = [
    "CleanupReport",
    "VoiceCacheInfo",
    "cleanup_unused_voices",
    "cleanup_unused_voices_async",
    "get_cache_status",
    "find_voice_files",
    "scan_kokoro_cache",
]