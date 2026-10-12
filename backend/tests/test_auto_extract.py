"""Tests for Auto Fact Extraction."""

import pytest
from backend.runtimes.memory.auto_extract import (
    extract_facts,
    _heuristic_extract,
    _llm_extract,
    extract_and_store,
    ExtractedFact,
)
from backend.runtimes.memory.contracts import MemoryType, Origin


class TestExtractedFact:
    """Test ExtractedFact dataclass."""
    
    def test_extracted_fact_defaults(self):
        fact = ExtractedFact(content="Test fact")
        assert fact.content == "Test fact"
        assert fact.memory_type == MemoryType.SEMANTIC
        assert fact.importance == 0.5
        assert fact.entities == []
        assert fact.confidence == 0.8
        assert fact.origin == Origin.CONVERSATION
        assert fact.metadata == {}
    
    def test_extracted_fact_custom(self):
        fact = ExtractedFact(
            content="Custom fact",
            memory_type=MemoryType.EPISODIC,
            importance=0.9,
            entities=["Entity1", "Entity2"],
            confidence=0.95,
            origin=Origin.USER_DOCUMENT,
            metadata={"source": "test"},
        )
        assert fact.content == "Custom fact"
        assert fact.memory_type == MemoryType.EPISODIC
        assert fact.importance == 0.9
        assert fact.entities == ["Entity1", "Entity2"]
        assert fact.confidence == 0.95
        assert fact.origin == Origin.USER_DOCUMENT
        assert fact.metadata == {"source": "test"}


class TestHeuristicExtract:
    """Test heuristic fact extraction."""
    
    def test_extract_is_pattern(self):
        facts = _heuristic_extract("my rate is $100/hr", {}, 10)
        assert len(facts) >= 1
        assert any("rate" in f.content.lower() for f in facts)
    
    def test_extract_cost_pattern(self):
        facts = _heuristic_extract("service costs $50", {}, 10)
        assert len(facts) >= 1
        assert any("cost" in f.content.lower() for f in facts)
    
    def test_extract_remember_pattern(self):
        facts = _heuristic_extract("remember that the deadline is Friday", {}, 10)
        assert len(facts) >= 1
        assert any("deadline" in f.content.lower() for f in facts)
    
    def test_extract_decided_pattern(self):
        facts = _heuristic_extract("decided to use PostgreSQL", {}, 10)
        assert len(facts) >= 1
        assert any("decided" in f.content.lower() for f in facts)
    
    def test_extract_deadline_pattern(self):
        facts = _heuristic_extract("deadline is March 15", {}, 10)
        assert len(facts) >= 1
        assert any("deadline" in f.content.lower() for f in facts)
    
    def test_extract_max_facts_limit(self):
        text = " ".join([f"fact {i} is value {i}" for i in range(20)])
        facts = _heuristic_extract(text, {}, 5)
        assert len(facts) <= 5
    
    def test_extract_short_content_ignored(self):
        facts = _heuristic_extract("x is y", {}, 10)
        # Too short (< 20 chars) should be ignored
        assert len(facts) == 0
    
    def test_extract_long_content_ignored(self):
        long_content = "a " * 300  # ~600 chars
        facts = _heuristic_extract(f"my thing is {long_content}", {}, 10)
        # Too long (> 500 chars) should be ignored
        assert len(facts) == 0


class TestExtractFacts:
    """Test extract_facts function."""
    
    @pytest.mark.asyncio
    async def test_extract_facts_fallback_to_heuristic(self):
        """Test extract_facts falls back to heuristic when no models_runtime."""
        facts = await extract_facts("my rate is $100/hr", {}, models_runtime=None)
        assert len(facts) >= 1
        assert all(isinstance(f, ExtractedFact) for f in facts)
    
    @pytest.mark.asyncio
    async def test_extract_facts_with_model_param(self):
        """Test extract_facts accepts model parameter."""
        facts = await extract_facts("test", {}, model="custom-model", max_facts=5, models_runtime=None)
        assert len(facts) <= 5


class TestExtractAndStore:
    """Test extract_and_store function."""
    
    @pytest.mark.asyncio
    async def test_extract_and_store_mock_runtime(self):
        """Test extract_and_store with mock runtime."""
        class MockMemoryRuntime:
            def __init__(self):
                self.store_calls = []
            
            async def store(self, content, memory_type, metadata, session_id, user_id, importance, scope, origin):
                self.store_calls.append({
                    "content": content,
                    "memory_type": memory_type,
                    "metadata": metadata,
                    "session_id": session_id,
                    "user_id": user_id,
                    "importance": importance,
                    "scope": scope,
                    "origin": origin,
                })
                return "test-id"
        
        runtime = MockMemoryRuntime()
        stored_ids = await extract_and_store(
            "my rate is $100/hr",
            {},
            runtime,
            project_id="proj1",
            session_id="sess1",
            user_id="user1",
        )
        
        assert len(stored_ids) >= 1
        assert all(id == "test-id" for id in stored_ids)
        assert len(runtime.store_calls) >= 1
        
        call = runtime.store_calls[0]
        assert call["scope"] == "proj1"
        assert call["session_id"] == "sess1"
        assert call["user_id"] == "user1"