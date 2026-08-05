# backend/main.py
import asyncio
import json
import os
import time
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

    # Which model is actually answering. The models runtime knows, because the
    # provider layer chose it at boot; nothing downstream could see it, so the
    # interface had no way to name the model without inventing one. Stays None
    # when unknown rather than falling back to a plausible-looking default —
    # the persistent bar omits the segment rather than claiming a model.
    active_model = None
    try:
        active_model = kernel.registry.get_runtime("models").health_check().get("model")
    except Exception:
        active_model = None

    inference_providers = []
    try:
        for cap in capabilities:
            if cap == "reasoning.generate":
                # Only the local engine is wired today. When a cloud engine is
                # added this must list it, or the Orb will under-report egress.
                inference_providers.append(
                    {"id": "ollama", "locality": "local", "model": active_model}
                )
    except Exception:
        pass

    search_on = web_search_enabled()

    # Whether anything *can* leave is now a fact about the policy, not a guess.
    # A destination with no rule is denied, so an empty policy means no route
    # off this machine exists at all — which is the honest thing for the Orb to
    # report, and it is now measured rather than inferred from a feature flag.
    egress_summary = {"allowed_hosts": 0, "entries": 0, "bytes_today": 0}
    try:
        from core.egress import Mode, get_gate

        gate = get_gate()
        rules = gate.policy.rules()
        egress_summary = {
            "allowed_hosts": sum(
                1 for m in rules.values() if m in (Mode.ALLOW.value, Mode.ASK.value)
            ),
            "entries": gate.log.count(),
            "bytes_today": gate.log.bytes_since(time.time() - 86400),
        }
    except Exception:
        pass

    can_egress = egress_summary["allowed_hosts"] > 0 or search_on
    routing = {
        # "local" while every path stays on this machine. Becomes "cloud" or
        # "mixed" once a remote provider is wired and selected.
        "mode": "local",
        "providers": inference_providers,
        "web_search": "enabled" if search_on else "disabled",
        # The honest summary: is there any route off this machine at all?
        "can_leave_device": can_egress,
        "egress": egress_summary,
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


@app.get("/memory")
async def list_memory(limit: int = 200, offset: int = 0, q: str = ""):
    """Everything in the Spine, newest first.

    Backs the Memory surface. Returns what is actually stored — if the Spine
    holds four records, this returns four records. There is no sample data
    anywhere behind this endpoint.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    # include_superseded: corrected facts are excluded from *recall* but must
    # still appear here. Showing the user where Zaram was wrong, struck through
    # and dated, is the point of supersession — a correction they cannot see is
    # indistinguishable from a deletion.
    records = await kernel.memory_runtime._store.all_records(include_superseded=True)
    records.sort(key=lambda r: r.created_at, reverse=True)

    if q:
        needle = q.lower()
        records = [r for r in records if needle in (r.content or "").lower()]

    total = len(records)
    page = records[offset : offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "records": [
            {
                "id": r.id,
                "content": r.content,
                "memory_type": getattr(r.memory_type, "value", str(r.memory_type)),
                "created_at": r.created_at,
                "last_accessed": r.last_accessed,
                "access_count": r.access_count,
                "importance": r.importance,
                "source": r.source,
                "tags": list(r.tags or []),
                "session_id": r.session_id,
                "superseded_by": r.superseded_by,
                "superseded_at": r.superseded_at,
                "pinned": r.pinned,
                # Set when this record replaced another, so the surface can link
                # a correction back to what it corrected.
                "corrects": (r.metadata or {}).get("corrects"),
            }
            for r in page
        ],
    }


@app.get("/memory/stats")
async def memory_stats():
    """Counts for the Memory surface. Every number is measured, none estimated."""
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    stats = await kernel.memory_runtime._store.stats()
    records = await kernel.memory_runtime._store.all_records()

    sessions = {r.session_id for r in records if r.session_id}
    newest = max((r.created_at for r in records), default=None)

    return {
        "total_records": stats.total_records,
        "by_type": dict(stats.by_type or {}),
        "sessions": len(sessions),
        "newest_at": newest,
        "storage_bytes": stats.storage_size_bytes,
        # Measured from the egress log. A real zero now means zero — before the
        # log existed this returned null, because an absent measurement must
        # never read as a measured zero on a privacy claim.
        "bytes_left_device_today": _egress_bytes_today(),
    }


def _egress_bytes_today() -> int | None:
    """Bytes that left in the last 24 hours, or None if the log is unreachable."""
    try:
        from core.egress import get_gate

        return get_gate().log.bytes_since(time.time() - 86400)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Egress — what left this machine.
#
# Rule 3 says every byte that leaves is logged. A log nobody can read satisfies
# the letter of that and none of the point, so these endpoints exist to make it
# legible: what left, when, to whom, whether the record has been tampered with,
# and which destinations are permitted at all.
# --------------------------------------------------------------------------- #


@app.get("/egress")
async def egress_log(limit: int = 100, offset: int = 0):
    """The log itself, newest first.

    ``literal_text`` is the point of this endpoint. Showing that a request went
    to wikipedia.org tells the user almost nothing; showing the exact query
    string that left is the thing they cannot get anywhere else.
    """
    from core.egress import get_gate

    gate = get_gate()
    limit = max(1, min(limit, 500))
    entries = gate.log.entries(limit=limit, offset=max(0, offset))

    return {
        "total": gate.log.count(),
        "entries": [
            {
                "id": e.id,
                "at": e.at,
                "kind": e.kind,
                "host": e.host,
                "method": e.method,
                "url": e.url,
                "body": e.body,
                "literal_text": e.url if not e.body else f"{e.url}\n\n{e.body}",
                "bytes": e.byte_count,
                "decision": e.decision,
                "reason": e.reason,
                "source": e.source,
                "meta": e.meta,
            }
            for e in entries
        ],
    }


@app.get("/egress/verify")
async def egress_verify():
    """Check the hash chain.

    Reports what the check actually proves. The chain detects alteration by
    anything that did not go through the log's own append path; it does not
    prevent someone with write access from rebuilding it. Saying otherwise in
    the interface would be the kind of absolute security claim the contract
    forbids, so the wording here is what the UI should show.
    """
    from core.egress import TamperDetected, get_gate

    gate = get_gate()
    try:
        gate.log.verify()
        return {
            "intact": True,
            "entries": gate.log.count(),
            "detail": "Every entry still matches its hash and the chain is unbroken.",
            "caveat": (
                "This detects changes made outside Zaram — an edit, a deletion, "
                "a reordering, or file corruption. It cannot stop someone with "
                "access to this machine from rebuilding the record."
            ),
        }
    except TamperDetected as exc:
        return {
            "intact": False,
            "entries": gate.log.count(),
            "at_row": exc.at_row,
            "entry_id": exc.entry_id,
            "detail": str(exc),
        }


@app.get("/egress/policy")
async def egress_policy():
    """Per-source rules, and every host ever contacted.

    Returns hosts seen but unruled as well, so the privacy pane can offer a
    decision about a destination the user has actually encountered rather than
    asking them to type hostnames from memory.
    """
    from core.egress import get_gate

    gate = get_gate()
    rules = gate.policy.rules()
    seen = list(gate.log.hosts())

    return {
        "default": "deny",
        "rules": rules,
        "hosts_seen": seen,
        "hosts_without_a_rule": [h for h in seen if h not in rules and h != "-"],
    }


class EgressPolicyUpdate(BaseModel):
    host: str
    #: "allow", "ask" or "deny". Anything else is rejected.
    mode: str


@app.put("/egress/policy")
async def set_egress_policy(update: EgressPolicyUpdate):
    """Set one host's rule. Rule 5's 'explicit, per-item policy' in practice."""
    from core.egress import Mode, get_gate

    host = (update.host or "").strip().lower()
    if not host:
        raise HTTPException(status_code=400, detail="A host is required")
    try:
        mode = Mode(update.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"mode must be one of: {', '.join(m.value for m in Mode)}",
        )

    get_gate().policy.set(host, mode)
    return {"host": host, "mode": mode.value}


@app.delete("/egress/policy/{host}")
async def forget_egress_policy(host: str):
    """Remove a rule. The host reverts to the default, which is deny."""
    from core.egress import get_gate

    get_gate().policy.forget(host)
    return {"host": host.lower(), "mode": "deny", "reverted_to_default": True}


class EgressRetentionUpdate(BaseModel):
    #: Days to keep. 0 means keep everything.
    days: int


@app.post("/egress/retention")
async def apply_egress_retention(update: EgressRetentionUpdate):
    """Prune the log, and record that the pruning happened.

    The contract requires retention to ship *with* the log rather than after it:
    a permanent record of every private question is itself a privacy problem.
    """
    from core.egress import get_gate

    if update.days < 0:
        raise HTTPException(status_code=400, detail="days cannot be negative")

    gate = get_gate()
    removed = gate.log.apply_retention(max_age_days=update.days or None)
    return {
        "removed": removed,
        "remaining": gate.log.count(),
        "days": update.days,
        "note": (
            "Pruning is itself recorded, so the log can always show that entries "
            "were removed even though it can no longer show what they were."
        ),
    }


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


class MemoryCorrection(BaseModel):
    content: str


@app.post("/memory/{record_id}/correct")
async def correct_memory(record_id: str, body: MemoryCorrection):
    """Correct a fact. The original is kept, struck through, and never recalled.

    Rule 4 says the user can correct any stored fact and the affected answers
    must change. Deletion only ever satisfied half of that: it stops the wrong
    fact being recalled, but discards the record that Zaram had it wrong and the
    user said so. That record is the point — a system that shows you where it
    was mistaken is one you can believe when it says it is right.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    corrected = (body.content or "").strip()
    if not corrected:
        raise HTTPException(status_code=400, detail="A correction cannot be empty")

    try:
        result = await kernel.memory_runtime.correct(record_id, corrected)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such memory")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return {
        **result,
        "note": (
            "The original is kept and shown struck through. It is excluded from "
            "recall, so answers that depended on it will change."
        ),
    }


class MemoryPin(BaseModel):
    pinned: bool


@app.post("/memory/{record_id}/pin")
async def pin_memory(record_id: str, body: MemoryPin):
    """Pin a fact so recall prefers it over merely-recent ones."""
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    if not await kernel.memory_runtime.set_pinned(record_id, body.pinned):
        raise HTTPException(status_code=404, detail="No such memory")
    return {"id": record_id, "pinned": body.pinned}


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
    uvicorn.run(app, host="0.0.0.0", port=8420)
