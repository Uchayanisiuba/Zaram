"""Tests for Breeze TTS Provider (Tier 1 stub)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from voice.providers.breeze_tts import (
    BreezeTTSProvider,
    AudioResult,
    AudioChunk,
    bootstrap_breeze_tts,
)
from voice.config import BreezeTTSConfig
from voice.health import AudioCache


class TestBreezeTTSConfig:
    """Tests for BreezeTTSConfig."""

    def test_defaults(self):
        config = BreezeTTSConfig()
        assert config.default_provider == "breeze_tts"
        assert config.default_voice == "breeze-default"
        assert config.sample_rate == 24000
        assert config.api_endpoint == "https://api.breeze-tts.com/v1"
        assert config.api_key_env == "ZARAM_BREEZE_API_KEY"

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("ZARAM_VOICE_BREEZE_DEFAULT_VOICE", "custom-voice")
        monkeypatch.setenv("ZARAM_VOICE_BREEZE_API_ENDPOINT", "https://custom.api/v1")
        monkeypatch.setenv("ZARAM_VOICE_BREEZE_TIMEOUT", "60.0")
        monkeypatch.setenv("ZARAM_VOICE_BREEZE_STREAMING", "0")

        config = BreezeTTSConfig.load()
        assert config.default_voice == "custom-voice"
        assert config.api_endpoint == "https://custom.api/v1"
        assert config.timeout_seconds == 60.0
        assert config.streaming_enabled is False


class TestBreezeTTSProvider:
    """Tests for BreezeTTSProvider."""

    @pytest.fixture
    def config(self):
        return BreezeTTSConfig(
            api_endpoint="https://test.api/v1",
            api_key_env="TEST_BREEZE_KEY",
        )

    @pytest.fixture
    def provider(self, config):
        return BreezeTTSProvider(config=config)

    @pytest.mark.asyncio
    async def test_initialization_without_api_key(self, provider):
        with patch.dict("os.environ", {}, clear=True):
            await provider.initialize()
        assert provider._initialized is True
        assert provider._api_key is None

    @pytest.mark.asyncio
    async def test_initialization_with_api_key(self, provider, monkeypatch):
        monkeypatch.setenv("TEST_BREEZE_KEY", "test-api-key")
        await provider.initialize()
        assert provider._initialized is True
        assert provider._api_key == "test-api-key"

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text(self, provider):
        await provider.initialize()
        result = await provider.generate_audio("", voice="breeze-default")
        assert result.success is False
        assert result.error == "empty_text"

    @pytest.mark.asyncio
    async def test_generate_audio_no_api_key(self, provider):
        await provider.initialize()
        result = await provider.generate_audio("Hello world", voice="breeze-default")
        assert result.success is False
        assert "API key" in result.error

    @pytest.mark.asyncio
    async def test_generate_audio_with_api_key_but_not_implemented(self, provider, monkeypatch):
        monkeypatch.setenv("TEST_BREEZE_KEY", "test-api-key")
        await provider.initialize()

        # Mock the egress gate check
        with patch("voice.providers.breeze_tts.get_gate") as mock_gate:
            mock_gate.return_value.check.return_value = None
            result = await provider.generate_audio("Hello world", voice="breeze-default")

        assert result.success is False
        assert "not yet implemented" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stream_audio(self, provider):
        await provider.initialize()
        chunks = []
        async for chunk in provider.stream_audio("Hello", voice="breeze-default"):
            chunks.append(chunk)
        # Should yield at least once (empty async iterator)
        # The stub implementation yields once then returns

    @pytest.mark.asyncio
    async def test_available_voices(self, provider):
        await provider.initialize()
        voices = await provider.available_voices()
        assert "breeze-default" in voices
        assert voices["breeze-default"]["provider"] == "breeze_tts"

    @pytest.mark.asyncio
    async def test_health_check_no_api_key(self, provider):
        await provider.initialize()
        health = await provider.health_check()
        assert health["provider"] == "breeze_tts"
        assert health["available"] is False
        assert health["checks"]["api_key_configured"] is False

    @pytest.mark.asyncio
    async def test_health_check_with_api_key(self, provider, monkeypatch):
        monkeypatch.setenv("TEST_BREEZE_KEY", "test-api-key")
        await provider.initialize()
        health = await provider.health_check()
        assert health["available"] is True
        assert health["checks"]["api_key_configured"] is True

    @pytest.mark.asyncio
    async def test_shutdown(self, provider):
        await provider.initialize()
        await provider.shutdown()
        assert provider._initialized is False

    def test_audio_result_dataclass(self):
        result = AudioResult(
            success=True,
            request_id="test-1",
            voice="breeze-default",
            audio=b"audio_data",
            sample_rate=24000,
            duration_ms=100.0,
        )
        assert result.success is True
        assert result.request_id == "test-1"
        assert result.voice == "breeze-default"

    def test_audio_chunk_dataclass(self):
        chunk = AudioChunk(
            request_id="test-1",
            voice="breeze-default",
            index=0,
            audio=b"chunk_data",
            sample_rate=24000,
            final=True,
        )
        assert chunk.index == 0
        assert chunk.final is True


class TestBootstrapBreezeTTS:
    """Tests for bootstrap_breeze_tts."""

    @pytest.mark.asyncio
    async def test_bootstrap_registers_and_initializes(self):
        mock_manager = MagicMock()
        mock_manager.register_provider = AsyncMock()
        mock_manager.initialize = AsyncMock()

        with patch.dict("os.environ", {"TEST_BREEZE_KEY": "test-key"}):
            provider = await bootstrap_breeze_tts(mock_manager)

        assert isinstance(provider, BreezeTTSProvider)
        mock_manager.register_provider.assert_called_once_with("breeze_tts", provider, set_active=True)
        mock_manager.initialize.assert_called_once()