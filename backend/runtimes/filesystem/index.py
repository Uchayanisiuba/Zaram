from __future__ import annotations

import json
import os
import time
import math
from typing import Any
from collections import defaultdict

from .contracts import FilesystemIndex, FilesystemQuery, FileRecord, SearchStrategy


class InMemoryFilesystemIndex(FilesystemIndex):
    """In-memory inverted index for full-text search."""

    def __init__(self):
        self._inverted_index: dict[str, set[str]] = defaultdict(set)
        self._records: dict[str, FileRecord] = {}
        self._rebuilt_at = 0.0

    def _tokenize(self, text: str) -> set[str]:
        import re
        return set(re.findall(r"\b\w+\b", text.lower()))

    async def add(self, record: FileRecord) -> None:
        self._records[record.id] = record
        tokens = self._tokenize(record.content)
        tokens.update(self._tokenize(record.name))
        for tag in record.tags:
            tokens.add(tag.lower())
        for token in tokens:
            self._inverted_index[token].add(record.id)

    async def remove(self, record_id: str) -> None:
        record = self._records.pop(record_id, None)
        if record:
            tokens = self._tokenize(record.content)
            tokens.update(self._tokenize(record.name))
            for tag in record.tags:
                tokens.add(tag.lower())
            for token in tokens:
                self._inverted_index[token].discard(record_id)

    async def search(self, query: FilesystemQuery) -> list[tuple[str, float]]:
        if not query.query.strip():
            return []

        query_tokens = self._tokenize(query.query)
        if not query_tokens:
            return []

        scores: dict[str, float] = defaultdict(float)
        for token in query_tokens:
            for rid in self._inverted_index.get(token, set()):
                record = self._records.get(rid)
                if not record:
                    continue
                if not self._matches_filters(record, query):
                    continue
                scores[rid] += 1.0

        results = [(rid, score / len(query_tokens)) for rid, score in scores.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[: query.max_results]

    def _matches_filters(self, record: FileRecord, query: FilesystemQuery) -> bool:
        if query.file_types and record.file_type not in query.file_types:
            return False
        if query.project_id and record.project_id != query.project_id:
            return False
        if query.path_prefix and not record.path.startswith(query.path_prefix):
            return False
        if query.tags and not any(t in record.tags for t in query.tags):
            return False
        if query.modified_after and record.modified_at < query.modified_after:
            return False
        if query.modified_before and record.modified_at > query.modified_before:
            return False
        for k, v in query.metadata_filters.items():
            if record.metadata.get(k) != v:
                return False
        return True

    async def rebuild(self) -> None:
        self._inverted_index.clear()
        for record in self._records.values():
            await self.add(record)
        self._rebuilt_at = time.time()

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "indexed_records": len(self._records),
            "unique_terms": len(self._inverted_index),
            "last_rebuilt": self._rebuilt_at,
        }


class HybridFilesystemIndex(FilesystemIndex):
    """Hybrid index combining full-text with metadata filtering."""

    def __init__(self):
        self._fulltext = InMemoryFilesystemIndex()
        self._by_type: dict[FileType, set[str]] = defaultdict(set)
        self._by_project: dict[str, set[str]] = defaultdict(set)
        self._by_tag: dict[str, set[str]] = defaultdict(set)

    async def add(self, record: FileRecord) -> None:
        await self._fulltext.add(record)
        self._by_type[record.file_type].add(record.id)
        if record.project_id:
            self._by_project[record.project_id].add(record.id)
        for tag in record.tags:
            self._by_tag[tag].add(record.id)

    async def remove(self, record_id: str) -> None:
        record = self._fulltext._records.get(record_id)
        if record:
            self._by_type[record.file_type].discard(record_id)
            if record.project_id:
                self._by_project[record.project_id].discard(record_id)
            for tag in record.tags:
                self._by_tag[tag].discard(record_id)
        await self._fulltext.remove(record_id)

    async def search(self, query: FilesystemQuery) -> list[tuple[str, float]]:
        if query.strategy == SearchStrategy.METADATA:
            return await self._metadata_search(query)
        return await self._fulltext.search(query)

    async def _metadata_search(self, query: FilesystemQuery) -> list[tuple[str, float]]:
        candidate_ids = set(self._fulltext._records.keys())
        if query.file_types:
            type_ids = set()
            for ft in query.file_types:
                type_ids.update(self._by_type.get(ft, set()))
            candidate_ids &= type_ids
        if query.project_id:
            candidate_ids &= self._by_project.get(query.project_id, set())
        if query.tags:
            tag_ids = set()
            for tag in query.tags:
                tag_ids.update(self._by_tag.get(tag, set()))
            candidate_ids &= tag_ids

        results = [(rid, 1.0) for rid in candidate_ids]
        return results[: query.max_results]

    async def rebuild(self) -> None:
        await self._fulltext.rebuild()
        self._by_type.clear()
        self._by_project.clear()
        self._by_tag.clear()
        for record in self._fulltext._records.values():
            self._by_type[record.file_type].add(record.id)
            if record.project_id:
                self._by_project[record.project_id].add(record.id)
            for tag in record.tags:
                self._by_tag[tag].add(record.id)

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "fulltext": await self._fulltext.health_check(),
            "by_type": {k.value: len(v) for k, v in self._by_type.items()},
            "by_project": {k: len(v) for k, v in self._by_project.items()},
            "by_tag": {k: len(v) for k, v in self._by_tag.items()},
        }


def create_filesystem_index(index_type: str = "hybrid") -> FilesystemIndex:
    if index_type == "fulltext":
        return InMemoryFilesystemIndex()
    return HybridFilesystemIndex()