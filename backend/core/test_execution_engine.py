# backend/test_execution_engine.py
import asyncio
import sys
from pathlib import Path

# Ensure the backend package root is importable regardless of invocation dir.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from core.bootstrapper import KernelBootstrapper
from runtimes.models.models_runtime import ModelsRuntime
from core.execution_engine import ExecutionEngine

async def main():
    print("=== Sprint 3: Execution Engine Test ===\n")
    
    # 1. Boot the Kernel
    kernel = KernelBootstrapper()
    await kernel.boot()
    
    # 2. Register the Models Runtime
    models_runtime = ModelsRuntime(kernel.event_bus)
    kernel.registry.register(models_runtime)
    await models_runtime.initialize()
    
    # 3. Initialize the Execution Engine
    engine = ExecutionEngine(kernel.registry, kernel.event_bus)
    
    # 4. Simulate a User Request (The API Layer would call this)
    user_prompt = "Say 'Zaram Execution Engine is online' in exactly five words."
    print(f"User Prompt: {user_prompt}\n")
    print("Streaming Response:")
    print("-" * 40)
    
    # 5. Execute and Stream
    for token in engine.execute(user_prompt):
        print(token, end="", flush=True)
        
    print("\n" + "-" * 40)
    print("\nSUCCESS: Execution Engine planned, routed, and dispatched successfully.")
    
    await kernel.shutdown()

if __name__ == "__main__":
    asyncio.run(main())