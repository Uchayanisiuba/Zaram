# Zaram OS — Sprint Alpha.1 Acceptance Test

## Prerequisites

- Node.js 18+ installed
- Python 3.10+ installed
- Ollama installed and running (`ollama serve`)
- At least one model pulled (`ollama pull gemma3:latest`)

## Test Steps

### 1. Clean Clone

```bash
git clone <repo-url> zaram-test
cd zaram-test
```

### 2. Install Dependencies

```bash
npm install
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Build Frontend

```bash
cd frontend
npm run build
cd ..
```

### 4. Build Desktop Runtime

```bash
cd desktop
npm run build
cd ..
```

### 5. Launch Application

```bash
npm run dev
```

Or directly:

```bash
cd desktop
npm run dev
```

### 6. Verify Launch

- [ ] Splash screen appears
- [ ] Main window opens within 30 seconds
- [ ] "Conversation" is the active view (not Orchestration)
- [ ] Sidebar shows "Conversation" as primary nav item
- [ ] "Developer" section is collapsed by default
- [ ] Footer shows "Desktop Runtime" (not "Browser Mode")
- [ ] No red error banners

### 7. Verify Backend Connection

- [ ] Top bar shows `BACKEND: ONLINE`
- [ ] If backend is offline, red banner appears with "Backend unavailable" and "Retry" button

### 8. Verify Workspace Detection

- [ ] Open a workspace folder (or the app auto-detects the project root)
- [ ] Runtime Inspector → Workspace Runtime shows:
  - [ ] Workspace name (folder name, not "root")
  - [ ] Language detected
  - [ ] Framework detected
  - [ ] Project count > 0
  - [ ] Confidence > 0%
- [ ] No "root" or "0 projects" or "No modules"

### 9. Verify Conversation Pipeline

Send the message: "What project is this?"

- [ ] User message appears in chat
- [ ] Executive state pill shows "Thinking..." → "Generating Response..."
- [ ] Execution timeline shows:
  - [ ] Goal step
  - [ ] Capability steps (e.g., "Read Workspace Snapshot")
  - [ ] Response Generated step
- [ ] Assistant response includes:
  - [ ] Workspace name
  - [ ] Framework
  - [ ] Language
  - [ ] Project count
  - [ ] Confidence percentage
  - [ ] Execution time
- [ ] No "Executive Runtime did not return a plan" error
- [ ] No placeholder or fake responses
- [ ] No raw exception text

### 10. Verify Orb Animation

- [ ] Navigate to Orchestration page
- [ ] Orb is visible and rendering
- [ ] Orb is NOT stuck on idle state
- [ ] Orb color changes based on executive state
- [ ] Frame Rate shows a value (e.g., 30 Hz)

### 11. Verify Runtime Inspector

- [ ] Navigate to Runtime Inspector (Developer → Runtime Inspector)
- [ ] All runtimes listed with status indicators
- [ ] Presence Runtime shows "healthy" or "running"
- [ ] Executive Runtime shows "busy" during conversation
- [ ] Execution Runtime shows "ready"
- [ ] Capability Runtime shows "ready"
- [ ] Workspace Runtime shows workspace details
- [ ] VS Code Runtime shows connection status

### 12. Verify Audit Terminal

- [ ] Navigate to Audit Terminal (Developer → Audit Terminal)
- [ ] Execution events appear during conversation
- [ ] Events show execution lifecycle (queued → running → completed)

### 13. Verify Capabilities

- [ ] Navigate to Capabilities (Developer → Capabilities)
- [ ] Filesystem capabilities listed (read, write, search, etc.)
- [ ] VS Code capabilities listed (editor, diagnostics, git)

### 14. Verify Error Handling

- [ ] Stop Ollama (`ollama stop`)
- [ ] Send a message in conversation
- [ ] Error message appears in chat (not a crash)
- [ ] Restart Ollama
- [ ] Retry works

### 15. Verify Backend Restart

- [ ] Stop the Python backend
- [ ] Backend status changes to OFFLINE
- [ ] Red banner appears: "Backend unavailable — Connection lost"
- [ ] Restart the Python backend
- [ ] Backend status changes to ONLINE
- [ ] Banner disappears

### 16. Verify No Console Exceptions

- [ ] Open DevTools (if in dev mode)
- [ ] No uncaught promise rejections
- [ ] No TypeError or ReferenceError in console
- [ ] No 404s for missing IPC channels

## Expected Results

All checkboxes should pass. If any fail, the root cause must be identified and fixed before the sprint is complete.

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Backend: OFFLINE | Python not running or port 8000 blocked | Start Python backend |
| "Executive Runtime did not return a plan" | Desktop runtime not loaded | Check electron main logs |
| Workspace: "root" | Workspace root not set | Check bootstrap logs |
| Orb: idle/static | Presence frames not pushing | Check IPC channels |
| Chat: no response | Ollama not running | Start Ollama and pull model |
