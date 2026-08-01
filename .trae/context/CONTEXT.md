# Zaram - Complete Project Context

**For:** Trae, Cursor, Kilo, Cline, and all AI coding agents  
**Version:** 1.0  
**Last Updated:** 2026-07-28

---

## What is Zaram?

Zaram is a **Local-First AI Productivity Operating System**—not a chatbot, not an AI assistant, not a wrapper. It's a workspace where users think, create, build, and execute work across industries.

**Core Philosophy:** Human ↔ Living Intelligence ↔ Unified Workspace ↔ Execution

---

## Tech Stack

### Frontend
- **Electron** (Desktop app)
- **React 19** (UI framework)
- **TypeScript** (Language)
- **Tailwind CSS v4** (Styling)
- **Framer Motion** (Animations)
- **Zustand** (State management)
- **Vite** (Build tool)

### Backend
- **FastAPI** (Python)
- **Ollama** (Local LLMs)
- **LanceDB** (Vector database)
- **Neo4j/Kuzu** (Graph database)
- **MCP** (Model Context Protocol)

---

## Core Architecture: 8 Engines

1. **Knowledge Engine** - RAG, semantic search, document understanding
2. **Memory Engine** - Persistent episodic/semantic memory
3. **Research Engine** - Deep reasoning, synthesis, citations
4. **Development Engine** - Code editing, debugging, git
5. **Creation Engine** - Image/video generation, design
6. **Automation Engine** - Workflow automation, scripting
7. **Communication Engine** - Voice, chat, transcription
8. **System Engine** - Orchestration, plugins, routing

All engines feed into the **Unified Memory Graph** (single source of truth).

---

## Key Design Principles

### 1. Local-First
- Everything runs locally by default
- Cloud is optional enhancement
- Privacy is non-negotiable
- Works offline

### 2. Unified Memory
- Everything connects: projects, docs, code, conversations, tasks
- Graph database stores relationships
- Vector database for semantic search
- No isolated data silos

### 3. Workspace-Centric
- The workspace is the hero, not the AI
- Living Orb represents AI state (bottom-center)
- Floating panels on infinite canvas
- Context preserved across sessions

### 4. Plugin Architecture
- Core stays generic
- Industry packs extend functionality (Medical, Finance, Robotics)
- Plugins run in isolated sidecars
- Capability-based security

---

## Folder Structure
