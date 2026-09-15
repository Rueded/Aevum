# Character Documentation

This directory contains specifications, schemas, and design documents for Character Foundation and the Character Engine in Project Aevum.

## Scope
* **Personality & Identity**: Baseline character attributes, values, linguistic styles, and quirks.
* **Temperament**: Core behavioral baseline that guides emotional recovery and default attitudes.
* **Boundaries & Autonomy**: Mechanisms enabling the character to decline requests, voice distinct opinions, and express personal limits.
* **Persona Profiles**: Extensible configuration schemas for defining character personas.

## Phase 2.1: Character Foundation
Phase 2.1 establishes the provider-independent, application-owned definition for Aevum.

### Core Architecture Principles
1. **Character Definition owns persistent identity and personality**: The LLM expresses character attributes; the LLM does not invent or redefine them.
2. **Normalized SQLite Persistence**:
   - `character_definitions`: Stable identity (`name`, `age`, `occupation`, `background`) and versioning metadata (`id`, `version`, `updated_at`).
   - `character_personality_traits`: Relational traits mapped to structured dimensions (`core_trait`, `social_style`, `emotional_style`, `communication_style`, `behavioral_tendency`, `flaw`).
   - `character_preferences`: Relational preferences with typed sentiment (`like`, `dislike`, `neutral`).
   - `character_boundaries`: Explicit behavioral boundaries and limits.
   - Zero arbitrary JSON blobs as sources of truth.
3. **Optimistic Concurrency**: `CharacterDefinitionService` enforces optimistic concurrency at the SQL execution level (`WHERE version = :expected_version`), protecting against stale writers.
4. **No LLM Integration in Phase 2.1**: `CharacterDefinition` is not yet connected to `LLMContext` or sent to Gemini. It remains strictly internal application state until the Character Engine is developed.

### Architectural Distinctions
* **Character Definition is NOT Relationship State**: Aevum's identity and baseline personality do not encode feelings towards the user, girlfriend status, or fixed affection. Relationship progression is a separate, future dynamic system (Phase 4).
* **Character Definition is NOT Emotion State**: Stable personality traits are distinct from transient emotional vectors (valence, arousal, current mood). Emotional simulation is a separate system (Phase 5).
* **Character Definition is NOT Memory**: Identity, traits, preferences, and boundaries are intrinsic to the character, not recalled dialogue transcripts or episodic memory (Phase 3).

## Phase 2.2: Character State Foundation
Phase 2.2 establishes the persistent, provider-independent representation of Aevum's mutable current condition.

### Fundamental Distinction
* **Character Definition = WHO Aevum is**: Stable baseline identity, traits, preferences, and principles.
* **Character State = HOW Aevum currently is**: Current condition, situational activity, and location.

### Core Architecture Principles
1. **Application-Owned Current State**: `CharacterState` (`app.character.state_models.CharacterState`) models mutable current condition:
   - Qualitative mood (`CharacterMood`): intentionally small and qualitative (`neutral`, `good`, `low`, `irritated`, `calm`, `tired`, `focused`).
   - Continuous physiological/cognitive indicators (`0.0 <= value <= 1.0`, rejecting NaN/inf): `energy`, `stress`, `social_energy`, `confidence`, `irritation`, `loneliness`.
   - Situational context: `current_activity`, `current_location`.
2. **Bootstrap Values**: Initial situational values (`current_activity = "resting"`, `current_location = "home"`) are deterministic bootstrap defaults and do not imply permanent activity or location. Future Life and Event systems will manage situational transitions.
3. **No Emotion Simulation in Phase 2.2**: Character State is a state container/foundation, not an emotion engine. No mood decay, emotional transitions, or causality calculations are implemented in this phase.
4. **Relational SQLite Persistence**: Persisted in `character_states` with explicit typed columns (`Float`, `String`, `Integer`, `DateTime`). Zero untyped JSON blobs.
5. **Database-Enforced Concurrency**: `CharacterStateService` executes atomic conditional updates (`WHERE version = :expected_version`), raising `CharacterStateConflictError` on stale writes.

### Architectural Boundary Guarantees
* **Character Definition ≠ Character State**: Separate models, separate tables, separate lifecycles.
* **Character State ≠ Emotion Engine**: No mood calculations or transition logic.
* **Character State ≠ Relationship State**: No user affection or attachment metrics.
* **Character State ≠ Memory**: No episodic facts or dialogue history.
* **Character State ≠ Life Simulation**: No autonomous scheduling or routine timers.

## Phase 2.3: Character State Mutation Foundation
Phase 2.3 establishes the provider-independent, application-owned mechanism through which future trusted internal systems can modify `CharacterState`.

### Core Architecture Principles
1. **Application-Owned State Mutations**: State mutations are strictly internal application operations. The LLM does not own or mutate reality.
2. **Validated Partial Updates (`CharacterStateUpdate`)**:
   - Immutable (`frozen=True`, `extra="forbid"`).
   - Validates all optional fields to match `CharacterState` constraints: continuous metrics bounded in `[0.0, 1.0]` (rejecting `NaN`/`inf`), strings non-empty, mood validated via `CharacterMood`.
   - Empty updates (no fields specified) are explicitly rejected.
3. **Atomic Selective Replacement (`apply_update`)**:
   - Merges supplied fields with existing canonical values while strictly preserving unspecified fields.
   - Reuses existing `character_states` table (zero new tables).
   - Increments `version` exactly once and updates `updated_at` to current UTC timestamp.
4. **Database-Enforced Optimistic Concurrency**:
   - Concurrency is enforced at the SQL execution level (`WHERE version = :expected_version`).
   - Stale writers encounter `CharacterStateConflictError` with expected vs actual versions.
5. **Strict Subsystem Isolation**:
   - Zero public HTTP endpoints.
   - Zero LLM prompt injection or extraction.
   - Zero emotion dynamics, life scheduling, event loops, or relationship modifications.



