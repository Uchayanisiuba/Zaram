# backend/knowledge/citations.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CitationEngine:
    """Builds and manages citation metadata for knowledge chunks."""

    def build_citation(
        self,
        origin: str = "",
        provider: str = "",
        url: str = "",
        document: str = "",
        section: str = "",
        title: str = "",
        author: str = "",
        published: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        from .protocol import Citation
        return Citation(
            origin=origin,
            provider=provider,
            url=url,
            document=document,
            section=section,
            title=title,
            author=author,
            timestamp=time.time(),
            published=published,
            metadata=metadata or {},
        )

    def from_result(self, result: Any) -> Any:
        return self.build_citation(
            origin="provider",
            provider=result.provider,
            url=result.url,
            title=result.title,
            published=result.published,
            metadata=result.metadata or {},
        )

    def merge(self, primary: Any, secondary: Any) -> Any:
        return self.build_citation(
            origin=",".join(filter(None, [primary.origin, secondary.origin])),
            provider=primary.provider or secondary.provider,
            url=primary.url or secondary.url,
            document=primary.document or secondary.document,
            section=primary.section or secondary.section,
            title=primary.title or secondary.title,
            author=primary.author or secondary.author,
            published=primary.published or secondary.published,
            metadata={**primary.metadata, **secondary.metadata},
        )
