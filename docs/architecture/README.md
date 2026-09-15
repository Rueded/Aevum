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











