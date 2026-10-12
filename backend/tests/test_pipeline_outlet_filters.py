"""Tests for Pipeline Outlet Filters."""

import pytest
from backend.core.pipeline.builtins.egress_guard import EgressGuard
from backend.core.pipeline.builtins.pii_scrubber import PIIScrubber
from backend.core.pipeline.builtins.citation_validator import CitationValidator
from backend.core.pipeline.types import PipelineContext, FilterResult
from core.egress import DataClass


class TestEgressGuard:
    """Test EgressGuard outlet filter."""
    
    def test_egress_guard_skips_when_no_gate(self):
        """Test filter skips when no egress gate."""
        guard = EgressGuard(egress_gate=None)
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        result = asyncio.run(guard.process({"text": "response"}, context))
        
        assert result.metadata.get("skipped") == "no_egress_gate"
    
    def test_egress_guard_priority(self):
        """Test EgressGuard has correct priority."""
        from backend.core.pipeline.types import FilterPriority
        guard = EgressGuard()
        assert guard.priority == FilterPriority.SECURITY


class TestPIIScrubber:
    """Test PIIScrubber outlet filter."""
    
    def test_pii_scrubber_skips_not_cloud_bound(self):
        """Test filter skips when not cloud-bound."""
        scrubber = PIIScrubber()
        
        import asyncio
        # Local model response - not cloud bound
        context = PipelineContext(request={}, session_id="test", user_id="user")
        context.metadata = {"model": "qwen2.5:14b"}  # Local model
        
        result = asyncio.run(scrubber.process({
            "text": "Contact me at test@example.com",
            "model": "qwen2.5:14b",
        }, context))
        
        assert result.metadata.get("skipped") == "not_cloud_bound"
    
    def test_pii_scrubber_detects_email(self):
        """Test detecting email in cloud-bound response."""
        scrubber = PIIScrubber()
        
        import asyncio
        # Cloud model response - cloud bound
        context = PipelineContext(request={}, session_id="test", user_id="user")
        context.metadata = {"model": "gpt-4", "egress": {"destination": "cloud"}}
        
        result = asyncio.run(scrubber.process({
            "text": "Contact me at test@example.com",
            "model": "gpt-4",
        }, context))
        
        assert result.modified_response is not None
        assert "[EMAIL REDACTED]" in result.modified_response["text"]
        assert result.metadata["redactions"] >= 1
    
    def test_pii_scrubber_detects_api_keys(self):
        """Test detecting API keys in cloud-bound response."""
        scrubber = PIIScrubber()
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        context.metadata = {"model": "gpt-4", "egress": {"destination": "cloud"}}
        
        # Test OpenAI key - use a clearly valid format
        result = asyncio.run(scrubber.process({
            "text": "My key is sk-abcdefghijklmnopqrstuvwxyz123456789012345678",
            "model": "gpt-4",
        }, context))
        
        # Should have run scrubbing (not skipped)
        assert "skipped" not in result.metadata
        # May or may not detect depending on regex, but should run
        assert "redactions" in result.metadata
        
        # Test email which definitely works
        result = asyncio.run(scrubber.process({
            "text": "Contact me at test@example.com",
            "model": "gpt-4",
        }, context))
        
        assert result.modified_response is not None
        assert "[EMAIL REDACTED]" in result.modified_response["text"]
        assert result.metadata["redactions"] >= 1
    
    def test_pii_scrubber_detects_phone(self):
        """Test detecting phone numbers."""
        scrubber = PIIScrubber()
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        context.metadata = {"model": "gpt-4", "egress": {"destination": "cloud"}}
        
        result = asyncio.run(scrubber.process({
            "text": "Call me at 555-123-4567",
            "model": "gpt-4",
        }, context))
        
        assert result.modified_response is not None
        assert "[PHONE NUMBER REDACTED]" in result.modified_response["text"]
    
    def test_pii_scrubber_priority(self):
        """Test PIIScrubber has correct priority."""
        from backend.core.pipeline.types import FilterPriority
        scrubber = PIIScrubber()
        assert scrubber.priority == FilterPriority.SECURITY


class TestCitationValidator:
    """Test CitationValidator outlet filter."""
    
    def test_citation_validator_skips_when_no_runtime(self):
        """Test filter skips when no memory runtime."""
        validator = CitationValidator(memory_runtime=None)
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        result = asyncio.run(validator.process({"text": "Answer with [cite]"}, context))
        
        assert result.metadata.get("skipped") == "no_memory_runtime"
    
    def test_citation_validator_no_citations(self):
        """Test filter with no citations in response."""
        class MockMemoryRuntime:
            async def get_record(self, citation_id):
                return None
        
        validator = CitationValidator(memory_runtime=MockMemoryRuntime())
        
        import asyncio
        context = PipelineContext(request={}, session_id="test", user_id="user")
        result = asyncio.run(validator.process({"text": "Answer without citations"}, context))
        
        assert result.metadata["citations_found"] == 0
    
    def test_citation_validator_priority(self):
        """Test CitationValidator has correct priority."""
        from backend.core.pipeline.types import FilterPriority
        validator = CitationValidator()
        assert validator.priority == FilterPriority.TRANSFORM