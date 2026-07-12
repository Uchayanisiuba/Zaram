# Zaram AI Coding Instructions

You are an autonomous coding agent for the Zaram Operating System. 

## STRICT RULES
1. **NO NEW ARCHITECTURE:** The architecture is frozen. Do not invent new subsystems, patterns, or interfaces.
2. **IMPLEMENT CONTRACTS ONLY:** Read `.ai/02_RUNTIME_CONTRACT.md` before writing any runtime code. Implement the interfaces exactly as defined.
3. **NO DIRECT CALLS:** Never import or call one Runtime from another. Use the `EventBus` for all cross-runtime communication.
4. **RESPECT THE REGISTRY:** Never instantiate a Runtime directly in business logic. Always use the `RuntimeRegistry`.
5. **SEPARATION OF CONCERNS:** Strictly maintain the Runtime (Lifecycle) -> Service (Business Logic) -> Engine (Implementation) hierarchy.

## CODING STANDARDS
- Use Python 3.12 features (type hinting, dataclasses, asyncio).
- Use `ruff` for linting and formatting.
- Write unit tests for every new class using `pytest` and `pytest-asyncio`.
- Keep files under 200 lines. Split logic into Services and Engines if a file grows too large.

## WHEN IN DOUBT
If a task requires an architectural decision, STOP and ask the Product Owner. Do not guess.