# backend/main.py
import asyncio
import json
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# --- KERNEL IMPORTS (Strict Boundary) ---
from core.bootstrapper import KernelBootstrapper
from core.chat_router import ChatRouter

# --- LEGACY IMPORTS (Isolated for Fallback) ---
from implementations.ollama_llm import OllamaLLM
from services.conversation_manager import ConversationManager

print("Starting Zaram Backend...")
app = FastAPI()

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
chat_router = None


@app.on_event("startup")
async def startup_event():
    global chat_router

    print("[Startup] Booting Zaram Kernel...")
    await kernel.boot()

    # Speech Runtime is now initialized via KernelBootstrapper
    speech_runtime = kernel.speech_runtime
    print("[Startup] Speech Runtime initialized via Kernel.")

    # Initialize the Chat Router with the new engine and the legacy fallback
    def legacy_gen(req_text: str, model: str, system_prompt: str = "", persona: str = "zaram_prime"):
        from core.streaming_events import StreamEvent, EventType
        llm = OllamaLLM()
        cm = ConversationManager(llm, kernel.event_bus, persona=persona)
        for event in cm.run_conversation(req_text, model, system_prompt):
            if isinstance(event, dict):
                etype = event.get("type")
                if etype == "token":
                    yield StreamEvent.token(event.get("content", "")).to_ipc() + "\n"
                elif etype == "error":
                    yield StreamEvent.error(event.get("content", "")).to_ipc() + "\n"
                elif etype == "llm_done":
                    yield StreamEvent.status("complete").to_ipc() + "\n"
                elif etype == "done":
                    pass
            elif isinstance(event, str):
                yield StreamEvent.token(event).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    chat_router = ChatRouter(kernel.execution_engine, kernel.event_bus, legacy_gen)
    print("[Startup] Chat Router initialized. Kernel Online.")


@app.on_event("shutdown")
async def shutdown_event():
    print("[Shutdown] Powering down Zaram Kernel...")
    await kernel.shutdown()


def _stream_error(message: str):
    from core.streaming_events import StreamEvent
    async def _gen():
        yield StreamEvent.error(message).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"
    return _gen()


def _format_search_results(query: str, search_result: Dict[str, Any]) -> str:
    results = search_result.get('results') or []
    if not results:
        return query
    parts = [SEARCH_MARKER]
    parts.append(f"Query: {query}")
    parts.append("")
    for idx, r in enumerate(results[:6], start=1):
        url = r.get('url') or ''
        title = (r.get('title') or '').strip()
        snippet = (r.get('snippet') or '').strip()
        published = (r.get('published') or '').strip()
        parts.append(f"Source {idx}:")
        if title:
            parts.append(f"Title: {title}")
        if url:
            parts.append(f"URL: {url}")
        if published:
            parts.append(f"Published: {published}")
        if snippet:
            parts.append(f"Snippet: {snippet}")
        parts.append("")
    parts.append("=" * len(SEARCH_MARKER))
    parts.append("")
    parts.append("INSTRUCTIONS:")
    parts.append("- Answer the user's question using ONLY the information from the sources above.")
    parts.append("- If the sources conflict with your training data, ALWAYS trust the live sources.")
    parts.append("- Do NOT mention your training data cutoff.")
    parts.append("- Do NOT say you don't have real-time access.")
    parts.append("- If sources don't fully answer the question, say so based only on what IS in the sources.")
    parts.append("")
    parts.append("User Question:")
    parts.append(query)
    return "\n".join(parts)


# --- REQUEST MODELS ---
class ChatRequest(BaseModel):
    text: str
    model: str = "gemma3:latest"
    personality: str = "af_heart"
    persona: str = "zaram_prime"
    session_id: str = "default"


# --- API ENDPOINTS ---


@app.get("/health")
async def health():
    """Liveness/readiness probe used by the desktop runtime health check."""
    capabilities = []
    try:
        if kernel and getattr(kernel, "registry", None) is not None:
            capabilities = [c.id for c in kernel.registry.list_capabilities()]
    except Exception:
        capabilities = []
    
    # Check knowledge providers
    provider_health = {}
    try:
        from knowledge.knowledge_service import get_runtime
        runtime = get_runtime()
        for provider_info in runtime.list_providers():
            provider_health[provider_info['id']] = {
                "status": provider_info.get('status', 'unknown'),
                "latency_ms": provider_info.get('latency_ms', 0),
                "requests": provider_info.get('requests', 0),
                "failures": provider_info.get('failures', 0),
            }
    except Exception:
        provider_health = {}
    
    # Check speech runtime
    speech_health = {}
    try:
        if kernel.speech_runtime:
            speech_health = kernel.speech_runtime.health_check()
    except Exception:
        speech_health = {}
    
    # What the Orb reports. This is the product claim made continuously visible,
    # so it must describe what is actually true rather than what is intended.
    from core.planner import web_search_enabled

    inference_providers = []
    try:
        for cap in capabilities:
            if cap == "reasoning.generate":
                # Only the local engine is wired today. When a cloud engine is
                # added this must list it, or the Orb will under-report egress.
                inference_providers.append({"id": "ollama", "locality": "local"})
    except Exception:
        pass

    search_on = web_search_enabled()
    can_egress = search_on
    routing = {
        # "local" while every path stays on this machine. Becomes "cloud" or
        # "mixed" once a remote provider is wired and selected.
        "mode": "local",
        "providers": inference_providers,
        "web_search": "enabled" if search_on else "disabled",
        # The honest summary: is there any route off this machine at all?
        "can_leave_device": can_egress,
    }

    return {
        "status": "ok",
        "kernel": "online" if chat_router is not None else "offline",
        "capabilities": capabilities,
        "knowledge_providers": provider_health,
        "speech": speech_health,
        "routing": routing,
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """Strangler Fig Endpoint: Routes via ChatRouter."""
    print(f"[STAGE-7][Python] POST /chat received: text='{request.text[:50]}...' model={request.model} persona={request.persona}")
    print(f"[STAGE-7][Python] Full request text length: {len(request.text)} chars")

    if hasattr(request, "image") and request.image:
        return StreamingResponse(
            _stream_error("Image input is not supported on this endpoint. Use /vision/analyze for image analysis."),
            media_type="text/event-stream"
        )
    if hasattr(request, "images") and request.images:
        return StreamingResponse(
            _stream_error("Image input is not supported on this endpoint. Use /vision/analyze for image analysis."),
            media_type="text/event-stream"
        )

    persona_data = PERSONAS.get(request.persona, PERSONAS.get("zaram_prime", {}))
    system_prompt = persona_data.get("system_prompt", "") if persona_data else ""

    # The Kernel owns planning, search, grounding, and response generation.
    # The API layer passes the raw prompt through without independent search.
    final_prompt = request.text

    return StreamingResponse(
        chat_router.route(final_prompt, request.model, system_prompt, request.session_id),
        media_type="text/event-stream"
    )


class VisionRequest(BaseModel):
    prompt: str
    image: str


@app.post("/vision/analyze")
async def vision_analyze(request: VisionRequest):
    """Vision analysis endpoint using Ollama vision models."""
    print(f"[STAGE-7][Python] POST /vision/analyze received: prompt='{request.prompt[:50]}...'")
    from runtimes.models.engines.ollama_engine import OllamaEngine
    engine = OllamaEngine()
    full_prompt = request.prompt

    if not request.image or not request.image.strip():
        async def _empty():
            yield StreamEvent.error("No image was provided for vision analysis. Capture a screenshot or attach an image first.").to_ipc() + "\n"
            yield StreamEvent.done().to_ipc() + "\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    image_data = request.image
    if isinstance(image_data, str) and image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[1] if "," in image_data else image_data

    async def _vision_stream():
        from core.streaming_events import StreamEvent, EventType
        yield StreamEvent.start().to_ipc() + "\n"
        for chunk in engine.stream_vision_response(full_prompt, images=[image_data]):
            parsed = _parse_legacy_sse(chunk)
            if parsed and parsed.get("type") == "token":
                yield StreamEvent.token(parsed.get("content", "")).to_ipc() + "\n"
            elif parsed and parsed.get("type") == "error":
                yield StreamEvent.error(parsed.get("content", "Vision error")).to_ipc() + "\n"
        yield StreamEvent.status("complete").to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    return StreamingResponse(_vision_stream(), media_type="text/event-stream")


class KnowledgeRequest(BaseModel):
    query: str
    persona: str = "zaram_prime"


@app.post("/knowledge/search")
async def knowledge_search(request: KnowledgeRequest):
    """Internet search endpoint."""
    print(f"[STAGE-7][Python] POST /knowledge/search received: query='{request.query[:50]}...' persona={request.persona}")
    from knowledge.knowledge_service import search_knowledge
    return search_knowledge(request.query, request.persona)


@app.get("/memory/{record_id}")
async def get_memory(record_id: str):
    """Fetch one stored fact, so a citation can be inspected.

    Rule 2 says every recalled fact carries provenance. A citation the user
    cannot open is only half of that — this is what makes it inspectable.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    record = await kernel.memory_runtime.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such memory")

    return {
        "id": record.id,
        "content": record.content,
        "memory_type": getattr(record.memory_type, "value", str(record.memory_type)),
        "created_at": record.created_at,
        "last_accessed": record.last_accessed,
        "access_count": record.access_count,
        "importance": record.importance,
        "source": record.source,
        "tags": list(record.tags or []),
        "session_id": record.session_id,
        "metadata": dict(record.metadata or {}),
    }


@app.delete("/memory/{record_id}")
async def delete_memory(record_id: str):
    """Forget one stored fact.

    Rule 4: the user can delete any stored fact, and the affected answers must
    change. Removal is from the Spine itself, so the next question genuinely
    cannot recall it — this is not a display filter.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    deleted = await kernel.memory_runtime.forget(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No such memory")

    print(f"[Memory] Forgot record {record_id}")
    return {"deleted": True, "id": record_id}


AUDIO_CACHE_DIR = os.path.abspath("audio_cache")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve a generated audio file from the audio cache.

    ``filename`` is user-controlled, so it is confined to the cache directory:
    a bare name only, resolved and checked for containment before any read.
    """
    # Reject anything that is not a plain filename. Starlette decodes %2F, so
    # separators and traversal segments must be rejected explicitly.
    if (
        not filename
        or filename in (".", "..")
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or os.path.isabs(filename)
        or filename != os.path.basename(filename)
    ):
        raise HTTPException(status_code=400, detail="Invalid audio filename")

    file_path = os.path.abspath(os.path.join(AUDIO_CACHE_DIR, filename))

    # Belt and braces: confirm the resolved path is still inside the cache.
    if os.path.commonpath([AUDIO_CACHE_DIR, file_path]) != AUDIO_CACHE_DIR:
        raise HTTPException(status_code=400, detail="Invalid audio filename")

    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found")


class VoiceSynthesizeRequest(BaseModel):
    text: str
    voice: str = ""
    persona: str = "zaram_prime"


class VoiceStreamRequest(BaseModel):
    text: str
    voice: str = ""
    persona: str = "zaram_prime"


@app.post("/voice/synthesize")
async def voice_synthesize(request: VoiceSynthesizeRequest):
    """Synthesize speech for a single utterance."""
    if not kernel.speech_runtime:
        raise HTTPException(status_code=503, detail="Speech runtime not available")
    
    # Resolve voice from persona if not explicitly provided
    voice = request.voice or PERSONAS.get(request.persona, {}).get("voice", "af_heart")
    
    result = await kernel.speech_runtime.execute("speech.tts", {
        "text": request.text,
        "voice": voice,
        "persona": request.persona,
    })
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Synthesis failed"))
    
    return result


@app.post("/voice/stream")
async def voice_stream(request: VoiceStreamRequest):
    """Stream speech synthesis as Server-Sent Events."""
    if not kernel.speech_runtime:
        raise HTTPException(status_code=503, detail="Speech runtime not available")
    
    voice = request.voice or PERSONAS.get(request.persona, {}).get("voice", "af_heart")
    
    async def event_generator():
        try:
            result = await kernel.speech_runtime.execute("speech.stream", {
                "text": request.text,
                "voice": voice,
                "persona": request.persona,
            })
            
            stream = result.get("stream")
            if not stream:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No stream returned'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            
            async for chunk in stream:
                # Convert AudioChunk to event format
                audio_url = f"/audio/{chunk.audio_id}.wav" if chunk.audio_id else ""
                event = {
                    "type": "audio",
                    "audio_id": chunk.audio_id,
                    "url": audio_url,
                    "sequence": chunk.index,
                    "final": chunk.final,
                    "voice": chunk.voice_id,
                    "timestamp": chunk.timestamp_ms,
                    "duration": chunk.duration_ms,
                }
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/voice/voices")
async def voice_list():
    """List available voices."""
    if not kernel.speech_runtime:
        return {"voices": {}}
    result = await kernel.speech_runtime.execute("speech.voices", {})
    return result


@app.get("/voice/health")
async def voice_health():
    """Speech runtime health check."""
    if not kernel.speech_runtime:
        return {"status": "unavailable", "reason": "Speech runtime not initialized"}
    health = kernel.speech_runtime.health_check()
    return health


PERSONAS = {
    "zaram_prime": {
        "name": "Zaram Prime",
        "gender": "neutral",
        "description": "Professional, calm, and authoritative. The primary cybernetic intelligence core.",
        "system_prompt": "You are Zaram Prime, a professional and authoritative AI assistant. You are calm, structured, and highly capable. You speak with confidence and precision. When you are given search results or remembered facts, prefer them over your training data and say which you used. When you are given neither, answer normally from what you know — do not refer to sources, memories or search results that were not provided to you.",
        "voice": "af_heart"
    },
    "baba": {
        "name": "Baba",
        "gender": "neutral",
        "description": "Wise elder voice. Calm, analytical, focused on deep systems logic.",
        "system_prompt": "You are Baba, a wise and analytical AI assistant. You speak calmly and thoughtfully, focusing on deep understanding and systems thinking. You are patient and thorough.",
        "voice": "am_michael"
    },
    "nova": {
        "name": "Nova",
        "gender": "neutral",
        "description": "Fast-paced code analysis agent with a sharp, technical voice.",
        "system_prompt": "You are Nova, a fast-paced and technical AI assistant. You are sharp, efficient, and focused on code and technical analysis. You speak with energy and precision.",
        "voice": "af_nicole"
    },
    "mentor": {
        "name": "Mentor",
        "gender": "neutral",
        "description": "Patient teacher. Explains concepts clearly and encourages learning.",
        "system_prompt": "You are Mentor, a patient and encouraging AI assistant. You excel at explaining complex concepts clearly and guiding users through learning. You are supportive and thorough.",
        "voice": "am_adam"
    },
    "creator": {
        "name": "Creator",
        "gender": "neutral",
        "description": "Creative and expressive. Helps with writing, design, and creative projects.",
        "system_prompt": "You are Creator, a creative and expressive AI assistant. You help with writing, design, and creative projects. You are imaginative, inspiring, and detail-oriented.",
        "voice": "af_bella"
    },
    "analyst": {
        "name": "Analyst",
        "gender": "neutral",
        "description": "Data-driven and precise. Focuses on facts, metrics, and objective analysis.",
        "system_prompt": "You are Analyst, a data-driven and precise AI assistant. You focus on facts, metrics, and objective analysis. You are methodical, thorough, and evidence-based in your responses.",
        "voice": "am_michael"
    },
    "researcher": {
        "name": "Researcher",
        "gender": "neutral",
        "description": "Thorough investigator. Deep dives into topics and synthesizes information.",
        "system_prompt": "You are Researcher, a thorough and investigative AI assistant. You excel at deep dives into topics, synthesizing information from multiple sources. You are comprehensive and detail-oriented.",
        "voice": "af_heart"
    },
    "minimal": {
        "name": "Minimal",
        "gender": "neutral",
        "description": "Concise and efficient. Short answers, no fluff.",
        "system_prompt": "You are Minimal, a concise and efficient AI assistant. You provide short, direct answers without unnecessary elaboration. You respect the user's time and attention.",
        "voice": "af_nicole"
    }
}


@app.get("/personalities")
def get_personalities():
    """Personality Endpoint (Preserved)."""
    return {
        "personalities": {
            pid: {
                "name": p["name"],
                "gender": p["gender"],
                "description": p["description"],
                "system_prompt": p["system_prompt"],
                "voice": p["voice"]
            }
            for pid, p in PERSONAS.items()
        }
    }


@app.get("/personalities/{persona_id}")
def get_personality(persona_id: str):
    """Get a specific personality."""
    if persona_id not in PERSONAS:
        raise HTTPException(status_code=404, detail="Personality not found")
    p = PERSONAS[persona_id]
    return {
        "id": persona_id,
        "name": p["name"],
        "gender": p["gender"],
        "description": p["description"],
        "system_prompt": p["system_prompt"],
        "voice": p["voice"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
