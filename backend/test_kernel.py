# backend/test_kernel.py
import asyncio
from core.bootstrapper import KernelBootstrapper
from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState

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
           