from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
import time

from runtimes.artifacts.runtime import ArtifactRuntime, ArtifactType


router = APIRouter(prefix="/artifacts", tags=["artifacts"])

_runtime: ArtifactRuntime | None = None


def set_artifact_runtime(runtime: ArtifactRuntime) -> None:
    global _runtime
    _runtime = runtime


class ArtifactCreateRequest(BaseModel):
    name: str
    type: str
    content: str = ""
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None
    parent_id: str | None = None


class ArtifactUpdateRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None
    pinned: bool | None = None
    tags: list[str] | None = None


class VersionRevertRequest(BaseModel):
    version_id: str


def _serialize(artifact) -> dict:
    return {
        "id": artifact.id,
        "name": artifact.name,
        "type": artifact.type.value if isinstance(artifact.type, ArtifactType) else artifact.type,
        "content": artifact.content,
        "metadata": artifact.metadata,
        "pinned": artifact.pinned,
        "versions": [
            {
                "id": v.id,
                "artifactId": v.artifact_id,
                "content": v.content,
                "metadata": v.metadata,
                "createdAt": v.created_at,
                "createdBy": v.created_by,
            }
            for v in artifact.versions
        ],
        "currentVersionId": artifact.current_version_id,
        "createdAt": artifact.created_at,
        "updatedAt": artifact.updated_at,
        "createdBy": artifact.created_by,
        "parentId": artifact.parent_id,
        "tags": artifact.tags,
    }


@router.get("")
def list_artifacts(type: str | None = None, pinned: bool | None = None, search: str | None = None):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    filter_type = ArtifactType(type) if type else None
    results = _runtime.list(filter_type=filter_type, pinned=pinned, search=search)
    return {"artifacts": [_serialize(a) for a in results]}


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    artifact = _runtime.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _serialize(artifact)


@router.post("")
def create_artifact(req: ArtifactCreateRequest):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    try:
        artifact_type = ArtifactType(req.type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid artifact type: {req.type}")
    artifact = _runtime.create(
        name=req.name,
        type=artifact_type,
        content=req.content,
        metadata=req.metadata,
        tags=req.tags,
        parent_id=req.parent_id,
    )
    return _serialize(artifact)


@router.patch("/{artifact_id}")
def update_artifact(artifact_id: str, req: ArtifactUpdateRequest):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.content is not None:
        updates["content"] = req.content
    if req.metadata is not None:
        updates["metadata"] = req.metadata
    if req.pinned is not None:
        updates["pinned"] = req.pinned
    if req.tags is not None:
        updates["tags"] = req.tags
    artifact = _runtime.update(artifact_id, **updates)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _serialize(artifact)


@router.delete("/{artifact_id}")
def delete_artifact(artifact_id: str):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    deleted = _runtime.delete(artifact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"success": True}


@router.post("/{artifact_id}/duplicate")
def duplicate_artifact(artifact_id: str):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    duplicated = _runtime.duplicate(artifact_id)
    if not duplicated:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _serialize(duplicated)


@router.post("/{artifact_id}/versions/save")
def save_version(artifact_id: str):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    version = _runtime.save_version(artifact_id)
    if not version:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {
        "id": version.id,
        "artifactId": version.artifact_id,
        "content": version.content,
        "metadata": version.metadata,
        "createdAt": version.created_at,
        "createdBy": version.created_by,
    }


@router.post("/{artifact_id}/versions/revert")
def revert_to_version(artifact_id: str, req: VersionRevertRequest):
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    reverted = _runtime.revert_to_version(artifact_id, req.version_id)
    if not reverted:
        raise HTTPException(status_code=404, detail="Artifact or version not found")
    return {"success": True}


@router.get("/stats/summary")
def get_stats():
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Artifact runtime not initialized")
    artifacts = _runtime.list()
    by_type: dict[str, int] = {}
    for a in artifacts:
        t = a.type.value if isinstance(a.type, ArtifactType) else a.type
        by_type[t] = by_type.get(t, 0) + 1
    now = time.time()
    return {
        "total": len(artifacts),
        "byType": by_type,
        "recentCount": sum(1 for a in artifacts if now - a.updated_at < 7 * 24 * 60 * 60),
        "pinnedCount": sum(1 for a in artifacts if a.pinned),
    }
