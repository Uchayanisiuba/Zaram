"""Centralized audio cache handling for the Voice Runtime.

All providers share this class so cache directory creation, unique/collision
-safe filenames, and cleanup logic live in exactly one place (no duplication
across providers). The cache operates only on bytes so it stays engine-agnostic.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import List


class AudioCache:
    def __init__(self, directory: str) -> None:
        self.directory = directory

    # --- directory management ---
    def ensure(self) -> bool:
        """Create the cache directory if missing. Returns success."""
        try:
            os.makedirs(self.directory, exist_ok=True)
            return True
        except Exception:
            return False

    def is_writable(self) -> bool:
        """True if the directory exists (or can be created) and is writable."""
        try:
            os.makedirs(self.directory, exist_ok=True)
            probe = Path(self.directory) / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            return True
        except Exception:
            return False

    # --- naming ---
    def generate_filename(
        self, *, voice: str, text: str, request_id: str = "", ext: str = "wav"
    ) -> str:
        """Collision-safe, deterministic-ish unique filename.

        Includes a nanosecond timestamp and content hash so identical requests
        made at different times never overwrite each other.
        """
        payload = f"{voice}|{text}|{request_id}|{time.time_ns()}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        safe_voice = "".join(c if c.isalnum() else "_" for c in (voice or "voice"))
        return f"{safe_voice}_{digest}.{ext}"

    def path_for(self, filename: str) -> str:
        return os.path.join(self.directory, filename)

    # --- read/write ---
    def write(
        self, data: bytes, *, voice: str, text: str, request_id: str = "", ext: str = "wav"
    ) -> str:
        """Persist ``data`` and return the absolute path (creates dir)."""
        self.ensure()
        filename = self.generate_filename(voice=voice, text=text, request_id=request_id, ext=ext)
        path = self.path_for(filename)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def list_files(self) -> List[str]:
        try:
            return [
                name
                for name in os.listdir(self.directory)
                if os.path.isfile(os.path.join(self.directory, name))
            ]
        except Exception:
            return []

    # --- cleanup ---
    def cleanup(self, max_age_seconds: float = 3600) -> int:
        """Remove files older than ``max_age_seconds``. Returns count removed."""
        removed = 0
        now = time.time()
        for name in self.list_files():
            path = os.path.join(self.directory, name)
            try:
                if now - os.path.getmtime(path) > max_age_seconds:
                    os.remove(path)
                    removed += 1
            except Exception:
                continue
        return removed

    def cleanup_all(self) -> int:
        """Remove every cached file. Returns count removed."""
        removed = 0
        for name in self.list_files():
            path = os.path.join(self.directory, name)
            try:
                os.remove(path)
                removed += 1
            except Exception:
                continue
        return removed
