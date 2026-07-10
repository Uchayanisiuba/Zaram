import os
import numpy as np
import soundfile as sf
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Kokoro TTS imports
from kokoro import KPipeline

# --- APP INITIALIZATION ---
app = FastAPI()

# Allow the frontend (React) to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- KOKORO TTS SETUP & WARMUP ---
AUDIO_DIR = "audio_cache"
os.makedirs(AUDIO_DIR, exist_ok=True)

print("⏳ Loading Kokoro TTS model into memory... (This takes a few seconds on first run)")
kokoro_pipeline = KPipeline(lang_code='a')
print("✅ Kokoro TTS model loaded and ready!")

# WARM UP: Generate a tiny audio to ensure the model is fully ready
# FIX: Using 'af_heart' which is a REAL Kokoro voice
print("🔥 Warming up audio engine...")
try:
    for _, _, audio in kokoro_pipeline("hi", voice="af_heart"):
        pass
    print("✅ Audio engine warmed up and ready for instant responses!")
except Exception as e:
    print(f"⚠️ Warmup failed, but model is loaded: {e}")

def generate_kokoro_audio(text: str, voice: str = "af_heart"):
    """
    Generates audio using Kokoro TTS and overwrites the cache file to save space.
    """
    try:
        audio_chunks = []
        for _, _, audio in kokoro_pipeline(text, voice=voice):
            audio_chunks.append(audio)
        
        if not audio_chunks:
            return None

        full_audio = np.concatenate(audio_chunks)
        
        cache_path = os.path.join(AUDIO_DIR, "latest_response.wav")
        sf.write(cache_path, full_audio, 24000, format='WAV') 
        
        return cache_path
        
    except Exception as e:
        print(f"❌ Kokoro TTS Error: {e}")
        return None

# --- ENDPOINTS ---

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serves the generated audio file to the frontend."""
    file_path = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Audio file not found")

@app.get("/personalities")
async def get_personalities():
    """Returns the list of available AI personalities/voices.
    NOTE: The IDs must match actual Kokoro voice files on HuggingFace!"""
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
async def chat(request: ChatRequest):
    """Handles the chat request: gets LLM response, generates audio, and returns both."""
    
    # 1. Get text response from Ollama
    ai_text = ""
    try:
        ollama_response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": request.model, 
                "prompt": request.text, 
                "stream": False
            },
            timeout=120
        )
        ollama_response.raise_for_status()
        ai_text = ollama_response.json().get("response", "I couldn't generate a response.")
    except requests.exceptions.ConnectionError:
        ai_text = "Error: Cannot connect to Ollama. Please ensure Ollama is running."
    except Exception as e:
        ai_text = f"Error connecting to LLM: {str(e)}"

    # 2. Generate Audio using Kokoro
    audio_file_path = generate_kokoro_audio(ai_text, voice=request.personality)
    
    # 3. Return the response to the frontend
    if audio_file_path:
        return {
            "text": ai_text,
            "audio_url": "http://127.0.0.1:8000/audio/latest_response.wav" 
        }
    else:
        return {
            "text": ai_text,
            "audio_url": None 
        }

# --- RUN SERVER ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)