# Zaram AI Model Router

Version: 1.0

Status: Living Document

Project: Zaram AI Operating System

Owner: Uche Anisiuba

Repository:
https://github.com/Uchayanisiuba/Zaram

Related Documents

- 00_PROJECT_BIBLE.md
- 01_ARCHITECTURE.md
- 04_MEMORY_SYSTEM.md
- 05_VOICE_ENGINE.md

---

# Document Purpose

The Model Router is the intelligence orchestration layer of the Zaram AI Operating System.

Its responsibility is to automatically determine which AI model or combination of AI models should execute every task.

Users should never manually select AI models.

The routing process should be intelligent, adaptive, transparent, and invisible.

---

# Design Philosophy

Every AI model has strengths and weaknesses.

Instead of forcing one model to perform every task, Zaram treats every model as a specialist.

The router assigns work to the model best suited for the task while balancing:

- Speed
- Accuracy
- GPU usage
- Context length
- Response quality
- Current system load

---

# Core Principles

The router must always:

- Prefer the fastest capable model
- Minimize GPU memory usage
- Reduce latency
- Support streaming responses
- Preserve conversation context
- Scale to future AI models
- Support local-first execution

The frontend must never know which model is currently active.

---

# Current AI Stack

| Purpose | Model |
|----------|-------|
| Conversation | Gemma3 |
| Planning | Qwen3 |
| Coding | Qwen2.5-Coder |
| Vision | Moondream |
| Autocomplete | Llama3.2 |

The router owns all model selection.

---

# Request Lifecycle

```
User Request
      │
      ▼
Intent Detection
      │
      ▼
Task Classification
      │
      ▼
Complexity Analysis
      │
      ▼
Memory Retrieval
      │
      ▼
Model Selection
      │
      ▼
Inference
      │
      ▼
Streaming Response
      │
      ▼
Voice Engine
      │
      ▼
Frontend
      │
      ▼
Orb
```

---

# Intent Classification

Every request is classified before inference.

Examples include:

- Conversation
- Coding
- Planning
- Vision
- Research
- Translation
- Document Analysis
- Summarization
- Image Understanding
- File Processing
- Tool Calling
- Knowledge Retrieval

Mixed requests may invoke multiple models.

---

# Conversation Tasks

Examples

"Hello"

"Explain this"

"What should I cook?"

↓

Model

Gemma3

Reason

Lowest latency

Natural dialogue

Small memory footprint

---

# Planning Tasks

Examples

"Design an architecture"

"Compare these approaches"

"Create a roadmap"

↓

Model

Qwen3

Reason

Better reasoning

Long-form thinking

Decision support

---

# Coding Tasks

Examples

"Refactor this component"

"Write a FastAPI endpoint"

"Generate React code"

↓

Model

Qwen2.5-Coder

Reason

Repository understanding

Code generation

Debugging

Documentation updates

---

# Vision Tasks

Examples

"Describe this screenshot"

"What error is shown?"

"Read this diagram"

↓

Model

Moondream

---

# Mixed Task Routing

Some requests require multiple models.

Example

"Analyse this UI screenshot and rewrite the React component."

Pipeline

Moondream

↓

Qwen2.5-Coder

The router automatically chains models without user intervention.

---

# Confidence Scoring

Each routing decision receives a confidence score.

High confidence

Proceed immediately.

Medium confidence

Retrieve additional context.

Low confidence

Escalate to a stronger reasoning model.

The user should never notice these transitions.

---

# Automatic Escalation

The router begins with the smallest capable model.

Example

Gemma3

↓

Qwen3

↓

Qwen2.5-Coder

Escalation should occur only when necessary to preserve responsiveness.

---

# Context Injection

Before inference the router gathers:

- Working Memory
- Conversation Memory
- Project Memory
- Knowledge Vault
- User Preferences
- Recent Files
- Active Task

Only relevant context should be injected.

Avoid unnecessary token usage.

---

# Streaming Strategy

Responses should stream immediately.

Pipeline

```
LLM

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

Never wait for the complete response before beginning output.

---

# GPU Resource Management

The router should minimise unnecessary model loading.

Guidelines

- Reuse loaded models where possible.
- Avoid loading multiple large models simultaneously unless required.
- Release inactive models after configurable idle periods.
- Prioritize responsiveness over maximum parallelism on limited hardware.

Target Hardware

- RTX 3060 12 GB VRAM
- 32 GB System RAM

---

# Failure Handling

If a model becomes unavailable:

1. Retry once.
2. Switch to fallback.
3. Notify the user only if the request cannot be completed.

Fallback Chain

Conversation

Gemma3 → Qwen3

Planning

Qwen3 → Gemma3

Coding

Qwen2.5-Coder → Qwen3

Vision

Moondream → Graceful error with explanation

The application should never expose raw backend exceptions.

---

# Future Expansion

The router must support:

- Additional Ollama models
- Cloud inference providers
- OpenAI
- Anthropic
- Google Gemini
- DeepSeek
- Mistral
- Enterprise-hosted models
- Fine-tuned domain-specific models

Adding a new model should require only backend configuration.

---

# Logging

The router should log:

- Selected model
- Task classification
- Response latency
- Token usage
- Fallback events
- Errors

Sensitive prompts and personal information should never be logged unless explicitly enabled.

---

# Performance Goals

Conversation routing

<100 ms

Model selection

<50 ms

Streaming begins

As soon as the first complete sentence is available.

The user should perceive the system as continuously responsive.

---

# Engineering Rules

- Model routing belongs exclusively to the backend.
- Frontend components must remain model-agnostic.
- Every routing decision should be deterministic where possible.
- New models must integrate without requiring frontend changes.
- Routing logic should remain modular and testable.

---

# Definition of Success

The Model Router is successful when users never think about AI models.

Instead, they experience an assistant that consistently delivers the right balance of speed, intelligence, and capability for every task while making efficient use of local hardware.

The routing system should remain flexible enough to evolve as new AI models become available without requiring architectural redesign.