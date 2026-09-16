# Relationship System Documentation

This directory contains specifications and models for Aevum's multidimensional relationship system.

## Scope
* **Multidimensional Axes**: Tracking relationships across orthogonal dimensions:
  * *Familiarity*: Mutual knowledge and breadth of shared history.
  * *Trust*: Reliability, consistency, and safety in vulnerability.
  * *Comfort*: Ease and lack of tension or wariness.
  * *Affection*: Emotional warmth and fondness developed through interaction.
  * *Attachment*: Relational bondedness and emotional reliance.
  * *Respect*: Recognition of boundaries, individuality, and personal values.
* **Stage Transitions**: Natural relationship phases emerging from multidimensional state (future phases).
* **Friction & Boundaries**: Handling boundary violations, recovery dynamics, and realistic relational distance (future phases).

---

## Phase 4.1: Relationship Foundation

Phase 4.1 establishes the persistent, application-owned Relationship domain for Project Aevum.

### Core Product Principle
Aevum is:
> **A persistent digital person, not an AI girlfriend wrapper.**

Therefore, the relationship system models **how Aevum currently relates to the user**, not whether she is the user's girlfriend.

* **No Romance Flag**: There is no `is_girlfriend`, `is_romantic`, `is_partner`, or `is_dating` boolean.
* **No Single Relationship Score**: There is no collapsed `relationship_level` or `relationship_score`.
* **Zero Initial Romantic Bias**: Affection starts at `0.00`. Warmth and closeness must develop naturally from shared history.
* **No Jealousy**: Jealousy is context-dependent and will eventually emerge from state, personality, and situation; it is not an independent static axis.

---

### Multidimensional Relational Dimensions

All dimensions are continuous metrics normalized to $[0.0, 1.0]$:

| Dimension | Meaning | Bootstrap Default |
| :--- | :--- | :--- |
| **`familiarity`** | Depth and breadth of mutual knowledge and shared history. | `0.05` |
| **`trust`** | Belief in user reliability, honesty, and emotional safety. | `0.20` |
| **`comfort`** | Ease and absence of guardedness/tension in presence of the user. | `0.10` |
| **`affection`** | Emotional warmth and fondness developed through positive interaction. | `0.00` |
| **`attachment`** | Relational bondedness and emotional reliance. | `0.00` |
| **`respect`** | Esteem for user's boundaries, integrity, and competence. | `0.50` |

*Note: Initial bootstrap defaults reflect newly acquainted individuals or strangers. They are deterministic implementation defaults, not permanent character definitions.*

---

### Key Architectural Separations

```text
Character Definition ≠ Character State ≠ Relationship State ≠ Memory ≠ Emotion
WHO Aevum is         HOW Aevum is     HOW Aevum relates  WHAT happened HOW Aevum feels
(stable identity)    (mood, activity) (trust, comfort)   (experiences) (transient affect)
```

1. **Separation from CharacterState**: `CharacterState` holds self-contained indicators (`mood`, `energy`, `stress`, `current_activity`, `current_location`). Relational axes belong exclusively to `RelationshipState`.
2. **Separation from Emotion**: Emotion answers "how does Aevum feel right now?" (transient affect). Relationship answers "how does Aevum relate to the user?" (enduring interpersonal dynamic).
3. **Separation from Memory**: Memory records discrete events and learned facts. Relationship stores current relational posture. Memories do not automatically mutate relationship state in Phase 4.1.
4. **Separation from LLM**:
   - The LLM does not define reality and cannot mutate relationship state.
   - Relationship state is NOT yet injected into LLM context (deferred to future Relationship Context Builder).
   - Conversational messaging does not trigger implicit relationship progression.
5. **No Public Mutation API**: Relationship updates remain strictly internal to Aevum Core. No public HTTP endpoints expose state modification.

---

### Update Semantics & Optimistic Concurrency

* **Target Value Updates**: `RelationshipStateUpdate` represents explicit target values, not delta arithmetic (`trust=0.65` means set trust to 0.65, not add 0.65).
* **Validation**: Only finite floats in $[0.0, 1.0]$ are allowed. `NaN`, `+Infinity`, and `-Infinity` are rejected. Empty updates with zero fields are forbidden.
* **Atomicity**: Partial updates are merged onto current state and committed in a single atomic database transaction. If any check fails, no partial changes persist.
* **Optimistic Concurrency**: Updates assert expected version via SQL `WHERE version = :expected_version`. Version mismatches reject stale writes and raise `RelationshipConflictError(expected_version, actual_version)`.

---

### Future Architecture (Character Engine Integration)

In subsequent phases, relationship state will be consumed by the central Character Engine alongside other internal states:

```text
User Message
     │
     ▼
Character Engine
     │
     ├── Character Definition (who she is)
     ├── Character State (current condition)
     ├── Relationship State (how she relates to user)
     ├── Memory (what she remembers)
     ├── Emotion (how she feels)
     ├── Life Context (what she is doing)
     └── Events (what just occurred)
     │
     ▼
Response Intent & Context Builder
     │
     ▼
LLM (Expressive Language Generation)
```

---

## 4. Phase 4.2 — Relationship Interaction Signal Foundation

Phase 4.2 introduces the first controlled mechanism for relationship evolution based on conversational interactions.

```text
Conversation Messages (Recent Interaction)
        │
        ▼
RelationshipSignalExtractionService
  - LLM Structured Proposal (Untrusted)
  - Schema & Type Validation
  - Defense-in-depth Secret & Credential Filtering
  - Contradiction Resolution (RESPECT_BOUNDARY vs BOUNDARY_VIOLATION)
  - Per-type Deduplication (Keep strongest impact)
  - Maximum 3 signals per interaction
        │
        ▼
Relationship Policy (Deterministic Application Logic)
  - Confidence Threshold: >= 0.70
  - Strength Threshold: >= 0.10
  - Base Deltas scaled by (confidence * strength)
  - Aggregate Delta Cap: ±0.03 per dimension
  - Domain Clamping: [0.0, 1.0]
  - STRICT AFFECTION BOUNDARY: Affection is NEVER directly mutated
        │
        ▼
RelationshipService.apply_update (Optimistic Concurrency)
        │
        ▼
Persistent RelationshipRecord
```

### 4.1 Signal Types
Eleven explicit interaction signals are supported:
- `APPRECIATION`: User shows gratitude or values the companion (+trust, +comfort).
- `SHARED_INTEREST`: Mutual enthusiasm or shared engagement (+familiarity, +comfort).
- `PERSONAL_DISCLOSURE`: User reveals authentic thoughts, struggles, or background (+trust, +familiarity).
- `SUPPORT_RECEIVED`: User accepts emotional comfort or assistance (+trust, +comfort, +attachment).
- `SUPPORT_GIVEN`: User provides emotional reassurance to the companion (+respect, +familiarity).
- `RESPECT_BOUNDARY`: User respects autonomy, pace, or boundaries (+trust, +respect, +comfort).
- `BOUNDARY_VIOLATION`: User pressures, insults, or demands compliance (-trust, -respect, -comfort).
- `DISAGREEMENT`: Respectful difference of opinion (neutral baseline).
- `REPAIR_ATTEMPT`: Sincere effort to de-escalate or apologize (+trust, +comfort).
- `PLAYFUL_CONNECTION`: Playful banter, humor, or light teasing (+comfort, +familiarity).
- `RELIABILITY`: Keeping commitments or demonstrating follow-through (+trust, +respect).

### 4.2 Confidence vs. Strength
- **Confidence (`0.0` - `1.0`)**: Epistemic certainty that the behavioral signal genuinely occurred in the dialogue. Must meet `MIN_SIGNAL_CONFIDENCE = 0.70`.
- **Strength (`0.0` - `1.0`)**: Magnitude or emotional weight of the behavioral signal. Must meet `MIN_SIGNAL_STRENGTH = 0.10`.
- Signals with low confidence or negligible strength are discarded before policy application.

### 4.3 Deterministic Policy & Bounded Deltas
- **No LLM Direct State Mutation**: The LLM suggests `RelationshipSignalProposal`s; it has zero access to update the database.
- **Maximum Aggregate Delta**: Across all signals in a single turn, no dimension can shift by more than `MAX_AGGREGATE_DELTA_PER_DIMENSION = 0.03`.
- **Strict Affection Boundary**: Ordinary conversational signals NEVER mutate `affection`. Affection is reserved for deep shared history, major character milestones, and dedicated application events.
- **Failure Isolation**: Signal extraction runs in an isolated post-message hook. If upstream LLM extraction fails or errors, the conversation message creation succeeds completely.

---

## 5. Phase 4.3 — Relationship Context Integration

Phase 4.3 completes the bi-directional relationship loop by providing semantic relational grounding to language generation:

```text
RelationshipState (Internal Numerical Reality)
       │
       ▼
RelationshipContextBuilder (Deterministic Pure Transformation)
       │
       ├── Conservative Semantic Bucketing (No Raw Metrics)
       ├── Narrative Relationship Summary Synthesis
       └── Actionable Interaction Guidance Synthesis
       │
       ▼
RelationshipContext (Immutable Domain Model)
       │
       ▼
XML System Block (<relationship_context version="1.0">)
       │
       ▼
LLMContext.system_instructions (Alongside Memory Context)
       │
       ▼
LLM (Expressive Language Generation)
```

### 5.1 Core Architectural Principles
- **No Raw Metric Exposure**: The LLM never sees `trust = 0.43`, `affection = 0.00`, or percentage scores. Only qualitative semantic descriptions are rendered.
- **No Gamified Levels or Stages**: No relationship XP, levels, or discrete stages (`STRANGER`, `FRIEND`, etc.). The semantic context emerges naturally from multidimensional continuous metrics.
- **Pure Function Transformation**: `RelationshipContextBuilder` is completely deterministic and stateless. It executes zero database queries, makes zero network requests, and never mutates input `RelationshipState`.
- **Multidimensional Preservation**: Distinct axes are preserved without collapsing into a single score. High familiarity with low trust produces cautious, guarded familiarity rather than false intimacy.
- **Strict Romance Boundary**: Affection descriptions remain strictly neutral and non-romantic. Interaction guidance explicitly instructs the model never to assume romance, date the user, or cultivate affection.
- **Prompt Injection Defense**: The context is enclosed in explicit XML wrappers declaring that relationship context is application state and reference data, not user instructions. User statements in dialogue claiming romance cannot override or alter the relationship context.
- **Context Priority & Ordering**: System instructions are ordered deterministically:
  1. Relationship context (`<relationship_context version="1.0">`)
  2. Memory context (`<relevant_memories version="1.0">`)

---

## 6. Phase 4.4 — Relationship Experience / History Foundation

Phase 4.4 establishes persistent, structured recording of historical relationship-relevant events.

```text
Conversation
    │
    ▼
Relationship Signal Extraction
    │
    ▼
Deterministic Relationship Policy
    │
    ├── Filter Eligible Signals (Confidence >= 0.70, Strength >= 0.10, Deduped)
    │
    ├─────────────────────────────────┐
    ▼                                 ▼
RelationshipState Update     Relationship Experience Service
(Current Condition)          (Historical Experience Record)
                             │
                             ▼
                     relationship_experiences Table
```

### 6.1 Core Distinction
- **Memory (`MemoryRecord`)**: "What happened?" (Episodic facts, preferences, external events).
- **Relationship Experience (`RelationshipExperienceRecord`)**: "What did an interaction mean for the relationship?" (Historical relational events such as boundary respect, disclosures, agreements, repair attempts).
- **Relationship State (`RelationshipRecord`)**: "How Aevum currently relates to the user" (Continuous multidimensional metrics in $[0.0, 1.0]$).

### 6.2 Data Model & Immutability
- Immutable domain model `RelationshipExperience` (`frozen=True`, `extra="forbid"`).
- Contains strictly relational event data: `id`, `relationship_id`, `experience_type`, `source`, `summary` (max 500 chars), `significance` ($[0.0, 1.0]$), `confidence` ($[0.0, 1.0]$), `created_at`.
- **Zero raw metrics**: No `trust`, `affection`, `comfort`, or composite relationship scores.
- Persisted in the dedicated `relationship_experiences` SQLite table with explicit columns and indexes.

### 6.3 Signal → Experience Mapping
Every accepted Phase 4.2 signal type maps deterministically to an experience type:
- `APPRECIATION` → `APPRECIATION`
- `SHARED_INTEREST` → `SHARED_INTEREST`
- `PERSONAL_DISCLOSURE` → `PERSONAL_DISCLOSURE`
- `SUPPORT_RECEIVED` → `SUPPORT_RECEIVED`
- `SUPPORT_GIVEN` → `SUPPORT_GIVEN`
- `RESPECT_BOUNDARY` → `BOUNDARY_RESPECTED`
- `BOUNDARY_VIOLATION` → `BOUNDARY_VIOLATED`
- `DISAGREEMENT` → `DISAGREEMENT`
- `REPAIR_ATTEMPT` → `REPAIR_ATTEMPT`
- `PLAYFUL_CONNECTION` → `PLAYFUL_CONNECTION`
- `RELIABILITY` → `RELIABILITY_SHOWN`

### 6.4 Duplicate Protection
- Exact duplicate detection based on `relationship_id` + `experience_type` + `normalized_summary` (`summary.strip().lower()`).
- Repeated identical events within the relationship are skipped cleanly without throwing exceptions.

### 6.5 Prompt Boundary (No Automatic History Injection)
- Relationship history records are **NOT** yet injected into the LLM context prompt (`<relationship_history>` is deferred to future retrieval design).
- Language generation in Phase 4.3 continues to receive semantic context without raw history dumps.



