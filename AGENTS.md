# AGENTS.md — Development Rules for AI Coding Agents

> **Audience**: AI coding assistants (including Antigravity, Claude, Cursor, Copilot, etc.) and human developers contributing to Project Aevum.

Welcome to **Project Aevum**. Before proposing or executing any modifications to this repository, read and adhere strictly to the rules, architecture guidelines, and operational standards documented below.

---

## 1. Golden Rules for AI Agents

All AI agents working within this repository must strictly follow these 20 mandatory rules:

1. **Read `AGENTS.md` before modifying the repository**: Review this document at the start of every session to align with the core philosophy and operational constraints.
2. **Read relevant architecture and documentation before implementing features**: Review `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`, and any domain-specific guides in `docs/` before touching code in that domain.
3. **Do not rewrite architecture without explicit approval**: Never unilaterally replace architectural foundations, data stores, design patterns, or major components.
4. **Keep changes small and focused**: Plan and implement incremental, atomic changes rather than sweeping refactors or oversized pull requests.
5. **Do not introduce unnecessary dependencies**: Strive for minimal dependency bloat. Every external package must have clear justification and be agreed upon in architectural discussions.
6. **Do not create huge monolithic files**: Maintain strict modularity. Split logic across cohesive, single-responsibility files and modules.
7. **Write testable code**: Design all components with clear interfaces, dependency injection, and isolation so they can be unit-tested without external network or LLM dependencies.
8. **Every meaningful feature must have appropriate tests**: Never consider a feature complete without accompanying automated tests in `tests/`.
9. **Do not mix unrelated changes into one task**: Separate refactorings, bug fixes, formatting changes, and new features into distinct steps.
10. **Do not expose secrets or API keys in source control**: Never hardcode API keys, credentials, or private configuration. Use `.env.example` templates and secure environment variable loading.
11. **The application owns persistent character state**: The deterministic application state machine in Aevum Core is the ultimate source of truth.
12. **The LLM generates language but does not define reality**: The LLM is an expressive engine. It never mutates character state directly through prompt output without validation and application state transitions.
13. **Memory must be separated from raw conversation history**: Raw chat logs are not long-term memory. Memory requires distillation, episodic encoding, semantic indexing, and confidence scoring.
14. **Low-confidence memories must not be presented as certain facts**: If the character's memory retrieval confidence is low or degraded, the character must reflect uncertainty, hesitation, or imperfect recall.
15. **Emotional state should have causes and state transitions**: Emotions are not random numbers or arbitrary LLM declarations. They must follow state transition models triggered by events, interactions, and internal drives.
16. **Relationship state must be multidimensional**: Relationships are not a single 0–100 "affinity" number. They track multi-axis dynamics (e.g., trust, familiarity, respect, boundary respect, shared history).
17. **Autonomous behavior must respect permissions, rate limits, cooldowns, and privacy**: The companion must not spam notifications, intrude during quiet hours, or act autonomously outside user-configured boundaries.
18. **Never silently access private files, microphone, camera, screen, browser sessions, accounts, or credentials**: Explicit, transparent user consent and clear visual indicators are mandatory before accessing any local system capability.
19. **Desktop UI must not become the source of truth for character state**: The Tauri / React frontend is an interface and visual representation ("the body"). The core state machine lives exclusively in the backend ("the mind").
20. **Do not prematurely implement future phases**: Strictly respect the boundaries of the current development phase as outlined in `ROADMAP.md`. Do not build forward-phase features (e.g., voice, Live2D, Android sync) before their time.

---

## 2. Core Architecture Principles

### 2.1 Reality vs. Language
```
┌──────────────────────────────────────────────────────────┐
│                   Aevum Core (Reality)                   │
│  - Mood: Contemplative, slightly tired                  │
│  - Schedule: Reading a book (14:00 - 15:30)              │
│  - Relationship: Acquaintance (Trust: 18, Familiarity: 25)│
│  - Memory: User mentioned liking tea yesterday (Conf: 0.9)│
└────────────────────────────┬─────────────────────────────┘
                             │ State context injection
                             ▼
┌──────────────────────────────────────────────────────────┐
│             LLM Provider (Language Generation)            │
│  Generates realistic, in-character dialogue aligned with  │
│  ground-truth reality without altering state arbitrarily. │
└──────────────────────────────────────────────────────────┘
```

* **No Hallucinated State**: If the user asks "Do you remember my dog's name?", the memory system checks database records first. The LLM receives the fact or a flag indicating "unknown/uncertain" and renders dialogue accordingly.
* **Deterministic Event Handling**: Routine ticks, emotional decays, and scheduled life events are managed by background loops and event handlers in Python/FastAPI, not prompted into existence.

### 2.2 Frontend / Backend Separation
* The frontend (`apps/desktop`) communicates with the backend (`backend/`) via typed REST endpoints and WebSockets.
* The frontend must never maintain canonical character state in React state, LocalStorage, or IndexedDB. It reflects state received from Aevum Core.

---

## 3. Workflow Expectations for AI Agents

When tasked with a feature or bug fix:
1. **Analyze Requirements**: Understand how the request fits into the current phase of `ROADMAP.md`.
2. **Inspect Existing Artifacts**: Review relevant files in `docs/` and `backend/` or `apps/`.
3. **Plan Small Steps**: Break complex features into bite-sized modifications.
4. **Mock External Services in Tests**: All tests against LLM providers or OS-level desktop APIs must use mock interfaces or test fixtures. No live LLM calls during automated unit test runs.
5. **Verify Clean Linting & Formatting**: Ensure code adheres to project formatting standards (e.g., `ruff` for Python, `prettier`/`eslint` for TypeScript).
6. **Preserve Documentation Integrity**: Update documentation when code structure changes, and preserve existing comments.
