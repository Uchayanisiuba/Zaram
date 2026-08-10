"""Tests for the Agent Runtime."""
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import pytest

from core.event_bus import EventBus, ZaramEvent
from core.contracts import RuntimeState
from runtimes.agent import (
    AgentRuntime,
    AgentConfig,
    AgentState,
    AgentStatus,
    AgentTask,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Contracts tests
# ---------------------------------------------------------------------------

class TestAgentContracts:
    def test_agent_config_defaults(self):
        config = AgentConfig(agent_id="test", name="Test Agent")
        assert config.agent_id == "test"
        assert config.name == "Test Agent"
        assert config.max_concurrent_tasks == 5
        assert config.timeout_seconds == 30.0
        assert config.auto_start is True

    def test_agent_config_custom(self):
        config = AgentConfig(
            agent_id="test",
            name="Test",
            capabilities=["search"],
            max_concurrent_tasks=3,
            timeout_seconds=60.0,
            auto_start=False,
        )
        assert config.capabilities == ["search"]
        assert config.max_concurrent_tasks == 3
        assert config.timeout_seconds == 60.0
        assert config.auto_start is False

    def test_agent_task_defaults(self):
        task = AgentTask(task_id="t1", agent_id="a1", description="test")
        assert task.status == TaskStatus.PENDING
        assert task.input_data == {}
        assert task.result is None
        assert task.error is None

    def test_agent_task_duration(self):
        task = AgentTask(task_id="t1", agent_id="a1", description="test")
        assert task.duration_seconds is None
        task.started_at = 100.0
        task.completed_at = 105.0
        assert task.duration_seconds == 5.0


# ---------------------------------------------------------------------------
# AgentRuntime tests
# ---------------------------------------------------------------------------

class TestAgentRuntime:
    def setup_method(self):
        self.event_bus = EventBus()
        self.runtime = AgentRuntime(self.event_bus)

    def test_get_runtime_id(self):
        assert self.runtime.get_runtime_id() == "agent"

    def test_get_metadata(self):
        meta = self.runtime.get_metadata()
        assert meta.runtime_id == "agent"
        assert len(meta.capabilities) > 0

    def test_get_state(self):
        assert self.runtime.get_state() == RuntimeState.UNINITIALIZED

    def test_health_check(self):
        health = self.runtime.health_check()
        assert health["runtime_id"] == "agent"
        assert "state" in health
        assert "stats" in health

    def test_get_stats(self):
        stats = self.runtime.get_stats()
        assert "agents_created" in stats
        assert "tasks_created" in stats

    @pytest.mark.asyncio
    async def test_initialize(self):
        await self.runtime.initialize()
        assert self.runtime.get_state() == RuntimeState.READY

    def test_create_agent(self):
        config = AgentConfig(agent_id="test1", name="Test Agent")
        agent_id = self.runtime.create_agent(config)
        assert agent_id == "test1"
        state = self.runtime.get_agent_state("test1")
        assert state is not None
        assert state.status == AgentStatus.RUNNING

    def test_create_agent_auto_start_false(self):
        config = AgentConfig(agent_id="test2", name="Test", auto_start=False)
        self.runtime.create_agent(config)
        state = self.runtime.get_agent_state("test2")
        assert state.status == AgentStatus.IDLE

    def test_create_agent_duplicate_raises(self):
        config = AgentConfig(agent_id="test3", name="Test")
        self.runtime.create_agent(config)
        with pytest.raises(ValueError):
            self.runtime.create_agent(config)

    def test_create_task(self):
        config = AgentConfig(agent_id="test4", name="Test")
        self.runtime.create_agent(config)
        task_id = self.runtime.create_task("test4", "Do something")
        assert task_id is not None
        task = self.runtime.get_task(task_id)
        assert task is not None
        assert task.description == "Do something"
        assert task.status == TaskStatus.PENDING

    def test_create_task_unknown_agent_raises(self):
        with pytest.raises(ValueError):
            self.runtime.create_task("nonexistent", "Do something")

    def test_execute_task(self):
        config = AgentConfig(agent_id="test5", name="Test")
        self.runtime.create_agent(config)
        task_id = self.runtime.create_task("test5", "Do something", {"key": "value"})
        result = self.runtime.execute_task(task_id)
        assert result["message"] is not None
        task = self.runtime.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None

    def test_execute_task_unknown_raises(self):
        with pytest.raises(ValueError):
            self.runtime.execute_task("nonexistent_task")

    def test_execute_task_already_running_raises(self):
        config = AgentConfig(agent_id="test6", name="Test")
        self.runtime.create_agent(config)
        task_id = self.runtime.create_task("test6", "Do something")
        self.runtime.execute_task(task_id)
        with pytest.raises(ValueError):
            self.runtime.execute_task(task_id)

    def test_register_handler(self):
        config = AgentConfig(agent_id="test7", name="Test")
        self.runtime.create_agent(config)

        def custom_handler(task: AgentTask) -> dict:
            return {"custom": True, "task_id": task.task_id}

        self.runtime.register_handler("test7", custom_handler)
        task_id = self.runtime.create_task("test7", "Do something")
        result = self.runtime.execute_task(task_id)
        assert result["custom"] is True

    def test_list_agents(self):
        config1 = AgentConfig(agent_id="a1", name="Agent 1")
        config2 = AgentConfig(agent_id="a2", name="Agent 2")
        self.runtime.create_agent(config1)
        self.runtime.create_agent(config2)
        agents = self.runtime.list_agents()
        assert len(agents) == 2

    def test_list_tasks(self):
        config = AgentConfig(agent_id="a3", name="Test")
        self.runtime.create_agent(config)
        self.runtime.create_task("a3", "Task 1")
        self.runtime.create_task("a3", "Task 2")
        tasks = self.runtime.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_filtered(self):
        config1 = AgentConfig(agent_id="a4", name="Test")
        config2 = AgentConfig(agent_id="a5", name="Test")
        self.runtime.create_agent(config1)
        self.runtime.create_agent(config2)
        self.runtime.create_task("a4", "Task 1")
        self.runtime.create_task("a5", "Task 2")
        tasks = self.runtime.list_tasks(agent_id="a4")
        assert len(tasks) == 1

    def test_stop_agent(self):
        config = AgentConfig(agent_id="a6", name="Test")
        self.runtime.create_agent(config)
        self.runtime.stop_agent("a6")
        state = self.runtime.get_agent_state("a6")
        assert state.status == AgentStatus.STOPPED

    def test_stop_agent_unknown_raises(self):
        with pytest.raises(ValueError):
            self.runtime.stop_agent("nonexistent")

    def test_create_agent_publishes_event(self):
        events = []
        self.event_bus.subscribe("agent.created", events.append)
        config = AgentConfig(agent_id="a7", name="Test")
        self.runtime.create_agent(config)
        assert len(events) == 1
        assert events[0].data["agent_id"] == "a7"

    def test_execute_task_publishes_events(self):
        events = []
        self.event_bus.subscribe("agent.task_started", events.append)
        self.event_bus.subscribe("agent.task_completed", events.append)
        config = AgentConfig(agent_id="a8", name="Test")
        self.runtime.create_agent(config)
        task_id = self.runtime.create_task("a8", "Do something")
        self.runtime.execute_task(task_id)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_handle_create_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.create_result", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="agent.create",
            data={"agent_id": "a9", "name": "Test Agent"},
        ))
        assert len(events) == 1
        assert events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_handle_execute_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.execute_result", events.append)
        config = AgentConfig(agent_id="a10", name="Test")
        self.runtime.create_agent(config)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="agent.execute",
            data={
                "agent_id": "a10",
                "description": "Test task",
                "input_data": {"key": "value"},
            },
        ))
        assert len(events) == 1
        assert events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_handle_list_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.list_result", events.append)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="agent.list",
            data={},
        ))
        assert len(events) == 1
        assert "agents" in events[0].data
        assert "tasks" in events[0].data

    @pytest.mark.asyncio
    async def test_handle_status_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.status_result", events.append)
        config = AgentConfig(agent_id="a11", name="Test")
        self.runtime.create_agent(config)
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="agent.status",
            data={"agent_id": "a11"},
        ))
        assert len(events) == 1
        assert events[0].data["agent_id"] == "a11"

    @pytest.mark.asyncio
    async def test_handle_task_get_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.task_result", events.append)
        config = AgentConfig(agent_id="a12", name="Test")
        self.runtime.create_agent(config)
        task_id = self.runtime.create_task("a12", "Test")
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="agent.task",
            data={"task_id": task_id, "action": "get"},
        ))
        assert len(events) == 1
        assert events[0].data["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_handle_task_cancel_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.task_cancelled", events.append)
        config = AgentConfig(agent_id="a13", name="Test")
        self.runtime.create_agent(config)
        task_id = self.runtime.create_task("a13", "Test")
        self.event_bus.publish(ZaramEvent(
            source_runtime="test",
            event_type="agent.task",
            data={"task_id": task_id, "action": "cancel"},
        ))
        assert len(events) == 1
        assert events[0].data["success"] is True
        task = self.runtime.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_task_failed_publishes_event(self):
        await self.runtime.initialize()
        events = []
        self.event_bus.subscribe("agent.task_failed", events.append)
        config = AgentConfig(agent_id="a14", name="Test")
        self.runtime.create_agent(config)
        self.runtime.register_handler("a14", lambda t: (_ for _ in ()).throw(RuntimeError("test error")))
        task_id = self.runtime.create_task("a14", "Fail")
        with pytest.raises(RuntimeError):
            self.runtime.execute_task(task_id)
        assert len(events) == 1
        assert events[0].data["success"] is False
