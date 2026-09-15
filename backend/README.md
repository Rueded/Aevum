# Aevum Core Backend

Backend service and state machine for Project Aevum.

## Overview
* **Runtime**: Python 3.11+ / FastAPI
* **Persistence**: SQLite with async SQLAlchemy
* **LLM Integration**: Google Gemini (`google-genai`) is the first concrete LLM provider implementation.
* **Architecture Principle**: The application owns persistent state; the LLM provides language generation.

## LLM Context & Provider Abstraction
* **Context Boundary**: The `LLMContext` (`app.llm.context.LLMContext`) is the provider-neutral boundary between Aevum Core application state and concrete LLM providers.
* **Context Construction**: `build_context` (`app.llm.context_builder.build_context`) converts application messages and optional system instructions into an `LLMContext`. It does not own or invent personality, character state, or memories.
* **Provider Independence**: Core domain logic interacts exclusively with the abstract `LLMProvider` interface (`app.llm.base.LLMProvider`).
* **Gemini Provider**: The concrete `GeminiProvider` (`app.llm.gemini.GeminiProvider`) converts neutral `LLMContext` into Google GenAI format and returns synthesized dialogue text.

## Application State Foundation
* **Ownership**: Canonical application state is strictly owned by Aevum Core and persisted in SQLite (`application_state` table).
* **Decoupled from Conversation**: Application state exists independently of individual conversations and LLM providers.
* **Model**: `ApplicationState` (`app.state.models.ApplicationState`) represents minimal foundational lifecycle and concurrency metadata (`id`, `version`, `updated_at`). It contains no speculative character or domain fields.
* **Optimistic Concurrency**: `ApplicationStateService` (`app.state.service.ApplicationStateService`) manages atomic state transitions and version increments, validating expected versions and rejecting stale updates with `StateConflictError`.
* **Subsystem Foundation**: Future domain subsystems (Character Engine, Emotion, Relationship, Memory, Life simulation) will build upon and coordinate with this application-owned foundation without delegating truth to the LLM or client.

## Character Foundation
* **Identity & Personality Models**: `CharacterDefinition` (`app.character.models.CharacterDefinition`) models stable character identity (`CharacterIdentity`), structured multi-dimensional personality tendencies (`Personality`), preferences (`Preference`), and behavioral boundaries (`Boundary`).
* **Normalized Relational Persistence**: Stored across 4 SQLite tables (`character_definitions`, `character_personality_traits`, `character_preferences`, `character_boundaries`). No arbitrary JSON.
* **Service & Concurrency**: `CharacterDefinitionService` (`app.character.service.CharacterDefinitionService`) handles initial seeding and updates with SQL-enforced optimistic concurrency (`CharacterDefinitionConflictError`).
* **Isolation**: Independent from LLMContext, Gemini, Conversations, Relationships, Emotions, and Memories.

## Character State Foundation
* **Mutable State Models**: `CharacterState` (`app.character.state_models.CharacterState`) models mutable current condition (`CharacterMood`, continuous metrics 0.0-1.0: `energy`, `stress`, `social_energy`, `confidence`, `irritation`, `loneliness`, situational context: `current_activity`, `current_location`).
* **Normalized Persistence**: Stored in `character_states` table in SQLite with explicit typed columns.
* **Service & Concurrency**: `CharacterStateService` (`app.character.state_service.CharacterStateService`) provides loading and updates with database-enforced optimistic concurrency (`CharacterStateConflictError`).
* **State vs Definition**: Strictly decoupled from `CharacterDefinition` (who she is vs how she currently is).

## Character State Mutation Foundation
* **State Update Model**: `CharacterStateUpdate` (`app.character.state_models.CharacterStateUpdate`) models immutable, validated partial state mutation requests. Enforces bounds, non-empty strings, valid moods, and forbids empty updates.
* **Partial Update Service**: `apply_update` (`app.character.state_service.CharacterStateService.apply_update`) atomically applies partial updates, updates timestamps, increments version, and enforces optimistic concurrency (`WHERE version = :expected_version`).
* **Isolation**: Internal application operation only; no HTTP endpoints, no LLM mutations, and no Emotion/Life/Relationship logic.

## Memory Foundation (Phase 3.1)
* **Domain Models**: `Memory` and `MemoryUpdate` (`app.memory.models`) define immutable representations of long-term memory records and validated partial updates.
* **Categories**: `MemoryCategory` spans `FACT`, `PREFERENCE`, `EVENT`, `EXPERIENCE`, `PROMISE`, `JOKE`, `RELATIONSHIP`, `USER_GOAL`, `USER_PROBLEM`, and `CHARACTER_EVENT`.
* **Persistence & Indexes**: Stored in `memories` table with indexes on `category`, `created_at`, and `updated_at`.
* **Service & Concurrency**: `MemoryService` (`app.memory.service`) provides creation, retrieval, listing, partial updates, recall tracking, and deletion with database-level optimistic concurrency (`MemoryConflictError`).
* **Decoupling**: Conversation logs and LLM interactions remain completely separate from long-term memory storage.

## Memory Candidate & Curation Foundation (Phase 3.2)
* **Candidate Models**: `MemoryCandidate`, `MemoryCandidateUpdate`, `MemoryCandidateStatus`, `MemoryCandidateSource` (`app.memory.models`).
* **Relational Storage**: Persisted in `memory_candidates` table with indexing on `category`, `status`, and `created_at`.
* **Curation Service**: `MemoryCurationService` (`app.memory.curation_service`) manages candidate lifecycle (`PENDING` -> `ACCEPTED` / `REJECTED`), deterministic exact duplicate detection against `memories`, and optimistic concurrency (`CandidateConflictError`, `CandidateTerminalStateError`).
* **Atomic Conversion**: `accept_candidate` guarantees that converting a candidate into a memory is fully atomic, committing a new `MemoryRecord` while marking the candidate `ACCEPTED`.

## LLM Memory Extraction Foundation (Phase 3.3)
* **Extraction Service**: `MemoryExtractionService` (`app.memory.extraction_service`) extracts candidate proposals from bounded conversation history using provider-neutral `LLMProvider.generate_structured`.
* **Proposal & Result Models**: `MemoryExtractionProposal`, `MemoryExtractionPayload`, `MemoryExtractionResult` (`app.memory.models`).
* **Security & Failure Isolation**: Credential detection (`contains_obvious_credentials`), prompt injection defense, proposal limit clamping (`MAX_PROPOSALS_PER_EXTRACTION = 5`), and isolation of LLM failures from chat.

## Automatic Memory Curation Foundation (Phase 3.4)
* **Deterministic Policy**: `evaluate_candidate` (`app.memory.curation_policy`) applies deterministic criteria (policy v1.0.0) without LLM calls, embeddings, or vector databases.
* **Curation Lifecycle**: Employs tri-state decisions `ACCEPT` (converted to persistent `Memory`), `REJECT` (terminal rejection), and `DEFER` (preserved in `PENDING` state).
* **Policy Hierarchy**: Rejects terminal states, obvious credentials/secrets (`_CREDENTIAL_PATTERNS`), low confidence (<0.70), and low importance (<0.30); defers ambiguous categories (`EXPERIENCE`, `JOKE`, `RELATIONSHIP`, `CHARACTER_EVENT`); accepts high-confidence category thresholds (`FACT`, `PREFERENCE`, `USER_GOAL`, `USER_PROBLEM`, `PROMISE`, `EVENT`); and defers borderline candidates.
* **Exact Duplicate Prevention**: Automatically rejects candidates duplicating existing persistent memories (`REJECTED_DUPLICATE`).
* **Bounded FIFO Batching**: `curate_pending_candidates` processes up to `DEFAULT_CURATION_BATCH_SIZE = 20` candidates in deterministic `created_at ASC, id ASC` order.
* **Configuration**: Controlled by environment variable `AEVUM_MEMORY_AUTO_CURATION_ENABLED` (default `false`).

## Memory Retrieval Foundation (Phase 3.5)
* **Domain Models**: `MemoryRetrievalQuery`, `MemoryRetrievalSignals`, `ScoredMemory`, and `MemoryRetrievalResult` (`app.memory.models`).
* **Retrieval Service**: `MemoryRetrievalService` (`app.memory.retrieval_service`) selects relevant persistent memories for context without mutating memories or invoking LLMs.
* **Lexical Scoring**: Uses deterministic token coverage (`0.70`), phrase bonuses (`0.35` exact, `0.20` n-grams), importance (`0.20`), confidence (`0.15`), and smooth recency decay (`0.10`, 30-day half-life).
* **Safe Filtering**: Disqualifies zero lexical relevance, low scores (< `MIN_RETRIEVAL_SCORE` = 0.20), credentials/secrets (`contains_obvious_credentials`), and candidate records.
* **Tie-Breaking**: Ranks deterministically by score DESC, importance DESC, confidence DESC, created_at DESC, and memory ID ASC.

## Semantic Memory Retrieval Foundation (Phase 3.6)
* **Domain Models**: `EmbeddingResult`, `MemoryEmbedding`, `SemanticMemoryRetrievalQuery`, `SemanticMemoryResult`, and `SemanticMemoryRetrievalResult` (`app.memory.models`).
* **Embedding Abstraction**: `EmbeddingProvider` protocol with `GeminiEmbeddingProvider` (`google-genai`) and deterministic `FakeEmbeddingProvider` (`app.memory.embedding_provider`).
* **Storage & Persistence**: Stored in `memory_embeddings` table with JSON serialization, dimension assertions, and foreign key cascades to `memories`.
* **Services**: `MemoryEmbeddingService` for explicit embedding lifecycle; `SemanticMemoryRetrievalService` for cosine similarity retrieval without memory mutations.
* **Safety & Guards**: Stale embedding rejection (`memory.updated_at > embedding.updated_at`), model/dimension mismatch checks, and secret exclusion.

## Hybrid Memory Context Integration (Phase 3.7)
* **Domain Models**: `HybridMemoryRetrievalQuery`, `HybridMemoryResult`, and `HybridMemoryRetrievalResult` (`app.memory.models`).
* **Hybrid Retrieval Service**: `HybridMemoryRetrievalService` (`app.memory.hybrid_retrieval_service`) combines lexical and semantic retrieval with deduplication and deterministic hybrid scoring (`0.50 * lexical + 0.50 * semantic`).
* **Memory Context Builder**: `build_memory_context` (`app.memory.context_builder`) formats retrieved memories inside XML delimiters (`<relevant_memories version="1.0">`) with explicit trust instructions and hard budget truncation (`MAX_MEMORY_CONTEXT_CHARS = 6000`).
* **Failure Resilience**: Automatic fallback to lexical retrieval if embeddings are unconfigured or fail. Isolated retrieval boundary inside `/conversations/{id}/messages` ensures chat continues even if memory fails.











