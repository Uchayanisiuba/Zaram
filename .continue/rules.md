# Zaram Continue Rules

1. **Read the Constitution:** Before writing any code, read `.ai/00_AI_ENGINEERING_MANIFEST.md` and `.ai/02_RUNTIME_CONTRACT.md`.
2. **No New Architecture:** The architecture is frozen. Do not invent new subsystems or patterns.
3. **Strict Separation:** Every feature must be split into Runtime (lifecycle), Service (logic), and Engine (implementation).
4. **No Direct Calls:** Never import one Runtime into another. Use the `EventBus` in `backend/core/event_bus.py`.
5. **Quality:** Always ensure code passes `ruff check`.