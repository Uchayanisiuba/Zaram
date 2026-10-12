"""EgressGuard - Outlet filter that enforces egress policy on outbound requests."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..types import BaseOutletFilter, FilterPriority, PipelineContext, FilterResult


class EgressGuard(BaseOutletFilter):
    """Outlet filter that intercepts outbound URLs and enforces egress policy."""
    
    priority = FilterPriority.SECURITY
    
    # Patterns to detect URLs in responses
    URL_PATTERN = re.compile(
        r'(?:https?://|ftp://)[^\s<>"\']+|'
        r'(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s<>"\']*)?'
    )
    
    # Tool call patterns that might contain URLs
    TOOL_CALL_PATTERN = re.compile(r'"url"\s*:\s*"([^"]+)"')
    
    def __init__(self, egress_gate: Any = None):
        self.egress_gate = egress_gate
    
    async def process(self, response: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Check response for outbound URLs and enforce egress policy."""
        if self.egress_gate is None:
            return FilterResult(metadata={"skipped": "no_egress_gate"})
        
        try:
            # Extract URLs from response
            urls = self._extract_urls(response)
            
            if not urls:
                return FilterResult(metadata={"urls_found": 0})
            
            blocked_urls = []
            allowed_urls = []
            
            for url in urls:
                try:
                    # Check with egress gate
                    approved = self.egress_gate.check(
                        url,
                        method="GET",
                        source="pipeline.outlet",
                    )
                    if approved:
                        allowed_urls.append(url)
                    else:
                        blocked_urls.append(url)
                except Exception as e:
                    # Egress denied
                    blocked_urls.append(url)
            
            metadata = {
                "urls_found": len(urls),
                "allowed": len(allowed_urls),
                "blocked": len(blocked_urls),
                "blocked_urls": blocked_urls,
            }
            
            if blocked_urls:
                # Modify response to indicate blocked URLs
                modified_response = dict(response)
                if "blocked_egress" not in modified_response:
                    modified_response["blocked_egress"] = []
                modified_response["blocked_egress"].extend(blocked_urls)
                
                return FilterResult(
                    modified_response=modified_response,
                    blocked=True,
                    block_reason=f"Egress blocked {len(blocked_urls)} URL(s)",
                    metadata=metadata,
                )
            
            return FilterResult(metadata=metadata)
            
        except Exception as e:
            return FilterResult(
                metadata={"error": str(e)},
            )
    
    def _extract_urls(self, response: Dict[str, Any]) -> List[str]:
        """Extract all URLs from a response."""
        urls = []
        
        def extract_from_obj(obj: Any, path: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if key in ("url", "href", "link", "image_url", "avatar_url") and isinstance(value, str):
                        urls.append(value)
                    elif isinstance(value, (dict, list)):
                        extract_from_obj(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_from_obj(item, f"{path}[{i}]")
            elif isinstance(obj, str):
                # Find URLs in string
                matches = self.URL_PATTERN.findall(obj)
                urls.extend(matches)
        
        extract_from_obj(response)
        
        # Deduplicate
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls