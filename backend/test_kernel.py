# backend/test_kernel.py
import asyncio

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, Runtime, RuntimeMetadata, RuntimeState


# 1. Create a Mock Runtime to test the Registry
class MockSpeechRuntime(Runtime):
    def get_runtime_id(self) -> str:
        return "speech"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="speech",
            version="1.0.0",
            priority="high",
            capabilities=[Capability(id="speech.tts", runtime_id="speech")]
        )

    async def initialize(self) -> None:
        print("Speech Runtime Initialized.")

    async def shutdown(self) -> None:
        print("Speech Runtime Stopped.")

    def get_state(self) -> RuntimeState:
        return RuntimeState.READY

    def health_check(self) -> dict:
        return {"status": "healthy"}

# 2. Boot the Kernel
async def main():
    kernel = KernelBootstrapper()
    await kernel.boot()

    # 3. Register the Mock Runtime
    kernel.registry.register(MockSpeechRuntime())

    # 4. Test Capability Routing
    runtime = kernel.registry.get_runtime_for_capability("speech.tts")
    print(f"\n✅ SUCCESS: Capability 'speech.tts' routed to Runtime: {runtime.get_runtime_id()}")

    await kernel.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
