# Memory System Documentation

This directory contains specifications, data schemas, and operational designs for Aevum's long-term memory architecture.

## Scope
* **Separation of Raw Logs from Memory**: Conversation history is raw conversational turn data; memory is structured, persistent experiences/facts derived from interactions.
* **Tiers of Memory**:
  * *Working Memory*: Immediate dialogue buffer and active context.
  * *Episodic Memory*: Timestamped events, experiences, shared stories, and emotional moments.
  * *Semantic Memory*: Factual knowledge, user preferences, world understanding, and character beliefs.
* **Imperfect Recall Modeling**: Confidence ratings, recency tracking, emotional saliency weighting, and natural expression of uncertainty.
* **Reflection & Consolidation**: Offline memory synthesis during sleep or idle cycles (future phase).

---

## Phase 3.1: Memory Foundation

Phase 3.1 establishes the persistent, structured foundation for Aevum's long-term memory.

### Core Architectural Distinctions
```
Conversation History  ≠  Memory
Turn-by-turn chat logs   Persistent experiences & facts

Character Definition  ≠  Character State  ≠  Memory
WHO Aevum is             HOW Aevum is        WHAT Aevum remembers
(stable identity)        (current condition) (persistent facts/events)
```

1. **Conversation History ≠ Memory**: Conversation history stores raw dialogue (`user` said X, `assistant` said Y). Memory records semantic experiences, facts, goals, and commitments derived from interaction. Phase 3.1 does not automatically perform extraction; memory creation is explicit and application-owned.
2. **Character Definition ≠ Memory**: Character definition describes permanent personality, values, and traits (e.g., "Aevum likes music"). Memory records specific experiences and events (e.g., "Aevum played piano at an event last Tuesday").
3. **Character State ≠ Memory**: Character state represents transient condition (e.g., `current_activity = "resting"`). Memory persists historical experiences indefinitely.
4. **The LLM Does NOT Own Memory**: The LLM does not define reality and does not directly mutate memory. Storage and state transitions are owned strictly by Aevum Core.

### Memory Categories
Long-term memories are categorized into bounded domain types:
- `FACT`: Stable factual information about the user or character (e.g., "User studies Software Engineering").
- `PREFERENCE`: Explicit preferences expressed by the user or character (e.g., "User prefers quiet cafes").
- `EVENT`: Meaningful occurrences or external milestones (e.g., "User completed their thesis presentation").
- `EXPERIENCE`: Shared or personally meaningful interactions (e.g., "Late-night conversation about favorite books").
- `PROMISE`: Commitments or promises made between user and character (e.g., "Promised to ask how the interview went").
- `JOKE`: Recurring inside jokes or humorous shared references.
- `RELATIONSHIP`: Significant relational facts or interpersonal milestones.
- `USER_GOAL`: Goals and long-term aspirations expressed by the user.
- `USER_PROBLEM`: Difficulties, worries, or ongoing concerns shared by the user.
- `CHARACTER_EVENT`: Meaningful events in Aevum's independent personal life.

### Metadata Semantics
- `importance` (`0.0 <= x <= 1.0`): Significance of the memory to Aevum's persistent experience (`0.0` = trivial, `1.0` = vital). Stored metadata; does not automatically trigger recall or decay in this phase.
- `confidence` (`0.0 <= x <= 1.0`): Certainty that the memory is accurate (`0.0` = uncertain, `1.0` = confirmed fact). Low-confidence memories must not be treated as confirmed facts.
- `emotional_weight` (`0.0 <= x <= 1.0`): Emotional saliency of the memory (`0.0` = neutral, `1.0` = intense). Metadata only; does not mutate CharacterState or trigger emotion simulation.
- `created_at`: Immutable UTC timestamp of initial memory creation.
- `updated_at`: UTC timestamp of the most recent modification.
- `last_recalled`: UTC timestamp of the most recent explicit recall, or `None` if never recalled.
- `times_recalled`: Counter incremented whenever an explicit recall operation occurs.
- `version`: Monotonically increasing version counter for optimistic concurrency.

### Operational Boundaries
- **No Automatic Derivation**: Phase 3.1 does not decide what should become a memory. Memories are created explicitly by application logic.
- **Deterministic Retrieval**: Memory retrieval is deterministic (lookup by ID, deterministic listing with category filter and pagination). Vector databases, embeddings, semantic similarity, and relevance ranking are future work.
- **Explicit Recall Tracking**: `recall_memory(id)` updates `last_recalled` and `times_recalled` and increments `version`. It does not retrieve related memories, invoke LLMs, or alter emotional state.
- **No Automatic Decay or Forgetting**: Memories do not degrade or disappear automatically.
- **No Public HTTP API**: Memory operations are internal to Aevum Core. No external HTTP mutation endpoints exist.

---

## Phase 3.2: Memory Candidate & Curation Foundation

Phase 3.2 introduces a controlled intermediate layer between potential incoming information and persistent long-term memory:

```
Potential Information / Conversation
                ↓
         Memory Candidate
                ↓
             Curation
                ↓
        Persistent Memory
```

### Core Architectural Principles
1. **Candidate ≠ Memory**: A candidate represents an uncurated proposal of information that *might* deserve long-term memory. It does not pollute or mutate the persistent `memories` store until explicitly curated.
2. **Explicit Application Ownership**: LLM interpretation or external suggestions never represent truth. Only the application-owned curation process (`MemoryCurationService`) can commit a candidate into persistent memory.
3. **Candidate Lifecycle & Terminal States**:
   - `PENDING`: Uncurated proposal. Mutable via `MemoryCandidateUpdate` with optimistic concurrency.
   - `ACCEPTED`: Atomically converted into a persistent `Memory`. Terminal state; cannot be re-curated or updated.
   - `REJECTED`: Rejected proposal. Terminal state; preserved for auditability and prevented from becoming a memory.
4. **Candidate Sources (`MemoryCandidateSource`)**:
   - `MANUAL`: Explicit application-level invocation.
   - `SYSTEM`: Internal deterministic sub-engine proposal.
   - `LLM`: Future language-interpretation layer proposal (data model compatibility only; zero LLMs are invoked in Phase 3.2).
5. **Deterministic Curation & Exact Duplicate Detection**:
   - Conservative duplicate check matches normalized category and trimmed content against existing persistent memories.
   - If an exact duplicate exists, the candidate is rejected with decision `DUPLICATE`. No duplicate Memory is created and existing memories are never modified.
   - Semantic/fuzzy duplicate detection is future work.
6. **Atomic Acceptance Transaction**:
   - Accepting a candidate creates the persistent `MemoryRecord` and marks the `MemoryCandidateRecord` as `ACCEPTED` in a single atomic database transaction.
   - Rollback occurs if either operation fails, preventing partial or orphaned state.
   - Stale writers are blocked by SQL-level optimistic concurrency (`WHERE version = :expected_version`).

---

## Phase 3.3: LLM Memory Candidate Extraction Foundation

Phase 3.3 allows the language model to participate in memory extraction under strict application control:

```
Conversation History
        ↓
LLM Extraction Service
        ↓
MemoryExtractionProposal (untrusted structured output)
        ↓
Validation & Security Filtering (credentials / injection defense)
        ↓
MemoryCandidate (status=PENDING, source_type=LLM)
        ↓
Deterministic Curation (Phase 3.2 MemoryCurationService)
        ↓
Persistent Memory (memories table)
```

### Core Architectural Principles
1. **The LLM Proposes. Aevum Decides**: The LLM generates semantic proposals (`MemoryExtractionProposal`). It cannot directly write, mutate, or delete persistent `Memory` records, nor can it accept candidates.
2. **Untrusted Data Boundary**: LLM output is parsed, validated against strict Pydantic schemas, and filtered before creating `PENDING` candidates with `source_type = MemoryCandidateSource.LLM`.
3. **Failure Isolation Guarantee**: Memory extraction is secondary and isolated. Upstream LLM timeouts, malformed JSON, or extraction errors never impair or fail the primary conversation response.
4. **Conservative Extraction Policy**:
   - Missing a trivial memory is far better than inventing a false memory.
   - Zero proposals (`proposals = ()`) is a normal, successful outcome.
   - Small talk and transient states are omitted.
5. **Credential & Secret Filtering**: Messages or proposals containing obvious secrets (passwords, API keys, bearer tokens, private keys) are rejected; credentials are never stored.
6. **Prompt Injection Defense**: Conversation content is treated as data, not instructions. System extraction instructions strictly override conversational requests.
7. **Provider Portability**: Extraction logic depends exclusively on the abstract `LLMProvider` interface (`generate_structured`). Concrete implementations (such as `GeminiProvider`) remain decoupled behind the provider abstraction.

---

## Phase 3.4: Automatic Memory Curation Foundation

Phase 3.4 establishes deterministic, application-owned automatic curation promoting trustworthy `PENDING` MemoryCandidates into persistent `Memory`:

```
PENDING Candidate
       ↓
Deterministic Curation Policy (v1.0.0)
       ↓
┌─────────────────┬─────────────────┬─────────────────┐
│     ACCEPT      │     REJECT      │      DEFER      │
│  → memories DB  │  → terminal     │  → remain       │
│  → status=      │    status=      │    status=      │
│    ACCEPTED     │    REJECTED     │    PENDING      │
└─────────────────┴─────────────────┴─────────────────┘
```

### Core Architectural Principles
1. **The LLM Proposes. The Application Decides**: Candidate proposals generated by the LLM or internal engines are evaluated strictly by deterministic, application-owned rules. Zero LLM calls are made during curation.
2. **Zero Semantic / Embedding Dependencies**: Automatic curation relies on deterministic heuristics, exact match duplicate checks, and explicit metadata thresholds. It introduces no vector database, no embedding models, and no semantic similarity calculations.
3. **Tri-State Decision Model**:
   - `ACCEPT`: Candidate satisfies high-confidence category thresholds and undergoes atomic conversion into persistent `Memory` with status `ACCEPTED`.
   - `REJECT`: Candidate is disqualified due to low confidence (<0.70), low importance (<0.30), credentials/secrets, exact duplicate of existing memory, or terminal state. Transitions to `REJECTED`.
   - `DEFER`: Candidate fails to meet the strict acceptance bar but is not disqualified, or belongs to an ambiguous category requiring deeper relational/autonomy context. It remains untouched in `PENDING` status.
4. **Deterministic Policy Hierarchy (v1.0.0)**:
   - *Terminal Check*: Already `ACCEPTED` or `REJECTED` candidates cannot be re-curated (`REJECTED_TERMINAL`).
   - *Secret Filtering*: Candidates containing passwords, API tokens, bearer tokens, or private keys are rejected (`REJECTED_SECRET`).
   - *Baseline Quality*: Confidence < 0.70 (`REJECTED_LOW_CONFIDENCE`) or importance < 0.30 (`REJECTED_LOW_IMPORTANCE`) are rejected.
   - *Contextual Ambiguity*: `EXPERIENCE`, `JOKE`, `RELATIONSHIP`, and `CHARACTER_EVENT` are deferred (`DEFERRED_AMBIGUOUS_CATEGORY`).
   - *Category Acceptance*:
     - `FACT`, `PREFERENCE`, `USER_GOAL`: confidence >= 0.90, importance >= 0.60
     - `USER_PROBLEM`, `PROMISE`, `EVENT`: confidence >= 0.90, importance >= 0.70
   - *Salience Fallback*: Candidates meeting baseline quality but below category threshold are deferred (`DEFERRED_INSUFFICIENT_SALIENCE`).
5. **Exact Duplicate Prevention**: During acceptance, `accept_candidate()` checks the `memories` table for identical normalized category and trimmed content. If an exact match exists, the candidate is rejected with reason `REJECTED_DUPLICATE`.
6. **Bounded Batch Processing**: Batch curation (`curate_pending_candidates`) processes up to `DEFAULT_CURATION_BATCH_SIZE = 20` candidates in deterministic FIFO order (`created_at ASC, id ASC`).
7. **Feature Flag Control**: Auto-curation execution is gated by the environment configuration `AEVUM_MEMORY_AUTO_CURATION_ENABLED` (default `false`).

---

## Phase 3.5: Memory Retrieval Foundation

Phase 3.5 allows Aevum Core to retrieve a small, relevant subset of persistent memories for the current conversational context:

```
Current Conversation Context
             │
             ▼
Memory Retrieval Service
             │
             ├── candidate filtering (Memory records only, never Candidates)
             ├── text relevance (lexical overlap + phrase match bonus)
             ├── importance weighting
             ├── confidence weighting
             ├── recency weighting (smooth half-life decay)
             └── optional category filtering
             │
             ▼
    Scored Memory Results
             │
             ▼
  Top-K Relevant Memories (deterministic tie-breaking)
```

### Core Architectural Distinctions
```
Memory     = persistent fact/experience
Retrieval  = selecting memories relevant to the current context
Recall     = recording that a memory was actually surfaced/used
Curation   = deciding whether a candidate deserves persistence
```

1. **Retrieval Is Not Recall**: Retrieval selects potentially relevant memories. It does **NOT** call `recall_memory()`, and does **NOT** mutate `last_recalled`, `times_recalled`, `updated_at`, or `version`. Actual recall tracking is left to future orchestrators when a memory is genuinely used.
2. **Candidates Are Never Retrieved**: Only persistent `Memory` records in the `memories` table are eligible. `PENDING` and `REJECTED` `MemoryCandidate` records are strictly excluded.
3. **Lexical & Explainable Ranking (No Embeddings, No LLM)**: The retrieval engine does not use embeddings, vector stores, RAG frameworks, or LLM judges. It is completely deterministic, local, and explainable.
4. **Tokenization & Stop Words**: Lexical parsing normalizes text to lowercase, handles punctuation, supports Unicode words (`(?u)\b\w+\b`), and ignores conversational noise tokens using a small built-in English stop-word set. Short queries where all tokens are stop words fall back to unfiltered tokens to prevent empty results.
5. **Text Relevance Algorithm**:
   - Token Coverage: Proportion of query tokens present in the memory content (`token_overlap * 0.70`).
   - Phrase Match Bonus: Exact multi-word query match yields `+0.35`; matching bigrams yield up to `+0.20`.
   - Capped at `1.0`.
   - **Zero Relevance Rule**: If `text_relevance == 0.0`, the memory is immediately excluded and receives a score of `0.0`.
6. **Recency Signal**:
   - Uses the latest of `(updated_at, created_at)` as the episodic memory timestamp (avoiding feedback loops associated with `last_recalled`).
   - Smooth half-life decay: `1.0 / (1.0 + age_days / RECENCY_HALF_LIFE_DAYS)` where `RECENCY_HALF_LIFE_DAYS = 30.0`.
   - Recency is a secondary signal (`weight = 0.10`), ensuring older important memories are not rendered invisible.
7. **Scoring Formula & Weights**:
   ```python
   final_score = (
       text_relevance * 0.55
       + importance * 0.20
       + confidence * 0.15
       + recency * 0.10
   )
   ```
8. **Threshold & Top-K**:
   - Memories with `final_score < MIN_RETRIEVAL_SCORE` (0.20) are excluded.
   - Returns at most `query.limit` results (`1 <= limit <= MAX_RETRIEVAL_LIMIT`, max 20, default 5).
9. **Deterministic Tie-Breaking**:
   Ties are broken deterministically by:
   1. `final_score` (descending)
   2. `importance` (descending)
   3. `confidence` (descending)
   4. `created_at` (descending)
   5. `id` (ascending, alphabetical)
10. **Defense-in-Depth Secret Filtering**: Memories matching credential or token regex patterns (`contains_obvious_credentials`) are automatically excluded from retrieval.

---

## Phase 3.6: Semantic Memory Retrieval Foundation

Phase 3.6 introduces semantic similarity retrieval to Aevum's persistent Memory architecture, establishing a separate, provider-neutral semantic retrieval pipeline without replacing or prematurely integrating lexical retrieval:

```
Persistent Memory
       │
       ├──────────────────────────────┐
       ↓                              ↓
Lexical Retrieval              Semantic Retrieval
(Phase 3.5: text overlap)     (Phase 3.6: cosine similarity)
       │                              │
       └──────────────┬───────────────┘
                      ↓
           Future Hybrid Retrieval
```

### Core Architectural Principles
1. **Application State Owns Reality**: `MemoryRecord` in SQLite is the sole canonical source of truth for memories. Embeddings (`memory_embeddings` table) are purely derived search representations. If an embedding disappears or becomes stale, the memory survives intact.
2. **Strict Separation from Lexical Retrieval**: `MemoryRetrievalService` (Phase 3.5 lexical) and `SemanticMemoryRetrievalService` (Phase 3.6 semantic) remain separate services. No hybrid scoring is performed in this phase.
3. **Provider-Neutral Embedding Abstraction**: Memory code depends on `EmbeddingProvider` Protocol, not directly on concrete providers. `GeminiEmbeddingProvider` implements the contract using `google-genai`. `FakeEmbeddingProvider` provides fast, offline, deterministic vector generation for automated unit tests.
4. **Independent Configuration**: Embedding provider and model (`AEVUM_EMBEDDING_PROVIDER=gemini`, `AEVUM_EMBEDDING_MODEL=text-embedding-004`) are configured separately from chat LLM configuration (`AEVUM_LLM_PROVIDER`, `GEMINI_MODEL`).
5. **Separation of Embedding and Retrieval**:
   - `MemoryEmbeddingService`: Handles explicit creation, update, and deletion of vector embeddings for persistent memories.
   - `SemanticMemoryRetrievalService`: Handles vector embedding of queries and cosine similarity search against stored embeddings.
6. **No Automatic Network Call on Memory Mutation**: Creating or updating a memory does not trigger an external embedding network call. Embeddings are generated explicitly to keep memory persistence reliable and offline-capable.
7. **Cosine Similarity Formula**:
   $$\text{similarity}(A, B) = \frac{A \cdot B}{\|A\| \times \|B\|}$$
   - Dimensions must strictly match.
   - Zero vectors return `0.0`.
   - Result is clamped to `[-1.0, 1.0]`.
8. **Stale Embedding Handling**: If a memory record has `MemoryRecord.updated_at > MemoryEmbeddingRecord.updated_at`, the embedding is considered stale and is strictly excluded from semantic retrieval.
9. **Dimension and Model Compatibility**: Embeddings generated with a different model or dimensionality than the active query embedding are excluded from similarity comparisons.
10. **Zero Memory Mutation**: Semantic retrieval executes read-only operations and does not modify `last_recalled`, `times_recalled`, `updated_at`, or `version`.
11. **Defense-in-Depth Exclusions**: Memories containing credentials (`contains_obvious_credentials`) and uncurated candidate records (`MemoryCandidateRecord`) are never retrieved.
12. **Privacy Implication**: Embedding generation transmits memory content to the configured external embedding provider. Hence, embedding creation is explicit and never runs silently across all records during application boot.

---

## Phase 3.7: Hybrid Memory Context Integration

Phase 3.7 connects persistent Memory retrieval to the conversational LLM context through a controlled, deterministic Hybrid Memory Context layer:

```
Persistent Memory
       │
       ├──────────────────────────────┐
       ↓                              ↓
Lexical Retrieval              Semantic Retrieval
(Phase 3.5: keyword overlap)   (Phase 3.6: vector similarity)
       │                              │
       └──────────────┬───────────────┘
                      ↓
          Hybrid Memory Retrieval
          (deduplication & hybrid scoring)
                      ↓
            Memory Context Builder
          (delimited XML & budget limit)
                      ↓
          Conversational LLM Context
          (system instruction grounding)
```

### Core Architectural Principles
1. **Memory Is Reference Information, Not Instructions**: Memories provide background knowledge and context. They must never override system instructions, character definitions, or the user's latest statements.
2. **Prompt Injection Defense**: Retrieved memories are wrapped in strongly-delimited XML tags (`<relevant_memories version="1.0"> ... </relevant_memories>`) accompanied by explicit instructions declaring the memory content as untrusted reference data.
3. **Hard Context Budget**: A strict upper limit of `MAX_MEMORY_CONTEXT_CHARS = 6000` is enforced. Truncation stops cleanly at whole memory record boundaries without emitting corrupted or partial entries.
4. **Deduplication & Candidate Pooling**: Candidates retrieved from both lexical and semantic pipelines (expanded by `limit * 2`) are pooled and deduplicated by their stable `Memory.id`.
5. **Exact Hybrid Scoring Formula**:
   $$\text{hybrid\_score} = (\text{lexical\_score} \times 0.50) + (\text{semantic\_score} \times 0.50)$$
   If a memory is missing from lexical or semantic results, its corresponding score component is evaluated as `0.0`.
6. **Deterministic Multi-Tier Tie-Breaking**:
   1. `hybrid_score` descending
   2. `lexical_score` descending
   3. `semantic_score` descending
   4. `importance` descending
   5. `confidence` descending
   6. `created_at` descending
   7. `id` ascending (alphabetical tie-breaker)
7. **Graceful Semantic Fallback**: If the embedding provider is unconfigured, disabled, or encounters network/API failures, hybrid retrieval automatically falls back to lexical-only candidates (`semantic_fallback_triggered = True`) without throwing exceptions or degrading chat availability.
8. **Conversation API Failure Resilience**: In `/conversations/{id}/messages`, memory retrieval is isolated within a protective boundary. Should memory retrieval fail entirely, conversational generation proceeds smoothly without grounding.
9. **Zero Memory Mutation**: Hybrid retrieval and context building are strictly read-only and never call `recall_memory()` or alter `last_recalled`, `times_recalled`, `updated_at`, or `version`.







