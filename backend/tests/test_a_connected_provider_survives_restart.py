"""Connecting a cloud provider has to outlive the process.

Reported by the maintainer, 31 August 2026: OpenRouter had worked for weeks and
stopped. The key was real and had been entered in Settings.

`connect` wrote it into `os.environ` and nowhere else, so it lasted exactly as
long as the backend process. On the next launch the only thing that came back
was the operating system's own environment, which on that machine held a Windows
*User* variable containing the literal string ``your-new-key``. Zaram sent it and
OpenRouter answered ``401 Missing Authentication header`` — a real credential
silently discarded at the first restart, and a forgotten placeholder winning over
a deliberate act.

Two halves, and both are needed. Connections are written to disk. And a saved
connection beats the environment rather than the other way round: typing a key
into the application is the more recent and more deliberate statement of intent,
while an exported variable is a default for the case where nobody has made one.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A connections file of this test's own, with module state reset."""
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))

    import core.paths as paths

    for cache in ("_data_dir", "_DATA_DIR"):
        if hasattr(paths, cache):
            monkeypatch.setattr(paths, cache, None, raising=False)

    from providers import cloud_config

    monkeypatch.setattr(cloud_config, "_connections", {}, raising=False)
    monkeypatch.setattr(cloud_config, "_providers_runtime", None, raising=False)
    monkeypatch.setattr(cloud_config, "_reload_engine", lambda: None, raising=False)
    monkeypatch.setattr(cloud_config, "_register_adapter", lambda c: None, raising=False)
    return cloud_config


class TestItIsWrittenDown:
    async def test_connecting_persists_the_key(self, store, tmp_path):
        await store.connect(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-real-key",
            provider_id="openrouter",
        )

        saved = json.loads((tmp_path / "cloud-connections.json").read_text("utf-8"))
        rows = saved["connections"]

        assert [r["provider_id"] for r in rows] == ["openrouter"]
        assert rows[0]["api_key"] == "sk-real-key"

    async def test_it_comes_back_after_a_restart(self, store, monkeypatch):
        """The defect itself. A new process, and the key is still there."""
        await store.connect(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-real-key",
            provider_id="openrouter",
        )

        monkeypatch.setattr(store, "_connections", {}, raising=False)
        store.seed_from_environment()

        assert store._connections["openrouter"].api_key == "sk-real-key"

    async def test_disconnecting_is_also_remembered(self, store, monkeypatch):
        await store.connect(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-real-key",
            provider_id="openrouter",
        )
        store.disconnect("openrouter")

        monkeypatch.setattr(store, "_connections", {}, raising=False)
        store.seed_from_environment()

        assert "openrouter" not in store._connections, (
            "a provider the user removed must not return on the next launch"
        )


class TestTheSavedKeyWins:
    async def test_a_stale_environment_variable_does_not_overwrite_it(
        self, store, monkeypatch
    ):
        """The exact shape of the bug, with the exact placeholder that caused it."""
        await store.connect(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-real-key",
            provider_id="openrouter",
        )

        monkeypatch.setattr(store, "_connections", {}, raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "your-new-key")
        store.seed_from_environment()

        assert store._connections["openrouter"].api_key == "sk-real-key", (
            "a forgotten shell variable beat a key the user typed into Settings, "
            "and the product reported the provider as broken"
        )

    def test_the_environment_still_seeds_when_nothing_is_saved(
        self, store, monkeypatch
    ):
        """Filling a gap is the environment's job and it keeps it.

        Someone who exports a key before launch and never opens Settings must
        still get a working provider.
        """
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")
        store.seed_from_environment()

        assert store._connections["openrouter"].api_key == "sk-from-env"

    def test_a_corrupt_store_costs_the_saved_providers_and_nothing_else(
        self, store, tmp_path, monkeypatch
    ):
        """Local answering must survive a file this module wrote badly."""
        (tmp_path / "cloud-connections.json").write_text("{ not json", encoding="utf-8")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")

        store.seed_from_environment()

        assert store._connections["openrouter"].api_key == "sk-from-env"
