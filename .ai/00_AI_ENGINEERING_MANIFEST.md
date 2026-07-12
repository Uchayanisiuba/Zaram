# Zaram AI Engineering Manifest
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Author:** Uche (Founder & Product Owner)

> **This document is the first document every AI collaborator must read before making architectural decisions or generating production code for Zaram.**

---

## Engineering Constitution

This document is the highest-level engineering document in the repository.

If another document, codebase, or AI suggestion conflicts with this Manifest, this Manifest takes precedence.

Major changes to these principles require deliberate review and approval by the Product Owner. No AI is permitted to override the architectural principles defined here.

> AI contributors do not invent architecture. They implement the contracts defined by the architecture documents. When uncertainty exists, they must request clarification rather than introducing new architectural patterns.

> Architecture documents define **stable interfaces**. Implementations may evolve freely provided they remain contract compliant.

---

## The North Star

> Every architectural, engineering, and product decision must move Zaram closer to becoming the world's best local-first personal AI operating system.
>
> If a decision improves a feature but weakens that vision, reject it.
> If a decision increases complexity without increasing long-term capability, reject it.
> If in doubt, optimize for longevity over speed.

---

## Founder Principles

- Build for the next decade, not the next demo.
- Local-first is the default; cloud is a user choice.
- The AI should adapt to the user, never the other way around.
- Every subsystem should be replaceable.
- Simplicity beats cleverness.
- Premium user experience is a feature.
- Preserve working software while evolving the architecture.

---

## 1. What is Zaram?

Zaram is a **Local-First Personal AI Operating System**.

It is not a chatbot. It is not an AI assistant. It is not a coding tool. Those are merely features.

The objective of Zaram is to create an intelligent companion that lives with the user, remembers what matters, reasons across time, grows with experience, and can take multiple forms—from a Living Energy Orb to a MetaHuman or future AR embodiment.

Everything in this repository exists to support that vision.

## 2. The Vision

Five years from now, people should describe Zaram as:
*"The personal AI operating system that lives with you."*

Not "the chatbot." Not "the coding assistant." Not "the Unreal avatar."

One intelligence. Many embodiments. One companion. Built entirely around the user.

## 3. The User Promise

Every feature should make the user feel that:

- Their data belongs to them.
- Their AI understands them better over time.
- They are interacting with one persistent intelligence.
- The technology remains invisible.
- Zaram becomes more valuable the longer it is used.

## 4. Core Philosophy

The user should never need to think about LLMs, APIs, model routing, prompt engineering, embeddings, or vector databases.

The user talks to **one intelligence**. Zaram decides everything else. Technology should disappear into the background, leaving only the feeling of interacting with a living, thinking entity.

## 5. What Zaram Is NOT

- **Zaram is not another chatbot.** It does not just reply; it acts, remembers, and orchestrates.
- **Zaram is not another productivity app.** It is an operating system for intelligence.
- **Zaram is not just an Unreal avatar.** The MetaHuman is an embodiment, not the product itself.
- **Zaram is not tied to any single AI model.** Models are interchangeable tools.

## 6. Design Principles

### Local First
Local computation is the default. Cloud services are optional. Users always own their data. Privacy is a feature—not an afterthought.

### Subsystem Independence Principle
A subsystem must never depend upon another subsystem's implementation. Subsystems communicate only through Contracts, Events, and Interfaces. Never through internal implementation details.

### Evolutionary Architecture
Never rewrite working systems. Introduce new runtimes beside existing implementations. Validate. Switch. Remove legacy afterwards. This follows the **Strangler Fig Pattern**. Always preserve a working application.

### Intelligence Before Interface
Everything begins with Core. The UI is only one embodiment. Changing the body must never require changing the intelligence.

## 7. AI Collaboration Policy

The project uses multiple AI systems with clearly defined responsibilities. No AI is "in charge" of the project.

- **Product Owner (Uche):** Owns product direction, final decisions, and integration testing.
- **Chief Architect:** Defines long-term architecture, runtime design, engineering standards, and technical review. Should rarely generate production code.
- **Lead Implementation Engineer:** Transforms architecture into production-quality implementations, refactoring, and feature delivery.
- **Autonomous Coding Agent:** Executes large-scale implementation tasks and multi-file refactoring.
- **Local Coding Assistant:** Provides autocomplete, explanations, debugging, and small edits.

## 8. Engineering & Coding Standards

- Readable code beats clever code.
- Prefer composition over inheritance. Avoid unnecessary abstractions.
- Never hardcode configuration. Always separate interfaces from implementations.
- Small commits beat massive rewrites.
- Feature flags are mandatory for migrations.
- Major architectural decisions require an Architecture Decision Record (ADR).

### Documentation Philosophy
Documentation should describe **Why** before **How**. Architecture documents are frozen once approved.

## 9. Decision Making

When multiple solutions exist, choose the one that:
1. Reduces coupling.
2. Improves maintainability.
3. Supports future embodiments.
4. Keeps data local.
5. Minimizes technical debt.

**Never optimize for today at the expense of tomorrow.**

## 10. Definition of Done

A feature is complete only when it is:

- ✓ Reliable and testable.
- ✓ Follows the Runtime Contract.
- ✓ Documented and observable.
- ✓ Integrated with Zaram Core.
- ✓ Preserves subsystem independence.
- ✓ Improves the user experience.
- ✓ Supports future embodiments.
- ✓ Can be maintained years from now.

Working code alone is not considered complete.

## 11. The Zaram Test

Before implementing any feature, ask:

Does this make Zaram feel...
- More intelligent?
- More personal?
- More trustworthy?
- More alive?

If not, reconsider the design.

## 12. The Golden Rule

> The user should never manage artificial intelligence.
> They should simply experience one intelligent companion.

---
*End of Manifest.*