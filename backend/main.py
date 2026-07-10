from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx
import edge_tts
import os

from services.text_processor import preprocess_text

app = FastAPI(title="Zaram Backend")

os.makedirs("audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="audio"), name="audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PERSONALITY ENGINE ---
PERSONALITIES = {
    "af_alexis": {
        "name": "Alexis", "voice": "en-US-AvaMultilingualNeural", 
        "gender": "female", "description": "Professional, calm, and authoritative."
    },
    "af_bella": {
        "name": "Bella", "voice": "en-US-AriaNeural", 
        "gender": "female", "description": "Warm, friendly, and expressive."
    },
    "af_nicole": {
        "name": "Nicole", "voice": "en-US-JennyNeural", 
        "gender": "female", "description": "Clear, concise, and helpful."
    },
    "am_adam": {
        "name": "Adam", "voice": "en-US-GuyNeural", 
        "gender": "male", "description": "Deep, confident, and reassuring."
    },
    "am_michael": {
        "name": "Michael", "voice": "en-US-DavisNeural", 
        "gender": "male", "description": "Casual, conversational, and relaxed."
    }
}

@app.get("/personalities")
async def get_personalities():
    """Fetches available voices for Frontend and Unreal Engine."""
    return {"personalities": PERSONALITIES}

@app.get("/")
async def root():
    return {"message": "Zaram Backend is running", "status": "online"}

@app.post("/chat")
async def chat_endpoint(request: Request):
    """Standard Chat Endpoint with Personality Support."""
    try:
        data = await request.json()
        user_text = data.get("text", "")
        model = data.get("model", "gemma3:latest")
        personality_id = data.get("personality", "af_alexis")
        
        # Get personality config
        personality = PERSONALITIES.get(personality_id, PERSONALITIES["af_alexis"])
        voice = personality["voice"]

        # 1. Get Text from Ollama
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": user_text, "stream": False}
            )
            ai_response = response.json().get("response", "")
            
        if not ai_response:
            return {"text": "Error: Empty response.", "model_used": model, "status": "error"}

        # 2. Preprocess Text (Removes emojis, asterisks, markdown)
        clean_text = preprocess_text(ai_response)

        # 3. Generate Audio using the selected Personality's voice
        communicate = edge_tts.Communicate(clean_text, voice)
        audio_file = "audio/response.mp3"
        await communicate.save(audio_file)
        
        return {
            "text": clean_text,
            "audio_url": "http://127.0.0.1:8000/audio/response.mp3",
            "model_used": model,
            "personality_used": personality_id,
            "status": "success"
        }
        
    except Exception as e:
        return {"text": f"Error: {str(e)}", "model_used": "unknown", "status": "error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)