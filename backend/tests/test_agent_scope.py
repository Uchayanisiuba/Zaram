"""Tests for Agent-Scoped Memory."""

import pytest
from backend.runtimes.memory.agent_scope import (
    AgentScopedMemoryRecord,
    AgentScopeManager,
)
from backend.runtimes.memory.contracts import MemoryRecord, MemoryType, Origin, GLOBAL_SCOPE


class TestAgentScopedMemoryRecord:
    """Test AgentScopedMemoryRecord dataclass."""
    
    def test_agent_scoped_record_creation(self):
        record = AgentScopedMemoryRecord(
            content="Test fact",
            memory_type=MemoryType.SEMANTIC,
            metadata={},
            session_id="sess1",
            user_id="user1",
            importance=0.5,
            scope=GLOBAL_SCOPE,
            origin=Origin.CONVERSATION,
            agent_id="agent1",
        )
        assert record.content == "Test fact"
        assert record.agent_id == "agent1"
    
    def test_effective_scope_agent(self):
        record = AgentScopedMemoryRecord(
            content="Test",
            agent_id="agent1",
        )
        assert record.effective_scope == "agent:agent1"
    
    def test_effective_scope_global(self):
        record = AgentScopedMemoryRecord(
            content="Test",
            scope=GLOBAL_SCOPE,
            agent_id=None,
        )
        assert record.effective_scope == GLOBAL_SCOPE
    
    def test_is_agent_scoped(self):
        record = AgentScopedMemoryRecord(content="Test", agent_id="agent1")
        assert record.is_agent_scoped is True
        
        record2 = AgentScopedMemoryRecord(content="Test", agent_id=None)
        assert record2.is_agent_scoped is False
    
    def test_is_global(self):
        record = AgentScopedMemoryRecord(content="Test", scope=GLOBAL_SCOPE, agent_id=None)
        assert record.is_global is True
        
        record2 = AgentScopedMemoryRecord(content="Test", scope=GLOBAL_SCOPE, agent_id="agent1")
        assert record2.is_global is False
    
    def test_is_project_scoped(self):
        record = AgentScopedMemoryRecord(content="Test", scope="project:123", agent_id=None)
        assert record.is_project_scoped is True
        
        record2 = AgentScopedMemoryRecord(content="Test", scope="project:123", agent_id="agent1")
        assert record2.is_project_scoped is False


class TestAgentScopeManager:
    """Test AgentScopeManager class."""
    
    @pytest.mark.asyncio
    async def test_store_for_agent(self):
        class MockMemoryRuntime:
            def __init__(self):
                self.stored = []
            
            async def store_record(self, record):
                self.stored.append(record)
                return "test-id"
        
        runtime = MockMemoryRuntime()
        manager = AgentScopeManager(runtime)
        
        fact_id = await manager.store_for_agent(
            agent_id="agent1",
            content="Agent-specific fact",
            project_id="proj1",
        )
        
        assert fact_id == "test-id"
        assert len(runtime.stored) == 1
        stored_record = runtime.stored[0]
        assert stored_record.agent_id == "agent1"
        assert stored_record.scope == "project:proj1"
    
    @pytest.mark.asyncio
    async def test_retrieve_for_agent(self):
        class MockRecord:
            def __init__(self, id, content, agent_id=None, scope=GLOBAL_SCOPE):
                self.id = id
                self.content = content
                self.agent_id = agent_id
                self.scope = scope
        
        class MockResult:
            def __init__(self, record):
                self.record = record
                self.relevance = 0.9
        
        class MockMemoryRuntime:
            async def retrieve(self, query, max_results, scope, **kwargs):
                # Return records matching scope
                if scope == "agent:agent1":
                    return [MockResult(MockRecord("1", "Agent fact", "agent1", "agent:agent1"))]
                elif scope == GLOBAL_SCOPE:
                    return [MockResult(MockRecord("2", "Global fact", None, GLOBAL_SCOPE))]
                elif scope == "project:proj1":
                    return [MockResult(MockRecord("3", "Project fact", None, "project:proj1"))]
                return []
        
        runtime = MockMemoryRuntime()
        manager = AgentScopeManager(runtime)
        
        results = await manager.retrieve_for_agent(
            agent_id="agent1",
            query="test",
            project_id="proj1",
            include_global=True,
            include_project=True,
        )
        
        # Should get results from all three scopes
        assert len(results) == 3
        
        # Check all scopes represented
        scopes = {getattr(r.record, "scope", None) for r in results}
        assert "agent:agent1" in scopes
        assert GLOBAL_SCOPE in scopes
        assert "project:proj1" in scopes
    
    @pytest.mark.asyncio
    async def test_retrieve_for_agent_excludes_global(self):
        class MockMemoryRuntime:
            async def retrieve(self, query, max_results, scope, **kwargs):
                return []
        
        runtime = MockMemoryRuntime()
        manager = AgentScopeManager(runtime)
        
        # Should not error even when excluding
        results = await manager.retrieve_for_agent(
            agent_id="agent1",
            query="test",
            include_global=False,
        )
        assert results == []
    
    @pytest.mark.asyncio
    async def test_promote_to_global(self):
        class MockRecord:
            def __init__(self, agent_id="agent1"):
                self.id = "rec1"
                self.content = "Test fact"
                self.memory_type = MemoryType.SEMANTIC
                self.metadata = {}
                self.session_id = "sess1"
                self.user_id = "user1"
                self.importance = 0.5
                self.scope = GLOBAL_SCOPE
                self.origin = Origin.CONVERSATION
                self.agent_id = agent_id
        
        class MockMemoryRuntime:
            def __init__(self):
                self.records = {"rec1": MockRecord()}
            
            async def get_record(self, record_id):
                return self.records.get(record_id)
            
            async def store_record(self, record):
                self.records[record.id] = record
                return record.id
        
        runtime = MockMemoryRuntime()
        manager = AgentScopeManager(runtime)
        
        success = await manager.promote_to_global("rec1", "agent1")
        assert success is True
        
        # Check global record was created
        global_record = runtime.records.get("rec1")
        assert global_record.agent_id is None
        assert global_record.scope == GLOBAL_SCOPE
    
    @pytest.mark.asyncio
    async def test_promote_to_global_wrong_agent(self):
        class MockRecord:
            def __init__(self):
                self.id = "rec1"
                self.agent_id = "agent2"  # Different agent
        
        class MockMemoryRuntime:
            async def get_record(self, record_id):
                return MockRecord()
            
            async def store_record(self, record):
                return record.id
        
        runtime = MockMemoryRuntime()
        manager = AgentScopeManager(runtime)
        
        success = await manager.promote_to_global("rec1", "agent1")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_get_agent_facts(self):
        class MockRecord:
            def __init__(self, agent_id=None):
                self.agent_id = agent_id
        
        class MockMemoryRuntime:
            def __init__(self):
                self.all_records = [
                    MockRecord(agent_id="agent1"),
                    MockRecord(agent_id="agent1"),
                    MockRecord(agent_id="agent2"),
                    MockRecord(agent_id=None),
                ]
            
            async def all_records(self):
                return self.all_records
        
        runtime = MockMemoryRuntime()
        class _Store:
            async def all_records(self):
                return runtime.all_records
        runtime._store = _Store()
        manager = AgentScopeManager(runtime)
        
        facts = await manager.get_agent_facts("agent1")
        assert len(facts) == 2
        assert all(f.agent_id == "agent1" for f in facts)