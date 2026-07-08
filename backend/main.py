#!/usr/bin/env python3
"""
Zaram Backend v4.5 — High-Fidelity Brain Orchestrator
- Multi-Model Router (Auto-route, qwen3:latest, gemma3:latest, moondream:latest, llama3.2:latest)
- Mapped Kokoro character voice selectors (Male & Female configurations)
- Pydantic JSON Payload parsing to fix the 422 Unprocessable Entity error
- Deep speech cleaner and text-to-speech normalizer
"""

import os
import re
import sys
import json
import time
import asyncio
import logging
import warnings
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

# FastAPI frameworks & Pydantic validation schemas
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Mapped perfectly to C:\Zaram structure shown in your folder project images
BASE_DIR = Path(__file__).parent.resolve()  # C:\Zaram\backend
ZARAM_ROOT = BASE_DIR.parent                # C:\Zaram

AUDIO_DIR = BASE_DIR / "audio_output"
TEMP_DIR  = BASE_DIR / "temp"
UPLOADS_DIR = ZARAM_ROOT / "uploads"

# Verify folders exist
AUDIO_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

CONFIG = {
    "OLLAMA_HOST": "http://localhost:11434",
    "AUTO_CODE_MODEL": "qwen3:latest",
    "AUTO_LOGIC_MODEL": "gemma3:latest",
    "AUTO_CONVO_MODEL": "llama3.2:latest",
    "AUTO_VISION_MODEL": "moondream:latest",
    "MAX_AUDIO_FILES": 5,
    "port": 8000,
    "SYSTEM_PROMPT": "You are Zaram, a unified machine intelligence console. Calm, authoritative, and helpful. Keep responses concise unless structured code or deep analysis is requested."
}

PORT = int(os.environ.get("ZARAM_PORT", CONFIG["port"]))
SERVER_URL = f"http://127.0.0.1:{PORT}"

# Logger configurations
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("zaram")

CHARACTERS = {
    "zaram_prime": {
        "name": "Zaram Prime (Female)",
        "voice_id": "af_heart",
        "personality": "Primary cybernetic intelligence core. Warm, fast, highly structured."
    },
    "nova_hacker": {
        "name": "Nova (Female)",
        "voice_id": "af_bella",
        "personality": "Fast-paced code analysis agent with a sharp, technical voice."
    },
    "baba_elder": {
        "name": "Baba (Male)",
        "voice_id": "am_adam",
        "personality": "Wise elder voice. Calm, analytical, focused on deep systems logic."
    },
    "michael_tech": {
        "name": "Michael (Male)",
        "voice_id": "am_michael",
        "personality": "Operational support unit. Concise and professional."
    }
}

class ChatPayload(BaseModel):
    text: Optional[str] = None
    message: Optional[str] = None
    character_id: Optional[str] = "zaram_prime"
    brain_id: Optional[str] = "auto"
    model: Optional[str] = "auto"
    web_search_override: Optional[str] = "false"
    filename: Optional[str] = None

class SpeechCleaner:
    """Strips Markdown symbols, brackets, block tags, and emojis for pure vocal audio output."""
    def __init__(self):
        self._build_filters()

    def _build_filters(self):
        self.rules = [
            (re.compile(r"&#(\d+);"), lambda m: chr(int(m.group(1)))),
            (re.compile(r"&\w+;"), ""),
            (re.compile(r"```[\s\S]*?```"), " [code output skipped] "),
            (re.compile(r"`{1,3}[\s\S]*?`{1,3}"), " [code block skipped] "),
            (re.compile(r"\*\*(.*?)\*\*"), r"\1"),
            (re.compile(r"\*(.*?)\*"), r"\1"),
            (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),
            (re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]"), ""),
            (re.compile(r"\n+"), " "),
            (re.compile(r"\s+"), " "),
        ]

    def clean(self, text: str) -> str:
        for pattern, replacement in self.rules:
            if callable(replacement):
                text = pattern.sub(replacement, text)
            else:
                text = pattern.sub(replacement, text)
        return text.strip()

class CircularAudioBuffer:
    def __init__(self, max_files: int = 5, output_dir: Path = AUDIO_DIR):
        self.max_files = max_files
        self.output_dir = output_dir
        self._index = 0
        self._lock = asyncio.Lock()

    def _filename(self, idx: int) -> str:
        return f"zaram_voice_{idx}.wav"

    async def get_next_path(self) -> Path:
        async with self._lock:
            path = self.output_dir / self._filename(self._index)
            self._index = (self._index + 1) % self.max_files
            return path

    async def cleanup(self):
        files = sorted(self.output_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_file in files[self.max_files:]:
            try:
                old_file.unlink()
            except Exception:
                pass

class KokoroTTS:
    def __init__(self):
        self.pipeline = None
        self.ready = False
        self._load_engine()

    def _load_engine(self):
        try:
            from kokoro import KPipeline
            self.pipeline = KPipeline(lang_code='a') # 'a' for American English
            self.ready = True
            logger.info("Kokoro local AI speech pipeline successfully initiated.")
        except Exception as err:
            logger.warning("Kokoro local library module offline. Audio generation suspended: %s", err)

    async def synthesize(self, text: str, voice_id: str, output_path: Path) -> bool:
        if not self.ready or not self.pipeline:
            return False
        try:
            import soundfile as sf
            import numpy as np

            def run_inference():
                generator = self.pipeline(text, voice=voice_id, speed=1.0, split_pattern=r'\n+')
                audio_segments = []
                for _, _, audio in generator:
                    if audio is not None and len(audio) > 0:
                        audio_segments.append(audio)
                return audio_segments

            segments = await asyncio.to_thread(run_inference)
            if not segments:
                return False

            combined = np.concatenate(segments)
            sf.write(str(output_path), combined, 24000) # Kokoro native sampling rate is 24kHz
            return output_path.exists() and output_path.stat().st_size > 512
        except Exception as e:
            logger.error("Kokoro synthesizer execution exception: %s", e)
            return False

class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")
        self.chat_url = f"{self.host}/api/chat"

    async def chat(self, model: str, messages: list) -> str:
        import aiohttp
        payload = {"model": model, "messages": messages, "stream": False}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.chat_url, json=payload, timeout=30.0) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("message", {}).get("content", "")

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cleaner = SpeechCleaner()
    app.state.audio_buffer = CircularAudioBuffer(CONFIG["MAX_AUDIO_FILES"])
    app.state.kokoro = KokoroTTS()
    app.state.ollama = OllamaClient(CONFIG["OLLAMA_HOST"])
    logger.info("Zaram active and listening on port %s", PORT)
    yield
    logger.info("Orchestrator resources safely released.")

app = FastAPI(title="Zaram Brain Orchestrator", version="4.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "kokoro_active": app.state.kokoro.ready,
        "engine": "Zaram Core Server v4.5"
    }

@app.post("/chat")
async def chat_endpoint(payload: ChatPayload):
    start_time = time.time()
    cleaner = app.state.cleaner
    ollama = app.state.ollama
    kokoro = app.state.kokoro
    audio_buffer = app.state.audio_buffer

    # Reconcile multi-key mapping parameters to support both styles seamlessly
    raw_message = payload.text or payload.message or ""
    selected_model = payload.brain_id or payload.model or "auto"
    character_id = payload.character_id or "zaram_prime"
    web_search = payload.web_search_override or "false"

    if not raw_message:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Text prompt parameter is required."})

    model_used = selected_model
    routing_reason = "Manual override config"
    prompt_lower = raw_message.lower()

    if selected_model == "auto" or not selected_model:
        if any(w in prompt_lower for w in ["write", "code", "html", "script", "function", "css", "json", "class"]):
            model_used = CONFIG["AUTO_CODE_MODEL"]
            routing_reason = f"Routed to Code Engine ({model_used})"
        elif any(w in prompt_lower for w in ["analyze", "explain", "why", "solve", "math", "logic", "reason", "compute"]):
            model_used = CONFIG["AUTO_LOGIC_MODEL"]
            routing_reason = f"Routed to Logic Engine ({model_used})"
        elif any(w in prompt_lower for w in ["describe", "look", "image", "vision", "camera", "picture"]):
            model_used = CONFIG["AUTO_VISION_MODEL"]
            routing_reason = f"Routed to Vision Engine ({model_used})"
        else:
            model_used = CONFIG["AUTO_CONVO_MODEL"]
            routing_reason = f"Routed to Conversational Engine ({model_used})"

    # Select Persona Prompt profile parameters
    persona = CHARACTERS.get(character_id, CHARACTERS["zaram_prime"])
    system_prompt = f"{CONFIG['SYSTEM_PROMPT']}\nPersonality Profile: {persona['personality']}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": raw_message}
    ]

    try:
        ai_raw_response = await ollama.chat(model_used, messages)
    except Exception as e:
        logger.error("Local chat model connection failed: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Ollama connection timed out. Is Ollama running {model_used}?"})

    response_speech = cleaner.clean(ai_raw_response)

    audio_url = None
    if kokoro.ready and response_speech:
        try:
            output_path = await audio_buffer.get_next_path()
            success = await kokoro.synthesize(response_speech, persona["voice_id"], output_path)
            if success:
                audio_url = f"/audio/{output_path.name}"
                await audio_buffer.cleanup()
        except Exception as e:
            logger.error("Vocal synthesis crash: %s", e)

    return {
        "status": "success",
        "text": ai_raw_response,
        "response": ai_raw_response,
        "audio_url": audio_url,
        "model_used": model_used,
        "routing_reason": routing_reason,
        "processing_time": round(time.time() - start_time, 2)
    }

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    path = AUDIO_DIR / filename
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "Audio track not found"})
    return FileResponse(path, media_type="audio/wav")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)