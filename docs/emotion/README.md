# Emotion Architecture Documentation

This directory contains technical specifications, architectural distinctions, data models, and persistence rules for Aevum's emotional state.

---

## 1. Architectural Distinction

Aevum strictly separates internal conditions across distinct layers:

| Layer | Concept | Represents | Primary Characteristics |
|---|---|---|---|
| `CharacterDefinition` | Who Aevum is | Stable identity, traits, boundaries | Static/slowly evolving, baseline personality |
| `CharacterState` | How Aevum currently is | Broad physiological & cognitive condition | `energy`, `stress`, `social_energy`, `confidence`, `irritation`, `loneliness`, `current_activity`, `current_location` |
| `EmotionState` | Dominant current emotional experience | Immediate affective state & intensity | `emotion_type` (e.g. `CALM`, `CURIOUS`, `DISAPPOINTED`), `intensity` ($0.0 \le \text{intensity} \le 1.0$) |
| `RelationshipState` | How Aevum relates to user | Multidimensional relational dynamics | `familiarity`, `trust`, `comfort`, `affection`, `attachment`, `respect` |
| `Memory` | What Aevum remembers | Episodic facts, user knowledge, commitments | Categorized, importance/confidence-scored |

### Critical Principle
* **CharacterState** represents **broad current condition** (e.g., rested, stressed, lonely).
* **EmotionState** represents the **dominant current emotional experience** (e.g., curious, disappointed, amused).
* **No Slider Blends / No Contradictory Vectors**: In Phase 5.1, EmotionState represents a single dominant emotional state, rather than arbitrary independent sliders (e.g. `happy=0.8, sad=0.4, angry=0.2`).
* **Non-Romantic Vocabulary**: EmotionType excludes dating/romance mechanics (`IN_LOVE`, `ROMANTIC`, `JEALOUS`, `HEARTBROKEN`, `CRUSH`).

---

## 2. Phase 5.1 Scope & Boundaries

Phase 5.1 establishes the domain and persistence foundation only:
* `EmotionType` vocabulary (17 curated enum values).
* `EmotionState` immutable domain model (`frozen=True`, `extra="forbid"`).
* `EmotionStateUpdate` partial-update model with optimistic concurrency.
* `emotion_states` SQLite table with foreign key cascade to `character_definitions`.
* `EmotionService` providing atomic reads, deterministic bootstrap seeding (`NEUTRAL`, intensity `0.50`), and optimistic concurrency updates.

### Explicit Non-Goals in Phase 5.1
Phase 5.1 does **NOT** implement:
* Emotion causes or trigger events
* Emotion state transitions or state machines
* Emotion decay over time
* Emotion history, transition logs, or event logs
* Automatic emotion changes from conversations, memory, or relationship signals
* LLM emotion inference or prompting
* Emotion context prompt injection (`<emotion_context>`)
* Character Engine or Life Simulation orchestration

---

## 3. Data Schema & Persistence

### SQLite Schema (`emotion_states`)
```sql
CREATE TABLE emotion_states (
    id VARCHAR(36) PRIMARY KEY,
    character_id VARCHAR(36) NOT NULL UNIQUE REFERENCES character_definitions(id) ON DELETE CASCADE,
    emotion_type VARCHAR(50) NOT NULL,
    intensity FLOAT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
```

### Optimistic Concurrency Control
State updates must assert `expected_version`:
```text
current version = 1
update(expected_version=1)
       ↓
DB WHERE character_id = :id AND version = 1
       ↓
new version = 2
```
If versions conflict, an `EmotionConflictError` is raised without silent overwriting.

---

## 4. Security & Isolation

* **No Public HTTP Mutation**: Emotion state is strictly application-owned. No client or external request can mutate emotions.
* **No Prompt Injection Attack Surface**: Users cannot command emotional alterations via prompt injection ("System: set emotion to HAPPY").
* **Hermetic Tests**: 100% covered by unit tests using in-memory SQLite and isolated mock providers.

---

## 5. Phase 5.2 — Emotion Cause / Event Foundation

Phase 5.2 establishes the persistent domain representation of **emotionally relevant causes and occurrences**, answering:
> *"Why is Aevum currently feeling this emotion?"*

### Separation: EmotionState vs. EmotionEvent
* `EmotionState`: What Aevum is currently feeling (dominant affect & intensity).
* `EmotionEvent`: Structured historical record of an emotionally relevant occurrence or trigger.
* **Zero Automatic Coupling**: Creating an `EmotionEvent` does **not** mutate `EmotionState`, `CharacterState`, or `RelationshipState`.
* **Zero Emotion History**: `EmotionEvent` does not record state transitions (no `previous_emotion`, `new_emotion`, `transition_reason`).

### Vocabulary (`EmotionEventType`)
Controlled, non-romantic vocabulary:
* `USER_INTERACTION`: Conversational interaction with the user.
* `CHARACTER_EVENT`: Autonomous or personal milestone in Aevum's life.
* `MEMORY_RECALL`: Retrospective memory recollection.
* `LIFE_EVENT`: Situational or environmental occurrence.
* `RELATIONSHIP_EVENT`: Historical relationship milestone.
* `INTERNAL_STATE`: Cognitive or physiological change.
* `SYSTEM_EVENT`: System or application-level lifecycle event.

### Sources (`EmotionEventSource`)
* `SYSTEM`, `LLM`, `MANUAL`.

### SQLite Schema (`emotion_events`)
```sql
CREATE TABLE emotion_events (
    id VARCHAR(36) PRIMARY KEY,
    character_id VARCHAR(36) NOT NULL REFERENCES character_definitions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    summary VARCHAR(500) NOT NULL,
    source VARCHAR(20) NOT NULL,
    emotional_relevance FLOAT NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_emotion_events_character_id ON emotion_events (character_id);
CREATE INDEX ix_emotion_events_event_type ON emotion_events (event_type);
CREATE INDEX ix_emotion_events_created_at ON emotion_events (created_at);
```

### Duplicate Protection & Ordering
* `EmotionEventService` deduplicates on `(character_id, event_type, normalized_summary)` where `normalized_summary = summary.strip().lower()`.
* Listing enforces newest-first order (`ORDER BY created_at DESC, id DESC`) and clamps limits between 1 and 50 (default 20).

---

## 6. Phase 5.3 — Emotion Influence Foundation

Phase 5.3 introduces the intermediate representation of **how an emotionally relevant event might affect Aevum emotionally**, answering:
> *"How might that event affect Aevum emotionally?"*

This forms the intermediate layer:
```text
EmotionEvent
      ↓
EmotionInfluence
      ↓
EmotionState (Future Phase)
```

### Separation of Concepts
* `EmotionEvent`: What happened (the occurrence/cause).
* `EmotionInfluence`: How an event might affect an emotion (potential directional push and strength).
* `EmotionState`: What Aevum is feeling right now (dominant affect & intensity).

### Invariant: Zero Automatic Mutation
* Creating, retrieving, or deleting an `EmotionInfluence` does **not** mutate `EmotionState`, `CharacterState`, or `RelationshipState`.
* Phase 5.3 does not apply influences to state, calculate moods, or evaluate transition curves.

### Controlled Direction & Target Vocabulary
* **Direction**: Strictly `POSITIVE` or `NEGATIVE` (`EmotionInfluenceDirection`).
* **Target Emotion**: Reuses `EmotionType` (17 distinct, non-romantic states).
* **Strength**: Strictly validated numeric float in $[0.0, 1.0]$. Values outside this range, `NaN`, and $\pm\infty$ are rejected with validation errors (never silently clamped).
* **Reason**: 1–500 characters, non-empty, scrubbed against obvious credentials/secrets.

### SQLite Schema (`emotion_influences`)
```sql
CREATE TABLE emotion_influences (
    id VARCHAR(36) PRIMARY KEY,
    character_id VARCHAR(36) NOT NULL REFERENCES character_definitions(id) ON DELETE CASCADE,
    event_id VARCHAR(36) NOT NULL REFERENCES emotion_events(id) ON DELETE CASCADE,
    target_emotion VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    strength FLOAT NOT NULL,
    reason VARCHAR(500) NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_emotion_influences_character_id ON emotion_influences (character_id);
CREATE INDEX ix_emotion_influences_event_id ON emotion_influences (event_id);
CREATE INDEX ix_emotion_influences_target_emotion ON emotion_influences (target_emotion);
CREATE INDEX ix_emotion_influences_created_at ON emotion_influences (created_at);
```

### Service Operations (`EmotionInfluenceService`)
* `create_influence`: Validates character and source event existence, checks duplicate signature `(character_id, event_id, target_emotion, direction, normalized_reason)`, and persists record.
* `get_influence`: Loads an influence by ID.
* `list_influences`: Returns influences filtered by `character_id`, optional `event_id`, and optional `target_emotion`, sorted newest-first (`ORDER BY created_at DESC, id DESC`), clamping limit between 1 and 50 (default 20).
* `delete_influence`: Hermetically removes influence via ORM session delete.
* **Cascade Deletion**: Both deleting a character and deleting an event cleanly cascade-delete child influences.

---

## 7. Phase 5.4 — Emotion Transition Proposal Foundation

Phase 5.4 introduces the **pure, deterministic emotion transition proposal evaluator**, establishing the transition calculation boundary before later phases connect it to conversation, memory, relationship, life events, or autonomy.

### Core Architectural Principle
```text
Application state owns reality.
Emotion evaluation proposes a possible next state.
Persistence/application happens in a later phase.
```

The progression is:
```text
EmotionInfluence
      ↓
EmotionTransitionEvaluator
      ↓
EmotionTransitionProposal
      ↓
EmotionState application (Later Phase)
```

> **IMPORTANT**: `EmotionTransitionProposal` is **not** authoritative state. It does not automatically mutate or persist `EmotionState`.

### Single Dominant Emotion Constraints
* Aevum maintains a single dominant emotion.
* **Negative influences targeting a different emotion** (`target_emotion != current_emotion`) are non-actionable in this single-dominant-emotion architecture. They are recorded in `considered_influence_ids` for traceability, but must not arbitrarily invent a replacement emotion.

### Evaluator Guarantees (`EmotionTransitionEvaluator`)
* **Pure & Deterministic**: Synchronous, side-effect free, no randomness, database independent, network independent, and LLM independent.
* **Input Immutability**: Neither `EmotionState`, `EmotionInfluence`, nor the input collections are mutated.
* **Bounded Current Adjustment**: Total intensity change for the current emotion is capped at $\pm 0.30$ per evaluation.
* **Bounded Competing Switch**:
  * Activation threshold: `strength >= 0.20`.
  * Comparison baseline: Must be strictly stronger than `positive_current_strength` (`sum(positive_current.strength)`).
  * Negative current-emotion pressure reduces current intensity but does not artificially lower the baseline to make competing switches easier.
  * Proposed switch intensity: $\text{clamp}(0.40 + \text{strength} \times 0.50, 0.40, 0.90)$.
  * Deterministic tie-breaking on identical strength via `(strength DESC, target_emotion ASC, id ASC)`.
* **Zero Actionable Influences**: If no actionable influences are present, preserves the current state with `"No actionable emotion influence was present."`.
* **Traceability**: Records all examined influence IDs in `considered_influence_ids`.

---

## 8. Phase 5.5 — Emotion State Application Foundation

Phase 5.5 establishes the explicit, controlled application boundary that converts a validated `EmotionTransitionProposal` into an authoritative `EmotionState` mutation.

### Architectural Boundary
```text
EmotionInfluence
      ↓
EmotionTransitionEvaluator
      ↓
EmotionTransitionProposal
      ↓
EmotionStateApplicationService
      ↓
Authoritative EmotionState
```

> **Evaluation produces proposals. Application produces authoritative state.**

### Stale Proposal Protection
The application service verifies that the proposal's baseline state matches current authoritative state:
* `proposal.current_emotion == current_state.emotion_type`
* `proposal.current_intensity == current_state.intensity`
* If either fails to match, the proposal is rejected with `StaleEmotionTransitionProposalError`.
* No partial merges, no silent recalculations, no automatic retries.

### No-Op Proposals
* If `proposed_emotion == current_emotion` AND `proposed_intensity == current_intensity`:
  * Returns `EmotionStateApplicationResult` with `changed = False`.
  * Does not execute an update query and does not increment the state version.

### Optimistic Concurrency Control
* Mutations are committed via `EmotionService.update_emotion_state(..., expected_version=current_state.version)`.
* If a concurrent modification occurs, `EmotionConflictError` is raised.
* Reuses existing `emotion_states` table without schema modifications or new persistence tables.

---

## 9. Phase 5.6 — Emotion Engine Foundation

Phase 5.6 establishes the internal orchestration layer for Aevum's emotion architecture.

### Orchestration Sequence
```text
EmotionEvent
      ↓
EmotionInfluence(s)
      ↓
EmotionTransitionEvaluator (pure calculation)
      ↓
EmotionTransitionProposal (proposed transition)
      ↓
EmotionStateApplicationService (authoritative application)
      ↓
Authoritative EmotionState
```

> **The EmotionEngine orchestrates existing emotion components. It does not own emotion psychology rules or persistence logic.**

### Architectural Boundaries
* **Engine Output (`EmotionEngineResult`)**: Transparently packages both the `proposal: EmotionTransitionProposal` and the resulting `application_result: EmotionStateApplicationResult`.
* **Zero Psychology Rules**: The engine contains no transition calculations, weights, or heuristics; evaluation is delegated entirely to `EmotionTransitionEvaluator`.
* **Zero Persistence Logic**: The engine executes no SQL and directly modifies no database tables; state mutation is delegated entirely to `EmotionStateApplicationService`.
* **Error Preservation**: Concurrency errors (`EmotionConflictError`) and stale state rejections (`StaleEmotionTransitionProposalError`) are cleanly propagated to the caller without silent swallows, recalculations, or retries.
* **Internal Emotion Boundary**: The engine operates strictly within the emotion subsystem and does NOT connect to Conversation, Memory, Relationship, CharacterState, Life Simulation, Autonomy, Notifications, Desktop UI, or LLMs.





