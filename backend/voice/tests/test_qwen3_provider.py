"""Tests for Qwen3-TTS Provider (Tier 3 stub)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock
import sys

import pytest

from voice.providers.qwen3_tts import (
    Qwen3TTSProvider,
    AudioResult,
    AudioChunk,
    bootstrap_qwen3_tts,
)
from voice.config import Qwen3TTSConfig
from voice.health import AudioCache


class TestQwen3TTSConfig:
    """Tests for Qwen3TTSConfig."""

    def test_defaults(self):
        config = Qwen3TTSConfig()
        assert config.default_provider == "qwen3_tts"
        assert config.default_voice == "qwen3-default"
        assert config.sample_rate == 24000
        assert config.device == "cpu"
        # Don't test exact n_threads since it depends on cpu_count()
        assert config.n_gpu_layers == 0
        assert config.context_size == 4096
        assert config.use_mlock is True
        assert config.use_mmap is True

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("ZARAM_VOICE_QWEN3_DEVICE", "cuda")
        monkeypatch.setenv("ZARAM_VOICE_QWEN3_N_THREADS", "8")
        monkeypatch.setenv("ZARAM_VOICE_QWEN3_N_GPU_LAYERS", "32")
        monkeypatch.setenv("ZARAM_VOICE_QWEN3_CONTEXT_SIZE", "8192")
        monkeypatch.setenv("ZARAM_VOICE_QWEN3_MLOCK", "0")
        monkeypatch.setenv("ZARAM_VOICE_QWEN3_MMAP", "0")

        config = Qwen3TTSConfig.load()
        assert config.device == "cuda"
        assert config.n_threads == 8
        assert config.n_gpu_layers == 32
        assert config.context_size == 8192
        assert config.use_mlock is False
        assert config.use_mmap is False


class TestQwen3TTSProvider:
    """Tests for Qwen3TTSProvider."""

    @pytest.fixture
    def config(self):
        return Qwen3TTSConfig()

    @pytest.fixture
    def provider(self, config):
        return Qwen3TTSProvider(config=config)

    @pytest.mark.asyncio
    async def test_initialization_no_llama_cpp(self, provider):
        await provider.initialize()
        assert provider._initialized is True

    @pytest.mark.asyncio
    async def test_initialization_with_llama_cpp(self, provider):
        mock_llama_cpp = MagicMock()
        sys.modules["llama_cpp"] = mock_llama_cpp
        try:
            await provider.initialize()
            assert provider._initialized is True
        finally:
            if "llama_cpp" in sys.modules:
                del sys.modules["llama_cpp"]

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text(self, provider):
        await provider.initialize()
        result = await provider.generate_audio("", voice="qwen3-default")
        assert result.success is False
        assert result.error == "empty_text"

    @pytest.mark.asyncio
    async def test_generate_audio_not_implemented(self, provider):
        await provider.initialize()
        result = await provider.generate_audio("Hello world", voice="qwen3-default")
        assert result.success is False
        assert "not yet implemented" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stream_audio(self, provider):
        await provider.initialize()
        chunks = []
        async for chunk in provider.stream_audio("Hello", voice="qwen3-default"):
            chunks.append(chunk)

    @pytest.mark.asyncio
    async def test_available_voices(self, provider):
        await provider.initialize()
        voices = await provider.available_voices()
        assert "qwen3-default" in voices
        assert voices["qwen3-default"]["provider"] == "qwen3_tts"

    @pytest.mark.asyncio
    async def test_health_check_no_llama_cpp(self, provider):
        await provider.initialize()
        health = await provider.health_check()
        assert health["provider"] == "qwen3_tts"
        assert health["available"] is False
        assert health["checks"]["llama_cpp_available"] is False

    @pytest.mark.asyncio
    async def test_health_check_with_llama_cpp(self, provider):
        mock_llama_cpp = MagicMock()
        sys.modules["llama_cpp"] = mock_llama_cpp
        try:
            await provider.initialize()
            health = await provider.health_check()
            assert health["available"] is True
            assert health["checks"]["llama_cpp_available"] is True
        finally:
            if "llama_cpp" in sys.modules:
                del sys.modules["llama_cpp"]

    @pytest.mark.asyncio
    async def test_health_check_ram_sufficient(self, provider):
        mock_llama_cpp = MagicMock()
        sys.modules["llama_cpp"] = mock_llama_cpp
        try:
            import voice.providers.qwen3_tts as qwen3_mod
            with patch.object(qwen3_mod, 'psutil', create=True) as mock_psutil:
                mock_psutil.virtual_memory.return_value = MagicMock(total=32 * 1024**3)  # 32GB
                await provider.initialize()
                health = await provider.health_check()
                assert health["checks"]["ram_sufficient"] is True
        finally:
            if "llama_cpp" in sys.modules:
                del sys.modules["llama_cpp"]

    @pytest.mark.asyncio
    async def test_health_check_ram_insufficient(self, provider):
        mock_llama_cpp = MagicMock()
        sys.modules["llama_cpp"] = mock_llama_cpp
        try:
            # ram_sufficient = total >= 16GB. `health_check` imports psutil inside the
            # function, so the module it finds is what decides -- patching an attribute
            # on this module left it reading the real machine's memory.
            mock_psutil = MagicMock()
            mock_psutil.virtual_memory.return_value = MagicMock(total=8 * 1024**3)  # 8GB
            with patch.dict(sys.modules, {"psutil": mock_psutil}):
                await provider.initialize()
                health = await provider.health_check()
                assert health["checks"]["ram_sufficient"] is False
        finally:
            if "llama_cpp" in sys.modules:
                del sys.modules["llama_cpp"]

    @pytest.mark.asyncio
    async def test_shutdown(self, provider):
        await provider.initialize()
        await provider.shutdown()
        assert provider._initialized is False


class TestBootstrapQwen3TTS:
    """Tests for bootstrap_qwen3_tts."""

    @pytest.mark.asyncio
    async def test_bootstrap_registers_and_initializes(self):
        mock_manager = MagicMock()
        mock_manager.register_provider = AsyncMock()
        mock_manager.initialize = AsyncMock()

        provider = await bootstrap_qwen3_tts(mock_manager)

        assert isinstance(provider, Qwen3TTSProvider)
        mock_manager.register_provider.assert_called_once_with("qwen3_tts", provider, set_active=True)
        mock_manager.initialize.assert_called_once()