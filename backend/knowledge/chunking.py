# backend/knowledge/chunking.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class ChunkingConfig:
    max_tokens: int = 512
    overlap_tokens: int = 50
    token_chars: int = 4
    min_chunk_chars: int = 20
    document_aware: bool = True
    paragraph_aware: bool = True


class SemanticChunker:
    """Splits text into semantically coherent chunks with document and paragraph awareness."""

    def __init__(self, config: ChunkingConfig | None = None):
        self.config = config or ChunkingConfig()

    def chunk(self, text: str, citation: Any = None, metadata: dict[str, Any] | None = None) -> list[Any]:
        from .protocol import KnowledgeChunk, FreshnessScore, ConfidenceScore
        metadata = metadata or {}
        chunks: list[KnowledgeChunk] = []

        if self.config.document_aware:
            sections = self._split_by_document_structure(text)
        else:
            sections = [text]

        raw_chunks: list[str] = []
        for section in sections:
            if self.config.paragraph_aware:
                paragraphs = self._split_paragraphs(section)
            else:
                paragraphs = [section]

            current: list[str] = []
            current_len = 0
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                token_len = max(1, len(para) // self.config.token_chars)
                if current_len + token_len > self.config.max_tokens and current:
                    chunk_text = " ".join(current)
                    if len(chunk_text) >= self.config.min_chunk_chars:
                        raw_chunks.append(chunk_text)
                    current = [para]
                    current_len = token_len
                else:
                    current.append(para)
                    current_len += token_len
            if current:
                chunk_text = " ".join(current)
                if len(chunk_text) >= self.config.min_chunk_chars:
                    raw_chunks.append(chunk_text)

        for idx, raw in enumerate(raw_chunks):
            chunks.append(KnowledgeChunk(
                id=str(uuid.uuid4()),
                text=raw,
                citation=citation,
                freshness=FreshnessScore(),
                confidence=ConfidenceScore(),
                token_count=max(1, len(raw) // self.config.token_chars),
                chunk_index=idx,
                metadata={**metadata, "chunk_method": "semantic"},
            ))
        return chunks

    def _split_by_document_structure(self, text: str) -> list[str]:
        parts = re.split(r"\n(?=(?:#{1,6}\s|[-*]\s|\d+\.\s|```))", text)
        return [p.strip() for p in parts if p.strip()]

    def _split_paragraphs(self, text: str) -> list[str]:
        return re.split(r"\n\s*\n", text)


def chunk_text(text: str, max_tokens: int = 512, overlap_tokens: int = 50, citation: Any = None, metadata: dict[str, Any] | None = None) -> list[Any]:
    chunker = SemanticChunker(ChunkingConfig(max_tokens=max_tokens, overlap_tokens=overlap_tokens))
    return chunker.chunk(text, citation=citation, metadata=metadata)
