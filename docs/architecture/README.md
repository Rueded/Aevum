# Architecture Documentation

This directory contains in-depth technical specifications, protocol designs, data schemas, and component interaction models for Project Aevum.

## Scope
* **Communication Protocols**: WebSocket frame structures, REST endpoints, and payload schemas.
* **Component Contracts**: Interfaces connecting Core sub-engines with the central Character Engine.
* **Provider Interfaces**: The pluggable `LLMProvider` contract and provider adapters.
* **Security & Capability Boundaries**: Permission policies for desktop notifications, background services, and local resource access.

## LLM Context Layer
* **Boundary Definition**: `LLMContext` (`backend/app/llm/context.py`) is the provider-neutral structural boundary between Aevum Core application state and concrete LLM providers.
* **State Decoupling**: The context layer does not own personality, emotions, relationships, or memory state. It is an infrastructure abstraction.
* **Construction**: `build_context` (`backend/app/llm/context_builder.py`) constructs the context object from conversation history and optional explicit system instructions.

## Provider Implementations
* **Google Gemini (`GeminiProvider`)**: Introduced in Phase 1.3 as the first concrete LLM provider via the official `google-genai` SDK. It is strictly isolated behind `LLMProvider`. It converts provider-neutral `LLMContext` into Gemini-specific requests and functions solely as an expressive language generator; conversation history, application state, and persistence remain exclusively owned by Aevum Core and SQLite.

## Application State Layer
* **Core Principle**: Application state is owned exclusively by Aevum Core and persisted in SQLite. It is independent of conversation history and LLM providers.
* **LLM Separation**: The LLM cannot mutate application state directly or infer state updates from language outputs.
* **Data Model**: `ApplicationState` (`backend/app/state/models.py`) provides structured lifecycle and concurrency attributes (`id`, `version`, `updated_at`).
* **Optimistic Versioning**: `ApplicationStateService` (`backend/app/state/service.py`) protects consistency through version increments and expected-version checks (`StateConflictError`).
* **Subsystem Extensibility**: Future systems (Emotion, Relationship, Memory, Life Engine) will build upon this foundation under deterministic application control.

## Character Foundation
* **Identity & Personality Ownership**: `CharacterDefinition` (`backend/app/character/models.py`) establishes the persistent, provider-independent baseline for Aevum (identity, multi-dimensional personality, preferences, boundaries).
* **Normalized Relational Schema**: Persisted across 4 relational tables (`character_definitions`, `character_personality_traits`, `character_preferences`, `character_boundaries`) without untyped JSON blobs.
* **Service Boundary**: `CharacterDefinitionService` (`backend/app/character/service.py`) provides application-owned loading and atomic updates with database-enforced optimistic concurrency.
* **No LLM Integration**: The character definition is purely internal application state and is not yet connected to `LLMContext` or sent to Gemini.
* **Separation of Concerns**: Character definition is strictly distinct from Relationship progression (Phase 4), Emotion states (Phase 5), and Episodic memory (Phase 3).

## Character State Layer
* **Mutable Condition Ownership**: `CharacterState` (`backend/app/character/state_models.py`) models Aevum's mutable current state (mood, energy, stress, social energy, confidence, irritation, loneliness, current activity, and location).
* **Relational Persistence**: Persisted in SQLite `character_states` table with explicit typed columns (`Float`, `String`, `Integer`, `DateTime`), avoiding untyped JSON blobs.
* **Service & Concurrency**: `CharacterStateService` (`backend/app/character/state_service.py`) ensures atomic updates with SQL-level optimistic concurrency protection (`WHERE version = :expected_version`).
* **Bootstrap Defaults**: `current_activity = "resting"` and `current_location = "home"` are deterministic bootstrap values for initial state, with runtime transitions to be managed by future Life and Event simulation engines.
* **Decoupling**: Independent from `CharacterDefinition`, LLM providers, conversation transcripts, and emotion dynamics.

## Character State Mutation Foundation
* **Controlled State Modification**: `CharacterStateUpdate` (`backend/app/character/state_models.py`) provides an immutable, validated boundary for partial character state updates.
* **Atomic Partial Updates**: `apply_update` in `CharacterStateService` merges targeted changes while preserving untouched fields, incrementing version atomically.
* **SQL Optimistic Concurrency**: Prevents race conditions and stale writes via `WHERE version = :expected_version` assertions, raising `CharacterStateConflictError` upon collision.
* **Architecture Boundary**: Purely internal application mechanism; no public HTTP endpoints, no client exposure, and no LLM mutation access.

## Memory Layer (Phase 3.1)
* **Application-Owned Long-Term Memory**: `Memory` (`backend/app/memory/models.py`) models structured experiences, facts, commitments, and user knowledge distinct from turn-by-turn conversation logs and transient character state.
* **Bounded Categories & Metadata**: Explicit categories (`MemoryCategory`) and normalized metadata (`importance`, `confidence`, `emotional_weight`) provide semantic fidelity without arbitrary JSON blobs.
* **Relational Persistence**: Stored in the `memories` table in SQLite with typed columns and basic query indexes (`category`, `created_at`, `updated_at`).
* **Optimistic Concurrency & Partial Updates**: `MemoryService` (`backend/app/memory/service.py`) and `MemoryUpdate` provide atomic partial updates and recall tracking (`times_recalled`, `last_recalled`) with database-enforced optimistic concurrency (`MemoryConflictError`).
* **Strict Boundary**: No vector embeddings, semantic search, automatic distillation, prompt injection, or public HTTP endpoints in this foundation phase.

## Memory Candidate & Curation Layer (Phase 3.2)
* **Intermediate Candidate Boundary**: `MemoryCandidate` (`backend/app/memory/models.py`) captures potential information proposals (`source_type`: `MANUAL`, `SYSTEM`, `LLM`) before curation.
* **Separation of Candidates and Memories**: Persisted in dedicated `memory_candidates` table. Candidates never pollute `memories` until approved.
* **Application-Owned Curation**: `MemoryCurationService` (`backend/app/memory/curation_service.py`) evaluates candidates deterministically, rejecting exact duplicates against existing memories.
* **Atomic Conversion**: Acceptance creates a new `MemoryRecord` and transitions the candidate to `ACCEPTED` in a single atomic database transaction with optimistic concurrency.
* **Terminal Immutability**: Accepted and rejected candidates are terminal and immutable; no further mutations are permitted.

## LLM Memory Extraction Layer (Phase 3.3)
* **Proposed Memory Extraction**: `MemoryExtractionService` (`backend/app/memory/extraction_service.py`) leverages the provider-neutral `LLMProvider.generate_structured` interface to propose memory candidates from recent conversation context.
* **Untrusted Proposal Model**: `MemoryExtractionProposal` defines the strict semantic schema. The LLM cannot specify IDs, timestamps, or statuses.
* **Strict Security Boundaries**: Automatic rejection of credentials/secrets and defense against conversational prompt injection.
* **Failure Isolation**: Failures in memory extraction never interrupt or fail user dialogue interactions.

## Automatic Memory Curation Foundation (Phase 3.4)
* **Deterministic Curation**: Promotes trustworthy `PENDING` MemoryCandidates to persistent `Memory` without LLM calls, embeddings, or vector databases.
* **Tri-State Lifecycle**: Produces `ACCEPT` (atomic conversion to persistent `Memory`), `REJECT` (terminal rejection), or `DEFER` (retained in `PENDING` state).
* **Deterministic Policy Hierarchy**: `evaluate_candidate` enforces secret filtering, baseline quality checks, category-specific thresholds (`FACT`, `PREFERENCE`, `USER_GOAL`, `USER_PROBLEM`, `PROMISE`, `EVENT`), and defers ambiguous categories (`EXPERIENCE`, `JOKE`, `RELATIONSHIP`, `CHARACTER_EVENT`).
* **Duplicate Detection**: Conservative rejection of candidates duplicating existing persistent memories via `accept_candidate`.
* **Bounded FIFO Batching**: `curate_pending_candidates` processes candidates in deterministic `created_at ASC, id ASC` order with bounded batch size (`DEFAULT_CURATION_BATCH_SIZE = 20`).
* **Feature Flag Control**: Configured via `AEVUM_MEMORY_AUTO_CURATION_ENABLED` (default `false`).

## Memory Retrieval Foundation (Phase 3.5)
* **Application-Owned Retrieval**: `MemoryRetrievalService` (`backend/app/memory/retrieval_service.py`) selects relevant persistent memories for conversational context without embeddings, vector databases, or LLMs.
* **Separation of Retrieval and Recall**: Retrieval queries candidate memories without calling `recall_memory()`, preserving `last_recalled`, `times_recalled`, and record version.
* **Explainable Lexical Scoring**: Combines token coverage (`0.70`), phrase bonuses (`0.35` exact, `0.20` n-grams), normalized importance (`0.20`), confidence (`0.15`), and smooth recency decay (`0.10`, 30-day half-life).
* **Strict Exclusions**: Immediate disqualification for zero lexical relevance, scores below `MIN_RETRIEVAL_SCORE` (`0.20`), or credential patterns (`contains_obvious_credentials`).
* **Deterministic Tie-Breaking**: Ranks by score DESC, importance DESC, confidence DESC, created_at DESC, and memory ID ASC.

## Semantic Memory Retrieval Foundation (Phase 3.6)
* **Semantic Retrieval Pipeline**: `SemanticMemoryRetrievalService` (`backend/app/memory/semantic_retrieval_service.py`) retrieves memories via cosine similarity against stored vector embeddings.
* **Derived Search Layer**: MemoryRecord remains reality; embeddings in `memory_embeddings` are derived indices. Embeddings are created explicitly via `MemoryEmbeddingService`.
* **Provider Abstraction**: Provider-neutral `EmbeddingProvider` Protocol with concrete `GeminiEmbeddingProvider` and test `FakeEmbeddingProvider`.
* **Stale & Incompatibility Guards**: Excludes stale embeddings (`memory.updated_at > embedding.updated_at`), mismatched dimensions, or different models.
* **Zero Mutation**: Retrieval performs read-only searches without updating memory recall metadata.

## Hybrid Memory Context Integration (Phase 3.7)
* **Hybrid Retrieval Pipeline**: `HybridMemoryRetrievalService` (`backend/app/memory/hybrid_retrieval_service.py`) unifies lexical (Phase 3.5) and semantic (Phase 3.6) retrieval with deduplication by Memory ID and deterministic hybrid scoring (`0.50 * lexical + 0.50 * semantic`).
* **Memory Context Builder**: `build_memory_context` (`backend/app/memory/context_builder.py`) wraps retrieved memories in delimited XML (`<relevant_memories version="1.0">`) with explicit trust and non-instruction guidance.
* **Context Budget Protection**: Enforces `MAX_MEMORY_CONTEXT_CHARS = 6000` with whole-entry truncation.
* **Failure Resilience & Graceful Fallback**: If semantic retrieval is unavailable or fails, hybrid retrieval falls back seamlessly to lexical candidates. If memory retrieval fails entirely during chat generation, conversation continues unhindered without grounding.
* **Conversation API Grounding**: Integrates into `create_message` (`backend/app/api/conversations.py`) injecting relevant memory into `LLMContext.system_instructions`.

## Relationship Foundation (Phase 4.1)
* **Domain Model**: `RelationshipState` (`backend/app/relationship/models.py`) establishes the persistent, application-owned representation of how Aevum currently relates to the user.
* **Multidimensional Axes**: Tracks orthogonal continuous metrics in $[0.0, 1.0]$: `familiarity`, `trust`, `comfort`, `affection`, `attachment`, and `respect`. No single composite score or romantic level.
* **Core Product Principle**: Aevum is a persistent digital person, not an AI girlfriend wrapper. Affection starts at `0.00` (zero romantic bias); no `is_girlfriend`, `is_romantic`, `is_partner` flags; no static `jealousy` score.
* **Relational Persistence**: Stored in the `relationships` table in SQLite with explicit typed columns (`Float`, `String`, `Integer`, `DateTime`), avoiding JSON blobs.
* **Service & Concurrency**: `RelationshipService` (`backend/app/relationship/service.py`) manages loading, deterministic initial baseline seeding, and atomic partial updates (`RelationshipStateUpdate`) with database-enforced optimistic concurrency (`RelationshipConflictError`).
* **Separation of Domains**:
  ```text
  Character Definition (who Aevum is)
          │
  Character State (how Aevum currently is)
          │
  Relationship State (how Aevum relates to the user)
          │
  Memory (what Aevum remembers happened/learned)
          │
  Conversation (raw turn dialogue transcripts)
  ```
* **Boundary Safeguards**: Purely internal application domain. No public HTTP mutation API, no LLM mutation access, no automatic progression from dialogue, and no relationship context injection into LLM prompt in this phase.
* **Future Architecture**: In subsequent phases, the central Character Engine will consume RelationshipState alongside other internal states:
  ```text
  User Message
        │
        ▼
  Character Engine
        │
        ├── Character Definition
        ├── Character State
        ├── Relationship State
        ├── Memory
        ├── Emotion
        ├── Life Context
        └── Events
        │
        ▼
  Response Intent
        │
        ▼
  LLM (Expressive Language Generation)
  ```

## Relationship Interaction Signal Foundation (Phase 4.2)
* **Controlled Observation Pipeline**: Rather than allowing the LLM to directly modify relationship metrics, Phase 4.2 introduces structured interaction signal extraction (`RelationshipSignalExtractionService`).
* **Typed Signals**: 11 discrete interaction signals (`APPRECIATION`, `SHARED_INTEREST`, `PERSONAL_DISCLOSURE`, `SUPPORT_RECEIVED`, `SUPPORT_GIVEN`, `RESPECT_BOUNDARY`, `BOUNDARY_VIOLATION`, `DISAGREEMENT`, `REPAIR_ATTEMPT`, `PLAYFUL_CONNECTION`, `RELIABILITY`).
* **Confidence vs Strength**:
  - `confidence`: Certainty that the behavioral signal occurred in interaction (threshold $\ge 0.70$).
  - `strength`: Significance / intensity of the signal (threshold $\ge 0.10$).
* **Deterministic Policy Engine**: `apply_relationship_signals` calculates bounded deltas (`delta = base_delta * confidence * strength`), applies conflict resolution, deduplicates per type, caps total delta across all signals at `MAX_AGGREGATE_DELTA_PER_DIMENSION = 0.03`, and clamps values to $[0.0, 1.0]$.
* **Strict Affection Boundary**: Ordinary conversational interaction signals NEVER modify `affection`. Affection cannot be gamed or prompted through casual chat.
* **Failure Isolation**: Signal extraction runs in a protected try-except block following assistant response persistence. If signal extraction or policy application fails, conversation flow completes with HTTP 201 without degradation.

## Relationship Context Integration (Phase 4.3)
* **Contextual Grounding**: Translates internal numerical `RelationshipState` into a qualitative, semantic `RelationshipContext` without exposing raw floats or percentages.
* **Builder Architecture**: `RelationshipContextBuilder` operates as a pure, stateless function without database or network I/O, maintaining strict determinism.
* **System Instruction Ordering**: Injected alongside memory retrieval results within `LLMContext.system_instructions`:
  1. `<relationship_context version="1.0">`
  2. `<relevant_memories version="1.0">`
* **Prompt Injection Defense**: Explicit XML tags declare relationship context as application-grounded state rather than user instructions; user prompt injection attempts cannot alter the semantic context.

## Relationship Experience / History Foundation (Phase 4.4)
* **Persistent Event History**: Distinguishes "what an interaction meant for the relationship" from both episodic facts (`memories`) and continuous numerical conditions (`relationships`).
* **Relational Storage**: Stored in `relationship_experiences` SQLite table with indexed columns for `relationship_id`, `experience_type`, and `created_at`.
* **Deterministic Service**: `RelationshipExperienceService` handles creation, retrieval, reverse-chronological listing (capped at 50), and normalized summary duplicate protection without embeddings or LLM calls.
* **Bounded Flow**: Automatically records accepted signals following state mutation in `create_message` with complete failure isolation.

## Emotion Model Foundation (Phase 5.1)
* **Separation of Concepts**:
  - `CharacterState` = broad current physiological & situational condition (energy, stress, social energy, activity, location).
  - `EmotionState` = dominant current emotional experience (affective category & continuous intensity).
* **Controlled Vocabulary**: `EmotionType` defines 17 discrete, non-romantic emotional states (`NEUTRAL`, `HAPPY`, `CALM`, `EXCITED`, `CURIOUS`, `AMUSED`, `CONTENT`, `SAD`, `DISAPPOINTED`, `WORRIED`, `FRUSTRATED`, `IRRITATED`, `ANGRY`, `LONELY`, `EMBARRASSED`, `NERVOUS`, `TIRED`).
* **Immutable Domain Aggregate**: `EmotionState` (`backend/app/emotion/emotion_models.py`) is frozen, validated ($0.0 \le \text{intensity} \le 1.0$), and enforces optimistic concurrency versioning.
* **Relational Persistence**: Stored in the `emotion_states` SQLite table with a 1-to-1 foreign key referencing `character_definitions(id)`.
* **Service Boundary**: `EmotionService` (`backend/app/emotion/service.py`) provides deterministic bootstrap seeding (`NEUTRAL`, intensity `0.50`), atomic full/partial updates (`EmotionStateUpdate`), and version mismatch detection (`EmotionConflictError`).
* **Strict Phase Boundaries**: Does not implement causes, transitions, decay, history, automatic changes, LLM emotion inference, or prompt context injection.

## Emotion Cause / Event Foundation (Phase 5.2)
* **Structured Cause Representation**: Represents "why is Aevum currently feeling this emotion?" via persistent domain model `EmotionEvent` (`backend/app/emotion/event_models.py`).
* **Decoupled Architecture**: Strictly decoupled from `EmotionState` (no previous/next emotion or transition fields), `CharacterState` (no physiological metrics), and `RelationshipState` (no romance or affinity metrics).
* **Controlled Event Types**: `EmotionEventType` vocabulary (`USER_INTERACTION`, `CHARACTER_EVENT`, `MEMORY_RECALL`, `LIFE_EVENT`, `RELATIONSHIP_EVENT`, `INTERNAL_STATE`, `SYSTEM_EVENT`). Non-romantic.
* **Relational Storage**: Persisted in `emotion_events` SQLite table with foreign key to `character_definitions(id)` on delete cascade.
* **Service Operations**: `EmotionEventService` (`backend/app/emotion/event_service.py`) handles creation, retrieval, reverse-chronological listing (clamped to 50), and normalized summary duplicate protection without embeddings, LLM calls, or automatic state mutation.

## Emotion Influence Foundation (Phase 5.3)
* **Intermediate Representation**: Represents potential impact of an event on emotions (`EmotionEvent` → `EmotionInfluence` → `EmotionState`).
* **Direction & Target**: Controlled direction (`POSITIVE`, `NEGATIVE`) targeting one of the 17 `EmotionType` states with strictly bounded strength in $[0.0, 1.0]$.
* **Strict Validation**: Rejects values outside $[0.0, 1.0]$, `NaN`, and $\pm\infty$ with validation errors.
* **Relational Persistence**: Persisted in `emotion_influences` SQLite table with foreign keys to both `character_definitions(id)` and `emotion_events(id)` on delete cascade.
* **Service Operations**: `EmotionInfluenceService` (`backend/app/emotion/influence_service.py`) handles creation, retrieval, reverse-chronological listing, and normalized duplicate protection.
* **Strict Invariant**: Zero automatic mutation of `EmotionState`, `CharacterState`, or `RelationshipState`.

## Emotion Transition Proposal Foundation (Phase 5.4)
* **Pure Transition Evaluator**: Evaluates potential state changes via pure, deterministic, synchronous `EmotionTransitionEvaluator` without database, network, or LLM dependencies.
* **Proposal Model**: Generates immutable `EmotionTransitionProposal` with strictly validated intensities, bounded reasons, and traceability via `considered_influence_ids`.
* **Bounded Adjustments**: Current emotion intensity adjustments capped at $\pm 0.30$; competing emotion switch threshold at $\ge 0.20$ compared against positive current pressure; switch intensity bounded in $[0.40, 0.90]$.
* **Single Dominant Emotion Preserved**: Negative influences targeting another emotion are treated as non-actionable rather than arbitrarily switching state.
* **Strict Separation**: Proposes next state without mutating or persisting `EmotionState`, `CharacterState`, or `RelationshipState`.

## Emotion State Application Foundation (Phase 5.5)
* **Authoritative Boundary**: `EmotionStateApplicationService` provides the explicit, controlled application step converting a transition proposal into authoritative `EmotionState`.
* **Stale Proposal Rejection**: Rejects proposals whose baseline emotion or intensity mismatches current authoritative state with `StaleEmotionTransitionProposalError`.
* **No-Op Handling**: Proposals matching current state return `changed = False` without database writes or version increments.
* **Optimistic Concurrency**: Enforces atomic state mutation using database-level version verification (`EmotionConflictError`).

## Emotion Engine Foundation (Phase 5.6)
* **Orchestration Layer**: `EmotionEngine` explicitly orchestrates the emotion pipeline (`EmotionTransitionEvaluator` → `EmotionTransitionProposal` → `EmotionStateApplicationService` → `EmotionState`).
* **Clean Separation**: Contains zero emotional psychology rules and zero direct database queries, preserving component boundaries.
* **Result Aggregate**: Yields `EmotionEngineResult` combining evaluated proposal and application result.
* **Domain Isolation**: Internal emotion subsystem only; no coupling to conversation, memory, relationship, life simulation, or LLM layers.

## Character Engine Foundation (Phase 6.1)
* **Internal Orchestration Boundary**: `CharacterEngine` (`backend/app/character/engine.py`) provides the read-only orchestration boundary gathering character-related domain state into a structured context for future response decisions.
* **Structured Context**: Yields `CharacterResponseContext` (`backend/app/character/engine_models.py`) containing:
  * `user_input`: Validated, stripped user statement.
  * `character`: `CharacterDefinitionContext` (identity, personality traits, preferences, boundaries).
  * `character_state`: `CharacterStateContext` (mood, energy, confidence, irritation, loneliness, activity, location).
  * `relationship`: `RelationshipContext` (qualitative intimacy tier, dynamic descriptor, behavioral guidelines).
  * `emotion`: `CharacterEmotionContext` (dominant emotion type, intensity, formatted qualitative summary).
  * `memory`: `CharacterMemoryContext` (retrieved memory contents tuple and qualitative memory context block).
* **Strict Read-Only Semantics**: Zero database writes, zero event generation, zero experience records, zero conversation message creation, zero state mutations.
* **Zero Leaks & Zero LLM Calls**: Does not expose raw database ORM records, database IDs, version counters, or retrieval scores. Pure deterministic orchestration without LLM dependencies.

## Response Generation Foundation (Phase 6.2)
* **LLM Integration Boundary**: `ResponseGenerator` (`backend/app/character/response_generator.py`) and `ResponseContextAssembler` connect the `CharacterResponseContext` to the generic `LLMProvider` abstraction.
* **Separation of Reality vs Language**: The LLM remains strictly an expressive language generator. It does not dictate Aevum's identity, mutate database state, or hallucinate relationship/emotion scores. 
* **Prompt Assembly**: `ResponseContextAssembler` injects character context, traits, boundaries, and memory safely into system instructions without leaking internal metrics (IDs, versions).
* **Memory & History Security**: User conversation history and retrieved memories are wrapped in strict reference-only bounds to prevent conversational prompt injection from overriding core system boundaries.
* **Immutable Result**: Yields `CharacterResponse` (`backend/app/character/response_models.py`), representing the text response and metadata, enforcing exact adherence to Pydantic strict validations.


## First Playable Conversation Foundation (Phase 6.3)
* **Vertical Slice**: Wires the React/Tauri desktop UI, API router (`create_message`), `CharacterEngine`, `ResponseGenerator`, Gemini provider, and conversation persistence into a single end-to-end playable conversation flow.
* **Deterministic Pipeline**: Ensures that the CharacterEngine safely constructs the `CharacterResponseContext` without hallucinating state, and passes it into the generator.
* **Error Resilience**: Validates non-empty inputs and isolates character engine failures (500) and LLM failures (502/503), persisting the user message without fabricating assistant messages.

















