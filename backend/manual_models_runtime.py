# backend/test_models_runtime.py
import asyncio
from core.bootstrapper import KernelBootstrapper
from runtimes.models.models_runtime import ModelsRuntime

async def main():
    # 1. Boot the Kernel
    kernel = KernelBootstrapper()
    await kernel.boot()
    
    # 2. Instantiate and Register the new Models Runtime
    models_runtime = ModelsRuntime(kernel.event_bus)
    kernel.registry.register(models_runtime)
    
    # 3. Initialize the Runtime (Starts Ollama Engine)
    await models_runtime.initialize()
    
    # 4. Test Capability Routing
    runtime = kernel.registry.get_runtime_for_capability("reasoning.generate")
    print(f"\n✅ SUCCESS: Capability 'reasoning.generate' routed to Runtime: {runtime.get_runtime_id()}")
    
    # 5. Test Actual Generation (Strangler Fig Test)
    print("\n Testing LLM Generation...")
    service = runtime.get_service()
    for token in service.generate_response("Say 'Zaram is online' in exactly three words."):
        print(token, end="", flush=True)
    print("\n")
    
    await kernel.shutdown()

if __name__ == "__main__":
    asyncio.run(main())