"""Read-only API tests for the provider layer (offline).

Builds an isolated FastAPI app mounting the provider layer router with a manager
populated by offline fakes — no server, no network.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from providers.api import router, set_providers_runtime
from providers.runtime import ProvidersRuntime


def _build_app(manager) -> FastAPI:
    rt = ProvidersRuntime(
        event_bus=None,
        registry=manager.registry,
        scanner=manager.scanner,
        manager=manager,
        hardware_profiler=None,
    )
    set_providers_runtime(rt)
    app = FastAPI()
    app.include_router(router)
    return app


async def test_api_models(manager):
    await manager.refresh(timeout=1.0)
    client = TestClient(_build_app(manager))
    r = client.get("/providers/models")
    assert r.status_code == 200
    assert len(r.json()) == 4


async def test_api_model_detail_and_404(manager):
    await manager.refresh(timeout=1.0)
    client = TestClient(_build_app(manager))
    ok = client.get("/providers/models/p1:llm-a")
    assert ok.status_code == 200
    assert ok.json()["id"] == "p1:llm-a"
    missing = client.get("/providers/models/nope")
    assert missing.status_code == 404


async def test_api_providers_voices_runtimes_personalities(manager):
    await manager.refresh(timeout=1.0)
    client = TestClient(_build_app(manager))
    assert len(client.get("/providers/sources").json()) == 2
    assert len(client.get("/providers/voices").json()) == 1
    assert {r["runtime_id"] for r in client.get("/providers/runtimes").json()} == {"media", "voice"}
    assert client.get("/providers/personalities").json()[0]["id"] == "zaram_prime"


async def test_api_hardware_and_health(manager):
    await manager.refresh(timeout=1.0)
    client = TestClient(_build_app(manager))
    hw = client.get("/providers/hardware").json()
    assert hw["cpu_count"] == 8
    health = client.get("/providers/health").json()
    assert health["model_count"] == 4
    assert health["runtime_count"] == 2


def test_api_503_without_runtime():
    set_providers_runtime(None)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/providers/models").status_code == 503
