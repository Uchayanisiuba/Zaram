# backend/core/dispatcher.py
from typing import Iterator
from core.contracts import ExecutionStep
from core.capability_router import CapabilityRouter

class ExecutionDispatcher:
    """Executes individual steps by dispatching to the correct Runtime Service."""
    
    def __init__(self, router: CapabilityRouter):
        self._router = router
        
    def execute_step(self, step: ExecutionStep) -> Iterator[str]:
        """Resolves the capability and executes the service."""
        runtime = self._router.resolve(step.capability_id)
        
        # Dispatch to the specific service based on the runtime type
        if hasattr(runtime, "get_service"):
            service = runtime.get_service()
            if hasattr(service, "generate_response"):
                prompt = step.input_data.get("prompt", "")
                yield from service.generate_response(prompt)
            else:
                yield f"⚠️ Service for {step.capability_id} does not support generate_response."
        else:
            yield f"⚠️ Runtime {runtime.get_runtime_id()} does not expose a service."