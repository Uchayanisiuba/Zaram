"""Agent-scoped memory - extends MemoryRecord with agent_id."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .contracts import MemoryRecord, MemoryType, Origin, GLOBAL_SCOPE, PROJECT_SCOPE_PREFIX, project_scope


@dataclass(frozen=True)
class AgentScopedMemoryRecord(MemoryRecord):
    """MemoryRecord extended with agent_id for agent-scoped memory."""
    agent_id: Optional[str] = None
    
    @property
    def effective_scope(self) -> str:
        """Get the effective scope including agent."""
        if self.agent_id:
            return f"agent:{self.agent_id}"
        return self.scope
    
    @property
    def is_agent_scoped(self) -> bool:
        return self.agent_id is not None
    
    @property
    def is_global(self) -> bool:
        return self.scope == GLOBAL_SCOPE and self.agent_id is None
    
    @property
    def is_project_scoped(self) -> bool:
        return self.scope.startswith(PROJECT_SCOPE_PREFIX) and self.agent_id is None


class AgentScopeManager:
    """Manages agent-scoped memory isolation."""
    
    def __init__(self, memory_runtime: Any):
        self.memory_runtime = memory_runtime
    
    async def store_for_agent(
        self,
        agent_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        metadata: Dict[str, Any] = None,
        session_id: str = None,
        user_id: str = None,
        importance: float = 0.5,
        project_id: str = None,
        origin: Origin = Origin.CONVERSATION,
    ) -> str:
        """Store a fact scoped to an agent."""
        scope = project_scope(project_id) if project_id else GLOBAL_SCOPE
        
        record = AgentScopedMemoryRecord(
            content=content,
            memory_type=memory_type,
            metadata=metadata or {},
            session_id=session_id,
            user_id=user_id,
            importance=importance,
            scope=scope,
            origin=origin,
            agent_id=agent_id,
        )
        
        return await self.memory_runtime.store_record(record)
    
    async def retrieve_for_agent(
        self,
        agent_id: str,
        query: str,
        project_id: str = None,
        max_results: int = 10,
        include_global: bool = True,
        include_project: bool = True,
    ) -> List[Any]:
        """Retrieve facts visible to an agent."""
        # Agent sees: their own facts + global + project (if allowed)
        scopes = [f"agent:{agent_id}"]
        
        if include_global:
            scopes.append(GLOBAL_SCOPE)
        
        if include_project and project_id:
            scopes.append(project_scope(project_id))
        
        # Query for each scope and merge results
        all_results = []
        for scope in scopes:
            results = await self.memory_runtime.retrieve(
                query=query,
                max_results=max_results,
                scope=scope,
            )
            all_results.extend(results)
        
        # Deduplicate by record ID
        seen = set()
        unique_results = []
        for result in all_results:
            record = getattr(result, "record", None)
            if record and record.id not in seen:
                seen.add(record.id)
                unique_results.append(result)
        
        # Sort by relevance/score
        unique_results.sort(key=lambda r: r.relevance or r.score or 0, reverse=True)
        return unique_results[:max_results]
    
    async def promote_to_global(self, record_id: str, agent_id: str) -> bool:
        """Promote agent-scoped fact to global (requires explicit user action)."""
        record = await self.memory_runtime.get_record(record_id)
        if not record:
            return False
        
        # Verify it belongs to this agent
        if getattr(record, "agent_id", None) != agent_id:
            return False
        
        # Create new global record
        global_record = AgentScopedMemoryRecord(
            **{**record.__dict__, "scope": GLOBAL_SCOPE, "agent_id": None}
        )
        
        await self.memory_runtime.store_record(global_record)
        return True
    
    async def get_agent_facts(self, agent_id: str) -> List[MemoryRecord]:
        """Get all facts for a specific agent."""
        all_records = await self.memory_runtime._store.all_records()
        return [
            r for r in all_records
            if getattr(r, "agent_id", None) == agent_id
        ]


def create_agent_scope_manager(memory_runtime: Any) -> AgentScopeManager:
    """Factory function to create an AgentScopeManager."""
    return AgentScopeManager(memory_runtime)