# backend/core/execution_engine.py
from typing import Iterator
from core.contracts import ExecutionPlan, PlanState
from core.event_bus import EventBus, ZaramEvent
from core.planner import IntentPlanner
from core.dispatcher import ExecutionDispatcher
from core.capability_router import CapabilityRouter
from core.registry import RuntimeRegistry

class ExecutionEngine:
    """The operational core of Zaram. Orchestrates the lifecycle of a user request."""
    
    def __init__(self, registry: RuntimeRegistry, event_bus: EventBus):
        self._registry = registry
        self._event_bus = event_bus
        self._planner = IntentPlanner()
        self._router = CapabilityRouter(registry)
        self._dispatcher = ExecutionDispatcher(self._router)
        
    def execute(self, prompt: str) -> Iterator[str]:
        """End-to-end execution: Plan -> Route -> Dispatch -> Stream."""
        # 1. Plan
        plan = self._planner.create_plan(prompt)
        plan.state = PlanState.RUNNING
        
        self._event_bus.publish(ZaramEvent(
            source_runtime="execution_engine",
            event_type="execution.plan_created",
            priority="high",
            data={"correlation_id": plan.correlation_id, "step_count": len(plan.steps)}
        ))
        
        # 2. Dispatch Steps
        for step in plan.steps:
            self._event_bus.publish(ZaramEvent(
                source_runtime="execution_engine",
                event_type="execution.step_started",
                priority="high",
                data={"correlation_id": plan.correlation_id, "capability_id": step.capability_id}
            ))
            
            # 3. Execute and Stream
            for token in self._dispatcher.execute_step(step):
                yield token
                
        # 4. Complete
        plan.state = PlanState.COMPLETED
        self._event_bus.publish(ZaramEvent(
            source_runtime="execution_engine",
            event_type="execution.plan_completed",
            priority="normal",
            data={"correlation_id": plan.correlation_id}
        ))