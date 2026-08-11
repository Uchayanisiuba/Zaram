# backend/main.py
import asyncio
import json
import os
import time
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# --- KERNEL IMPORTS (Strict Boundary) ---
from core.bootstrapper import KernelBootstrapper
from core.chat_router import ChatRouter
# `_format_search_results` has referenced this without importing it: a
# NameError latent only because web search is off by default.
from core.query_classifier import SEARCH_MARKER

# --- LEGACY IMPORTS (Isolated for Fallback) ---
from implementations.ollama_llm import OllamaLLM
from runtimes.memory.maintenance import SpineMaintenance
# One spelling of `project:<id>`, from the module that owns it. A scope string
# built by hand at a call site is rule 7i's privacy boundary written twice.
from runtimes.memory.contracts import project_scope
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
spine_maintenance = None


@app.on_event("startup")
async def startup_event():
    global chat_router, spine_maintenance

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

    # Ingest can now reach the Spine, and the engine can say what it could not
    # read. `core/` keeps no import of `ingest/`; the dependency points inward
    # from here, which is what lets the engine be tested without either.
    ingest_service.attach_memory(kernel.memory_runtime)
    kernel.execution_engine.set_notice_source(ingest_service.notice_text)

    # Rule 7e stops being a document here. The decay rules and the promotion
    # evidence were written, tested and never once invoked by anything running
    # — see `runtimes/memory/maintenance.py` for why the schedule is "shortly
    # after boot, then daily" rather than a shorter interval.
    if kernel.memory_runtime is not None:
        spine_maintenance = SpineMaintenance(kernel.memory_runtime, kernel.event_bus)
        spine_maintenance.start()

    print("[Startup] Chat Router initialized. Kernel Online.")


@app.on_event("shutdown")
async def shutdown_event():
    print("[Shutdown] Powering down Zaram Kernel...")
    if spine_maintenance is not None:
        await spine_maintenance.stop()
    # No-op unless somebody actually used the microphone this session; the
    # recogniser is built on first use, not at boot.
    from voice.stt.service import shutdown_recogniser
    await shutdown_recogniser()
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
    #: Which project this exchange belongs to, or "" for none (rule 7i).
    #:
    #: Empty is a real answer, not a missing one: a question asked outside any
    #: project genuinely is not about one, and facts captured from it stay
    #: `global`. Inventing a project here would be a value nobody entered.
    project_id: str = ""


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
    
    # Which build is answering, and since when. Cheap, and it exists because a
    # backend from 06:32 served this port all day while two already-fixed bugs
    # were re-diagnosed against it. See core/build_stamp.py.
    from core.build_stamp import build_stamp

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
        # `curl localhost:8420/health` now answers "which build is this?" —
        # the question that would have saved two rounds of re-fixing bugs that
        # were already fixed.
        "build": build_stamp(),
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
        chat_router.route(
            final_prompt, request.model, system_prompt, request.session_id,
            project_id=request.project_id or None,
        ),
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
                # Rule 7i: `global` or `project:<id>`. One field, sent as one
                # field — the surface derives the project id from it rather
                # than being handed a second spelling that can disagree.
                "scope": r.scope,
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


@app.get("/memory/maintenance")
async def memory_maintenance_status():
    """What the last decay pass did, and what promotion is now being offered.

    Exists so the maintenance pass is observable rather than merely running.
    A background job that silently deletes the user's facts is the wrong shape
    for this product even when the deletions are correct — rule 4 gives the
    user authority over stored facts, and authority without visibility is not
    authority.

    `last_result` is null when no pass has run yet, which is a different claim
    from a pass that ran and changed nothing.
    """
    if spine_maintenance is None:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    result = spine_maintenance.last_result
    candidate_ids = (result or {}).get("promotion_candidates", [])

    # Resolved to content here rather than in the pass: the pass runs
    # unattended and should hold ids, not copies of facts that a correction may
    # have since changed underneath it.
    candidates = []
    if kernel.memory_runtime and candidate_ids:
        for rid in candidate_ids:
            record = await kernel.memory_runtime._store.get(rid)
            if record is None:
                continue
            candidates.append({
                "id": record.id,
                "content": record.content,
                "scope": record.scope,
                "recalled_in": sorted(record.recalled_in or []),
                "access_count": record.access_count,
            })

    return {
        "last_result": result,
        # Proposals, never applied. Promotion moves a fact from project scope to
        # global, changing what is shareable, and rule 6 says that is the user's
        # to grant. The caller promotes with POST /memory/{id}/scope.
        "promotion_candidates": candidates,
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
        # Where this fact belongs. Absent until 10 August, which meant a fact
        # could be scoped to a project and there was no way to see that it was
        # — rule 7i's field existed and was invisible from the outside.
        "scope": record.scope,
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


# --- ARTIFACTS -------------------------------------------------------------
#
# Backs the Work surface and the in-conversation file cards. Both read the same
# records, because they are the same thing shown twice — Work is "everything I
# made", a file card is "the thing I just made", and letting them diverge is how
# a document appears in one and not the other.

from artifacts import export as artifact_export  # noqa: E402
from artifacts.records import ArtifactRecords, default_db_path  # noqa: E402
from artifacts.service import ArtifactService  # noqa: E402
from artifacts.store import ArtifactStore, default_output_root  # noqa: E402

artifact_service = ArtifactService(
    ArtifactRecords(default_db_path()),
    ArtifactStore(default_output_root()),
)


def _artifact_json(artifact, *, include_html: bool = False) -> Dict[str, Any]:
    """One artifact, shaped for the frontend.

    `html` is omitted by default. It is the re-export source and can be large,
    and a list of twenty documents would carry twenty full documents to draw
    twenty rows.
    """
    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    if include_html:
        payload["html"] = artifact.html
    return payload


@app.get("/artifacts")
async def list_artifacts(
    project_id: str = "",
    kind: str = "",
    conversation_id: str = "",
    limit: int = 200,
    offset: int = 0,
):
    """Everything the user has made, newest first.

    Returns what is actually stored. If nothing has been generated this returns
    an empty list, and Work says so — there is no sample data behind this
    endpoint, and the module that used to provide some is gone.
    """
    artifacts = artifact_service.records.list(
        project_id=project_id or None,
        kind=kind or None,
        conversation_id=conversation_id or None,
        limit=limit,
        offset=offset,
    )
    return {
        "total": artifact_service.records.count(
            project_id=project_id or None, kind=kind or None
        ),
        "offset": offset,
        "limit": limit,
        "artifacts": [_artifact_json(a) for a in artifacts],
    }


# Declared before `/artifacts/{artifact_id}`: FastAPI matches in declaration
# order, so a static segment registered after a path parameter is unreachable —
# "projects" would be read as an artifact id and 404.
@app.get("/artifacts/projects")
async def list_artifact_projects():
    """Projects that actually hold artifacts, with counts.

    A *view over artifacts*, and now explicitly only that. It is what Work uses
    to offer a filter that cannot lead to an empty list. The list of projects
    that **exist** is `/projects`, which is a different question and used to be
    conflated with this one — a project you had only talked about was invisible,
    and one made by a typo could never be removed.
    """
    return {"projects": artifact_service.records.projects()}


# --------------------------------------------------------------------------- #
# Projects
#
# A project is an object here, not a label derived from artifacts. It carries
# the type that activates a pack, and it exists before anything has been saved
# into it — which is what lets a user work *inside* a project and have their
# facts scoped to it, rather than only after they have generated a file.
# --------------------------------------------------------------------------- #

from projects import ProjectRecords, ProjectType, UnknownProject  # noqa: E402
from projects.records import default_db_path as projects_db_path  # noqa: E402

project_records = ProjectRecords(projects_db_path())


def _project_json(project) -> Dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "type": project.type.value,
        "created_at": project.created_at,
        "note": project.note,
        "scope": project.scope,
    }


class ProjectCreateRequest(BaseModel):
    name: str
    type: str = "general"
    note: str = ""


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    type: str | None = None
    note: str | None = None


@app.get("/projects")
async def list_projects():
    """Every project that exists, with what is in it.

    The counts come from the stores that own those things rather than from a
    column here, so they cannot drift. They are what the delete confirmation is
    built on: "this holds 3 files and 11 facts" is the difference between an
    informed decision and a surprise.
    """
    out = []
    for project in project_records.list():
        entry = _project_json(project)
        entry["artifacts"] = artifact_service.records.count_for_project(project.id)
        entry["facts"] = await _fact_count_for_scope(project.scope)
        out.append(entry)
    return {"projects": out}


async def _fact_count_for_scope(scope: str) -> int:
    """How many facts are scoped to this project, or ``-1`` when unknown.

    ``-1`` rather than ``0``: a memory runtime that cannot answer is not the
    same as a project with no facts, and showing "0 facts" on a delete
    confirmation that then destroys eleven of them is the exact failure this
    count exists to prevent.
    """
    try:
        runtime = kernel.memory_runtime
        if runtime is None:
            return -1
        return await runtime.count_by_scope(scope)
    except Exception:
        return -1


@app.post("/projects")
async def create_project(body: ProjectCreateRequest):
    try:
        project = project_records.create(
            body.name, type=ProjectType(body.type), note=body.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _project_json(project)


@app.patch("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdateRequest):
    """Rename, retype or annotate. **The id never moves.**

    Facts carry `project:<id>` and artifacts carry `project_id`; re-slugging on
    rename would orphan every one of them.
    """
    try:
        project = project_records.get(project_id)
        if body.name is not None:
            project = project_records.rename(project_id, body.name)
        if body.type is not None:
            project = project_records.set_type(project_id, ProjectType(body.type))
        if body.note is not None:
            project = project_records.set_note(project_id, body.note)
    except UnknownProject:
        raise HTTPException(status_code=404, detail=f"No project called {project_id!r}.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _project_json(project)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str, contents: str = "keep"):
    """Remove a project. **The caller must say what happens to its contents.**

    `contents=keep` re-scopes the project's facts to global and leaves its files
    where they are, so nothing is lost — only the grouping. This is the default
    because it is the recoverable one.

    `contents=delete` removes the facts too. It is never implicit: a container
    quietly exercising rule 4 on the user's behalf is how someone loses a
    client's rates by tidying a sidebar.

    Files are never deleted by either path. Zaram has no capability to remove a
    file from disk and deliberately never has — that is the operating system's
    job, and a record claiming a file is gone while it sits in the output folder
    is worse than no record.
    """
    if contents not in ("keep", "delete"):
        raise HTTPException(
            status_code=400,
            detail="contents must be 'keep' (re-scope facts to global) or 'delete'.",
        )

    try:
        project = project_records.get(project_id)
    except UnknownProject:
        raise HTTPException(status_code=404, detail=f"No project called {project_id!r}.")

    moved = removed = 0
    try:
        runtime = kernel.memory_runtime
        if runtime is not None:
            if contents == "keep":
                moved = await runtime.rescope_to_global(project.scope)
            else:
                removed = await runtime.forget_scope(project.scope)
    except Exception as exc:
        # The facts are the irreplaceable half. If they cannot be dealt with,
        # the project stays — a half-completed delete that orphans facts under a
        # scope nothing points at is worse than a delete that did not happen.
        raise HTTPException(
            status_code=500,
            detail=f"The project was left in place: its facts could not be {contents}d ({exc}).",
        )

    project_records.delete(project_id)
    return {
        "deleted": project_id,
        "facts_moved_to_global": moved,
        "facts_deleted": removed,
        "files_untouched": artifact_service.records.count_for_project(project_id),
    }


class ArtifactUpdateRequest(BaseModel):
    """`None` means "not mentioned"; `""` means "no project".

    The same distinction the remember override draws, for the same reason: a
    field the caller left out and a field the caller cleared are different
    instructions, and collapsing them makes unassigning indistinguishable from
    forgetting to say.
    """

    project_id: str | None = None


@app.patch("/artifacts/{artifact_id}")
async def update_artifact(artifact_id: str, body: ArtifactUpdateRequest):
    """Move a file into a project, out of one, or between two.

    Assignment lives here rather than at generation time because the decision
    is usually made afterwards: a file exists, and *then* it becomes clear what
    it belongs to. Rule 7h — the offer belongs at the moment of doubt, not as a
    question asked in advance of the work.

    **The destination is checked before the move.** A typo would otherwise
    create a project that exists only as a string on one file: invisible in
    `/projects`, unnameable, undeletable, and carrying facts nothing points at.
    That is the bug `/artifacts/projects` and `/projects` were split to fix, and
    an unvalidated write here would put it straight back.

    Files are only ever re-labelled. Nothing moves on disk — the output
    directory is not a folder tree and a project is not a folder.
    """
    if body.project_id is None:
        raise HTTPException(
            status_code=400,
            detail="Nothing to change. Send project_id, or \"\" to remove it from its project.",
        )

    destination = body.project_id.strip()
    if destination:
        try:
            project_records.get(destination)
        except UnknownProject:
            raise HTTPException(
                status_code=400,
                detail=f"No project called {destination!r}. Create it first.",
            )

    if not artifact_service.records.set_project(artifact_id, destination):
        raise HTTPException(status_code=404, detail="No such artifact")

    return {"id": artifact_id, "project_id": destination}


# Declared here, among the project routes, rather than beside the other
# `/memory` ones: validating the destination needs `project_records`, which is
# imported at the top of this section. The alternative was hoisting that import
# above the whole artifacts block for one route's benefit.
class MemoryScope(BaseModel):
    """Where a fact belongs. `""` means global — about the user, not the work."""

    project_id: str


@app.post("/memory/{record_id}/scope")
async def set_memory_scope(record_id: str, body: MemoryScope):
    """Move a fact between global and a project, or between two projects.

    Rule 7i keeps scope as **one field on one store** precisely so this is a
    move rather than a copy between two stores. It is also the multiplayer
    boundary, which is what makes the direction matter: project memory is
    shareable and global memory never is, so moving a fact *into* a project
    widens who could eventually see it. That has to be the user's decision,
    which is why nothing here infers it.

    Promotion to global stays evidence-driven per rule 7e — a fact recalled
    across three projects is probably about the person, and that is when Zaram
    asks. This route is the answer to that question, and the manual override
    for when the system never asks.
    """
    if not kernel.memory_runtime:
        raise HTTPException(status_code=503, detail="Memory runtime not available")

    destination = (body.project_id or "").strip()
    if destination:
        try:
            project_records.get(destination)
        except UnknownProject:
            raise HTTPException(
                status_code=400,
                detail=f"No project called {destination!r}. Create it first.",
            )

    scope = project_scope(destination)
    if not await kernel.memory_runtime.set_scope(record_id, scope):
        raise HTTPException(status_code=404, detail="No such memory")

    return {
        "id": record_id,
        "scope": scope,
        "note": (
            "Facts about you stay global; facts about the work move with the "
            "project. Recall reads both."
        ),
    }


@app.get("/artifacts/formats")
async def list_artifact_formats():
    """Which export formats work on this machine, and why the others do not.

    CLAUDE.md: disabled capabilities are visible, not silent. PDF is expected to
    be unavailable on Windows until the installer carries the GTK runtime, and
    the UI is meant to show that reason rather than hide the option.
    """
    return {
        "formats": [
            {
                "extension": extension,
                "label": artifact_export.get(extension).label,
                "available": availability.ok,
                "reason": availability.reason,
                "remedy": availability.remedy,
            }
            for extension, availability in artifact_export.formats()
        ]
    }


@app.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, include_html: bool = False):
    artifact = artifact_service.records.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="No such artifact")

    return _artifact_json(artifact, include_html=include_html)


@app.get("/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    """The file itself.

    The path comes from the record, not from the request, so there is nothing
    user-controlled in it — but it is still checked for containment before being
    served. The store confines every write to the output root; this asserts the
    same thing on the way out, because a record written by an older build is an
    input this endpoint does not control.
    """
    artifact = artifact_service.records.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="No such artifact")
    if not artifact.path:
        raise HTTPException(status_code=404, detail="No file was written")

    resolved = os.path.abspath(artifact.path)
    root = os.path.abspath(str(artifact_service.store.root))
    if os.path.commonpath([resolved, root]) != root:
        raise HTTPException(status_code=403, detail="Outside the output directory")
    if not os.path.isfile(resolved):
        # The record exists and the file does not. Say which, rather than a bare
        # 404 that reads as "no such document" — the user may have moved it, and
        # that is a different problem from Zaram having lost it.
        raise HTTPException(
            status_code=410,
            detail="The record is here but the file is not at the path it was written to",
        )

    exporter_media = {
        e: artifact_export.get(e).media_type for e in artifact_export.EXPORTERS
    }
    extension = os.path.splitext(resolved)[1].lstrip(".").lower()

    return FileResponse(
        resolved,
        media_type=exporter_media.get(extension, "application/octet-stream"),
        filename=artifact.filename,
    )


class GenerateClaim(BaseModel):
    id: str
    source_id: str
    excerpt: str
    source_excerpt: str = ""
    source_revision: str | None = None


class GenerateSource(BaseModel):
    kind: str
    url: str | None = None
    title: str | None = None


class GenerateLineItem(BaseModel):
    description: str
    #: Strings, so JSON's single double-precision number type cannot round the
    #: money before it reaches the Decimal that is supposed to protect it.
    quantity: str = "1"
    unit_price: str
    unit: str = ""


class GenerateAdjustment(BaseModel):
    """A named amount after the subtotal — tax, discount, deposit held.

    `label` is the user's word for it and is printed as given. Zaram does not
    know whether this is VAT or GST, does not decide whether it applies, and
    holds no table of rates: CLAUDE.md forbids computing tax liability. Summing
    what someone tells you is bookkeeping; deciding it is advice.
    """

    label: str
    rate: str | None = None
    amount: str | None = None


class GenerateSlide(BaseModel):
    """One slide: a heading and its bullets.

    A heading with no bullets is kept — it is a section marker, and dropping it
    loses the deck's structure.
    """

    heading: str
    bullets: list[str] = []


class GenerateBody(BaseModel):
    title: str
    #: Prose. A string is a plain paragraph; an object with a matching claim id
    #: is a sentence traceable to a fact and gets an anchor in the output.
    blocks: list[Any] = []
    kind: str = "document"
    fmt: str | None = None
    filename: str = ""
    project_id: str = ""
    conversation_id: str = ""
    conversation_title: str = ""
    sources: list[GenerateSource] = []
    claims: list[GenerateClaim] = []
    # Spreadsheet only.
    header: list[str] = []
    rows: list[list[Any]] = []
    caption: str = ""
    # Deck only. The outline: one heading per slide, bullets beneath it. Not a
    # second authoring path — the exporter splits any document on its headings,
    # and this is only how a caller says "I meant slides" so `.pptx` is the
    # default format and the preview is the outline.
    slides: list[GenerateSlide] = []
    # Invoice only.
    #
    # Amounts are strings, not floats. JSON has one number type and it is a
    # double, so `"unit_price": 0.1` arrives as 0.1000000000000000055…, and an
    # invoice built from that cannot be reconciled by hand. `invoice.py` refuses
    # a float rather than converting one; keeping the wire type a string is what
    # makes that refusal reachable instead of a 500 nobody can act on.
    items: list[GenerateLineItem] = []
    adjustments: list[GenerateAdjustment] = []
    number: str = ""
    #: ISO date. Defaults to today, which is what "make me an invoice" means.
    issued: str = ""
    #: Days from issue until payment is due. Produces both the printed terms
    #: sentence and the Due date, from one number, so they cannot disagree.
    terms_days: int | None = None
    currency: str = ""
    bill_to: list[str] = []
    notes: str = ""
    payment: list[str] = []
    #: The masthead — who the invoice is from. Optional: with nothing supplied
    #: the document is still titled and ruled rather than a bare heading, which
    #: is why the absence of branding does not read as a rendering failure.
    from_name: str = ""
    from_lines: list[str] = []


@app.post("/artifacts/generate")
async def generate_artifact(body: GenerateBody):
    """Make a document, spreadsheet or chart, and record it.

    The seam between "a model produced some prose" and "the user has a file".
    Generative tier: it creates new artifacts and changes nothing that already
    exists, so it needs no undo, no sandbox and no confirmation — the safety is
    structural. Files land in one output directory, the write path cannot
    overwrite or delete, and a name collision increments.

    Not yet reachable from natural language. Saying "write that up as a
    proposal" in chat does not trigger this — that needs a capability registered
    with the router, which is separate work. This endpoint is the thing that
    capability will call.
    """
    from datetime import date

    from artifacts import invoice as invoice_module
    from artifacts.contracts import ArtifactKind, ArtifactSource, Claim
    from artifacts.letterhead import Letterhead

    try:
        kind = ArtifactKind(body.kind)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown kind {body.kind!r}; use one of "
            f"{[k.value for k in ArtifactKind]}",
        ) from None

    if body.fmt:
        try:
            availability = artifact_export.get(body.fmt).availability()
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"No exporter for {body.fmt!r}"
            ) from None
        if not availability.ok:
            # 503, not 500: the request is fine and the machine cannot serve it.
            # The reason and the remedy go back so the UI can say which.
            raise HTTPException(
                status_code=503,
                detail={
                    "reason": availability.reason,
                    "remedy": availability.remedy,
                },
            )

    sources = [ArtifactSource(**s.model_dump()) for s in body.sources]
    claims = [Claim(**c.model_dump()) for c in body.claims]
    by_id = {c.id: c for c in claims}

    common = dict(
        title=body.title,
        filename=body.filename,
        project_id=body.project_id,
        conversation_id=body.conversation_id,
        conversation_title=body.conversation_title,
        sources=sources,
        claims=claims,
    )

    try:
        if kind == ArtifactKind.INVOICE:
            artifact = artifact_service.create_invoice(
                items=[
                    invoice_module.line_item(
                        description=i.description,
                        quantity=i.quantity,
                        unit_price=i.unit_price,
                        unit=i.unit,
                    )
                    for i in body.items
                ],
                adjustments=[
                    invoice_module.Adjustment(
                        label=a.label,
                        rate=invoice_module.to_decimal(a.rate, field_name=f"rate for {a.label!r}")
                        if a.rate is not None
                        else None,
                        amount=invoice_module.to_decimal(
                            a.amount, field_name=f"amount for {a.label!r}"
                        )
                        if a.amount is not None
                        else None,
                    )
                    for a in body.adjustments
                ],
                number=body.number,
                issued=date.fromisoformat(body.issued) if body.issued else None,
                terms_days=body.terms_days,
                currency=body.currency,
                bill_to=body.bill_to,
                notes=body.notes,
                payment=body.payment,
                # Supplied per request, not read from a store, because **where
                # branding is captured is an open decision** (see MILESTONES,
                # "Where branding is captured — decided, not yet built"). A
                # request field commits to nothing: when capture lands, this
                # becomes its default rather than a second source of truth.
                letterhead=(
                    Letterhead(name=body.from_name, lines=body.from_lines)
                    if (body.from_name or body.from_lines)
                    else None
                ),
                fmt=body.fmt,
                **common,
            )
        elif kind == ArtifactKind.DECK:
            artifact = artifact_service.create_deck(
                slides=[(s.heading, s.bullets) for s in body.slides],
                subtitle=body.caption,
                fmt=body.fmt,
                **common,
            )
        elif kind == ArtifactKind.SPREADSHEET:
            artifact = artifact_service.create_spreadsheet(
                header=body.header, rows=body.rows, caption=body.caption,
                fmt=body.fmt, **common
            )
        else:
            # A block naming a claim becomes that claim, so the anchor and the
            # Sources entry agree. A block naming one that was not supplied is
            # rejected rather than silently written as plain prose — an
            # unanchored sentence that was meant to be cited is the failure the
            # whole provenance chain exists to prevent.
            blocks: list[Any] = []
            for block in body.blocks:
                if isinstance(block, dict):
                    claim_id = block.get("claim_id") or block.get("id")
                    if claim_id not in by_id:
                        raise HTTPException(
                            status_code=400,
                            detail=f"block cites claim {claim_id!r}, which is not in claims",
                        )
                    blocks.append(by_id[claim_id])
                else:
                    blocks.append(str(block))

            artifact = artifact_service.create_document(
                blocks=blocks, kind=kind, fmt=body.fmt, **common
            )
    except HTTPException:
        raise
    except invoice_module.InvoiceIncomplete as exc:
        # 400, not 500. Rule 9 refusals are the caller being told what is
        # missing — "an invoice needs at least one line" is actionable, and a
        # 500 would present a deliberate, correct refusal as a crash. The
        # message is written for a person and goes back unchanged.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        # Chiefly `date.fromisoformat` on a malformed `issued`. Same reasoning.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    print(f"[Artifacts] Wrote {artifact.filename} ({artifact.size_bytes} bytes)")
    return _artifact_json(artifact)


class RememberBody(BaseModel):
    remember: bool | None = None


@app.post("/artifacts/{artifact_id}/remember")
async def set_artifact_remember(artifact_id: str, body: RememberBody):
    """The "Don't remember this" override on a file card.

    `null` clears the override rather than setting it to false: "I have not
    decided" and "no" are different answers, and only the first is allowed to be
    changed later by a default.
    """
    if not artifact_service.records.set_remember_override(artifact_id, body.remember):
        raise HTTPException(status_code=404, detail="No such artifact")

    return {"id": artifact_id, "remember_override": body.remember}


# --- Ingest -------------------------------------------------------------- #
#
# Knowledge reads these. The service already produced a reason and a remedy per
# file; without somewhere to read them from, "failures must be loud" reduces to
# whether anyone happened to be watching the response stream.

from ingest.records import IngestRecords  # noqa: E402
from ingest.service_api import IngestService, default_db_path as ingest_db_path  # noqa: E402

ingest_service = IngestService(IngestRecords(ingest_db_path()))


class IngestBody(BaseModel):
    path: str


class PolicyBody(BaseModel):
    policy: str


@app.post("/ingest")
async def start_ingest(body: IngestBody):
    """Index a folder, streaming one event per file as it is read.

    NDJSON on the same pattern as `/chat`, because the frontend already parses
    it and a second streaming format would be a second set of split-chunk bugs.

    Progress is per *file*, not a percentage: a bar that stops at 90% says
    nothing about which document is missing, and the name plus what happened to
    it is the only part the user can act on.
    """
    ingest_service.attach_memory(getattr(kernel, "memory_runtime", None))

    def _stream():
        for event in ingest_service.stream_scan(body.path):
            yield json.dumps(event) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@app.get("/ingest/sources")
async def list_ingest_sources():
    """Every folder the user has pointed at, with its counts."""
    return {"sources": ingest_service.records.sources()}


@app.get("/ingest/outcomes")
async def list_ingest_outcomes(source_id: str = "", problems_only: bool = False):
    """What happened to each file. The list Knowledge shows."""
    return {
        "outcomes": ingest_service.records.outcomes(
            source_id=source_id or None, problems_only=problems_only
        )
    }


@app.post("/ingest/outcomes/{outcome_id}/retry")
async def retry_ingest_outcome(outcome_id: str):
    """Re-read one file.

    Offered on every visible problem, because the commonest reason a file
    failed is that it was open in Word at the time — and a failure the user
    cannot act on is just bad news.
    """
    ingest_service.attach_memory(getattr(kernel, "memory_runtime", None))
    outcome = ingest_service.retry(outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="No such outcome")
    return outcome


@app.post("/ingest/sources/{source_id}/policy")
async def set_ingest_policy(source_id: str, body: PolicyBody):
    """Rule 5: per-source, default deny."""
    try:
        changed = ingest_service.records.set_policy(source_id, body.policy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail="No such source")
    return {"id": source_id, "policy": body.policy}


@app.delete("/ingest/sources/{source_id}")
async def remove_ingest_source(source_id: str):
    """Withdraw a folder, and take its facts out of the Spine with it.

    Rule 4: the user can delete any stored fact and the affected answers
    change. Removing the folder while leaving its facts recallable would be the
    rule failing quietly, which is worse than not offering removal at all.
    """
    fact_ids = ingest_service.records.remove_source(source_id)
    forgotten = 0
    runtime = getattr(kernel, "memory_runtime", None)
    if runtime is not None:
        for fact_id in fact_ids:
            try:
                if await runtime.forget(fact_id):
                    forgotten += 1
            except Exception:
                print(f"[Ingest] could not forget {fact_id}")
    return {"id": source_id, "facts_removed": forgotten, "facts_recorded": len(fact_ids)}


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
                # KNOWN WRONG, and unused: this builds the URL from the request
                # id, which is the defect that made /voice/synthesize return a
                # 404 for every utterance — AudioCache names files
                # `{voice}_{hash}.wav`. Fixed there by carrying
                # `SynthesisResult.audio_filename`; fixing it here needs the
                # same field on AudioChunk. Nothing in the frontend calls
                # /voice/stream, so it is marked rather than migrated — but it
                # must not be wired up in this state.
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


# --------------------------------------------------------------------------- #
# Listening
#
# The audio arrives as a raw body rather than a multipart form: it is one blob
# with one content type, and a form would add a filename and a field name that
# nothing reads. It is transcribed in this process, on this machine, and is
# never written to disk — a microphone recording is the most sensitive input
# Zaram takes, and a temp file would outlive the request that needed it.
# --------------------------------------------------------------------------- #

#: A push-to-talk clip is seconds long. The cap is not about disk — nothing is
#: written — but about not reading an unbounded body into memory because a
#: caller said so.
MAX_TRANSCRIBE_BYTES = 25 * 1024 * 1024


@app.get("/voice/stt/health")
async def stt_health():
    """Whether Zaram can listen, and when it cannot, why.

    Called by the UI to decide whether the microphone button is offered.
    CLAUDE.md: disabled capabilities are visible, not silent — a mic button that
    is simply absent tells the user nothing, and one that fails on press tells
    them something worse.
    """
    from voice.stt.service import get_recogniser

    recogniser = await get_recogniser()
    return await recogniser.health_check()


@app.post("/voice/transcribe")
async def voice_transcribe(request: Request, language: str | None = None):
    """Turn a recording into text. Local only."""
    from voice.stt.service import get_recogniser

    audio = await request.body()
    if len(audio) > MAX_TRANSCRIBE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That recording is larger than the {MAX_TRANSCRIBE_BYTES // (1024 * 1024)} MB limit.",
        )

    recogniser = await get_recogniser()
    if not recogniser.is_available():
        report = await recogniser.health_check()
        # 503 with the recogniser's own reason. It is written for a user — it
        # names the install and its size, or the blocked download and its size —
        # so it is passed through rather than replaced with "unavailable".
        raise HTTPException(status_code=503, detail=report.get("reason", "Speech recognition is unavailable."))

    try:
        transcript = await recogniser.transcribe(audio, language=language)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    # Measured: the same sentence transcribed three ways, and one of them turned
    # *naira* into **$** — wrong by ~1500x, in the direction that looks
    # reasonable on an invoice. Nothing downstream can catch that, because
    # `$400,000` is a well-formed amount. So the transcript says so itself
    # rather than arriving looking like ordinary prose.
    #
    # Reported, never corrected. Rewriting `$` to `₦` would be guessing intent
    # from audio that has already proven unreliable, which is the failure rule 9
    # is about.
    from voice.stt.figures import CONFIRMATION_NOTICE, figures_in

    figures = figures_in(transcript.text)

    return {
        "text": transcript.text,
        "language": transcript.language,
        "duration_s": transcript.duration_s,
        "segments": [
            {"text": s.text, "start_s": s.start_s, "end_s": s.end_s}
            for s in transcript.segments
        ],
        "figures": [
            {"kind": f.kind, "text": f.text, "start": f.start, "end": f.end}
            for f in figures
        ],
        "needs_confirmation": bool(figures),
        # Sent rather than duplicated in the frontend, so the wording tracks the
        # measurement that justifies it.
        "confirmation_notice": CONFIRMATION_NOTICE if figures else None,
    }


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
