import asyncio
import json
import logging
import os
import sys
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from core.event_bus import ZaramEvent

# Load environment variables (Feature Flag)
load_dotenv()
USE_NEW_KERNEL = os.getenv("USE_NEW_KERNEL", "false").lower() == "true"

# --- KERNEL IMPORTS (Strict Boundary) ---
from core.bootstrapper import KernelBootstrapper
from core.execution_engine import ExecutionEngine

# --- VOICE RUNTIME IMPORTS (Modular, Kernel-independent) ---
from voice.voice_manager import VoiceManager, VoiceRuntime

# --- LEGACY IMPORTS (Isolated for Fallback) ---
from implementations.ollama_llm import OllamaLLM
from services.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

print("🚀 Starting Zaram Backend...")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global execution_engine, voice_runtime
    logger.info("Booting Zaram Kernel...")
    await kernel.boot()

    from runtimes.models.models_runtime import ModelsRuntime
    models_runtime = ModelsRuntime(kernel.event_bus)
    kernel.registry.register(models_runtime)
    await models_runtime.initialize()
    logger.info("✓ Kernel Runtime ready")
    logger.info("✓ Models Runtime ready")

    execution_engine = ExecutionEngine(kernel.registry, kernel.event_bus)

    # Voice Runtime is initialized independently from the Kernel.
    voice_runtime = VoiceRuntime(auto_register_kokoro=True)
    try:
        await voice_runtime.initialize()
    except Exception as exc:
        logger.error("Voice Runtime failed to initialize: %s", exc)

    # Single canonical speech path: ConversationManager depends only on the
    # VoiceManager (which routes to the registered Kokoro provider).
    global conversation_manager
    conversation_manager = ConversationManager(OllamaLLM(), voice_runtime.manager)
    logger.info("Legacy Speech Pipeline disabled")

    yield

    logger.info("Powering down Zaram Kernel...")
    if voice_runtime is not None:
        await voice_runtime.shutdown()
    await kernel.shutdown()


app = FastAPI(lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- KERNEL LIFECYCLE ---
kernel = KernelBootstrapper()
execution_engine = None
voice_runtime = None
conversation_manager = None

# --- REQUEST MODELS ---
class ChatRequest(BaseModel):
    text: str
    model: str = "gemma3:latest"
    personality: str = "default"


# --- GENERATORS ---
async def legacy_stream_generator(request: ChatRequest):
    """Legacy path: ConversationManager -> VoiceManager -> KokoroProvider."""
    if conversation_manager is None:
        conversation_manager = ConversationManager(OllamaLLM(), VoiceManager())
    for event in conversation_manager.run_conversation(request.text, request.model, request.personality):
        yield f"data: {json.dumps(event)}\n\n"
    yield "data: [DONE]\n\n"


async def kernel_stream_generator(text: str):
    """New Kernel path: Execution Engine orchestration."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | dict | None] = asyncio.Queue()

    def _produce() -> None:
        try:
            for token in execution_engine.execute(text):
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "token", "content": token})
        except Exception as e:
            tb = (
                "".join(traceback.format_exception(type(e), e, e.__traceback__))
                if e.__traceback__
                else ""
            )
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "content": str(e)})
            loop.call_soon_threadsafe(
                kernel.event_bus.publish,
                ZaramEvent(
                    source_runtime="execution_engine",
                    event_type="execution.error",
                    priority="high",
                    data={
                        "correlation_id": getattr(execution_engine, "correlation_id", ""),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "traceback": tb,
                    },
                ),
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    fut = loop.run_in_executor(None, _produce)
    while True:
        item = await queue.get()
        if item is None:
            break
        yield f"data: {json.dumps(item)}\n\n"
    await fut
    yield "data: [DONE]\n\n"


# --- PERSISTENCE HELPERS ---
BASE_DIR = Path(__file__).resolve().parent
PERSONALITIES_PATH = BASE_DIR / "characters.json"
AUDIO_CACHE_DIR = BASE_DIR / "audio_cache"


def load_personalities() -> dict:
    if os.path.exists(PERSONALITIES_PATH):
        with open(PERSONALITIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_personalities(data: dict) -> None:
    with open(PERSONALITIES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- API ENDPOINTS ---
@app.get("/personalities")
def get_personalities():
    return {"personalities": load_personalities()}


@app.post("/personalities")
def update_personalities(payload: dict):
    save_personalities(payload)
    return {"personalities": payload}


@app.get("/audio/{filename}")
def get_audio(filename: str):
    # Resolve against the canonical audio cache directory to avoid
    # broken relative paths and path-traversal attempts.
    requested = (AUDIO_CACHE_DIR / filename).resolve()
    cache_root = AUDIO_CACHE_DIR.resolve()
    if requested != cache_root and cache_root not in requested.parents:
        raise HTTPException(status_code=400, detail="Invalid audio path")
    if requested.is_file():
        return FileResponse(requested, media_type="audio/wav", filename=filename)
    raise HTTPException(status_code=404, detail="Audio not found")


@app.post("/api/chat")
async def chat_api(request: ChatRequest):
    if USE_NEW_KERNEL:
        return StreamingResponse(kernel_stream_generator(request.text), media_type="text/event-stream")
    else:
        return StreamingResponse(legacy_stream_generator(request), media_type="text/event-stream")


@app.post("/chat")
async def chat(request: ChatRequest):
    return await chat_api(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
