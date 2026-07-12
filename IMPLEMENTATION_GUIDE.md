# Zaram Implementation Guide

## 1. Definition of Done
A feature/runtime is complete ONLY when:
- [ ] It implements the `Runtime` Protocol from `backend/core/contracts.py`.
- [ ] It is separated into Runtime, Service, and Engine layers.
- [ ] It uses the Event Bus for all external communication.
- [ ] It has 80%+ unit test coverage in `backend/tests/`.
- [ ] It passes `ruff check` and `mypy` with zero errors.

## 2. Git & Branch Strategy
- `main`: Production-ready code.
- `dev`: Integration branch for new runtimes.
- `feature/<runtime-name>`: e.g., `feature/runtime-speech`.

## 3. Commit Message Convention
Use Conventional Commits:
- `feat(runtime): add speech runtime lifecycle`
- `fix(eventbus): resolve async subscriber blocking`
- `refactor(core): simplify registry capability mapping`

## 4. Coding Conventions
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants.
- **Typing:** Strict type hints are mandatory. No `Any` unless absolutely necessary.
- **Async:** Use `asyncio` for all I/O bound operations (Event Bus, LLM calls). Use threads only for CPU-bound tasks (Audio generation).
- **Logging:** Use Python's standard `logging` module. Never use `print()` in production code.