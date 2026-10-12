"""Tests for Chatterbox Turbo Provider (Tier 2 stub)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock
import sys

import pytest

from voice.providers.chatterbox_turbo import (
    ChatterboxTurboProvider,
    AudioResult,
    AudioChunk,
    bootstrap_chatterbox_turbo,
)
from voice.config import ChatterboxTurboConfig
from voice.health import AudioCache


class TestChatterboxTurboConfig:
    """Tests for ChatterboxTurboConfig."""

    def test_defaults(self):
        config = ChatterboxTurboConfig()
        assert config.default_provider == "chatterbox_turbo"
        assert config.default_voice == "chatterbox-default"
        assert config.sample_rate == 24000
        assert config.device == "cuda"
        assert config.max_vram_gb == 2.0
        assert config.compile_model is True
        assert config.fp16 is True
        assert config.zero_shot_cloning is True

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("ZARAM_VOICE_CHATTERBOX_DEVICE", "cpu")
        monkeypatch.setenv("ZARAM_VOICE_CHATTERBOX_MAX_VRAM", "3.0")
        monkeypatch.setenv("ZARAM_VOICE_CHATTERBOX_COMPILE", "0")
        monkeypatch.setenv("ZARAM_VOICE_CHATTERBOX_FP16", "0")
        monkeypatch.setenv("ZARAM_VOICE_CHATTERBOX_ZERO_SHOT", "0")

        config = ChatterboxTurboConfig.load()
        assert config.device == "cpu"
        assert config.max_vram_gb == 3.0
        assert config.compile_model is False
        assert config.fp16 is False
        assert config.zero_shot_cloning is False


class TestChatterboxTurboProvider:
    """Tests for ChatterboxTurboProvider."""

    @pytest.fixture
    def config(self):
        return ChatterboxTurboConfig()

    @pytest.fixture
    def provider(self, config):
        return ChatterboxTurboProvider(config=config)

    @pytest.mark.asyncio
    async def test_initialization_cuda_not_available(self, provider):
        # Import torch inside the test to mock it properly
        import torch
        original_is_available = torch.cuda.is_available
        try:
            torch.cuda.is_available = lambda: False
            await provider.initialize()
        finally:
            torch.cuda.is_available = original_is_available
        assert provider._initialized is True

    @pytest.mark.asyncio
    async def test_initialization_cuda_available_insufficient_vram(self, provider):
        import torch
        original_is_available = torch.cuda.is_available
        original_mem_get_info = torch.cuda.mem_get_info
        try:
            torch.cuda.is_available = lambda: True
            torch.cuda.mem_get_info = lambda: (1024**3, 1024**3 * 1.5)  # 1.5GB free
            await provider.initialize()
        finally:
            torch.cuda.is_available = original_is_available
            torch.cuda.mem_get_info = original_mem_get_info
        assert provider._initialized is True

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text(self, provider):
        await provider.initialize()
        result = await provider.generate_audio("", voice="chatterbox-default")
        assert result.success is False
        assert result.error == "empty_text"

    @pytest.mark.asyncio
    async def test_generate_audio_not_implemented(self, provider):
        await provider.initialize()
        result = await provider.generate_audio("Hello world", voice="chatterbox-default")
        assert result.success is False
        assert "not yet implemented" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stream_audio(self, provider):
        await provider.initialize()
        chunks = []
        async for chunk in provider.stream_audio("Hello", voice="chatterbox-default"):
            chunks.append(chunk)
        # Should yield at least once

    @pytest.mark.asyncio
    async def test_available_voices(self, provider):
        await provider.initialize()
        voices = await provider.available_voices()
        assert "chatterbox-default" in voices
        assert voices["chatterbox-default"]["provider"] == "chatterbox_turbo"

    @pytest.mark.asyncio
    async def test_health_check_cuda_available(self, provider):
        import torch
        original_is_available = torch.cuda.is_available
        original_mem_get_info = torch.cuda.mem_get_info
        original_get_device_properties = torch.cuda.get_device_properties
        try:
            torch.cuda.is_available = lambda: True
            torch.cuda.mem_get_info = lambda: (1024**3 * 3, 1024**3 * 4)  # 3GB free, 4GB total
            torch.cuda.get_device_properties = lambda _: MagicMock(total_memory=12 * 1024**3)
            await provider.initialize()
            health = await provider.health_check()
            assert health["provider"] == "chatterbox_turbo"
            assert health["available"] is True
            assert health["checks"]["cuda_available"] is True
            assert health["checks"]["vram_sufficient"] is True
        finally:
            torch.cuda.is_available = original_is_available
            torch.cuda.mem_get_info = original_mem_get_info
            torch.cuda.get_device_properties = original_get_device_properties

    @pytest.mark.asyncio
    async def test_health_check_cuda_not_available(self, provider):
        import torch
        original_is_available = torch.cuda.is_available
        try:
            torch.cuda.is_available = lambda: False
            await provider.initialize()
            health = await provider.health_check()
            assert health["available"] is False
            assert health["checks"]["cuda_available"] is False
        finally:
            torch.cuda.is_available = original_is_available

    @pytest.mark.asyncio
    async def test_shutdown(self, provider):
        await provider.initialize()
        await provider.shutdown()
        assert provider._initialized is False


class TestBootstrapChatterboxTurbo:
    """Tests for bootstrap_chatterbox_turbo."""

    @pytest.mark.asyncio
    async def test_bootstrap_registers_and_initializes(self):
        mock_manager = MagicMock()
        mock_manager.register_provider = AsyncMock()
        mock_manager.initialize = AsyncMock()

        provider = await bootstrap_chatterbox_turbo(mock_manager)

        assert isinstance(provider, ChatterboxTurboProvider)
        mock_manager.register_provider.assert_called_once_with("chatterbox_turbo", provider, set_active=True)
        mock_manager.initialize.assert_called_once()