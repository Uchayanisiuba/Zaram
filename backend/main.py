import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

# Import our new modular components
from implementations.ollama_llm import OllamaLLM
from implementations.kokoro_tts import KokoroTTS
from services.conversation_manager import ConversationManager

print("🚀 Starting Zaram Backend...")

# --- APP INITIALIZATION ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines ONCE at startup
print("⏳ Initializing Engines...")
ollama_engine = OllamaLLM()
kokoro_engine = KokoroTTS()
conversation_manager = ConversationManager(ollama_engine, kokoro_engine)
print("✅ Engines initialized successfully. Zaram is ready.")

def format_sse(data_dict):
    return f"data: {json.dumps(data_dict)}\n\n"

# --- ENDPOINTS ---
@app.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = os.path.join("audio_cache", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found")

@app.get("/personalities")
def get_personalities():
    return {
        "personalities": {
            "af_heart": {"name": "Alexis", "gender": "female", "description": "Professional, calm, and authoritative."},
            "af_bella": {"name": "Bella", "gender": "female", "description": "Warm, friendly, and expressive."},
            "af_nicole": {"name": "Nicole", "gender": "female", "description": "Clear, concise, and helpful."},
            "am_adam": {"name": "Adam", "gender": "male", "description": "Deep, confident, and reassuring."},
            "am_michael": {"name": "Michael", "gender": "male", "description": "Casual, conversational, and relaxed."}
        }
    }

class ChatRequest(BaseModel):
    text: str
    model: str = "gemma3:latest"
    personality: str = "af_heart"

@app.post("/chat")
def chat(request: ChatRequest):
    def event_generator():
        for event in conversation_manager.run_conversation(request.text, request.model, request.personality):
            yield format_sse(event)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)