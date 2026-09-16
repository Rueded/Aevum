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

## Relationship Foundation (Phase 4.1)
* **Domain Models**: `RelationshipState` and `RelationshipStateUpdate` (`app.relationship.models`).
* **Multidimensional Axes**: Continuous normalized metrics in $[0.0, 1.0]$: `familiarity`, `trust`, `comfort`, `affection`, `attachment`, `respect`.
* **Product Alignment**: Aevum is a digital person, not an AI girlfriend wrapper. Affection starts at `0.00`; no romance flags (`is_girlfriend`, `is_romantic`, `is_partner`), no static `jealousy`, and no single composite score.
* **Relational Persistence**: Stored in `relationships` SQLite table with explicit typed columns (`Float`, `String`, `Integer`, `DateTime`), avoiding JSON blobs.
* **Service & Concurrency**: `RelationshipService` (`app.relationship.service`) provides initial baseline seeding, atomic partial updates (`apply_update`), and SQL-enforced optimistic concurrency (`RelationshipConflictError`).
* **Isolation**: Internal application domain only. No public HTTP mutation API, no LLM mutation access, no automatic progression from conversations, and no injection into LLM context in this phase.

## Relationship Interaction Signal Foundation (Phase 4.2)
* **Domain Models**: `RelationshipSignalType`, `RelationshipSignalSource`, `RelationshipSignalProposal`, `RelationshipSignalPayload`, `RelationshipSignal`, `RelationshipSignalExtractionResult` (`app.relationship.models`).
* **Extraction Service**: `RelationshipSignalExtractionService` (`app.relationship.extraction_service`) parses structured interaction signal proposals from conversation exchanges, applying schema validation, secret credential filtering, contradiction resolution, and deduplication.
* **Deterministic Policy**: `apply_relationship_signals` (`app.relationship.policy`) maps signals to state updates with bounded base deltas, confidence/strength scaling, aggregate per-dimension capping (`MAX_AGGREGATE_DELTA_PER_DIMENSION = 0.03`), and boundary clamping to $[0.0, 1.0]$.
* **Strict Affection Boundary**: Ordinary conversational signals NEVER mutate `affection`.
* **Failure Isolation**: Conversation messaging generates and persists the assistant reply first. Signal extraction and policy application run safely in an isolated post-generation block.

## Relationship Context Integration (Phase 4.3)
* **Domain Model**: `RelationshipContext` (`app.relationship.context_models`). Strictly semantic representation with bounded qualitative summaries (`relationship_summary`, dimension summaries, `interaction_guidance`). Zero raw numerical metrics exposed.
* **Context Builder**: `RelationshipContextBuilder` (`app.relationship.context_builder`) provides pure, deterministic translation of `RelationshipState` into `RelationshipContext` and `<relationship_context version="1.0">` XML.
* **Context Budget & Safety**: Enforces `MAX_RELATIONSHIP_CONTEXT_CHARS = 3500`. Explicit anti-romance, anti-manipulation, and prompt injection defense instructions.
* **Conversation Integration**: Injected into `LLMContext.system_instructions` alongside memory retrieval context prior to calling downstream LLM providers.

## Relationship Experience / History Foundation (Phase 4.4)
* **Domain Models**: `RelationshipExperienceType`, `RelationshipExperienceSource`, `RelationshipExperienceCreate`, `RelationshipExperience` (`app.relationship.experience_models`). Immutable and strictly decoupled from continuous metrics.
* **Relational Storage**: Persisted in `relationship_experiences` SQLite table with indexing on `relationship_id`, `experience_type`, and `created_at`.
* **Experience Service**: `RelationshipExperienceService` (`app.relationship.experience_service`) provides create, get, reverse-chronological list (capped at 50), and deterministic normalized summary duplicate detection.
* **Signal Mapping & Pipeline**: Automatically maps accepted signals surviving policy thresholds to historical experiences inside `create_message` with complete failure isolation.

## Emotion Model Foundation (Phase 5.1)
* **Domain Models**: `EmotionType`, `EmotionState`, `EmotionStateUpdate` (`app.emotion.emotion_models`). Represents dominant current emotional experience (`intensity` $0.0 \le v \le 1.0$) distinct from broad physiological/cognitive `CharacterState`.
* **Vocabulary**: 17 qualitative, human-readable, non-romantic emotion types (`NEUTRAL`, `HAPPY`, `CALM`, `EXCITED`, `CURIOUS`, `AMUSED`, `CONTENT`, `SAD`, `DISAPPOINTED`, `WORRIED`, `FRUSTRATED`, `IRRITATED`, `ANGRY`, `LONELY`, `EMBARRASSED`, `NERVOUS`, `TIRED`).
* **Relational Persistence**: Persisted in `emotion_states` SQLite table with a 1-to-1 foreign key to `character_definitions(id)`.
* **Emotion Service**: `EmotionService` (`app.emotion.service`) provides initial deterministic baseline seeding (`NEUTRAL`, intensity `0.50`), atomic full/partial updates (`apply_update`), and database-enforced optimistic concurrency (`EmotionConflictError`).
* **Strict Decoupling**: Does not contain relationship metrics, does not duplicate CharacterState fields, and does not implement causes, transitions, decay, history, or prompt injection.

## Emotion Cause / Event Foundation (Phase 5.2)
* **Domain Models**: `EmotionEventType`, `EmotionEventSource`, `EmotionEventCreate`, `EmotionEvent` (`app.emotion.event_models`). Structured representation of emotional causes and triggers.
* **Controlled Event Types**: 7 distinct types (`USER_INTERACTION`, `CHARACTER_EVENT`, `MEMORY_RECALL`, `LIFE_EVENT`, `RELATIONSHIP_EVENT`, `INTERNAL_STATE`, `SYSTEM_EVENT`).
* **Relational Persistence**: Stored in `emotion_events` SQLite table with foreign key cascade to `character_definitions(id)`.
* **Event Service**: `EmotionEventService` (`app.emotion.event_service`) provides create, get, reverse-chronological list (clamped to 50), and deterministic normalized summary duplicate detection without automatic state mutations.

## Emotion Influence Foundation (Phase 5.3)
* **Domain Models**: `EmotionInfluenceDirection`, `EmotionInfluenceCreate`, `EmotionInfluence` (`app.emotion.influence_models`). Intermediate representation of how an event might influence an emotion.
* **Controlled Vocabulary**: Direction strictly `POSITIVE` / `NEGATIVE`; targets 17 non-romantic `EmotionType` states; strength strictly bounded $[0.0, 1.0]$.
* **Relational Persistence**: Stored in `emotion_influences` SQLite table with cascade deletion from both `character_definitions(id)` and `emotion_events(id)`.
* **Influence Service**: `EmotionInfluenceService` (`app.emotion.influence_service`) provides create, get, reverse-chronological list (clamped to 50), and duplicate protection without mutating `EmotionState`, `CharacterState`, or `RelationshipState`.

## Emotion Transition Proposal Foundation (Phase 5.4)
* **Domain Models**: `EmotionTransitionProposal` (`app.emotion.transition_models`). Represents an immutable, validated transition calculation proposal.
* **Transition Evaluator**: `EmotionTransitionEvaluator` (`app.emotion.transition_evaluator`). Pure, deterministic, side-effect free evaluator calculating proposed next emotion states from explicit influences.
* **Evaluator Rules**: Jump magnitude cap $\pm 0.30$, competing switch activation threshold $\ge 0.20$ compared against positive current pressure, switch intensity bounded in $[0.40, 0.90]$, and single-dominant-emotion boundary preservation without automatic state mutation.

## Emotion State Application Foundation (Phase 5.5)
* **Domain Models**: `EmotionStateApplicationResult` (`app.emotion.application_models`). Immutable representation of application result with before/after state and mutation flag.
* **Application Service**: `EmotionStateApplicationService` (`app.emotion.application_service`). Validates and applies proposals to authoritative `EmotionState` with optimistic concurrency and stale-proposal rejection (`StaleEmotionTransitionProposalError`).

## Emotion Engine Foundation (Phase 5.6)
* **Domain Models**: `EmotionEngineResult` (`app.emotion.engine_models`). Structured result of an emotion engine cycle.
* **Engine Service**: `EmotionEngine` (`app.emotion.engine`). Internal orchestration service connecting `EmotionTransitionEvaluator` and `EmotionStateApplicationService` without direct persistence or psychology rules.

## Character Engine Foundation (Phase 6.1)
* **Domain Models**: `CharacterResponseContext`, `CharacterDefinitionContext`, `CharacterStateContext`, `CharacterEmotionContext`, `CharacterMemoryContext` (`app.character.engine_models`). Pure frozen Pydantic contexts containing character, state, relationship, emotion, and memory domains.
* **Engine Service**: `CharacterEngine` (`app.character.engine`). Read-only internal orchestration boundary gathering authoritative domain state into an immutable context for downstream response decisions without LLM calls, raw database leaks, or side effects.

## Response Generation Foundation (Phase 6.2)
* **Domain Models**: `CharacterResponse` (`app.character.response_models`). Immutable Pydantic model capturing the final generated text and usage metadata from the LLM.
* **Prompt Assembly**: `ResponseContextAssembler` (`app.character.prompt_assembler`). Converts `CharacterResponseContext` into `LLMContext`, injecting memory and relationship context with strict anti-injection and bounding rules.
* **Response Generation**: `ResponseGenerator` (`app.character.response_generator`). Wraps the upstream `LLMProvider` call, ensuring provider-agnostic text generation without mutating the backend state or orchestrating domain components.
## First Playable Conversation Foundation (Phase 6.3)
* **Conversation API Orchestration**: `create_message` (`app.api.conversations`) was refactored to seamlessly compose `CharacterEngine`, `ResponseContextAssembler`, and `ResponseGenerator`.
* **Reliability**: Guarantees preservation of the original user message during unexpected CharacterEngine or LLM provider failures, shielding the `messages` table from corrupted state or phantom assistant messages.




















