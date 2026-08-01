# Core Specifications

## FrameState Contract
The universal contract driving all embodiments.
- **Visual:** presence, energy, focus, activity
- **Audio:** voiceLevel, microphoneLevel
- **Emotion:** calmness, confidence, curiosity, warmth, empathy, playfulness
- **System:** state, cognitiveLoad, adaptiveQuality, visualIdentity

## Knowledge Runtime Architecture
Provider-agnostic search and retrieval.
Executive Runtime → `knowledge.search` → Knowledge Runtime → Provider Manager → Providers (Memory, Projects, Local Docs, RSS, Wikipedia, DuckDuckGo, GitHub).
*The Executive Runtime never knows provider implementation.*

## Local Model Manager
On first launch, Zaram benchmarks CPU, GPU, RAM, VRAM, Disk, and OS. It recommends and installs Ollama, LM Studio, or llama.cpp models directly from within Zaram. No browser required.