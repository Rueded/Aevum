# DECISIONS.md — Architecture Decision Records (ADR)

This document records the foundational architectural decisions made for Project Aevum.

---

## ADR-001: Tauri 2 for Desktop Shell

* **Status**: Accepted
* **Context**: The desktop client requires cross-platform execution, low memory overhead, security isolation, and native operating system integration (tray, notifications, window management). Electron carries significant memory and bundle size overhead.
* **Decision**: Use Tauri 2 as the desktop shell framework.
* **Consequences**:
  * Highly efficient memory footprint compared to Chromium-bundled alternatives.
  * Native OS integration via Rust bindings.
  * Enhanced security model with fine-grained capability permissions.
  * Development requires Rust toolchain on developer machines for Tauri builds.

---

## ADR-002: React + TypeScript for Desktop UI

* **Status**: Accepted
* **Context**: The presentation layer requires a robust, reactive, and type-safe ecosystem with mature support for rich interactive components, state management, audio visualization, and future canvas/WebGL integrations (Live2D).
* **Decision**: Adopt React with TypeScript for the desktop user interface.
* **Consequences**:
  * Type-safety across API contracts and UI components.
  * Access to the vast React ecosystem and component libraries.
  * Clean component lifecycle management for streaming text, voice playback, and visual avatars.

---

## ADR-003: Python + FastAPI for Core Backend

* **Status**: Accepted
* **Context**: The core character engine coordinates state machines, memory indexing, asynchronous scheduling, life simulation, and LLM integrations. Python offers the richest ecosystem for AI/LLM tooling, data processing, and rapid prototyping.
* **Decision**: Use Python (3.11+) with FastAPI as the backend framework (`Aevum Core`).
* **Consequences**:
  * High-performance asynchronous endpoint handling with `asyncio`.
  * Automatic OpenAPI documentation and strong data validation via Pydantic.
  * Seamless integration with AI/ML libraries, tokenizers, and future local model providers.
  * Python environment managed via modern tooling (`uv`).

---

## ADR-004: SQLite for Initial Persistence

* **Status**: Accepted
* **Context**: Project Aevum is designed to run locally on the user's personal hardware without requiring the user to deploy, maintain, or configure complex external database servers (like PostgreSQL or MySQL).
* **Decision**: Use SQLite as the initial persistence database engine.
* **Consequences**:
  * Zero configuration: the database is a self-contained local file.
  * High reliability with ACID transaction guarantees.
  * Easy backup, portability, and reset for users.
  * SQLite WAL (Write-Ahead Logging) mode provides solid concurrency for local multi-threaded/async access.

---

## ADR-005: SQLAlchemy for Database Access

* **Status**: Accepted
* **Context**: While SQLite is the initial database, the system may eventually support alternative database backends (e.g., PostgreSQL for multi-device sync or remote servers). Hand-crafting raw SQL strings increases refactoring friction and syntax coupling.
* **Decision**: Use SQLAlchemy (v2.0+ async) as the Object Relational Mapper and database abstraction layer.
* **Consequences**:
  * Clean domain model definition with declarative mappings and typing.
  * Async database session management compatible with FastAPI.
  * Portable query construction decoupling domain logic from SQLite-specific dialect nuances.

---

## ADR-006: Gemini as Initial LLM Provider with Provider Abstraction

* **Status**: Accepted
* **Context**: The project needs high-quality language synthesis, broad context window capabilities, and multimodal potential. However, the system must never be vendor-locked to a single provider (e.g., Anthropic, OpenAI, or local Ollama/vLLM models must be easily swappable).
* **Decision**: Implement Google Gemini API as the initial LLM provider, wrapped strictly behind a modular `LLMProvider` abstraction interface.
* **Consequences**:
  * Immediate access to powerful, low-latency reasoning and conversational generation.
  * No core character logic or state machine code may directly import or call the Gemini SDK.
  * Adding another provider in the future requires only implementing the `LLMProvider` protocol without touching domain logic.

---

## ADR-007: Application State Owns Reality

* **Status**: Accepted
* **Context**: Traditional AI chatbots let the LLM generate both language and state on the fly. This results in hallucinations, sudden personality shifts, inconsistent memories, and an artificial lack of continuity.
* **Decision**: The deterministic application state machine in Aevum Core is the ultimate source of truth. The LLM generates natural language grounded in this state, but does not alter reality directly.
* **Consequences**:
  * The character cannot simply "forget" a major fact or change emotional mode without causal triggers in the state engine.
  * State transitions (mood, relationship level, schedule, knowledge) are managed deterministically.
  * LLM prompt injection attacks or hallucinations cannot corrupt character state.

---

## ADR-008: Desktop Client is the Interface/Body, Not the Character Itself

* **Status**: Accepted
* **Context**: The character should eventually be accessible from multiple devices (desktop, Android, mobile web) without fragmenting her identity, memory, or emotional state.
* **Decision**: The Desktop Client is treated strictly as an interface and physical manifestation ("body"), while character identity, memory, and state reside entirely in Aevum Core.
* **Consequences**:
  * The desktop client contains zero proprietary character state logic.
  * Shutting down the client does not destroy or desync the character.
  * Future clients (e.g., Android app) can connect to the same Aevum Core without duplicate backend development.

---

## ADR-009: Event-Driven Life Simulation

* **Status**: Accepted
* **Context**: A static companion that only responds when prompted feels like an inanimate tool. A realistic digital life must experience the passage of time, execute routines, progress personal interests, and undergo spontaneous experiences even when the user is inactive.
* **Decision**: Implement an asynchronous event-driven simulation loop within Aevum Core that drives scheduled routines, stochastic events, and autonomous reflections.
* **Consequences**:
  * The character can share stories of what she did while the user was away.
  * Proactive communication can be scheduled naturally.
  * Must include strict cooldowns, rate limits, and quiet-hour safeguards to avoid user disruption.

---

## ADR-010: Incremental AI-Assisted Development

* **Status**: Accepted
* **Context**: Large-scale autonomous software generation often suffers from context drift, bloated changes, premature optimizations, and breaking architectural patterns when AI agents take on overly large scopes.
* **Decision**: Adopt a disciplined, documentation-first, phase-gated approach to AI-assisted development governed by strict rules (`AGENTS.md`).
* **Consequences**:
  * Changes are kept small, atomic, and thoroughly tested.
  * Strict phase boundaries prevent premature implementation of forward-phase components.
  * Every AI coding agent operates within bounded guidelines and architectural consensus.
