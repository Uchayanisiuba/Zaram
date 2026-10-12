"""CitationValidator - Outlet filter that validates citations reference valid Spine records."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from ..types import BaseOutletFilter, FilterPriority, PipelineContext, FilterResult


class CitationValidator(BaseOutletFilter):
    """Outlet filter that validates citations reference valid Spine records."""

    priority = FilterPriority.TRANSFORM  # Was LOGGING (90), changed to TRANSFORM (30) per plan

    # Citation patterns to detect in response text
    CITATION_PATTERNS = [
        r'\[([A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12})\]',  # UUID
        r'\[([MS]\d+)\]',  # M1, S2 style
        r'\(source:\s*([A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12})\)',  # (source: uuid)
    ]

    def __init__(
        self,
        memory_runtime: Optional[Any] = None,
        strip_invalid: bool = True,
        log_failures: bool = True,
    ):
        self.memory_runtime = memory_runtime
        self.strip_invalid = strip_invalid
        self.log_failures = log_failures

    async def process(self, response: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Validate citations in response."""
        if self.memory_runtime is None:
            return FilterResult(metadata={"skipped": "no_memory_runtime"})

        text_fields = ["text", "content", "response", "message", "answer", "body"]
        all_citations: Dict[str, int] = {}  # citation -> count
        invalid_citations: List[str] = []
        valid_citations: Set[str] = set()

        # Extract all citations from response text
        for field in text_fields:
            if field in response and isinstance(response[field], str):
                citations = self._extract_citations(response[field])
                for cite in citations:
                    all_citations[cite] = all_citations.get(cite, 0) + 1

        if not all_citations:
            return FilterResult(metadata={"citations_found": 0})

        # Validate each unique citation
        for citation in all_citations.keys():
            is_valid = await self._validate_citation(citation, context)
            if is_valid:
                valid_citations.add(citation)
            else:
                invalid_citations.append(citation)

        metadata = {
            "citations_found": len(all_citations),
            "valid_citations": len(valid_citations),
            "invalid_citations": len(invalid_citations),
            "invalid_list": invalid_citations,
        }

        if invalid_citations and self.strip_invalid:
            # Strip invalid citations from response
            modified_response = dict(response)
            for field in text_fields:
                if field in modified_response and isinstance(modified_response[field], str):
                    modified_response[field] = self._strip_citations(
                        modified_response[field],
                        invalid_citations
                    )
            metadata["stripped"] = True
            return FilterResult(
                modified_response=modified_response,
                metadata=metadata,
            )

        if invalid_citations and self.log_failures:
            metadata["logged_failures"] = True

        return FilterResult(metadata=metadata)

    def _extract_citations(self, text: str) -> List[str]:
        """Extract all citations from text."""
        citations = []
        for pattern in self.CITATION_PATTERNS:
            matches = re.findall(pattern, text)
            citations.extend(matches)
        return citations

    def _strip_citations(self, text: str, invalid_citations: List[str]) -> str:
        """Remove invalid citations from text."""
        result = text
        for cite in invalid_citations:
            # Remove various citation formats
            patterns = [
                rf'\[{re.escape(cite)}\]',
                rf'\(source:\s*{re.escape(cite)}\)',
                rf'{re.escape(cite)}',
            ]
            for pattern in patterns:
                result = re.sub(pattern, '', result)
        # Clean up extra spaces
        result = re.sub(r'\s+', ' ', result).strip()
        return result

    async def _validate_citation(self, citation: str, context: PipelineContext) -> bool:
        """Check if citation references a valid Spine record."""
        try:
            # Try to retrieve the record from Spine
            record = await self.memory_runtime.get_record(citation)
            if record:
                return True
        except Exception:
            pass
        return False


def create_citation_validator(
    memory_runtime: Optional[Any] = None,
    strip_invalid: bool = True,
    log_failures: bool = True,
) -> CitationValidator:
    """Factory function to create a CitationValidator."""
    return CitationValidator(
        memory_runtime=memory_runtime,
        strip_invalid=strip_invalid,
        log_failures=log_failures,
    )