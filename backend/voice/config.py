"""Configuration for the Kokoro voice provider.

All Kokoro runtime settings live here so nothing is hard-coded across the
provider. Values are resolved from environment variables (``ZARAM_VOICE_*``)
with sensible, project-relative defaults. Paths are resolved relative to the
backend package root, never as absolute literals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_REPO_ID = "hexgrad/Kokoro-82M"
DEFAULT_LANG_CODE = "a"
DEFAULT_VOICE = "af_heart"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_CACHE_SUBDIR = "audio_cache"
ENV_PREFIX = "ZARAM_VOICE_"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _backend_root() -> Path:
    """Resolve the backend/ directory (parent of the voice package)."""
    return Path(__file__).resolve().parent.parent


def _resolve_cache_dir(value: str) -> str:
    """Resolve a cache directory, relative paths anchored to backend root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _backend_root() / path
    return str(path)


@dataclass
class KokoroConfig:
    default_provider: str = "kokoro"
    default_voice: str = DEFAULT_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    cache_directory: str = DEFAULT_CACHE_SUBDIR
    lang_code: str = DEFAULT_LANG_CODE
    repo_id: str = DEFAULT_REPO_ID
    device: Optional[str] = None
    load_model_eagerly: bool = False
    run_synthesis_probe: bool = False
    voice_discovery_enabled: bool = True

    def resolved_cache_directory(self) -> str:
        return _resolve_cache_dir(self.cache_directory)

    @classmethod
    def load(cls, **overrides: object) -> "KokoroConfig":
        """Build a config from environment variables plus explicit overrides."""
        config = cls(
            default_provider=os.getenv(f"{ENV_PREFIX}DEFAULT_PROVIDER", cls.default_provider),
            default_voice=os.getenv(f"{ENV_PREFIX}DEFAULT_VOICE", cls.default_voice),
            sample_rate=int(os.getenv(f"{ENV_PREFIX}SAMPLE_RATE", cls.sample_rate)),
            cache_directory=os.getenv(f"{ENV_PREFIX}CACHE_DIR", cls.cache_directory),
            lang_code=os.getenv(f"{ENV_PREFIX}LANG_CODE", cls.lang_code),
            repo_id=os.getenv(f"{ENV_PREFIX}REPO_ID", cls.repo_id),
            device=os.getenv(f"{ENV_PREFIX}DEVICE") or None,
            load_model_eagerly=_env_bool(f"{ENV_PREFIX}EAGER_LOAD", cls.load_model_eagerly),
            run_synthesis_probe=_env_bool(f"{ENV_PREFIX}SYNTHESIS_PROBE", cls.run_synthesis_probe),
            voice_discovery_enabled=_env_bool(f"{ENV_PREFIX}DISCOVERY", cls.voice_discovery_enabled),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        config.cache_directory = config.resolved_cache_directory()
        return config
