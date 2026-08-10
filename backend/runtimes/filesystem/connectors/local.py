from __future__ import annotations

import os
import mimetypes
import hashlib
from pathlib import Path
from typing import Any
import time

from .contracts import FileRecord, FileMetadata, FilesystemConnector, FileType


class LocalFilesystemConnector(FilesystemConnector):
    """Local filesystem connector with support for various file types."""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path).resolve()
        self._file_type_map = {
            ".md": FileType.MARKDOWN,
            ".markdown": FileType.MARKDOWN,
            ".txt": FileType.NOTE,
            ".pdf": FileType.PDF,
            ".png": FileType.IMAGE,
            ".jpg": FileType.IMAGE,
            ".jpeg": FileType.IMAGE,
            ".gif": FileType.IMAGE,
            ".webp": FileType.IMAGE,
            ".py": FileType.CODE,
            ".js": FileType.CODE,
            ".ts": FileType.CODE,
            ".tsx": FileType.CODE,
            ".jsx": FileType.CODE,
            ".java": FileType.CODE,
            ".cpp": FileType.CODE,
            ".c": FileType.CODE,
            ".h": FileType.CODE,
            ".rs": FileType.CODE,
            ".go": FileType.CODE,
            ".html": FileType.CODE,
            ".css": FileType.CODE,
            ".json": FileType.DOCUMENT,
            ".yaml": FileType.DOCUMENT,
            ".yml": FileType.DOCUMENT,
            ".toml": FileType.DOCUMENT,
            ".xml": FileType.DOCUMENT,
            ".csv": FileType.DOCUMENT,
            ".docx": FileType.DOCUMENT,
            ".doc": FileType.DOCUMENT,
            ".pptx": FileType.DOCUMENT,
            ".xlsx": FileType.DOCUMENT,
        }

    def _get_file_type(self, path: Path) -> FileType:
        return self._file_type_map.get(path.suffix.lower(), FileType.UNKNOWN)

    def _get_mime_type(self, path: Path) -> str:
        mime, _ = mimetypes.guess_type(str(path))
        return mime or "application/octet-stream"

    def _compute_checksum(self, path: Path) -> str:
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()[:16]
        except Exception:
            return ""

    async def list_files(self, path: str, recursive: bool = True) -> list[str]:
        full_path = self.root_path / path
        if not full_path.exists():
            return []

        files = []
        if recursive:
            for f in full_path.rglob("*"):
                if f.is_file() and not self._should_ignore(f):
                    files.append(str(f.relative_to(self.root_path)))
        else:
            for f in full_path.iterdir():
                if f.is_file() and not self._should_ignore(f):
                    files.append(str(f.relative_to(self.root_path)))
        return files

    def _should_ignore(self, path: Path) -> bool:
        ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".idea", ".vscode"}
        ignore_files = {".DS_Store", "Thumbs.db", "*.pyc", "*.pyo", "*.pyd"}
        
        for part in path.parts:
            if part in ignore_dirs:
                return True
            if part.startswith(".") and part not in {".gitignore", ".env"}:
                return True
        return False

    async def read_file(self, path: str) -> str | bytes:
        full_path = self.root_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        file_type = self._get_file_type(full_path)
        if file_type == FileType.IMAGE:
            return full_path.read_bytes()
        try:
            return full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return full_path.read_bytes()

    async def get_metadata(self, path: str) -> FileMetadata:
        full_path = self.root_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        stat = full_path.stat()
        return FileMetadata(
            path=path,
            size_bytes=stat.st_size,
            mime_type=self._get_mime_type(full_path),
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
            permissions=oct(stat.st_mode)[-3:],
            is_directory=full_path.is_dir(),
            extension=full_path.suffix,
        )

    async def watch(self, path: str, callback):
        import asyncio
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class WatchHandler(FileSystemEventHandler):
            def __init__(self, cb):
                self.cb = cb

            def on_any_event(self, event):
                asyncio.create_task(self.cb(event.src_path, event.event_type))

        full_path = self.root_path / path
        observer = Observer()
        observer.schedule(WatchHandler(callback), str(full_path), recursive=True)
        observer.start()
        return observer

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self.root_path.exists() else "unavailable",
            "root_path": str(self.root_path),
            "writable": os.access(self.root_path, os.W_OK),
        }


class ProjectFilesystemConnector(LocalFilesystemConnector):
    """Project-scoped filesystem connector."""

    def __init__(self, root_path: str, project_id: str):
        super().__init__(root_path)
        self.project_id = project_id

    async def list_files(self, path: str = "", recursive: bool = True) -> list[str]:
        return await super().list_files(path, recursive)