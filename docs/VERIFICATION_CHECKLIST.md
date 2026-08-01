# Documentation Verification Checklist

## 1. Structural Integrity
- [ ] `.ai/` folder contains only frozen constitutional documents.
- [ ] `docs/` folder contains living implementation docs and ADRs.
- [ ] No duplicate runtime names exist across documents.
- [ ] No duplicate "06_" numbering exists in `.ai/`.

## 2. Architectural Alignment
- [ ] 5-Layer OS diagram is present and accurate.
- [ ] Renderer Independence is explicitly stated in all rendering docs.
- [ ] Strangler Fig migration is documented in ADR-001.
- [ ] Business Model ($49, Marketplace, Cloud Credits) is in `00_OVERVIEW.md`.

## 3. Implementation Sync
- [ ] Documented Runtimes match actual Python code in `backend/runtimes/`.
- [ ] Future work (Knowledge Universe, MetaHuman) is clearly marked as "Planned".
- [ ] No fictional features are documented as "Implemented".

## 4. AI Guardrails
- [ ] `.github/copilot-instructions.md` enforces the frozen architecture.
- [ ] `.kilocode/instructions.md` points to the correct `.ai/` contracts.
- [ ] `CLAUDE.md` and `QWEN.md` define strict boundaries.