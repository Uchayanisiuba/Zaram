# Zaram Changelog

## [Unreleased] — Direction reset

Zaram was repositioned from a "Local-First AI Productivity Operating System" to **the
memory and control layer for people who use more than one AI**. This is a narrowing, not
a rebrand: most of what was previously in scope is now explicitly out of scope until a
single end-to-end loop works.

### Changed

- **Product definition.** Zaram is a layer between the user and whatever models they
  use, not an operating system and not an agent framework.
- **Scope reduced to six items for v1:** ingest a folder into the Spine, chat routed to
  at least two providers, recall across providers with provenance, correct/delete a fact
  and see answers change, a viewable egress log, and per-source privacy policy.
- **Tool protocol fixed to MCP.** No proprietary plugin or shim format.
- **Business model.** The previous $49 one-time licence, marketplace and cloud-credit
  model is withdrawn. Single user on a single machine is free and unlimited forever;
  the paid tier is the second person (shared Spine, permissions, sync).
- **Documentation collapsed.** Roughly 150 accumulated specification, audit and review
  documents were removed. `CLAUDE.md` and `docs/VISION.md` are now the only project
  documents; assistant tool configs were rewritten to match.

### Removed from scope

Agents and agent constellations, code studio / IDE integration, extensions marketplace,
updates feed, voice, document generation, multi-user and additional workspaces. Code for
several of these exists in the tree and is dormant — it is not to be activated.

### Retired vocabulary

"AI operating system", "faculty", "nursery", "aperture", "synapse web". Canonical terms
are now Spine, Recall, Provenance, Routing, Egress log, Orb, Workspace.

---

## [1.0.0-Alpha] — Documentation Freeze & Architecture Lock

Superseded by the direction reset above. Retained for history.

### Added

- 5-layer OS architecture (Kernel, Intelligence, Projection, Embodiment, Platform).
- Dual embodiment system: Living Orb, Avatar, Knowledge Universe modes.
- Knowledge Runtime specification, provider-agnostic.
- Local Model Manager with hardware benchmarking.
- 12 Architecture Decision Records.

### Changed

- Strangler-fig migration: FastAPI `main.py` integrated with the Execution Engine behind
  the `USE_NEW_KERNEL` flag.
- Standardised runtime naming (`Runtime_Models`, `Execution Engine`).
