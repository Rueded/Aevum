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

---

## ADR-011: Governed Reality Pipeline (Phase 7D) — Freeze Record

* **Status**: Accepted & Frozen (2026-09-23)
* **Context**: The 7B.3-era `RealityBeliefEngine` performed evidence processing, candidate formation, and canonical state mutation in a single monolithic, unauditable method. This prevented clean boundary enforcement between observation, competition, choice, and promotion.
* **Decision**: Replace `RealityBeliefEngine` with a layered, phase-gated governed reality pipeline across Phase 7D.1–7D.5. Each sub-phase is independently frozen before the next is designed.

### Frozen Sub-Phases

| Phase | Component | Status |
|:---|:---|:---|
| 7D.1 | `CandidateHypothesis` foundation (`candidate_models.py`, `candidate_repository.py`) | 🔒 FROZEN |
| 7D.2 | Competition & Choice (`competition_service.py`, `choice_service.py`, `volatility_policy.py`) | 🔒 FROZEN |
| 7D.3 | Reality Repair & Biography Promotion (`repair_service.py`, `biography_promotion_service.py`) | 🔒 FROZEN |
| 7D.4 | Prompt Context Assembly (`reality_context_builder.py`, `reality_context_models.py`) | 🔒 FROZEN |
| 7D.5 | CharacterEngine Integration (`reality_orchestration_service.py`, `evidence_classifier.py`, `world_facts_selector.py`) | 🔒 FROZEN |

* **Consequences**:
  * `CharacterEngine` now delegates per-turn governed reality to `RealityOrchestrationService` only.
  * Legacy `RealityBeliefEngine` and `RealityPromotionService` (7B.3) are preserved but have no runtime dependency from the governed path.
  * `RealityContextBuilder.build_context()` is a pure, read-only assembly function — no DB writes, no lifecycle mutations.

---

## ADR-012: Canonical Mutation Authority Chain

* **Status**: Accepted & Frozen (2026-09-23)
* **Context**: Without a strict mutation authority, multiple code paths could independently modify `character_core_facts`, leading to conflicting state and audit gaps.
* **Decision**: Only `BiographyPromotionService` may call `CharacterCoreService.set_fact()`. This is enforced by architectural rule, AST audit, and GC test suite.

### Authority Chain

```
User input signal
    ↓
EvidenceClassifier → CandidateHypothesis (7D.1)
    ↓
CandidateCompetitionService (7D.2)
    ↓
ChoiceSelectionService (7D.2)
    ↓
BiographyPromotionService.authorize_promotion() → PromotionAuthorizationToken (7D.3)
    ↓
CharacterCoreService.set_fact() → DB commit
```

* **No other path** in the 7D governed layer creates `PromotionAuthorizationToken` or calls `set_fact()`.
* **Consequences**:
  * Single auditable mutation point.
  * `PromotionAuthorizationToken` serves as a typed capability proof that promotion was authorized via the correct channel.
  * AST enforcement verified at every phase freeze.

---

## ADR-013: DB Failure vs. Empty State Semantic Boundary

* **Status**: Accepted & Frozen (2026-09-23)
* **Context**: An infrastructure failure querying candidate records must not be silently reinterpreted as "no candidates exist." These are two distinct epistemic states.
* **Decision**: `CandidateRepository.get_all_active_candidates()` raises `CandidateRepositoryUnavailableError` on any DB exception. The orchestration service propagates this to `CharacterEngine`, which uses its pre-orchestration fail-closed path. An empty `[]` result (DB query succeeded, zero rows) is a valid normal state and must never be treated as infrastructure failure.
* **Consequences**:
  * GC-135 and GC-139 form a complementary test pair enforcing this boundary.
  * Callers cannot accidentally treat "DB down" as "confirmed empty state."

---

## ADR-014: Legacy 7B.3 Module Retirement Policy

* **Status**: Accepted (2026-09-23), Retirement Deferred
* **Context**: Modules `RealityBeliefEngine` (`belief_engine.py`) and `RealityPromotionService` (`promotion_service.py`) are superseded by the 7D governed pipeline but still exist in the codebase.
* **Decision**: These modules are preserved but disconnected from the governed path. Physical deletion is deferred to a future cleanup phase, to be executed after broader integration stability is confirmed. No 7D.5 (or later) code may import or depend on them.
* **Consequences**:
  * Reduces risk of accidental breakage during active development.
  * A future ADR will govern their retirement.
  * AST audit at each freeze checks that no governed-path file imports these modules.

---

## ADR-015: WorldFactsSelector — Lexical-Only Constraint

* **Status**: Accepted (2026-09-23), Known Limitation Recorded
* **Context**: The `WorldFactsSelector` must select objective world facts relevant to the current user turn without performing semantic retrieval or embedding lookups, which would introduce LLM dependency into the reality assembly pipeline.
* **Decision**: Selection is strictly lexical: token-set intersection for Latin/single-char tokens, plus verbatim CJK alias substring match for multi-character Chinese phrases. No embedding, no NLP, no fallback to registry insertion order. Unmatched input returns `{}`.
* **Known Limitation**: Very short CJK tokens (e.g., `"大学"`) used as aliases could produce false positives if added to `_ENTITY_ALIASES` in future. This is a 7D.6 candidate, not a current defect.
* **Consequences**:
  * Deterministic, auditable, zero-latency selection.
  * Maximum 4 items returned, sorted deterministically by key.
  * Only `STATIC_FACT` and `ENTITY_RELATION` kinds are eligible — `PLAUSIBILITY_RULE` and `TEMPORAL_RULE` are always excluded.
