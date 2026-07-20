import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class ArtifactType(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    CODE = "code"
    IMAGE = "image"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    HTML = "html"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class ArtifactVersion:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    artifact_id: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    created_by: str = "system"


@dataclass
class Artifact:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: ArtifactType = ArtifactType.TEXT
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    pinned: bool = False
    versions: list[ArtifactVersion] = field(default_factory=list)
    current_version_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "system"
    parent_id: str | None = None
    tags: list[str] = field(default_factory=list)


class ArtifactRuntime:
    def __init__(self, event_bus):
        self._artifacts: dict[str, Artifact] = {}
        self._event_bus = event_bus
        self._runtime_id = "artifacts"

    def get_runtime_id(self) -> str:
        return self._runtime_id

    def get_metadata(self):
        from core.contracts import RuntimeMetadata, Capability
        return RuntimeMetadata(
            runtime_id=self._runtime_id,
            version="1.0.0",
            capabilities=[
                Capability(id="artifact.create", runtime_id=self._runtime_id),
                Capability(id="artifact.read", runtime_id=self._runtime_id),
                Capability(id="artifact.update", runtime_id=self._runtime_id),
                Capability(id="artifact.delete", runtime_id=self._runtime_id),
                Capability(id="artifact.version", runtime_id=self._runtime_id),
            ],
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        self._artifacts.clear()

    def create(self, name: str, type: ArtifactType, content: str = "", metadata: dict | None = None, tags: list[str] | None = None, parent_id: str | None = None) -> Artifact:
        now = time.time()
        version = ArtifactVersion(
            artifact_id="",
            content=content,
            metadata=metadata or {},
            created_at=now,
            created_by="system",
        )
        version.artifact_id = version.id
        artifact = Artifact(
            name=name,
            type=type,
            content=content,
            metadata=metadata or {},
            versions=[version],
            current_version_id=version.id,
            created_at=now,
            updated_at=now,
            parent_id=parent_id,
            tags=tags or [],
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    def list(self, filter_type: ArtifactType | None = None, pinned: bool | None = None, search: str | None = None) -> list[Artifact]:
        results = list(self._artifacts.values())
        if filter_type:
            results = [a for a in results if a.type == filter_type]
        if pinned is not None:
            results = [a for a in results if a.pinned == pinned]
        if search:
            q = search.lower()
            results = [a for a in results if q in a.name.lower() or q in a.content.lower()]
        results.sort(key=lambda a: a.updated_at, reverse=True)
        return results

    def update(self, artifact_id: str, **kwargs) -> Artifact | None:
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            return None
        for key, value in kwargs.items():
            if hasattr(artifact, key):
                setattr(artifact, key, value)
        artifact.updated_at = time.time()
        return artifact

    def delete(self, artifact_id: str) -> bool:
        if artifact_id in self._artifacts:
            del self._artifacts[artifact_id]
            return True
        return False

    def duplicate(self, artifact_id: str) -> Artifact | None:
        original = self._artifacts.get(artifact_id)
        if not original:
            return None
        now = time.time()
        version = ArtifactVersion(
            content=original.content,
            metadata=dict(original.metadata),
            created_at=now,
            created_by="system",
        )
        version.artifact_id = version.id
        duplicated = Artifact(
            name=f"{original.name} (Copy)",
            type=original.type,
            content=original.content,
            metadata=dict(original.metadata),
            versions=[version],
            current_version_id=version.id,
            created_at=now,
            updated_at=now,
            parent_id=original.id,
            tags=list(original.tags),
        )
        self._artifacts[duplicated.id] = duplicated
        return duplicated

    def save_version(self, artifact_id: str) -> ArtifactVersion | None:
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            return None
        version = ArtifactVersion(
            artifact_id=artifact_id,
            content=artifact.content,
            metadata=dict(artifact.metadata),
            created_at=time.time(),
            created_by="system",
        )
        artifact.versions.append(version)
        artifact.current_version_id = version.id
        artifact.updated_at = time.time()
        return version

    def revert_to_version(self, artifact_id: str, version_id: str) -> bool:
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            return False
        version = next((v for v in artifact.versions if v.id == version_id), None)
        if not version:
            return False
        artifact.content = version.content
        artifact.metadata = dict(version.metadata)
        artifact.current_version_id = version_id
        artifact.updated_at = time.time()
        return True

    def get_state(self):
        return "ready"

    def health_check(self):
        return {"state": "ready"}
