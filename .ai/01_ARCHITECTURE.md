# Zaram System Architecture

Version: 1.0

Status: Living Document

Project: Zaram AI Operating System

Owner: Uche Anisiuba

Repository:
https://github.com/Uchayanisiuba/Zaram

Related Documents

- 00_PROJECT_BIBLE.md

---

# Document Purpose

This document defines the software architecture of the Zaram AI Operating System. It establishes the major system components, their responsibilities, communication patterns, and engineering principles. Every implementation within the repository should align with this architecture.

---

# Architectural Philosophy

Zaram is designed as a **modular, local-first AI Operating System**, not a traditional chatbot.

The architecture emphasizes:

- Modular services
- Local AI execution
- Low-latency streaming
- Replaceable AI models
- Clean separation of concerns
- Long-term maintainability
- Scalability

Each subsystem should operate independently while communicating through clearly defined interfaces.

---

# System Overview

```
                  React Frontend
                         │
                         ▼
                FastAPI Backend API
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
 Model Router      Memory Engine     Voice Engine
       │                 │                 │
       └──────────────┬──┴──────────────┬──┘
                      ▼                 ▼
              Knowledge Vault     Plugin System
                      │
                      ▼
                 Ollama Models
                      │
                      ▼
               Unreal Engine 5.6
```

---

# Major Layers

## Presentation Layer

Technology

- React
- TypeScript
- TailwindCSS
- Framer Motion
- Zustand

Responsibilities

- Chat Interface
- Orb
- Voice Controls
- File Upload
- Settings
- Notifications
- Conversation History

The frontend should never contain business logic or model-selection logic.

---

## Backend Layer

Technology

- FastAPI
- Python
- AsyncIO

Responsibilities

- API Gateway
- Session Management
- Authentication
- Streaming
- AI Routing
- Memory
- File Processing
- Plugin Execution

The backend acts as the intelligence coordinator for the entire platform.

---

# Core Services

## Model Router

Responsible for selecting the optimal AI model based on task complexity and intent.

Responsibilities

- Intent classification
- Automatic model selection
- Fallback handling
- Context injection
- Streaming orchestration

See:
`03_MODEL_ROUTER.md`

---

## Memory Engine

Responsible for managing all memory layers.

Includes

- Working Memory
- Conversation Memory
- Project Memory
- Knowledge Vault
- Long-Term Memory

See:
`04_MEMORY_SYSTEM.md`

---

## Voice Engine

Responsible for

- Speech-to-Text
- Text-to-Speech
- Voice Activity Detection
- Streaming Audio
- Barge-In
- Audio Queue Management
- Orb synchronization

See:
`05_VOICE_ENGINE.md`

---

## Knowledge Vault

Stores and indexes user knowledge.

Supported content

- PDF
- DOCX
- PPTX
- TXT
- Markdown
- HTML
- Images
- Source Code
- Repository Documentation

Responsibilities

- Parsing
- Chunking
- Embedding generation
- Semantic search
- Citation tracking

---

## Orb Engine

The Orb is a visual state machine.

States

- Idle
- Listening
- Thinking
- Generating
- Speaking
- Creative
- Working
- Error

Inputs

- Voice Activity Detection
- Audio FFT
- AI State
- User Interaction
- Backend Events

Outputs

- Color
- Glow
- Shape
- Particle Emission
- Motion
- Pulse

The Orb should never become completely static.

---

# AI Model Layer

Current local AI stack

| Purpose | Model |
|----------|-------|
| Conversation | Gemma3 |
| Planning | Qwen3 |
| Coding | Qwen2.5-Coder |
| Vision | Moondream |
| Autocomplete | Llama3.2 |

Future models must integrate through the Model Router without requiring frontend modifications.

---

# Streaming Pipeline

```
User

↓

Frontend

↓

FastAPI

↓

Model Router

↓

Selected AI Model

↓

Sentence Buffer

↓

Voice Engine

↓

Frontend

↓

Orb

↓

Unreal Engine
```

The entire architecture is designed around streaming. The user should never wait for complete responses before receiving feedback.

---

# Unreal Engine Integration

Primary objectives

- MetaHuman support
- Live Link
- Streaming audio
- NeuroSync
- Facial animation
- Future body animation
- Spatial UI

Communication between Zaram and Unreal should remain asynchronous and low-latency.

---

# Folder Structure

```
frontend/

backend/

.ai/

.continue/

docs/

plugins/

knowledge/

memory/

uploads/

logs/
```

Each module should own its internal logic.

Avoid cross-module dependencies wherever possible.

---

# Engineering Principles

Every implementation should follow these principles:

- Single Responsibility Principle
- Separation of Concerns
- Dependency Injection
- Modular Services
- Reusable Components
- Streaming First
- Local First
- Model Agnostic
- Clean Interfaces
- Minimal Coupling
- Maximum Cohesion

---

# Scalability

The architecture must support future expansion, including:

- Additional AI models
- Cloud inference
- Multi-user environments
- Team workspaces
- Mobile applications
- VR and AR interfaces
- Autonomous AI agents
- Third-party plugins
- Distributed inference

No major architectural redesign should be required to support future capabilities.

---

# Definition of Done

A feature is complete only when it:

- Aligns with this architecture
- Passes testing
- Includes error handling
- Supports streaming where applicable
- Integrates cleanly with existing services
- Maintains modularity
- Preserves performance
- Is documented if it introduces new architecture

---

# Closing Statement

The architecture of Zaram is designed to support long-term evolution rather than short-term implementation. Every engineering decision should prioritize maintainability, extensibility, performance, and user experience while remaining faithful to the vision defined in the Project Bible.