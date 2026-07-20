# backend/tests/test_artifacts.py
"""Tests for the Artifact Runtime."""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from runtimes.artifacts.runtime import ArtifactRuntime, ArtifactType


class _FakeEventBus:
    def subscribe(self, *args, **kwargs):
        return "sub_0"

    def publish(self, event):
        pass


def test_artifact_runtime_create():
    runtime = ArtifactRuntime(_FakeEventBus())
    artifact = runtime.create("Test", ArtifactType.TEXT, "Hello")
    assert artifact.id is not None
    assert artifact.name == "Test"
    assert artifact.type == ArtifactType.TEXT
    assert artifact.content == "Hello"
    assert len(artifact.versions) == 1


def test_artifact_runtime_get():
    runtime = ArtifactRuntime(_FakeEventBus())
    artifact = runtime.create("Get Me", ArtifactType.TEXT, "content")
    fetched = runtime.get(artifact.id)
    assert fetched is not None
    assert fetched.name == "Get Me"


def test_artifact_runtime_list():
    runtime = ArtifactRuntime(_FakeEventBus())
    runtime.create("A", ArtifactType.TEXT)
    runtime.create("B", ArtifactType.CODE)
    runtime.create("C", ArtifactType.TEXT)
    all_items = runtime.list()
    assert len(all_items) == 3
    text_items = runtime.list(filter_type=ArtifactType.TEXT)
    assert len(text_items) == 2


def test_artifact_runtime_update():
    runtime = ArtifactRuntime(_FakeEventBus())
    artifact = runtime.create("Updatable", ArtifactType.TEXT, "old")
    updated = runtime.update(artifact.id, name="New Name", content="new", pinned=True)
    assert updated is not None
    assert updated.name == "New Name"
    assert updated.content == "new"
    assert updated.pinned is True


def test_artifact_runtime_delete():
    runtime = ArtifactRuntime(_FakeEventBus())
    artifact = runtime.create("Delete Me", ArtifactType.TEXT)
    assert len(runtime.list()) == 1
    deleted = runtime.delete(artifact.id)
    assert deleted is True
    assert len(runtime.list()) == 0
    assert runtime.delete(artifact.id) is False


def test_artifact_runtime_duplicate():
    runtime = ArtifactRuntime(_FakeEventBus())
    artifact = runtime.create("Original", ArtifactType.TEXT, "content")
    duplicated = runtime.duplicate(artifact.id)
    assert duplicated is not None
    assert duplicated.name == "Original (Copy)"
    assert duplicated.parent_id == artifact.id
    assert duplicated.content == "content"
    assert len(runtime.list()) == 2


def test_artifact_runtime_versions():
    runtime = ArtifactRuntime(_FakeEventBus())
    artifact = runtime.create("Versioned", ArtifactType.TEXT, "v1")
    runtime.update(artifact.id, content="v2")
    v2 = runtime.save_version(artifact.id)
    assert v2 is not None
    assert v2.content == "v2"
    assert len(artifact.versions) == 2
    reverted = runtime.revert_to_version(artifact.id, artifact.versions[0].id)
    assert reverted is True
    assert artifact.content == "v1"


def test_artifact_runtime_search():
    runtime = ArtifactRuntime(_FakeEventBus())
    runtime.create("Documentation", ArtifactType.MARKDOWN, "alpha")
    runtime.create("Source Code", ArtifactType.CODE, "beta")
    results = runtime.list(search="doc")
    assert len(results) == 1
    assert results[0].name == "Documentation"


def test_artifact_runtime_pinned():
    runtime = ArtifactRuntime(_FakeEventBus())
    a1 = runtime.create("A", ArtifactType.TEXT)
    a2 = runtime.create("B", ArtifactType.TEXT)
    runtime.update(a1.id, pinned=True)
    pinned = runtime.list(pinned=True)
    assert len(pinned) == 1
    assert pinned[0].id == a1.id
