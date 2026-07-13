"""Media Asset model tests (offline)."""

from __future__ import annotations

import pytest

from media.assets import MediaAsset
from media.contracts import MediaType


def test_asset_defaults():
    asset = MediaAsset()
    assert asset.type is MediaType.UNKNOWN
    assert asset.id.startswith("asset_")
    assert asset.metadata == {}


def test_asset_create_with_enum_type():
    asset = MediaAsset.create(
        type=MediaType.AUDIO,
        provider="kokoro",
        mime_type="audio/wav",
        location="/tmp/a.wav",
        streamable=True,
        duration=3.5,
        format="wav",
        size=1234,
    )
    assert asset.type is MediaType.AUDIO
    assert asset.provider == "kokoro"
    assert asset.streamable is True
    assert asset.duration == 3.5
    assert asset.is_streamable
    assert asset.is_persisted is False  # /tmp/a.wav does not exist


def test_asset_create_with_string_type():
    asset = MediaAsset.create(type="image", provider="vision")
    assert asset.type is MediaType.IMAGE


def test_asset_create_invalid_type_falls_back():
    asset = MediaAsset.create(type="does-not-exist", provider="x")
    assert asset.type is MediaType.UNKNOWN


def test_asset_roundtrip_dict():
    asset = MediaAsset.create(
        type="video", provider="ffmpeg", mime_type="video/mp4", duration=10.0
    )
    restored = MediaAsset.from_dict(asset.to_dict())
    assert restored.id == asset.id
    assert restored.type is MediaType.VIDEO
    assert restored.provider == "ffmpeg"
    assert restored.duration == 10.0


def test_asset_type_value_property():
    asset = MediaAsset.create(type=MediaType.SENSOR, provider="lidar")
    assert asset.type_value == "sensor"
