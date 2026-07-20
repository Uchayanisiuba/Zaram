# Architecture Principles
**Version:** 1.0 | **Status:** Frozen

## 1. Subsystem Independence Principle
A subsystem must never depend upon another subsystem's implementation. Subsystems communicate only through Contracts, Events, and Interfaces.

## 2. Evolutionary Architecture (Strangler Fig)
Never rewrite working systems. Introduce new runtimes beside existing implementations. Validate. Switch. Remove legacy afterwards.

## 3. Intelligence Before Interface
Everything begins with Core. The UI is only one embodiment. Changing the body (Orb to MetaHuman) must never require changing the intelligence.

## 4. Renderer Independence
The application never communicates directly with renderers. Everything passes through the Presence Runtime. The renderer changes; the application does not.

## 5. Local-First, Cloud-Optional
Local computation is the default. Cloud services are optional. Users always own their data.