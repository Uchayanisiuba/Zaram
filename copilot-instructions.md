# Copilot Instructions for Zaram

**Version:** Prototype v0.1  
**Status:** Active Development  
**Project Owner:** Uche Anisiuba  
**Company:** Quadron Studios

---

## 1. PROJECT OVERVIEW

**Project Name:** Zaram  
**Purpose:** An AI Operating System presented through a photorealistic digital human. Not a chatbot—an AI companion that becomes smarter about the user's work over time through memory, knowledge, projects, and personal context.

**Core Components:**
- The MetaHuman (face of the system)
- The AI Brain (reasoning engine)
- The Memory System (long-term value)

**Target Audience:** Knowledge workers, executives, and professionals who need an AI companion throughout their workday.

**Core Value Proposition:** Users get a knowledgeable teammate that understands their conversations, uploaded documents, preferences, projects, and deadlines—feeling like a trusted colleague rather than a chatbot.

---

## 2. TECHNOLOGY STACK

### Frontend
- **React** (modern, functional components)
- **Vite** (build tool)
- **Tailwind CSS** (utility-first styling)
- **JavaScript** (currently; transitioning to TypeScript in the future)

### Backend
- **Python** (simple, explicit code)
- **FastAPI** (REST API framework)

### Data & AI
- **Local AI Models:** Qwen, Gemma, Moondream, Llama (all interchangeable)
- **Database:** SQLite (local persistence)
- **Vector DB:** ChromaDB (embeddings and semantic search)
- **No Cloud APIs:** Core functionality runs entirely locally

### Voice Pipeline
Speech → Speech Recognition → LLM → Text-to-Speech → Unreal Engine → MetaHuman Facial Animation

---

## 3. ARCHITECTURE & DESIGN PATTERNS

**Architecture Style:** Modular Service Architecture
- Each service is independent and exposes its own API
- Services should NOT tightly depend on each other
- Services communicate via REST APIs

**Core Services:**
1. **Conversation Service** — Chat sessions, message history, session summaries
2. **Memory Service** — User preferences, facts, learned rules, relationships, project memories (user-editable, exportable)
3. **Knowledge Service** — File upload, parsing, chunking, embeddings, semantic search (RAG-based)
4. **Calendar Service** — Reminders, meetings, deadlines, expiry dates, recurring events
5. **Project Service** — Isolated context with conversations, documents, images, videos, tasks, reminders, knowledge, timeline
6. **Speech Service** — Voice I/O pipeline integration
7. **Tool Service** — Tool execution and orchestration

**Design Principle:** Services should remain modular and reusable. Cross-service references are allowed (e.g., Calendar references documents, Projects reference memories, Reminders reference projects), but no duplicate information.

---

## 4. DIRECTORY STRUCTURE

```
Zaram/
├── .github/
│   └── copilot-instructions.md    # Copilot context (this file)
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Main application component
│   │   ├── components/             # Reusable React components
│   │   ├── assets/                 # Images, icons, static files
│   │   ├── index.css               # Global styles
│   │   └── main.jsx                # Entry point
│   ├── public/                      # Static assets
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── eslint.config.js
├── backend/
│   ├── main.py                     # FastAPI entry point
│   ├── requirements.txt             # Python dependencies
│   ├── config.json                 # Configuration
│   ├── brains.json                 # AI model configuration
│   ├── character.json              # MetaHuman character data
│   ├── audio_output/               # Generated speech files
│   ├── image_output/               # Generated images
│   └── temp/                       # Temporary files
├── services/                        # Future service modules
├── parsers/                         # Document parsing logic
├── processors/                      # Data processing logic
├── uploads/                         # User uploaded files
└── README.md
```

---

## 5. CODING STANDARDS & CONVENTIONS

### General Principles
- **Prefer readable code over clever code.**
- **Avoid unnecessary complexity.**
- **Use modular architecture.**
- **Every service should expose clean APIs.**
- **Document public methods.**
- **Avoid large monolithic files.**
- **Keep frontend components reusable.**
- **Keep backend services independent.**

### React / JavaScript / Frontend
- Prefer **functional components** with React Hooks
- Use **named exports** for components
- Use **PascalCase** for component files and names
- Use **camelCase** for functions, variables, and props
- Keep components focused and reusable
- Avoid inline styles; use **Tailwind CSS classes exclusively**
- Do NOT use `any` in TypeScript (future)—use `unknown` and narrow types

### Python / FastAPI / Backend
- Write **simple, explicit code**
- Follow **PEP 8** naming conventions
- Use **snake_case** for functions and variables
- Use **PascalCase** for classes
- Always include **type hints** in function signatures
- Document complex logic with comments
- Use try/catch blocks for error handling; never swallow errors

### Naming Conventions
- **Files/Folders:** `kebab-case` for folders in frontend, `snake_case` in backend
- **React Components:** `PascalCase` (e.g., `ChatInterface.jsx`)
- **Utilities/Functions:** `camelCase` in JS, `snake_case` in Python
- **Database/Models:** `PascalCase` for model names, `snake_case` for fields

### Comments & Documentation
- Do NOT write obvious comments (e.g., `// increment i`)
- Write JSDoc for public functions and complex logic
- Include `@param`, `@returns` tags where applicable
- In Python, use docstrings for public functions

---

## 6. DATA & DATABASE RULES

- **Primary Keys:** Use appropriate ID types for each service
- **Timestamps:** All models should include `createdAt` and `updatedAt` timestamps
- **Soft Deletes:** TBD (to be specified per service)
- **Queries:** Use ORM/SQLAlchemy when possible; avoid raw SQL
- **Schema Changes:** Track migrations in version control
- **User Data:** Always allow users to view, edit, export, and delete their data (especially memories)

---

## 7. TESTING STRATEGY

- **Frontend Testing:** React components should be testable and modular
- **Backend Testing:** FastAPI routes should have clear input/output contracts
- **Integration Testing:** Services should expose APIs that can be tested independently
- **Specific Framework:** TBD (to be defined in future sprints)

---

## 8. STRICT "DO NOT" LIST (ANTI-PATTERNS)

**AI must NEVER:**
1. Hardcode API keys, model paths, or configuration values
2. Create tightly coupled services—maintain independence
3. Duplicate logic across services or components
4. Invent new dependencies without existing project precedent
5. Break existing behavior unless explicitly required
6. Mix concerns within a single service
7. Use cloud APIs for core functionality (must use local models)
8. Create massive "God components" or monolithic files
9. Mutate data structures directly—maintain immutability in React
10. Use `console.log` in production code—log appropriately to files/services

---

## 9. ENVIRONMENT VARIABLES

*To be expanded as services develop. Currently:*

- Model paths and selections (Qwen, Gemma, Moondream, Llama)
- SQLite database path
- ChromaDB path
- Voice model selection
- Voice output device selection
- TBD: Additional vars as new services are added

---

## 10. CURRENT DEVELOPMENT STATUS

### Completed ✓
- Modern React interface
- Sidebar navigation
- Chat interface
- Voice playback
- Model selection
- Voice selection
- FastAPI backend
- Local model integration
- File attachment interface

### In Progress 🔄
- Modular React architecture
- Memory Service
- Knowledge Vault
- SQLite persistence
- ChromaDB integration

### Not Started ⏳
- Calendar Service
- Timeline
- Project Workspaces
- Automation Engine
- Desktop integration
- Unreal Engine integration (MetaHuman)

---

## 11. ROADMAP

**Phase 1:** Stable chat, voice, memory, knowledge vault  
**Phase 2:** Projects, timeline, search  
**Phase 3:** Calendar, reminders, smart document associations  
**Phase 4:** Desktop automation, tool execution, workflow assistance  
**Phase 5:** AI personalities, advanced body animation, multi-agent orchestration

---

## 12. CORE ENGINEERING PRINCIPLES

1. **Always build reusable systems, not one-off features.**
2. **Avoid duplicate logic.** If two services share logic, create a shared utility.
3. **Everything should plug into existing services.** Don't create silos.
4. **Cross-service references are encouraged:**
   - Calendar references documents
   - Projects reference memories
   - Reminders reference projects
   - Knowledge references uploaded files
5. **Never duplicate information unnecessarily.**
6. **Services remain independent.** Use APIs to communicate.
7. **User control is paramount.** Users must be able to view, edit, export, and delete their data.

---

## 13. LONG-TERM VISION

Zaram will evolve into a complete **AI Operating System** that combines:
- Conversational AI
- Long-term memory system
- Personal knowledge vault
- Project management
- Calendar and reminders
- Desktop automation
- Natural voice conversation
- Photorealistic digital human interaction

The AI should become more valuable over time by learning about the user's work and personal preferences through user-controlled memory and uploaded knowledge. The ultimate goal is to create an AI companion that users rely on daily because it understands their projects, remembers important information, and helps them complete meaningful work.

---

## 💡 Pro Tips for Copilot

1. **Keep this file updated.** Review Section 10 (Current Development Status) weekly to ensure Copilot has the latest context.
2. **Be specific in requests.** Tell Copilot which service you're working on (e.g., "In the Memory Service, implement...").
3. **Reference existing patterns.** When adding features, ask Copilot to match the existing code style in that service.
4. **Preserve modularity.** When working across services, ensure they remain independent.
5. **Use `@workspace` in Copilot Chat** to force context inclusion from this file.
