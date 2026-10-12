"""Tests for cleanup.py - automated local asset cleanup for Kokoro voice models."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from voice.cleanup import (
    CleanupReport,
    VoiceCacheInfo,
    cleanup_unused_voices,
    get_cache_status,
    scan_kokoro_cache,
    find_voice_files,
    _get_kokoro_repo_ids,
    _get_voice_filename,
    _cleanup_onnx_patched_models,
)
from huggingface_hub.constants import HF_HUB_CACHE


class TestCleanupReport:
    """Tests for CleanupReport dataclass."""

    def test_to_dict(self):
        report = CleanupReport(
            deleted_files=["/path/to/file1.pt", "/path/to/file2.pt"],
            deleted_count=2,
            freed_bytes=1046000,
            kept_files=["/path/to/am_michael.pt"],
            errors=[],
            dry_run=False,
        )
        d = report.to_dict()
        assert d["deleted_count"] == 2
        assert d["freed_bytes"] == 1046000
        assert d["freed_mb"] == round(1046000 / (1024 * 1024), 2)
        assert d["kept_count"] == 1
        assert d["dry_run"] is False
        assert d["errors"] == []

    def test_defaults(self):
        report = CleanupReport()
        assert report.deleted_files == []
        assert report.deleted_count == 0
        assert report.freed_bytes == 0
        assert report.kept_files == []
        assert report.errors == []
        assert report.dry_run is False


class TestVoiceCacheInfo:
    """Tests for VoiceCacheInfo dataclass."""

    def test_creation(self):
        info = VoiceCacheInfo(
            voice_id="am_michael",
            file_path=Path("/cache/voices/am_michael.pt"),
            size_bytes=523000,
            repo_id="hexgrad/Kokoro-82M",
            revision="abc123",
            backend="torch",
        )
        assert info.voice_id == "am_michael"
        assert info.size_bytes == 523000
        assert info.backend == "torch"


class TestGetKokoroRepoIds:
    """Tests for _get_kokoro_repo_ids."""

    def test_returns_both_repos(self):
        repos = _get_kokoro_repo_ids()
        assert repos["torch"] == "hexgrad/Kokoro-82M"
        assert repos["onnx"] == "onnx-community/Kokoro-82M-v1.0-ONNX"


class TestGetVoiceFilename:
    """Tests for _get_voice_filename."""

    def test_torch_filename(self):
        assert _get_voice_filename("am_michael", "torch") == "voices/am_michael.pt"

    def test_onnx_filename(self):
        assert _get_voice_filename("bf_emma", "onnx") == "voices/bf_emma.bin"


class TestScanKokoroCache:
    """Tests for scan_kokoro_cache."""

    @patch("voice.cleanup._scan_cache_dir")
    def test_scan_torch_and_onnx(self, mock_scan):
        # Mock the HF cache scan result
        mock_repo_torch = MagicMock()
        mock_repo_torch.repo_id = "hexgrad/Kokoro-82M"
        mock_rev_torch = MagicMock()
        mock_rev_torch.commit_hash = "rev1"
        mock_rev_torch.snapshot_path = Path("/hub/models--a/snapshots/rev1")
        mock_file_torch = MagicMock()
        mock_file_torch.file_path = Path("/hub/models--a/snapshots/rev1/voices/am_michael.pt")
        mock_file_torch.blob_path = Path("/hub/models--a/blobs/aaa")
        mock_file_torch.size_on_disk = 523000
        mock_rev_torch.files = [mock_file_torch]
        mock_repo_torch.revisions = [mock_rev_torch]

        mock_repo_onnx = MagicMock()
        mock_repo_onnx.repo_id = "onnx-community/Kokoro-82M-v1.0-ONNX"
        mock_rev_onnx = MagicMock()
        mock_rev_onnx.commit_hash = "rev2"
        mock_rev_onnx.snapshot_path = Path("/hub/models--b/snapshots/rev2")
        mock_file_onnx = MagicMock()
        mock_file_onnx.file_path = Path("/hub/models--b/snapshots/rev2/voices/bf_emma.bin")
        mock_file_onnx.blob_path = Path("/hub/models--b/blobs/bbb")
        mock_file_onnx.size_on_disk = 523000
        mock_rev_onnx.files = [mock_file_onnx]
        mock_repo_onnx.revisions = [mock_rev_onnx]

        mock_cache_info = MagicMock()
        mock_cache_info.repos = [mock_repo_torch, mock_repo_onnx]
        mock_scan.return_value = mock_cache_info

        result = scan_kokoro_cache()

        assert len(result["torch"]) == 1
        assert result["torch"][0].voice_id == "am_michael"
        assert result["torch"][0].backend == "torch"
        assert len(result["onnx"]) == 1
        assert result["onnx"][0].voice_id == "bf_emma"
        assert result["onnx"][0].backend == "onnx"

    @patch("voice.cleanup._scan_cache_dir")
    def test_scan_no_repos(self, mock_scan):
        mock_cache_info = MagicMock()
        mock_cache_info.repos = []
        mock_scan.return_value = mock_cache_info

        result = scan_kokoro_cache()
        assert result["torch"] == []
        assert result["onnx"] == []

    @patch("voice.cleanup._scan_cache_dir")
    def test_scan_exception(self, mock_scan):
        mock_scan.side_effect = Exception("Cache error")
        result = scan_kokoro_cache()
        assert result["torch"] == []
        assert result["onnx"] == []


class TestFindVoiceFiles:
    """Tests for find_voice_files."""

    def test_find_voice_files_not_found(self):
        result = find_voice_files("nonexistent", "torch", HF_HUB_CACHE)
        assert result == []


class TestCleanupUnusedVoices:
    """Tests for cleanup_unused_voices."""

    @patch("voice.cleanup.scan_kokoro_cache")
    @patch("voice.cleanup.Path.exists")
    @patch("voice.cleanup.Path.unlink")
    @patch("voice.cleanup.Path.stat")
    def test_cleanup_keeps_active_voice(self, mock_stat, mock_unlink, mock_exists, mock_scan):
        mock_scan.return_value = {
            "torch": [
                VoiceCacheInfo(
                    voice_id="am_michael",
                    file_path=Path("/cache/am_michael.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
                VoiceCacheInfo(
                    voice_id="bf_emma",
                    file_path=Path("/cache/bf_emma.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
            ],
            "onnx": [],
        }
        mock_exists.return_value = True
        mock_stat.return_value = MagicMock(st_size=523000)

        report = cleanup_unused_voices(keep_voice="am_michael", backends=["torch"], dry_run=False)

        assert report.deleted_count == 1
        assert report.freed_bytes == 523000
        assert "bf_emma" in str(report.deleted_files)
        assert "am_michael" in str(report.kept_files)

    @patch("voice.cleanup.scan_kokoro_cache")
    @patch("voice.cleanup.Path.exists")
    @patch("voice.cleanup.Path.unlink")
    @patch("voice.cleanup.Path.stat")
    def test_cleanup_dry_run(self, mock_stat, mock_unlink, mock_exists, mock_scan):
        mock_scan.return_value = {
            "torch": [
                VoiceCacheInfo(
                    voice_id="am_michael",
                    file_path=Path("/cache/am_michael.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
                VoiceCacheInfo(
                    voice_id="bf_emma",
                    file_path=Path("/cache/bf_emma.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
            ],
            "onnx": [],
        }
        mock_exists.return_value = True
        mock_stat.return_value = MagicMock(st_size=523000)

        report = cleanup_unused_voices(keep_voice="am_michael", backends=["torch"], dry_run=True)

        assert report.deleted_count == 1
        assert report.freed_bytes == 523000
        assert report.dry_run is True
        # Files should not be unlinked in dry run
        mock_unlink.assert_not_called()

    @patch("voice.cleanup.scan_kokoro_cache")
    @patch("voice.cleanup.Path.exists")
    @patch("voice.cleanup.Path.unlink")
    @patch("voice.cleanup.Path.stat")
    def test_cleanup_both_backends(self, mock_stat, mock_unlink, mock_exists, mock_scan):
        mock_scan.return_value = {
            "torch": [
                VoiceCacheInfo(
                    voice_id="am_michael",
                    file_path=Path("/cache/am_michael.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
                VoiceCacheInfo(
                    voice_id="bf_emma",
                    file_path=Path("/cache/bf_emma.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
            ],
            "onnx": [
                VoiceCacheInfo(
                    voice_id="am_michael",
                    file_path=Path("/cache/am_michael.bin"),
                    size_bytes=523000,
                    repo_id="onnx-community/Kokoro-82M-v1.0-ONNX",
                    revision="rev2",
                    backend="onnx",
                ),
                VoiceCacheInfo(
                    voice_id="bf_emma",
                    file_path=Path("/cache/bf_emma.bin"),
                    size_bytes=523000,
                    repo_id="onnx-community/Kokoro-82M-v1.0-ONNX",
                    revision="rev2",
                    backend="onnx",
                ),
            ],
        }
        mock_exists.return_value = True
        mock_stat.return_value = MagicMock(st_size=523000)

        report = cleanup_unused_voices(keep_voice="am_michael", backends=["torch", "onnx"], dry_run=False)

        assert report.deleted_count == 2  # bf_emma in both backends
        assert report.freed_bytes == 2 * 523000
        # am_michael files are kept
        assert len(report.kept_files) == 2


class TestGetCacheStatus:
    """Tests for get_cache_status."""

    @patch("voice.cleanup.scan_kokoro_cache")
    def test_cache_status_calculation(self, mock_scan):
        mock_scan.return_value = {
            "torch": [
                VoiceCacheInfo(
                    voice_id="am_michael",
                    file_path=Path("/cache/am_michael.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
                VoiceCacheInfo(
                    voice_id="bf_emma",
                    file_path=Path("/cache/bf_emma.pt"),
                    size_bytes=523000,
                    repo_id="hexgrad/Kokoro-82M",
                    revision="rev1",
                    backend="torch",
                ),
            ],
            "onnx": [
                VoiceCacheInfo(
                    voice_id="am_michael",
                    file_path=Path("/cache/am_michael.bin"),
                    size_bytes=523000,
                    repo_id="onnx-community/Kokoro-82M-v1.0-ONNX",
                    revision="rev2",
                    backend="onnx",
                ),
            ],
        }

        status = get_cache_status(keep_voice="am_michael")

        assert status["total_voices_cached"] == 3
        assert status["total_size_bytes"] == 3 * 523000
        assert status["keep_voice"] == "am_michael"
        assert status["keep_voice_size_bytes"] == 2 * 523000  # am_michael in both backends
        assert status["deletable_voices"] == 1  # bf_emma only (in torch)
        assert status["deletable_size_bytes"] == 523000
        assert "torch" in status["by_backend"]
        assert "onnx" in status["by_backend"]
        assert status["by_backend"]["torch"]["count"] == 2
        assert status["by_backend"]["onnx"]["count"] == 1


class TestCleanupOnnxPatchedModels:
    """Tests for _cleanup_onnx_patched_models."""

    def test_cleanup_no_patched_models(self):
        # Test with non-existent directory
        removed = _cleanup_onnx_patched_models("/nonexistent/path")
        assert removed == 0


class TestAgainstARealCacheLayout:
    """The same functions on real files, shaped as `huggingface_hub` returns them.

    10 October 2026: the scan called `.startswith` on `file_path`, which is a `Path`,
    so Settings showed "Internal Server Error" on any machine with a Kokoro cache; and
    the delete step built paths that are not in the cache layout. Both had only ever run
    against mocks that were strings.
    """

    def _cache(self, tmp_path, *, separate_blobs):
        from types import SimpleNamespace

        snapshot = tmp_path / "models--hexgrad--Kokoro-82M" / "snapshots" / "rev1"
        blobs = tmp_path / "models--hexgrad--Kokoro-82M" / "blobs"
        (snapshot / "voices").mkdir(parents=True)
        blobs.mkdir(parents=True)
        files = []
        for index, voice in enumerate(["am_michael", "af_bella", "am_adam"]):
            path = snapshot / "voices" / f"{voice}.pt"
            path.write_bytes(b"x" * (1000 + index))
            blob = path
            if separate_blobs:
                blob = blobs / f"blob{index}"
                blob.write_bytes(b"y" * (2000 + index))
            files.append(SimpleNamespace(file_path=path, blob_path=blob, size_on_disk=blob.stat().st_size))
        # A file that is not a voice must never be touched.
        config = snapshot / "config.json"
        config.write_text("{}")
        files.append(SimpleNamespace(file_path=config, blob_path=config, size_on_disk=2))
        revision = SimpleNamespace(commit_hash="rev1", snapshot_path=snapshot, files=files)
        repo = SimpleNamespace(repo_id="hexgrad/Kokoro-82M", revisions=[revision])
        return snapshot, blobs, SimpleNamespace(repos=[repo])

    def test_the_scan_finds_the_voices_and_ignores_everything_else(self, tmp_path):
        _, _, info = self._cache(tmp_path, separate_blobs=False)
        with patch("voice.cleanup._scan_cache_dir", return_value=info), patch(
            "voice.cleanup._hf_hub_cache", return_value=str(tmp_path)
        ):
            found = scan_kokoro_cache()
        assert sorted(v.voice_id for v in found["torch"]) == ["af_bella", "am_adam", "am_michael"]
        assert all(v.file_path.is_absolute() for v in found["torch"])

    def test_a_dry_run_names_what_would_go_and_removes_nothing(self, tmp_path):
        snapshot, _, info = self._cache(tmp_path, separate_blobs=False)
        with patch("voice.cleanup._scan_cache_dir", return_value=info), patch(
            "voice.cleanup._hf_hub_cache", return_value=str(tmp_path)
        ):
            report = cleanup_unused_voices(keep_voice="am_michael", dry_run=True)
        assert report.deleted_count == 2 and report.dry_run is True
        assert all((snapshot / "voices" / f"{v}.pt").exists() for v in ("am_michael", "af_bella", "am_adam"))

    def test_the_voice_to_keep_stays_and_the_others_and_only_they_go(self, tmp_path):
        snapshot, _, info = self._cache(tmp_path, separate_blobs=False)
        with patch("voice.cleanup._scan_cache_dir", return_value=info), patch(
            "voice.cleanup._hf_hub_cache", return_value=str(tmp_path)
        ):
            report = cleanup_unused_voices(keep_voice="am_michael", dry_run=False)
        assert (snapshot / "voices" / "am_michael.pt").exists()
        assert not (snapshot / "voices" / "af_bella.pt").exists()
        assert not (snapshot / "voices" / "am_adam.pt").exists()
        assert (snapshot / "config.json").exists()
        assert report.deleted_count == 2 and report.errors == []
        assert report.freed_bytes == 1001 + 1002

    def test_with_separate_blobs_the_blob_goes_too_and_the_freed_figure_is_the_blob(self, tmp_path):
        snapshot, blobs, info = self._cache(tmp_path, separate_blobs=True)
        with patch("voice.cleanup._scan_cache_dir", return_value=info), patch(
            "voice.cleanup._hf_hub_cache", return_value=str(tmp_path)
        ):
            report = cleanup_unused_voices(keep_voice="am_michael", dry_run=False)
        assert (blobs / "blob0").exists(), "the kept voice's bytes must survive"
        assert not (blobs / "blob1").exists() and not (blobs / "blob2").exists()
        assert report.freed_bytes == 2001 + 2002
