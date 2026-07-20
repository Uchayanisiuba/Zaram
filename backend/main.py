# backend/main.py
import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
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
    
    # Initialize the Chat Router with the new engine and the legacy fallback
    def legacy_gen(req_text: str, model: str, system_prompt: str = ""):
        llm = OllamaLLM()
        cm = ConversationManager(llm, None)
        for event in cm.run_conversation(req_text, model, system_prompt):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    chat_router = ChatRouter(kernel.execution_engine, legacy_gen)
    print("[Startup] Chat Router initialized. Kernel Online.")

@app.on_event("shutdown")
async def shutdown_event():
    print("[Shutdown] Powering down Zaram Kernel...")
    await kernel.shutdown()

# --- REQUEST MODELS ---
class ChatRequest(BaseModel):
    text: str
    model: str = "gemma3:latest"
    personality: str = "af_heart"
    persona: str = "zaram_prime"

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
    return {
        "status": "ok",
        "kernel": "online" if chat_router is not None else "offline",
        "capabilities": capabilities,
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """Strangler Fig Endpoint: Routes via ChatRouter."""
    print(f"[STAGE-7][Python] POST /chat received: text='{request.text[:50]}...' model={request.model} persona={request.persona}")
    
    # Resolve persona system prompt
    persona_data = PERSONAS.get(request.persona, PERSONAS.get("zaram_prime", {}))
    system_prompt = persona_data.get("system_prompt", "") if persona_data else ""
    
    return StreamingResponse(
        chat_router.route(request.text, request.model, system_prompt), 
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
            yield f"data: {json.dumps({'type': 'error', 'content': 'No image was provided for vision analysis. Capture a screenshot or attach an image first.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    return StreamingResponse(
        engine.stream_vision_response(full_prompt, images=[request.image]),
        media_type="text/event-stream"
    )

class KnowledgeRequest(BaseModel):
    query: str
    persona: str = "zaram_prime"

@app.post("/knowledge/search")
async def knowledge_search(request: KnowledgeRequest):
    """Internet search endpoint."""
    print(f"[STAGE-7][Python] POST /knowledge/search received: query='{request.query[:50]}...' persona={request.persona}")
    results = await perform_knowledge_search(request.query, request.persona)
    return results

async def perform_knowledge_search(query: str, persona: str = "zaram_prime"):
    """Performs internet search and returns results."""
    import json
    try:
        search_results = [
            {
                "title": f"Search results for: {query}",
                "url": "https://example.com/search",
                "snippet": f"This is a simulated search result for '{query}'. In a production environment, this would connect to a real search API like DuckDuckGo, Google, or Bing to return fresh results."
            },
            {
                "title": f"Latest information about {query}",
                "url": "https://example.com/latest",
                "snippet": f"Current information and recent developments related to '{query}'. The AI would synthesize this information to provide an accurate, up-to-date answer."
            },
            {
                "title": f"{query} - Wikipedia",
                "url": "https://example.com/wiki",
                "snippet": f"Comprehensive overview of '{query}' with references and detailed explanations. This represents how the AI would gather and synthesize information from authoritative sources."
            }
        ]
        
        return {
            "query": query,
            "persona": persona,
            "results": search_results,
            "total_results": len(search_results),
            "status": "success"
        }
    except Exception as exc:
        return {
            "query": query,
            "persona": persona,
            "results": [],
            "total_results": 0,
            "status": "error",
            "error": str(exc)
        }

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Legacy Audio Endpoint (Preserved)."""
    file_path = os.path.join("audio_cache", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found")

PERSONAS = {
    "zaram_prime": {
        "name": "Zaram Prime",
        "gender": "neutral",
        "description": "Professional, calm, and authoritative. The primary cybernetic intelligence core.",
        "system_prompt": "You are Zaram Prime, a professional and authoritative AI assistant. You are calm, structured, and highly capable. You speak with confidence and precision.",
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