# backend/core/dispatcher.py
from typing import Iterator
from core.contracts import ExecutionStep
from core.capability_router import CapabilityRouter

class ExecutionDispatcher:
    """Executes individual steps by dispatching to the correct Runtime Service."""
    def __init__(self, router: CapabilityRouter):
        self._router = router

    def execute_step(self, step: ExecutionStep, model: str = "gemma3:latest", system_prompt: str = "") -> Iterator[str]:
        """Resolves the capability and executes the service."""
        print(f"[STAGE-8][Kernel] execute_step: capability_id={step.capability_id} model={model}")
        runtime = self._router.resolve(step.capability_id)
        print(f"[STAGE-8][Kernel] Resolved runtime: {runtime.get_runtime_id() if hasattr(runtime, 'get_runtime_id') else type(runtime).__name__}")
        
        if hasattr(runtime, "get_service"):
            service = runtime.get_service()
            if step.capability_id.startswith("vision.") and hasattr(service, "analyze_image"):
                prompt = step.input_data.get("prompt", "")
                image = step.input_data.get("image", "")
                print(f"[STAGE-8][Kernel] Calling analyze_image with prompt: '{prompt[:50]}...', image={'yes' if image else 'no'}")
                yield from service.analyze_image(prompt, image, system_prompt)
            elif hasattr(service, "generate_response"):
                prompt = step.input_data.get("prompt", "")
                print(f"[STAGE-8][Kernel] Calling generate_response with prompt: '{prompt[:50]}...' model={model}")
                yield from service.generate_response(prompt, system_prompt)
            else:
                yield f"[WARN] Service for {step.capability_id} does not support generate_response."
        else:
            yield f"[WARN] Runtime {runtime.get_runtime_id()} does not expose a service."