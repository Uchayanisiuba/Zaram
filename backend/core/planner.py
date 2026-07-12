# backend/core/planner.py
import time
import uuid
from core.contracts import ExecutionPlan, ExecutionStep, PlanState

class IntentPlanner:
    """Analyzes intent and builds an ExecutionPlan."""
    
    def create_plan(self, prompt: str) -> ExecutionPlan:
        """Creates a single-step execution plan for reasoning."""
        step = ExecutionStep(
            capability_id="reasoning.generate",
            input_data={"prompt": prompt},
            depends_on=[]
        )
        
        return ExecutionPlan(
            correlation_id=str(uuid.uuid4()),
            original_prompt=prompt,
            steps=[step],
            state=PlanState.PENDING,
            created_at=time.time()
        )