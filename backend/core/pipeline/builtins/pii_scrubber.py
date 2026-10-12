"""PIIScrubber - Outlet filter that detects and redacts PII before cloud egress."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Pattern

from ..types import BaseOutletFilter, FilterPriority, PipelineContext, FilterResult


class PIIScrubber(BaseOutletFilter):
    """Outlet filter that scrubs PII from responses before they leave the device."""
    
    priority = FilterPriority.SECURITY
    
    # PII patterns
    PATTERNS: Dict[str, Pattern] = {
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "api_key_openai": re.compile(r'\bsk-[A-Za-z0-9]{48,}\b'),
        "api_key_github": re.compile(r'\bgh[pousr]_[A-Za-z0-9]{36,}\b'),
        "api_key_anthropic": re.compile(r'\bsk-ant-[A-Za-z0-9_-]{95,}\b'),
        "api_key_google": re.compile(r'\bAIza[A-Za-z0-9_-]{35}\b'),
        "api_key_generic": re.compile(r'\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}["\']?', re.IGNORECASE),
        "phone_us": re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
        "ssn": re.compile(r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b'),
        "credit_card": re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
        "ipv4": re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
        "aws_key": re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
        "jwt": re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
    }
    
    REDACTION_MAP = {
        "email": "[EMAIL REDACTED]",
        "api_key_openai": "[OPENAI API KEY REDACTED]",
        "api_key_github": "[GITHUB TOKEN REDACTED]",
        "api_key_anthropic": "[ANTHROPIC API KEY REDACTED]",
        "api_key_google": "[GOOGLE API KEY REDACTED]",
        "api_key_generic": "[API KEY REDACTED]",
        "phone_us": "[PHONE NUMBER REDACTED]",
        "ssn": "[SSN REDACTED]",
        "credit_card": "[CREDIT CARD REDACTED]",
        "ipv4": "[IP ADDRESS REDACTED]",
        "aws_key": "[AWS ACCESS KEY REDACTED]",
        "jwt": "[JWT TOKEN REDACTED]",
    }
    
    def __init__(
        self,
        enabled_patterns: Optional[List[str]] = None,
        custom_patterns: Optional[Dict[str, Pattern]] = None,
        log_to_egress: bool = True,
    ):
        self.enabled_patterns = enabled_patterns or list(self.PATTERNS.keys())
        self.custom_patterns = custom_patterns or {}
        self.log_to_egress = log_to_egress
        # Combine built-in and custom patterns
        self.all_patterns = {**self.PATTERNS, **self.custom_patterns}
    
    async def process(self, response: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Scrub PII from response text fields."""
        try:
            # Check if this response is going to cloud (has egress indicators)
            if not self._is_cloud_bound(response, context):
                return FilterResult(metadata={"skipped": "not_cloud_bound"})
            
            scrubbed_response = dict(response)
            total_redactions = 0
            redaction_details = []
            
            # Scrub text fields
            for key in ("text", "content", "response", "message", "answer", "body"):
                if key in scrubbed_response and isinstance(scrubbed_response[key], str):
                    original = scrubbed_response[key]
                    scrubbed, count, details = self._scrub_text(original)
                    scrubbed_response[key] = scrubbed
                    total_redactions += count
                    redaction_details.extend(details)
            
            # Also scrub nested objects
            for key, value in scrubbed_response.items():
                if isinstance(value, (dict, list)):
                    scrubbed_obj, count, details = self._scrub_object(value)
                    scrubbed_response[key] = scrubbed_obj
                    total_redactions += count
                    redaction_details.extend(details)
            
            metadata = {
                "redactions": total_redactions,
                "details": redaction_details,
            }
            
            if total_redactions > 0:
                return FilterResult(
                    modified_response=scrubbed_response,
                    metadata=metadata,
                )
            
            return FilterResult(metadata=metadata)
            
        except Exception as e:
            return FilterResult(
                metadata={"error": str(e)},
            )
    
    def _is_cloud_bound(self, response: Dict[str, Any], context: PipelineContext) -> bool:
        """Check if response is destined for cloud egress."""
        # Check metadata for cloud indicators
        meta = context.metadata.get("egress", {})
        if meta.get("destination") == "cloud":
            return True
        
        # Check if model is cloud-based
        model = response.get("model") or context.metadata.get("model")
        if model and self._is_cloud_model(model):
            return True
        
        # Check for explicit tool calls to cloud
        tool_calls = response.get("tool_calls") or []
        for call in tool_calls:
            if isinstance(call, dict):
                tool_name = call.get("name") or call.get("function", {}).get("name")
                if tool_name and self._is_cloud_tool(tool_name):
                    return True
        
        return False
    
    def _is_cloud_model(self, model: str) -> bool:
        """Check if a model identifier indicates cloud."""
        cloud_indicators = [
            "gpt-", "claude-", "gemini-", "mistral-", "cohere-",
            "openai/", "anthropic/", "google/", "azure/", "bedrock/",
        ]
        model_lower = model.lower()
        return any(indicator in model_lower for indicator in cloud_indicators)
    
    def _is_cloud_tool(self, tool_name: str) -> bool:
        """Check if a tool is cloud-based."""
        cloud_tools = [
            "web.search", "internet.search", "browser.visit",
            "cloud.", "remote.", "api.",
        ]
        tool_lower = tool_name.lower()
        return any(indicator in tool_lower for indicator in cloud_tools)
    
    def _scrub_text(self, text: str) -> tuple[str, int, List[Dict]]:
        """Scrub PII from a single text string."""
        result = text
        total_count = 0
        details = []
        
        for pattern_name in self.enabled_patterns:
            if pattern_name not in self.all_patterns:
                continue
            
            pattern = self.all_patterns[pattern_name]
            redaction = self.REDACTION_MAP.get(pattern_name, "[REDACTED]")
            
            matches = list(pattern.finditer(result))
            if matches:
                # Replace from end to start to maintain positions
                for match in reversed(matches):
                    start, end = match.span()
                    result = result[:start] + redaction + result[end:]
                    total_count += 1
                    details.append({
                        "type": pattern_name,
                        "position": start,
                        "length": end - start,
                    })
        
        return result, total_count, details
    
    def _scrub_object(self, obj: Any) -> tuple[Any, int, List[Dict]]:
        """Recursively scrub PII from dict/list objects."""
        total_count = 0
        details = []
        
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if isinstance(value, str):
                    scrubbed, count, dets = self._scrub_text(value)
                    result[key] = scrubbed
                    total_count += count
                    details.extend(dets)
                elif isinstance(value, (dict, list)):
                    scrubbed, count, dets = self._scrub_object(value)
                    result[key] = scrubbed
                    total_count += count
                    details.extend(dets)
                else:
                    result[key] = value
            return result, total_count, details
        
        elif isinstance(obj, list):
            result = []
            for item in obj:
                if isinstance(item, str):
                    scrubbed, count, dets = self._scrub_text(item)
                    result.append(scrubbed)
                    total_count += count
                    details.extend(dets)
                elif isinstance(item, (dict, list)):
                    scrubbed, count, dets = self._scrub_object(item)
                    result.append(scrubbed)
                    total_count += count
                    details.extend(dets)
                else:
                    result.append(item)
            return result, total_count, details
        
        return obj, 0, []


def create_pii_scrubber(
    enabled_patterns: Optional[List[str]] = None,
    custom_patterns: Optional[Dict[str, Pattern]] = None,
) -> PIIScrubber:
    """Factory function to create a PIIScrubber."""
    return PIIScrubber(
        enabled_patterns=enabled_patterns,
        custom_patterns=custom_patterns,
    )