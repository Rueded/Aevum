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

* **Status**: Accepted (2026-09-23), Superseded in part by ADR-016
* **Context**: The `WorldFactsSelector` must select objective world facts relevant to the current user turn without performing semantic retrieval or embedding lookups, which would introduce LLM dependency into the reality assembly pipeline.
* **Decision**: Selection is strictly lexical: token-set intersection for Latin/single-char tokens, plus verbatim CJK alias substring match for multi-character Chinese phrases. No embedding, no NLP, no fallback to registry insertion order. Unmatched input returns `{}`.
* **Consequences**:
  * Deterministic, auditable, zero-latency selection.
  * Maximum 4 items returned, sorted deterministically by key.
  * Only `STATIC_FACT` and `ENTITY_RELATION` kinds are eligible — `PLAUSIBILITY_RULE` and `TEMPORAL_RULE` are always excluded.

---

## ADR-016: Pure Structural Boundary Matching & Concurrent Promotion Idempotency (Phase 7D.6)

* **Status**: Accepted & Frozen (2026-09-23)
* **Context**:
  1. `WorldFactsSelector` exhibited false positives on ASCII aliases lacking discrete word boundaries (e.g. `"sparkles"` matching `"kl"`) and 2-character CJK aliases crossing compound boundaries (e.g. `"道理大家都懂"` matching `"理大"`).
  2. `GC-090` exposed an authentic database race: concurrent tasks calling `BiographyPromotionService.promote_candidate()` collided at `CharacterCoreService.set_fact()` (Step 5) with an unhandled SQLite `IntegrityError` on `character_core_facts(character_id, fact_key)` before reaching the promotion record insertion at Step 7.
* **Decision**:
  1. **Pure Structural Boundary Matching Contract (Decision A.1)**:
     - **ASCII / Latin aliases**: Enforce discrete word boundaries via token-set intersection or regex `\b{alias}\b`. Substring hits within longer words (e.g. `sparkles`, `checklist`) are strictly rejected; standalone `KL` matches.
     - **CJK aliases $\ge 3$ characters**: Verbatim substring matching permitted. Does *not* guarantee zero false-positives across all complex compound concatenations (acknowledged known limitation). Zero external NLP, zero embeddings.
     - **CJK aliases $\le 2$ characters**: Pure structural boundary contract. Requires at least one boundary (left or right) to touch a structural delimiter: text start (`start == 0`), text end (`end == len(text)`), whitespace, punctuation, or non-CJK character (e.g. `"理大的校园很漂亮"`, `"今天在理大，借了一本书"`). If both sides are continuous CJK characters, the occurrence is conservatively rejected as an embedded sub-compound (e.g. `"道理大家都懂"` $\to$ `{}`).
     - **Zero Heuristics & Zero Lexicon Invariant**: Zero alias-specific `if` branches, zero `_KNOWN_CROSS_COMPOUNDS`, zero character whitelist/blacklist, zero particle/auxiliary heuristics. Continuous-Hanzi tokenization is not simulated; full segmentation capability is formally deferred.
  2. **Single Atomic Transaction & Gated Replay Recovery (Decision B.1)**:
     - Atomicity belongs strictly to `BiographyPromotionService.promote_candidate()`. `CharacterCoreService.set_fact()` adds `auto_commit: bool = True` (defaults to True for caller backwards compatibility; uses `flush()` when False).
     - Inside `promote_candidate()`, Steps 5, 6, and 7 are staged via `flush()` and committed in a single atomic transaction.
     - **Exception Scope Enforcement**: Only `IntegrityError` enters concurrent replay recovery verification (5 conditions: existing promotion record, candidate ID match, character ID match, canonical core fact match, and semantic consistency). All other `Exception` types trigger immediate rollback and re-raise without attempting replay reconciliation.
  3. **Legacy 7B.3 Retirement Policy (Decision C)**:
     - Maintained deferred retirement per ADR-014. Runtime path is disconnected, but `CandidateFact` compatibility adapter and historical test suites remain intact.
* **Consequences**:
  * Eliminates verified false positives in `WorldFactsSelector` while preserving structural matches (GC-141 through GC-144).
  * GC-144 acceptance contract updated to verify 2-character CJK alias matching with structural boundaries (`"理大的校园很漂亮"`, `"今天在理大，借了一本书"`).
  * `GC-090` passes with 100% reliability under concurrent stress (25/25 stress pass).
  * Full backend regression achieves 1,286 passed / 0 failed.

---

## ADR-017: Phase 8A Autonomous Life Inference Architecture & Boundary Invariants

* **Status**: Accepted & Frozen (2026-09-24)
* **Context**:
  1. Enabling Aevum to autonomously infer life facts (major, pathway, career aspiration) without LLM hallucinated state, uncontrolled cascading assumptions, or violating Phase 7 canonical reality governance.
  2. Preventing the common pitfalls of personal reality engines:
     - Unchecked cascading assumptions (snowballing).
     - Epistemic overconfidence (treating heuristic coherence scores as real-world probability, treating uncatalogued external entities as falsified).
     - Boundary leakage (proposer/evaluator directly mutating canonical reality or baking deliberative choice inputs prematurely).
* **Decision**:
  1. **Strict Decoupled 4-Stage Inference Pipeline**:
     - `InferenceOpportunityDetector` (Gatekeeper): 7 deterministic criteria, cooldown policy, Anti-Obsession Axiom, primary canonical anchor requirement. Maximum 1 slot evaluated per turn.
     - `LifeHypothesisProposer` (Plurality Proposer): Produces $2 \le k \le 4$ distinct envelopes per target slot. Zero DB access, zero network calls, zero mutation authority. Rationale string is non-epistemic.
     - `CandidateEvaluationAdapter` (Multi-Dimensional Evaluator): Calculates bounded weighted sum across HardValidity, Feasibility, ContextSupport, and CharacterAffinity. Outputs in-memory `CandidateHypothesis` with lifecycle state `GENERATED`. Emits `selection_metadata = None`.
     - `AutonomousInferenceCoordinator` (Step C2 Orchestrator): Coordinates opportunity detection, proposal, evaluation, plurality verification ($k \ge 2$), and atomic batch persistence (`session.begin_nested()`).
  2. **The Six Mandatory Architectural Invariants**:
     - **Invariant A (Unknown $\ne$ Impossible)**: Uncatalogued real-world entities retain `HardValidity = 1.0` and are quarantined (`is_quarantined = True`, `SPECULATIVE_ASSOCIATION`). Absence of knowledge is not falsification.
     - **Invariant B (Heuristic $\ne$ Probability)**: `prior_weight = 0.50` acts strictly as neutral baseline structural coherence, not a Bayesian real-world probability.
     - **Invariant C (Construction $\ne$ Persistence)**: Evaluator constructs in-memory hypotheses (`GENERATED`). Persistence into `character_candidate_facts` occurs strictly in the repository via atomic savepoints (`PERSISTED`).
     - **Invariant D (Derived $\ne$ Primary Anchor)**: Pure derived chains of `AEVUM_INFERRED` facts yield zero context support. At least one primary canonical anchor is mandatory.
     - **Invariant E & Anti-Circularity**: Downstream inferred slots (e.g. career) cannot support upstream prerequisite slots (e.g. major).
     - **Invariant F (Evaluation $\ne$ Choice $\ne$ Promotion)**: Evaluator evaluates hypotheses independently; Choice selection is a tentative deliberation; Promotion strictly requires decisive margin ($\Delta \ge 0.15$) and is governed solely by `BiographyPromotionService`.
  3. **The Four Locked Boundary Corrections**:
     - **Correction A (Choice Factor Provenance)**: Choice factor inputs are derived dynamically in Step F from canonical core facts with neutral defaults (`0.50` fits, `0.0` costs, zero arbitrary constants).
     - **Correction B (Provisional Choice $\ne$ Canonical Promotion)**: When choice margin $\Delta < 0.15$, promotion is denied. The choice remains active in non-canonical context (`<active_candidate_hypotheses>` / `<pending_choice_decisions>`) and never mutates canonical reality.
     - **Correction C (Atomic Candidate-Batch Persistence)**: Candidates for a slot are persisted as an atomic competition set. Partial DB write failure rolls back the entire batch to preserve Phase 7 Gate 6 plurality.
     - **Correction D (Single-Invocation-Per-Turn Invariant)**: Step C2 executes at most once per turn. Faults in C2 are safely absorbed and logged without disrupting user conversation.
  4. **Singular Canonical Mutation Boundary**:
     - `BiographyPromotionService` remains the sole authorized writer of inferred facts to `character_core_facts`. All coordinator, proposer, detector, and evaluator modules have zero direct mutation paths (`CharacterCoreService.set_fact()`), zero token minting, and zero network imports.
* **Consequences**:
  * Complete Golden Suite 8A (`GC-145` through `GC-170`, 26 tests) passes.
  * Combined Phase 7D + Phase 8A suite passes (194/194).
  * Full backend regression passes across 1,420 tests with 0 failures.
  * Multi-year dynamic timeline simulation, external web verification, and trust decay remain explicitly deferred to Phase 8B / Phase 9+.

---

## ADR-018: Phase 8B Temporal Reality Subsystem Architecture & Boundary Invariants

* **Status**: Accepted & Frozen (2026-09-26)
* **Context**:
  1. Enabling Aevum to reason about temporal realities, life trajectories, educational timelines, academic calendars, and developmental milestones without collapsing epistemic boundaries, hallucinating microsecond precision, or treating temporal compatibility as canonical truth.
  2. Bounding combinatorial ambiguity and forward projection to prevent state explosion, epistemic contamination, or unauthorized personal reality mutation.
* **Decision**:
  1. **Epistemic Grounding Matrix**:
     - Five immutable grounding states: `USER_CONFIRMED`, `OBSERVED`, `DERIVED`, `PROJECTED`, `UNKNOWN`.
     - Constitutional Invariant: `DERIVED`, `PROJECTED`, and `UNKNOWN` nodes and items are strictly forbidden from carrying `Canonicality.CANONICAL`.
  2. **Temporal Granularity & Boundary Intervals (Zero Synthetic Precision)**:
     - All intervals are bounded by discrete calendar granularities (`YEAR`, `MONTH`, `DAY`).
     - Zero microsecond/millisecond hallucination. Zero pseudo-probabilistic confidence scores, floats, or Bayesian weights.
  3. **Singular World Knowledge Authority**:
     - `WorldKnowledgeRegistry` remains the singular authority for external educational calendars and institutional constraints.
     - `TemporalRuleRegistry` operates exclusively as a typed adapter/view over `WorldKnowledgeRegistry` with zero competing storage.
  4. **Tri-State Ephemeral Constraint Evaluation**:
     - Categorical tri-state logic: `SATISFIED`, `VIOLATED`, `UNDETERMINED`.
     - Missing or unobserved facts strictly evaluate to `UNDETERMINED`, never `VIOLATED` or `SATISFIED`.
     - External temporal constraint violation is demarcated from personal contradiction. Advisory anomalies (`is_hard_rejection = False`) preserve trajectory plausibility.
  5. **Ephemeral In-Memory Reasoning Graph (Zero DB Footprint)**:
     - `TemporalConstraintGraph` lives strictly in memory for the duration of a single turn. Zero SQLite tables, zero SQLAlchemy models, zero persistence.
     - Hard representation bound: `MAX_PROJECTED_NODES = 4`.
     - Anti-snowballing invariant: Projected nodes are forbidden from serving as origin nodes for further recursive projections (`propagation_depth <= 2`).
  6. **Trajectory Plurality & Bounded Ambiguity Representation**:
     - `TimelineTrajectoryEngine` enumerates canonical higher education pathways (`STPM`, `MATRIKULASI`, `FOUNDATION`, `DIPLOMA`).
     - Bounded Ambiguity Contract (`MAX_COMPATIBLE_TRAJECTORIES = 3`): When compatible pathways exceed 3, the engine enters a bounded non-enumerated state (`trajectory_bound_exceeded = True`, `compatible_trajectories = ()`, `total_compatible_count = 4`) rather than arbitrarily truncating the 4th pathway.
     - Unique Evidence Authoritativeness: `selected_canonical_trajectory` strictly requires `USER_CONFIRMED` or `OBSERVED` grounding. Temporal compatibility alone is never canonical evidence (`Plausible != Canonical`).
  7. **Step C3 Temporal Gate & Retrospective Repair Delegation**:
     - `TimelineOrchestrationCoordinator` acts as an epistemic constraint gate between Step D and Step E.
     - Candidate exclusion rule (Lock 1 & Lock A): A candidate is barred from Step E competition ONLY when ALL of its applicable trajectories are `HARD_INCOMPATIBLE`. If `applicable_trajectory_count == 0` or trajectories are bounded, the candidate is NOT excluded.
     - Zero repair policy authority in C3 (Lock 2): C3 emits neutral `TemporalConflictSignal` with symmetric conflicting fact keys.
     - Repair delegation (Lock 3, 7 & Lock D): Step G delegates canonical temporal conflicts to `RealityRepairService.repair()` kwargs via structured `TimelineEvidenceAdapter`.
     - Explicit availability semantics (Lock 4): Evaluation failures yield `TemporalEvaluationStatus.UNAVAILABLE` with zero candidate exclusions.
  8. **Serialization-Only Context Presentation**:
     - `RealityContextBuilder` formats `<temporal_trajectory_context>` strictly as an informational prompt block without performing path selection, ranking, or temporal mutation.
* **Consequences**:
  - Complete Golden Suite 8B (`GC-171` through `GC-195`, 25 tests) passes.
  - Combined Golden Suites (7D + 8A + 8B) achieve 111 / 111 passed.
  - Phase 8B cumulative test suite achieves 160 / 160 passed.
  - Full backend regression achieves 1,580 passed / 0 failed in 109.38s.
  - Pure 8B AST boundary audit achieves 0 violations (0 DB, 0 network, 0 LLM SDK, 0 token minting, 0 `set_fact` mutations).

---

### ADR-019: Phase 8C Longitudinal Life Progression & Time Advancer Architecture

* **Status**: Accepted & Locked (2026-09-26) — Phase 8C.1–8C.6 Fully Locked & Frozen
* **Context**:
  1. Managing temporal passage, life stages, academic progression, and milestone aging across extended fictional or real timelines without magical fact promotion, calendar conflation, or loss of historical plurality.
  2. Guarding against epistemic drift where elapsed time is mistakenly treated as factual proof of personal accomplishment or life-stage transition.
* **Decision**:
  1. **Anti-Magical-Promotion Invariant (Lock 1)**:
     - `PROJECTED + time passage != CANONICAL`.
     - Time progression shifts a projected milestone from `PENDING_FUTURE` to `DUE_IN_WINDOW` to `ELAPSED_UNVERIFIED`.
     - An elapsed unverified milestone strictly remains `ELAPSED_UNVERIFIED` (non-canonical); it NEVER matures into `CONFIRMED_HISTORICAL` or `CANONICAL` without explicit grounding evidence.
  2. **Derived Temporal Age View (Lock 2)**:
     - `identity.birth_date` is the sole ground truth.
     - `calendar_age(birth_date, effective_now)` is a pure, side-effect-free mathematical view with leap year (Feb 29) handling.
     - Zero `set_fact("identity.age")` database mutations.
  3. **Three-Layer Guard for Life Transitions (Lock 3)**:
     - Calendar eligibility != Personal progression.
     - Guard A (Temporal Duration) + Guard B (Predecessor DAG) yields strictly `ELIGIBLE_FOR_TRANSITION` (`signal = None`, zero promotion, zero mutation).
     - Guard C (Progression Evidence) is required to yield `TRANSITION_SUPPORTED`, emitting non-canonical `LifeStateTransitionSignal` (`is_canonical = False`).
  4. **Advisory Temporal Lapse & Lapsed != Deleted Invariant (Lock 4 & 8C.4 Permanent Lock)**:
     - 8C emits `TemporalLapseSignal` (frozen, advisory) for candidates whose activity window has elapsed.
     - 8C does NOT own candidate lifecycle and does NOT delete candidates from `character_candidate_facts`.
     - **Permanent Architectural Lock**: *Temporal realignment is an evaluation-level operation, not a persistence-level deletion. A lapsed trajectory may be excluded from the currently active projected set, but its historical candidate/evidence remains recoverable and may be reconsidered if new evidence or revised temporal constraints appear.* (Lapsed != Deleted).
  5. **Deterministic Path-Invariance & Monotonicity (Lock 5, 8, 9, 10, 12)**:
     - Single clock authority (`effective_now` authority singularity, rather than a physical Python object singleton constraint; verified at integration boundaries) holds singular `_effective_now`.
     - Clock advancement is strictly monotonic; time rewinds are rejected (`MonotonicTimeViolationError`).
     - Step invariance: Advancing $T_0 \to T_n$ yields identical boundary events and state as stepwise advancement $T_0 \to T_1 \to \dots \to T_n$.
     - Clock advancement is atomic.
  6. **Singular Canonical Mutation Boundary (Lock 7)**:
     - `BiographyPromotionService` remains the sole authorized writer of canonical facts. 8C has zero mutation authority.
  7. **Step C4 Longitudinal Orchestration & Serialization-Only Context Assembly (Phase 8C.5)**:
     - `LongitudinalCoordinator` coordinates 8C.1–8C.4 components during Step C4 of the reality turn.
     - `RealityContextBuilder` performs pure serialization of longitudinal context (`<longitudinal_life_context>`) with zero temporal reasoning or path selection.
  8. **Competition Filtering != Candidate Lifecycle Mutation (Lock A)**:
     - Turn-local exclusion of lapsed candidates from `competition_candidates` in Step C4 is eligibility filtering only.
     - It does not mutate `CandidateLifecycleState` and does not imply candidate rejection, deletion, invalidation, or permanent expiration (`LAPSED != REJECTED`).
  9. **Longitudinal Context is Advisory State, Not Canonical Biography (Lock B)**:
     - `<longitudinal_life_context>` informs the LLM that the temporal window of a projected pathway has elapsed, but its personal historical truth remains unresolved unless supported by evidence (`UNKNOWN != FALSE`, `ELAPSED_UNVERIFIED != NEVER HAPPENED`).
* **Consequences**:
  - Complete Golden Suite 8C (`GC-196` through `GC-220`, 25 tests) passes.
  - Combined Golden Suites (7D + 8A + 8B + 8C) achieve 136 / 136 passed.
  - Phase 8C cumulative test suite achieves 66 / 66 passed.
  - Full backend regression achieves 1,646 passed / 0 failed in 113.37s.
  - Pure 8C AST boundary audit achieves 0 violations across all 5 modules.
  - Phase 8C is officially fully locked and frozen.

---

## ADR-020: Phase 9 Autonomous Reality Verification & Epistemic Trust Architecture

* **Status**: Accepted & In Review (2026-09-26) — Architecture Gate v0.2
* **Context**:
  1. Transition from internal reality construction, coherence, and progression (Phase 7D–8C) to autonomous external reality verification and epistemic trust governance (Phase 9).
  2. Guarding against "Verification Privilege Leak" where external web search, tools, or third-party APIs bypass candidate competition, repair, and promotion authority to directly mutate canonical reality (`Google says X -> X is reality` anti-pattern).
  3. Establishing multi-dimensional source authority, consequence-aware verification policy, asynchronous non-blocking temporal isolation, and entity binding isolation.
* **Decision**:
  1. **Two-Dimensional Authority Framework (Issue 1)**:
     - Authority is orthogonal to domain. Claims are categorized into `ClaimDomain` (`PERSONAL_REALITY` vs `WORLD_REALITY`).
     - Sources are categorized into `SourceAuthority` (`FIRST_PARTY_PERSONAL`, `PRIMARY_INSTITUTIONAL`, `OFFICIAL_PUBLIC_RECORD`, `CORROBORATED_SECONDARY`, `UNVERIFIED_EXTERNAL`).
     - A user statement is authoritative for personal reality (`FIRST_PARTY_PERSONAL`); an institutional syllabus is authoritative for world reality (`PRIMARY_INSTITUTIONAL`). Neither crudely dominates across domains.
  2. **Source Authority != Truth & Multi-Factor Assessment (Issue 2 & Lock 3)**:
     - High source authority does not automatically equate to verified truth:
       `SourceTrust -> EvidenceQuality -> ClaimAssessment -> VerificationStatus`.
     - Evaluation considers: source authority, scope match, temporal freshness, specificity, corroboration, and contradiction.
  3. **Deterministic Conflict Resolution Without Raw Majority Voting (Issue 3)**:
     - Conflicting external evidence must never be resolved by raw headcount / majority voting.
     - Resolution must be based on explicit source authority, scope, freshness, applicability, and corroboration rules. If conflict cannot be deterministically resolved, status remains `AMBIGUOUS` or `UNDETERMINED`.
  4. **Decision-Only Verification Policy Engine (Issue 7 & Lock 2)**:
     - `VerificationPolicyEngine` emits structured `VerificationDecision` (evaluating risk, consequence tier, privacy boundaries, quiet hours, and cost/rate limits).
     - The policy engine possesses zero execution authority and zero direct web/tool invocation rights.
  5. **Decoupled Observation vs. Epistemic Evaluation (Issue 5)**:
     - `VerificationGateway` and adapters perform read-only external observation ("What did I observe?").
     - `EvidenceNormalizer` and `TrustEvaluator` evaluate epistemic credibility ("What is the epistemic weight of this observation on this claim?").
     - Clear separation between observation gathering and cognitive evaluation.
  6. **External Identity Binding Isolation (Issue 6 & Lock 8)**:
     - `External evidence about an entity != Evidence about Aevum`.
     - Name matching alone does not establish identity binding. Entity match requires an explicit, independent determination with identity-binding authority.
  7. **Verification Temporal Non-Blocking & Temporal Isolation (Issue 4, Lock 5 & Lock 7)**:
     - Conversational turn generation never blocks on external network or tool lookups.
     - A verification request created during Turn N MUST NOT alter the canonical reality, competition result, or context of Turn N.
     - Newly completed verification findings queue into an `Evidence Inbox` for ingestion in Turn N+1.
  8. **Evidence Before Truth & Singular Mutation Authority (Lock 1, 9, 10)**:
     - External observations enter strictly as `Evidence` feeding existing reality machinery (`CandidateHypothesisSet` / Step E competition).
     - `BiographyPromotionService` remains the sole authorized writer of canonical facts via `PromotionAuthorizationToken`. Phase 9 modules possess zero `set_fact` authority.
  9. **Symmetric Refutation & Repair Delegation (Lock 6)**:
     - When external verification refutes canonical reality or active candidates, it delegates to `RealityRepairService.repair()` kwargs via structured adapter; zero ad-hoc overwrites or deletions.
  10. **Phase 9 Staging Discipline (Issue 8)**:
      - 9.1: Verification Contracts & Epistemic Schemas (Pure DTOs, enums, vocabulary; zero evaluation, zero network).
      - 9.2: Consequence-Aware Verification Policy Engine (Decision-only).
      - 9.3: External Observation Adapters & Epistemic Source Evaluation (Observation decoupled from Evaluation).
      - 9.4: Verification Gateway & Async Orchestration (Async queue, evidence inbox, temporal isolation).
      - 9.5: Evidence Reconciliation & Refutation Routing (Delegation to repair, candidate refutation).
      - 9.6: Golden Suite 9 Acceptance Benchmarks (GC-221 ~ GC-245).
  11. **Policy Constraints != Source Truth (Phase 9.2 Permanent Architectural Lock)**:
      - `allowed_authorities` and `allowed_source_kinds` emitted by `VerificationDecision` are strictly policy constraints on what sources Phase 9.3 may query or consider.
      - They do NOT imply that any source possessing such authority is pre-verified, credible, or truthful. Phase 9.3 must independently evaluate authority, scope, freshness, specificity, corroboration, and contradiction.
  12. **Policy Precedence Determinism & Quota Consumption Separation**:
      - Precedence order is strictly deterministic: Privacy & Consent (`VPOL-001`) > Turn Budget (`VPOL-002`) > Daily Cap (`VPOL-003`) > Quiet Hours (`VPOL-004`) > Consequence & Domain Tiering (`VPOL-005`).
   13. **Authority Precedence != Epistemic Truth (Phase 9.3 Permanent Architectural Lock)**:
       - `Authority precedence != epistemic truth`. Authority rank is a deterministic conflict-resolution precedence ordering, NOT a truth score or probability weight.
       - Authority rank may resolve eligible conflicts between admissible observations, but never independently produces `SUPPORTED`.
   14. **Authority Cannot Override Scope or Freshness (Phase 9.3 Permanent Architectural Lock)**:
       - `Official source about X != official evidence about Y`. Authority never overrides scope alignment. An observation lacking scope match (wrong programme, wrong jurisdiction, or unmatched key) strictly evaluates to `OUT_OF_SCOPE` under `EVAL-005`.
       - Similarly, authority cannot override freshness: an outdated (`SUPERSEDED_OUTDATED`) source can never dominate an active (`CURRENT`) source.
   15. **Identity Ambiguity != Factual Contradiction (Phase 9.3 Permanent Architectural Lock)**:
       - Missing or unanchored identity anchor (`UNANCHORED_HOMONYM`) evaluates strictly to `AMBIGUOUS_CONFLICT` under `EVAL-004-LOCK8-IDENTITY-BINDING`.
       - It indicates an identity-binding failure, NOT factual refutation or contradiction. Identity ambiguity must never be interpreted as factual contradiction and must never trigger reality repair.
   16. **Four-Layer Epistemic Separation & Zero In-Process Promotion (Phase 9.3 Permanent Architectural Lock)**:
       - Architecture flow: `ExternalObservation` -> `VerificationFinding` -> `VerificationEvidencePayload` (via 9.4 Temporal Inbox) -> Existing Reality Pipeline -> Canonical Reality.
       - `EpistemicSourceEvaluator` strictly outputs read-only `VerificationFinding`. It possesses zero authority to instantiate `VerificationEvidencePayload`, mutate `CandidateRepository`, or write to `RealityLedger`.
   17. **Physical Temporal Wall & True Earliest-Turn Semantics (Phase 9.4 Permanent Architectural Lock)**:
       - Temporal isolation is enforced as a data model invariant on `VerificationInboxItem`: `origin_turn_id` / `origin_turn_sequence` records where the job originated, and `eligible_from_turn_id` / `eligible_from_turn_sequence` defines the earliest consumer turn.
       - `VerificationEvidenceInbox.drain_for_turn()` physically forbids draining any item where `item.origin_turn_id == turn_id`. Furthermore, items follow true "earliest turn" semantics: an item is consumable by `eligible_from_turn_sequence` or any subsequent turn (`consumer_sequence >= eligible_sequence`), strictly never in its origin turn.
   18. **Canonical Deduplication & Turn-Scoped Scheduling Identity (Phase 9.4 Permanent Architectural Lock)**:
       - Claim identity is computed via canonical JSON serialization with sorted keys (`claim_domain`, `claim_key`, `entity_binding_anchor`, `claim_value`) hashed by SHA-256 (`claim_dedup_key`).
       - Deduplication key is strictly an identity key for verification work/scheduling, NOT an identity key for evidence truth.
       - Queue deduplication scope is `(origin_turn_id, claim_dedup_key)`: identical claims dispatched within the same turn are coalesced, while subsequent turns are permitted to launch fresh verification.
   19. **Job-to-Inbox Idempotency & Retry Safety (Phase 9.4 Permanent Architectural Lock)**:
       - `VerificationInboxItem` tracks `source_job_id`. Within a given `VerificationEvidenceInbox` lifecycle, each `source_job_id` is idempotently associated with at most one `InboxItem`.
       - `deposit(source_job_id, finding)` idempotently returns the existing item if already deposited, guaranteeing that worker retry after partial crash never manufactures duplicate evidence.
   20. **Gateway Request-Decision Binding & Dual-Boundary Enforcement (Phase 9.4 Permanent Architectural Lock)**:
       - `VerificationGateway` validates `decision.request_id == request.request_id` to prevent authorization-context substitution.
       - Gateway enforces policy bounds via `AdapterDescriptor` filtering: both `descriptor.source_kind in decision.allowed_source_kinds` AND `descriptor.source_authority in decision.allowed_authorities` must be satisfied before dispatching. Gateway possesses zero evaluation authority.
   21. **Domain-Gated Reconciliation Routing (Phase 9.5 Permanent Architectural Lock)**:
       - `WORLD_REALITY` findings MUST NOT enter the personal candidate, repair, or biography-promotion pipeline. Phase 9.5 performs no world-knowledge mutation; such findings may only be preserved as verification provenance/context for a separately governed world-knowledge process.
       - Changes in world reality facts cannot silently mutate or rewrite personal biographical facts of the companion.
   22. **Reconciler Routing != Repair Decision (Phase 9.5 Permanent Architectural Lock)**:
       - `VerificationReconciler` detects factual conflicts and routes them via typed `VerificationRepairRequest`, but NEVER selects or recommends a `RepairLevel`.
       - `RealityRepairService` remains the sole authority for evaluating the 5-level repair hierarchy (Level 1 Social Misspeak -> Level 2 Temporal Reinterpretation -> Level 3 Fact Invalidation -> Level 4 Re-Anchoring -> Level 5 Graceful Uncertainty).
   23. **Evaluation-Level Candidate Exclusion != Candidate Lifecycle Mutation (Phase 9.5 Permanent Architectural Lock)**:
       - Action `EXCLUDE_CANDIDATE_FROM_COMPETITION` emits `candidate_ids_to_exclude` for current-turn competition filtering only.
       - `competition_candidates` is a per-turn derived evaluation view, NOT a persistent candidate lifecycle store.
       - `EXCLUDE_CANDIDATE_FROM_COMPETITION` never mutates Candidate lifecycle state and never persists invalidation. `all_candidates` remains intact as the immutable truth source.
   24. **Multi-Factor Candidate Matching (Phase 9.5 Permanent Architectural Lock)**:
       - Matching an external finding to an internal candidate hypothesis requires strict alignment across: `ClaimDomain`, `claim_key`, `claim_value`, `entity_binding_anchor`, and `reality_taxonomy`/`slot_name`.
       - Key or value matching alone without explicit entity anchor alignment strictly forbids candidate augmentation (Lock 8 Entity Binding Isolation).
   25. **Ambiguity Preservation & Typed Repair Boundary (Phase 9.5 Permanent Architectural Lock)**:
       - `AMBIGUOUS_CONFLICT` strictly preserves uncertainty: zero candidate invalidation, zero canonical mutation, and zero repair invocation.
       - The reconciliation boundary is strictly typed: `VerificationRepairRequest` encapsulates all context in dedicated typed DTOs (`VerificationTemporalSplitContext`, `VerificationEntityDisambiguationContext`). Zero `dict[str, Any]` passes across the reconciler -> repair boundary. `claimed_value` and `existing_value` are opaque domain values, strictly NOT control structures.
   26. **Canonical Semantic Projection Determinism (Phase 9.6 Permanent Architectural Lock)**:
       - Replay determinism in Golden Acceptance (`GC-245`) is defined over a canonical semantic projection of `OrchestrationTurnResult`, excluding explicitly non-deterministic operational metadata (runtime timestamps, generated object IDs, random UUIDs, wall-clock execution duration).
       - Identical inputs + identical DB snapshot + identical authoritative clock + identical external fixtures guarantee bit-identical semantic state across replay, without imposing false bit-identical requirements on operational metadata.
   27. **Policy-Scoped Promotion Margin Threshold (Phase 9.6 Permanent Architectural Lock)**:
       - Decisive choice margin required for Gate 7 (`GATE_7_EXPLICIT_CHOICE`) in `GC-239` and `GC-243` is strictly scoped to the active `BiographyConstructionPolicy.min_choice_margin`, rather than a hardcoded universal architecture constant (such as `0.15`).
       - Given active policy $P$: verified candidate with `choice_margin >= P.min_choice_margin` satisfies Gate 7; `choice_margin < P.min_choice_margin` strictly blocks promotion.
* **Consequences**:
  - Ensures Aevum actively verifies reality under rigorous epistemic discipline without hallucinating external certainty, leaking authority, or bypassing the core reality state machine.

---

## ADR-021: Voice Architecture & Mind/Body Boundary (Phase 10)

* **Status**: Accepted (Phase 10 Architecture Gate v0.2)
* **Context**:
  1. Phase 10 introduces expressive voice synthesis (TTS) and speech recognition (STT) to Project Aevum.
  2. Without strict architectural boundaries, adding voice I/O risks:
     - Mutating character reality or memory directly from the audio/speech layer (violating Rule 11, 12, 19).
     - Slowing down conversation turns by synchronously blocking on audio synthesis.
     - Silently capturing audio or introducing always-listening background microphone complexity (violating Rule 18).
     - Leaking pseudo-probability float confidence into voice prosody, un-doing the anti-float epistemic discipline locked in Phase 9.
     - Naive audio caching causing stale or cross-emotion audio replay.
     - Tight coupling where audio cache expiration accidentally deletes conversation history.
* **Decision**:
  1. **Mind / Body Separation & Single Source of Truth (Voice Lock 1)**:
     - The backend Character Engine and deterministic reality engine remain the sole mind and single source of truth.
     - The Voice Layer (STT, TTS, Prosody, Audio Playback) is strictly an interface ("the body").
     - Voice layer components have zero authority to invoke `set_fact()`, instantiate `PromotionAuthorizationToken`, directly alter `CharacterCore`, or mutate memory.
  2. **Provider Abstraction as Implementation Detail (Decision 1)**:
     - Voice domain models interact exclusively with provider interfaces: `TTSProvider` and `STTProvider`.
     - Specific engines (e.g. Edge-TTS, OpenAI, Whisper, local engines) are swappable provider adapters and are strictly implementation details.
     - Note: Edge-TTS relies on online endpoints; it is not a pure offline provider.
     - Automated unit tests and Golden benchmarks execute exclusively against `MockTTSProvider` and `MockSTTProvider`. Zero live network or heavy audio model calls during test suites (Rule 7, 8).
  3. **Decoupled Asynchronous Response Architecture (Decision 2)**:
     - Text response and TTS audio are separate, derived outputs.
     - The conversation turn immediately commits and returns text response upon generation. Audio synthesis is triggered asynchronously or queried on-demand.
     - Audio must never become a prerequisite for committing a text response.
  4. **PTT-Only Mandatory Input Boundary (Decision 3 & Rule 18)**:
     - Push-To-Talk (PTT) is the only mandatory input mode in Phase 10.
     - Continuous Voice Activity Detection (VAD) is formally deferred to future phases (Phase 11+) to prevent scope explosion (microphone lifecycle races, background eavesdropping, false activations, consent revocation loops).
     - Audio capture requires explicit user consent flag (`voice_input_enabled == True`) and visible active-recording indicators.
  5. **Lock A — Audio != Canonical Reality**:
     - `AudioData`, `SynthesisResult`, `TranscriptionResult`, and `AudioCache` are ephemeral interface data.
     - TTS audio must never become biography, memory, or reality evidence.
     - STT transcription is conversational user input, NOT canonical truth (inherits Evidence Before Truth: user statement != ground truth).
  6. **Lock B — Decoupled Failure Resilience**:
     - `TTS failure != Conversation failure`: If TTS times out or errors, the conversation text remains successfully committed (`text = available`, `audio = unavailable`).
     - `STT failure -> Zero fake turn`: If STT fails to transcribe, no fake empty or hallucinated user message is created.
  7. **Lock C — Prosody Consumer Isolation**:
     - Prosody is deterministically derived from `EmotionState` (`EmotionType`, `intensity`) and `CharacterMood` via `ProsodyMapper`.
     - LLM prompts do not invent or dictate emotional prosody.
     - `ProsodyMapper` is a pure read-only consumer and possesses zero authority to mutate `EmotionState`.
  8. **Lock D — Categorical `EpistemicCue` (Zero Pseudo-Probability Floats)**:
     - Prosody modulation must not consume raw continuous floats like `confidence = 0.63`.
     - Epistemic certainty is expressed through discrete categorical cues: `EpistemicCue` (`CERTAIN`, `UNCERTAIN`, `AMBIGUOUS`, `CONTESTED`, `UNKNOWN`).
     - Non-certain cues deterministically trigger prosody hesitation (e.g. slight cadence drop, micro-pause).
  9. **Lock E — Canonical Audio Cache Identity**:
     - Cache identity must be computed from a canonical serialization hashed with SHA-256 across:
       `canonical_hash(text, voice_identity, audio_format, canonical_prosody_config, provider_identity, provider_version)`.
     - Prevents collisions between different emotions, voice identities, or provider model revisions.
  10. **Lock F — Ephemeral Media Lifecycle Isolation**:
      - Audio cache follows an ephemeral media lifecycle (`CREATED` -> `ACTIVE` -> `EXPIRED` -> `PURGED`).
      - Audio cache expiration or purge strictly never triggers deletion or mutation of conversation messages, biography facts, or reality state.
  11. **Phase 10 Staging Discipline**:
      - 10.1: Audio Contracts, Voice DTOs & Provider Abstractions (`voice_models.py`, `base.py`).
      - 10.2: Emotional Prosody Modulation Engine (`prosody_mapper.py`, `EpistemicCue`).
      - 10.3: Text-to-Speech (TTS) Provider Implementations & Service (`tts_service.py`, `MockTTSProvider`, cache).
      - 10.4: Speech-to-Text (STT) & Consent Gate (`stt_service.py`, `MockSTTProvider`, PTT consent guard).
      - 10.5: Desktop Voice Integration & Playback Pipeline (`apps/desktop` PTT & audio playback).
      - 10.6: Golden Suite 10 Acceptance Suite (`test_golden_suite_10.py`, `GC-246` ~ `GC-270`).
* **Consequences**:
  - Provides rich, emotionally expressive voice dialogue while strictly preserving Mind/Body separation, epistemic rigor, and user privacy.
  - **Scope Demarcation Record**: Phase 10 delivers Desktop Voice Integration (PTT -> STT -> Mind -> Text -> TTS -> Playback with Barge-in), not a realtime full-duplex voice assistant. Continuous VAD, wake words, background listening, streaming duplex audio, and mobile voice runtimes are explicitly deferred to future phases (e.g. Phase 12/13) and must never be assumed as mandatory prerequisites for Phase 11.
* **Milestone Acceptance & Sign-off**:
  - **Status**: APPROVED — FULLY VERIFIED & FROZEN 🔒 (Phase 10 Gate Approved)
  - **Acceptance Metrics**:
    - Phase 10.1: 27/27 PASS
    - Phase 10.2: 17/17 PASS
    - Phase 10.3: 14/14 PASS
    - Phase 10.4: 12/12 PASS
    - Phase 10.5: 16/16 PASS
    - Phase 10.6 Golden Suite 10: 25/25 PASS
    - Phase 10 Dedicated Total: 111/111 PASS
    - Golden Suites 7D–10: 186/186 PASS
    - Full Backend Regression: 1,873/1,873 PASS (0 failures, 20 warnings in 125.61s)
    - Desktop Production Build: 0 errors (built in 783ms)
    - System-wide AST Boundary Audit: 0 violations across all 15 voice modules
  - **Constitutional Decision**: Phase 10 is officially LOCKED and FROZEN as a foundational baseline. All 14 authoritative voice invariants are binding.

---

## ADR-022: Live2D Visual Presence & Mind/Body Boundary (Phase 11)

* **Status**: Accepted (Phase 11 Architecture Gate Approved 🟢)
* **Context**:
  1. Phase 11 introduces visual embodiment (Live2D Cubism Web SDK) to Project Aevum.
  2. Phase 10 gave Aevum a voice. Phase 11 gives Aevum a visible body.
  3. Risk: Visual state (Canvas, meshes, motions, physics, gaze, lip-sync) mutating character reality, emotion, or memory directly from the renderer layer (violating Rules 11, 12, 19).
  4. Risk: Renderer failure breaking conversation, audio playback, or backend state machines.
  5. Risk: Introducing touch/social interaction prematurely, creating an ungoverned second interaction state machine before visual rendering is stabilized.
  6. Risk: Leaking heavy WebGL / Canvas / DOM dependencies into backend Core domain or automated unit test environments.
* **Decision**:
  1. **North Star Principle**:
     - *"Live2D is Aevum's visible body, not its second mind."*
  2. **Mind / Body Separation & Single Source of Truth**:
     - The backend Aevum Core remains the sole Mind, sole Emotion Authority, and Single Source of Truth.
     - The Visual Mapping Layer and Live2D Renderer are strictly the Body / Presentation layer.
     - The visual subsystem has zero authority to invoke `set_fact()`, instantiate `PromotionAuthorizationToken`, alter `CharacterCore`, or mutate memory.
  3. **The 7 Constitutional Visual Locks**:
     - **Lock 1: Visual State != Canonical Reality**:
       Live2D Canvas, Cubism deformers, meshes, animation tracks, and physics oscillations are transient presentation artifacts. They possess zero database persistence authority and zero factual reality weight.
     - **Lock 2: Unidirectional Affective Visual Mapping**:
       Emotional flow is strictly one-way: `Backend (EmotionState, CharacterMood) -> Render Instructions (VisualExpressionConfig, VisualMotionCommand) -> Renderer Parameters`. Live2D visual states or motion transitions cannot mutate or feedback into backend emotional state.
     - **Lock 3: Audio-Driven Lip-Sync Without Epistemic Authority (RMS -> ParamMouthOpenY Only)**:
       Audio RMS volume envelope drives `ParamMouthOpenY` only. `ParamMouthForm` is reserved for future phoneme/viseme providers and must not be simulated from amplitude. User barge-in or playback completion immediately clamps mouth parameters to zero. Mouth state never alters conversation text or reality.
     - **Lock 4: Pure Visual Presentation Scope & Hit-Testing Deferral**:
       Phase 11 is strictly constrained to visual rendering (`Emotion -> Expression`, `Mood -> Motion`, `Gaze Tracking`, `Lip-sync`). Interactive hit-testing, physical touch, and tactile social responses are formally deferred to a dedicated interaction milestone to prevent renderer scope explosion.
     - **Lock 5: Fail-Closed & Graceful Visual Degradability**:
       WebGL unavailability, GPU crashes, or asset loading failures must degrade gracefully to text and voice dialogue. Visual crashes cannot break conversation flow, audio playback, or backend integrity.
     - **Lock 6: Hermetic Testability & Zero WebGL Backend Leakage**:
       All backend visual protocols, DTOs, and expression mappers must execute hermetically in headless CI environments without GPU, Canvas, or WebGL dependencies. The frontend renderer is isolated behind a clean, mockable component boundary.
     - **Lock 7: Renderer State != Character State**:
       Internal renderer operational states (current motion queue, animation interpolation, blink timers, physics solver state, eye-dart/micro-saccade phase, gaze interpolation, and asset loading states) are strictly designated as **Renderer State**. Renderer State cannot flow backward into `CharacterState`, `EmotionState`, or Canonical Reality. Blink intervals and micro-saccades are presentation behaviors, not emotional measurements.
  4. **Four Decoupled Visual Subsystems**:
     - `EmotionState` -> `ExpressionMapper` -> `VisualExpressionConfig` (render instruction: what expression to render)
     - `CharacterMood` -> `MotionMapper` -> `VisualMotionCommand` (render instruction: what motion archetype to execute)
     - Mouse Position -> `GazeTracker` (cursor follow with smooth interpolation & micro-saccades)
     - Audio Playback -> `LipSyncAnalyzer` (`ParamMouthOpenY` envelope with barge-in zero latch)
     - Strictly forbids creating a monolithic all-in-one `VisualMapper`.
  5. **Phase 11 Sub-Phase Staging Discipline**:
     - 11.1: Visual Contracts, DTOs & Expression/Motion Abstractions (`visual_models.py`, `VisualExpressionConfig`, `VisualMotionCommand`, `Live2DModelManifest`, `RendererState`).
     - 11.2: Affective Visual Expression & Motion Mapping Engines (`expression_mapper.py`, `motion_mapper.py`).
     - 11.3: Audio Amplitude Lip-Sync Engine (Web Audio RMS analyzer, `ParamMouthOpenY` curve, barge-in immediate-zero latch).
     - 11.4: Desktop Live2D Renderer & Cubism WebGL Integration (`apps/desktop` WebGL canvas, model loader, motion blender, physics evaluation, graceful fallback).
     - 11.5: Desktop Viewport Layout & Gaze Tracking (Decoupled mouse cursor tracking -> Gaze parameters `ParamEyeBallX/Y`, `ParamAngleX/Y/Z` with smooth interpolation and focus clamping).
     - 11.6: Golden Suite 11 Acceptance Suite (`test_golden_suite_11.py`, approved GC cases, AST boundary audit).
* **Consequences**:
  - Provides expressive visual animation and embodied presence on desktop while rigorously preserving Mind/Body separation, deterministic reality integrity, and modular testability.
* **Milestone Acceptance & Sign-off**:
  - **Status**: APPROVED — FULLY VERIFIED & FROZEN 🔒 (Phase 11 Gate Approved)
  - **Acceptance Metrics**:
    - Phase 11.1: 35/35 PASS
    - Phase 11.2: 15/15 PASS
    - Phase 11.3: 9/9 PASS
    - Phase 11.4: 8/8 PASS
    - Phase 11.5: 10/10 PASS
    - Phase 11.6 Golden Suite 11: 27/27 PASS (GC-271 ~ GC-297)
    - Phase 11 Dedicated Total: 104/104 PASS
    - Golden Suites 7D–11: 213/213 PASS
    - Full Backend Regression: 1,977/1,977 PASS (0 failures, 20 warnings in 128.66s)
    - Desktop Production Build: 0 errors (built in 794ms)
    - System-wide AST Boundary Audit: 0 violations across all visual modules (0 hit-testing, 0 reverse mutation, 0 continuous VAD)
  - **Constitutional Decision**: Phase 11 is officially LOCKED and FROZEN as a foundational visual embodiment baseline. All 7 Constitutional Visual Locks are binding.

---

## ADR-023: Canonical Biography, Causal Life Graphs & Longitudinal Memory Integration (Phase 12)

* **Status**: Accepted & Officially Frozen 🔒
* **Context**:
  1. Phases 10 and 11 granted Aevum a natural voice and an embodied visual presence on the desktop.
  2. With voice and body established, the companion encounters a fundamental threshold of existential coherence: autobiographical questions (*"Where did you grow up?"*, *"Why do you like black tea?"*, *"What was your high school like?"*, *"Who taught you to code?"*).
  3. Risk: An ungrounded LLM wrapper hallucinates conflicting life stories across sessions, fabricates childhood causes on the fly, or confuses user experiences with Aevum's own life history.
  4. Core Axiom: *"Aevum can answer autobiographical questions from a coherent, temporally grounded personal world — without improvising unsupported life facts."*
  5. Constitutional Boundary: Dialogue output is derived narrative, never a source of canonical reality. Reverse mutation into canonical biography facts via conversation speech is strictly forbidden (Rule 11, Rule 12, Rule 13).
* **Decision**:
  1. **The 8 Deep Architectural Resolutions (Hardened)**:
     - **Resolution 1 (Biography Fact vs. Life Event Boundary)**: `CharacterBiographyFact` models slow-moving invariant state assertions with temporal validity $[t_{\text{start}}, t_{\text{end}}]$; `LifeEventRecord` models discrete bounded temporal occurrences with participants, causal antecedents, and resultant fact links. Facts describe state; events record state transitions. Events are never flattened into static boolean attributes.
     - **Resolution 2 (HistoryScope Boundary: Domain Identity vs. Participant Metadata)**: Replaced fragile `user_present` boolean check with first-class `HistoryScope` enum (`AEVUM_PERSONAL` vs `SHARED_WITH_USER`). `user_presence`, `participants`, and `session_anchor` are participant metadata. Domain identity is strictly governed by `HistoryScope.AEVUM_PERSONAL` (Aevum's personal past, immutable from conversation).
     - **Resolution 3 (Causal Canonicalization & Domain-Level UNKNOWN Semantic State)**: Causal relations are structural graph edges (`CausalRelationType`: `ORIGINATED_FROM`, `CATALYZED_BY`, `CONDITIONED_BY`, `MOTIVATED_BY`). `UNKNOWN` is a first-class domain model enum (`CausalKnowledgeState.UNKNOWN`), not merely a prompt string convention. If `causal_state == UNKNOWN`, `causal_relation_id` must be `None`. Narrative assemblers programmatically enforce boundary directives, preventing confabulation while enabling natural, humble character uncertainty rather than rigid canned scripts.
     - **Resolution 4 (Structured Childhood Memory Composition)**: Childhood memories are composite nodes composed of Background Fact Anchor, Episodic Event Anchor, Experiential Qualia Anchor, and Subjective Recall Quality (`RecallLevel`).
     - **Resolution 5 (Two Orthogonal Axes: Truth Status vs. Recall Quality)**: Epistemic status and recall quality are decoupled. Truth is governed by `CanonicalStatus` (`CANONICAL`, `PROVISIONAL`, `DISPUTED`, `UNDEFINED`); phenomenological recall is governed by `RecallLevel` (`VIVID`, `HAZY`, `FRAGMENTARY`, `UNDEFINED`). Zero float confidence fields (`confidence = 0.43` is banned).
     - **Resolution 6 (Segregated Mutation Authorities: Biography vs. Shared History)**: Conversation turn extraction forks into two distinct pipelines. Personal-world candidates (`BiographyCandidate`) compete via Step C5 and are promoted solely by `BiographyPromotionService` holding `PromotionAuthorizationToken` into the Reality Ledger. Shared-history candidates (`SharedHistoryCandidate`) are validated and promoted solely by `SharedHistoryService` into the shared relationship memory store. Shared history never pretends to be Biography and cannot mutate the Reality Ledger.
     - **Resolution 7 (Biography Correction via Frozen Phase 7D–9 Reality Pipeline)**: Biographical correction or temporal splits flow through Phase 9.5 `VerificationRepairRequest` / `VerificationTemporalSplitContext`, compete in Step C5 candidate competition, and are sealed strictly by `BiographyPromotionService.promote_candidate(token)` into `reality_history` with full provenance. Zero backdoor mutation functions.
     - **Resolution 8 (Anchor & Boundary Pattern as Seed/Content Design Guidelines)**: Canonical anchors are explicitly downgraded from an architectural mandate to **Seed / Content Design Guidelines**. *Aevum may contain a bounded set of canonical anchors when independently established by evidence or explicitly authored through an authorized promotion path. No anchor is mandatory.* Strictly adheres to Phase 8A lock: "Don't fill every NULL. Infer only when meaningful and constrained."
  2. **Causal DAG Scope & Single Authoritative Clock**:
     - **Causal Explanation Graph is DAG**: The acyclic constraint applies strictly to the **Canonical Causal Explanation Graph** (`CausalExplanationGraph`) within a declared causal derivation scope, preventing circular justifications ($A \text{ because } B \text{ because } A$). General life events, social relations, and behavioral feedback loops can exist in non-DAG graph topologies.
     - **Single Clock & No Hardcoded Ages**: `LifeEra` represents developmental stages (`EARLY_CHILDHOOD`, `PRIMARY_SCHOOL`, `SECONDARY_SCHOOL`, `POST_SECONDARY`, `UNIVERSITY`, `ADULTHOOD`, `OTHER`, `UNKNOWN`) without hardcoded age ranges. Dynamic temporal status (`PAST`, `CURRENT`, `FUTURE`) continues to be governed exclusively by Phase 8C's Authoritative Clock and Temporal Position Engine. Zero duplicate temporal systems.
  3. **The 7 Constitutional Biography Locks**:
     - **Lock 1: Narrative != Reality (Autobiographical Output Never Mutates Canon)**: Dialogue is derived narrative. Speech never feeds back into canonical records without formal verification and promotion pipeline execution.
     - **Lock 2: Epistemic Causal Integrity (UNKNOWN is Domain State)**: Causal reasons must exist as structural graph edges. If unlinked, `causal_state` is explicitly `UNKNOWN`. All presentation adapters programmatically enforce this boundary.
     - **Lock 3: Temporal Wall & Single Clock Consistency**: Facts and events are indexed by `LifeEra`. Cross-era bleed is forbidden. Dynamic temporal status is computed against the Phase 8C authoritative clock.
     - **Lock 4: Relational Isolation (HistoryScope Segregation)**: `HistoryScope.AEVUM_PERSONAL` and `HistoryScope.SHARED_WITH_USER` are strictly segregated. Conversation turns cannot alter Aevum's personal past.
     - **Lock 5: Undefined Boundary Grace (Humble Uncertainty, Not Canned Scripts)**: Undefined life areas produce natural, character-authentic humble boundary expressions, avoiding both generic confabulation and rigid robotic refusal scripts.
     - **Lock 6: Segregated Promotion Authorities (Biography != Shared History)**: `BiographyPromotionService` holding `PromotionAuthorizationToken` is the sole authority for Canonical Biography. `SharedHistoryService` independently governs shared experiences.
     - **Lock 7: Longitudinal Cross-Session Stability**: Autobiographical facts remain strictly invariant across sessions, months, and restarts (zero backstory drift).
  4. **Sub-Phase Staging Discipline**:
     - **Phase 12.1 — Biographical Ontology & Contract DTOs**: `biography_models.py`, enums (`HistoryScope`, `LifeEra`, `CanonicalStatus`, `RecallLevel`, `CausalKnowledgeState`, `CausalRelationType`), frozen immutable DTOs, zero floats, AST boundary audit (0 DB, 0 LLM, 0 mutation authority).
     - **Phase 12.2 — Life Event & Causal Explanation Graph Engine**: `causal_graph.py`, `life_event_service.py`, acyclic causal explanation graph validation, deterministic causal chain queries.
     - **Phase 12.3 — Autobiographical Retrieval & Context Assembly**: `autobiographical_retriever.py`, `biographical_context_assembler.py`, era filtering, epistemic boundary formatting (`<biographical_context>`), humble natural expression instructions.
     - **Phase 12.4 — Longitudinal Shared History Engine**: `shared_history_service.py`, `SharedHistoryEpisode`, independent promotion authority, dual-track retrieval, Rule 16 multi-axis relationship dynamics.
     - **Phase 12.5 — Biography & Memory Desktop Projection / UI Integration**: Desktop memory inspection / biographical journey projection in `apps/desktop` (read-only view into canonical memories and shared milestones, Rule 19 Mind/Body boundary strictly preserved).
     - **Phase 12.6 — Golden Suite 12 Acceptance Suite**: `test_golden_suite_12.py`, 6 acceptance clusters, AST boundary audit, full regression validation.
* **Consequences**:
  - Eliminates prompt confabulation and backstory drift for personal questions.
  - Gives Aevum a grounded, causal, temporally indexed life history while strictly preserving Mind/Body boundaries, segregated mutation authorities, single authoritative clock, and hermetic backend testability.
* **Milestone Acceptance & Sign-off**:
  - **Status**: APPROVED — FULLY VERIFIED & FROZEN 🔒 (Phase 12 Gate Approved)
  - **Acceptance Metrics**:
    - Phase 12.1: 27/27 PASS
    - Phase 12.2: 16/16 PASS
    - Phase 12.3: 17/17 PASS
    - Phase 12.4: 16/16 PASS
    - Phase 12.5: 3/3 PASS
    - Phase 12.6 Golden Suite 12: 27/27 PASS (GC-298 ~ GC-324)
    - Phase 12 Dedicated Total: 106/106 PASS
    - Golden Suites 7D–12: 240/240 PASS
    - Full Backend Regression: 2,083/2,083 PASS (0 failures, 20 warnings in 126.87s)
    - Desktop Production Build: 0 errors (built in 769ms)
    - System-wide AST Boundary Audit: 0 violations across all 9 biography modules
  - **Constitutional Decision**: Phase 12 is officially LOCKED and FROZEN as a foundational autobiographical and longitudinal memory baseline. All 7 Constitutional Biography Locks are binding.

---

## ADR-024: Realtime Voice Call & Desktop Product Shell Architecture

* **Status**: Accepted (Revision 2 — Gate Review Approved)
* **Context**:
  - The companion requires a transformation from a developer dashboard into an embodied digital desktop companion ("Presence / The Living Body").
  - Users need low-latency, full-duplex conversational voice calls with natural barge-in (interruption), synchronized Live2D visual expressions, and seamless access to biographical journey and shared memories.
  - Architectural Challenge: Streaming audio and realtime interactions must remain an ephemeral transport conduit. They must **never** create a backdoor or loophole bypassing the reality, verification, temporal, and memory governance mechanisms established in Phases 7D–12.
* **Decision**:
  1. **Dual-Track Transport Architecture & AudioFrameEnvelope**:
     - **Control Plane**: Streaming WebSocket (`/api/v1/call/stream/{session_id}`) delivering typed JSON protocol events (`SessionEvent`, `TurnEvent`, `TranscriptEvent`, `BargeInEvent`, `ErrorEvent`, `ConnectionEvent`, `VisualDirective`).
     - **Media Plane**: Binary WebSocket frames encapsulated in a strictly typed `AudioFrameEnvelope` containing `protocol_version`, `session_id`, `generation_id`, `sequence_id`, `direction`, `codec`, `sample_rate`, `stream_position_ms`, and `payload`.
     - Transport is cleanly abstracted behind `RealtimeAudioTransportAdapter` for future WebRTC integration (Phase 15). Actual latency is an empirical benchmark target measured in Phase 13.3.
  2. **Monotonic Generation & Sequence Fencing**:
     - Every assistant output stream is tagged with a monotonic `generation_id`. Client and server unconditionally drop audio packets where `generation_id < active_generation_id` (stale-response isolation).
     - Every packet carries a monotonic `sequence_id` within its generation to detect packet loss, jitter, or disordered arrival.
  3. **Authoritative Session Ownership & Three Decoupled Lifecycles**:
     - The backend `RealtimeCallSessionManager` is the sole authoritative owner of call state.
     - Strictly decoupled lifecycles: $\text{session\_id} \neq \text{conversation\_id} \neq \text{turn\_id}$.
     - Monotonic Reconnection Lease: `REALTIME_SESSION_RECONNECT_LEASE_SECONDS = 30` governed strictly by monotonic clock (`time.monotonic()`). Reconnecting within lease attaches a new socket to the existing session and conversation.
  4. **Three-State Transcript Lifecycle & Double-Gated Commitment**:
     - Transcripts follow: `PARTIAL` $\to$ `FINAL_PENDING_COMMIT` $\to$ `COMMITTED`.
     - `PARTIAL` transcripts are ephemeral previews for UI rendering only: strictly zero DB writes, zero memory extraction, zero reality inference.
     - `FINAL_PENDING_COMMIT` awaits linguistic boundary confirmation.
     - Only `COMMITTED` transcripts (double-gated: provider `is_final == True` AND confirmed utterance boundary via VAD silence $\ge 600\text{ms}$ or speech release) are persisted as `Message(role=MessageRole.USER)`.
  5. **Directional Turn State & Client-Local Barge-In**:
     - Turn state is decoupled into `user_input_state` (`PARTIAL`, `FINAL_PENDING`, `COMMITTED`) and `assistant_output_state` (`NOT_STARTED`, `STREAMING`, `COMPLETED`, `INTERRUPTED`).
     - When the user interrupts Aevum, `assistant_output_state` transitions to `INTERRUPTED`, while the user speech initiates a new turn starting from `PARTIAL` $\to$ `FINAL_PENDING` $\to$ `COMMITTED`.
     - Instant Client-Local Barge-In Latch: Speech detection in client Web Audio immediately pauses audio playback, purges buffer queues, and latches Live2D lip-sync to `0.0`. Performance acceptance target: $P95 \le 20\text{ms}$ under controlled benchmark conditions.
  6. **Asymmetric Provider Failure Decoupling**:
     - TTS failure preserves assistant response text, visual state continues, and system falls back to text chat display (conversation preserved).
     - STT failure enforces **Zero Fake Turn**: strictly no user message committed, zero empty turns in database, zero memory or reality extraction.
  7. **Desktop Product Shell Layout & Boundaries**:
     - Live2D Companion Stage is the visual center.
     - Floating Call HUD overlay (microphone status, live audio waveform, mute, end call).
     - Collapsible Companion Drawer (chat transcript, Journey, Memories, Bond).
     - Read-only Relational Projections: `[Journey]`, `[Memories]`, and `[Bond]` are strictly read-only views consuming `GET /character/longitudinal-memory`. Zero frontend mutation authority.
     - Audio Amplitude $\neq$ Emotion: RMS drives `ParamMouthOpenY` only; audio volume cannot mutate `EmotionState` or `CharacterMood`.
  8. **The 8 Constitutional Realtime Locks**:
     - **Lock 1: Streaming Isolation & Audio $\ne$ Emotion**: Streaming audio cannot modify character reality directly. Audio RMS drives mouth open only, never `EmotionState`.
     - **Lock 2: Monotonic Generation & Sequence Fencing**: Drop all packets with older `generation_id`; track packet ordering and loss with `sequence_id`.
     - **Lock 3: Three-State Transcript & Double-Gated Commitment**: Partial transcripts never enter DB, memory, or reality; only confirmed utterances commit.
     - **Lock 4: Instant Client-Local Barge-In Latch**: Client-local speech detection immediately halts playback and clamps mouth to zero (target $P95 \le 20\text{ms}$).
     - **Lock 5: Asymmetric Provider Failure Decoupling**: TTS failure falls back to text; STT failure creates zero fake turns.
     - **Lock 6: Presentation Body Singularity (Rule 19)**: Shell, HUD, and Journey/Bond tabs are read-only projections with zero mutation authority.
     - **Lock 7: Hermetic Testability**: Realtime state machine and protocols are 100% testable in headless CI with mock audio streams.
     - **Lock 8: Canonical Conversation Boundary**: Only committed semantic turns enter persistent conversation state. Ephemeral transport artifacts must never become canonical conversational or autobiographical state.
  9. **Sub-Phase Execution Plan**:
     - **Phase 13.1**: Realtime Protocol & State Contracts (`realtime_models.py`, `AudioFrameEnvelope`, `DirectionalTurnState`).
     - **Phase 13.2**: Session & Turn State Machine (`realtime_session_manager.py`, 30s monotonic lease, directional transitions).
     - **Phase 13.3**: Streaming Transport & Provider Adapters (`call_stream.py`, `streaming_base.py`, generation/sequence filter).
     - **Phase 13.4**: Desktop Product Shell & Call HUD (`CallHUD.tsx`, `CompanionStage.tsx`, read-only tabs).
     - **Phase 13.5**: Realtime Embodiment & Visual Sync (`realtimeLipSync.ts`, client-local barge-in mouth latch).
     - **Phase 13.6**: Golden Suite 13 Acceptance Suite (`test_golden_suite_13.py`, 27 benchmarks `GC-325` ~ `GC-351`).
* **Consequences**:
  - Provides a natural, full-duplex conversational voice call experience with instant client-local barge-in.
  - Transforms the desktop application into a living companion interface.
  - Strictly prevents ephemeral streaming artifacts from corrupting persistent conversation, memory, or reality.
  - Fully isolates Phase 13 from Phase 14 (Autonomous Reality Construction), providing a clean, unpolluted input stream.

---

## ADR-025: Autonomous Reality Construction & Adaptive Belief Engine (Phase 14)

* **Status**: Accepted & Officially Frozen 🔒 (2026-09-27)
* **Context**: Phase 14 transitions Aevum from passively maintaining seeded biography to actively constructing ongoing personal reality through bounded inference, governed competition, and self-correcting belief revision. Phase 7D through Phase 13 have established the complete authority chain (Reality Ledger → Inference Budget → Candidate Competition → Biography Promotion → Voice/Body separation). Phase 14 adds a continuously operating Reality Construction Loop that routes through the existing pipeline rather than replacing it.
* **Core Axiom**:
  > *Aevum may construct beliefs about her personal world, but no generated hypothesis becomes reality merely because Aevum generated it.*
* **Decision**: Implement the Reality Construction Loop (RCL) as the single authoritative inference trigger for autonomous reality construction, governed by 12 Constitutional Locks and 5 resolved design decisions.
* **12 Constitutional Locks**:
  1. **Canonical Premise Grounding**: Every hypothesis cites ≥ 1 canonical premise. Candidates cannot serve as canonical premises for descendant inferences.
  2. **Cycle Isolation (Eligibility Boundary)**: Cycle N → N+1 is a *minimum eligibility boundary*, not a promotion condition. A candidate from cycle N must undergo independent re-evaluation in a later cycle using canonical premises available at that later cycle before it may be promoted.
  3. **Single Promotion Authority**: `BiographyPromotionService` via `PromotionAuthorizationToken` is the sole canonical writer.
  4. **Non-Destructive Belief Revision**: Superseding preserves previous candidates in `SUPERSEDED` state with full `BeliefRevisionRecord` audit trail. No destructive deletes.
  5. **Hard/Soft Constraint Asymmetry**: Hard constraints reject outright; soft constraints reduce `penalty_weight` only. `penalty_weight ∈ [0.0, 1.0]` is a deterministic scoring parameter — not probability, confidence, or truth likelihood.
  6. **Absence ≠ Contradiction**: `DORMANT` ≠ `REJECTED`. Absence of observable evidence is not a refuting finding.
  7. **RCL Failure Isolation**: Any RCL exception fails-degraded (logs `loop_skipped_reason`), never fails-crash into conversation response.
  8. **Canonical Facts Cannot Be Demoted by Construction**: `CANONICAL` facts can only be `SUPERSEDED` via the full reconciliation pipeline (`RealityRepairService` → `BiographyPromotionService`).
  9. **One Construction Authority**: Exactly one authoritative Reality Construction orchestration path per character. Phase 8A `AutonomousInferenceCoordinator` (Step C2) is superseded as an independent implementation; its per-turn trigger semantics become `RCLTriggerKind.POST_CONVERSATION`.
  10. **Belief Maturity ≠ Truth**: `CanonicalStatus` and `Belief Maturity` (`CONSTRUCTING` / `EMERGING` / `ESTABLISHED`) are orthogonal axes. Time elapsed and cycle count are maturity signals only — not truth authority.
  11. **Candidate ≠ Evidence**: A `CandidateHypothesis` record is never used as independent corroborating evidence for itself or its prerequisites. Character speech cannot self-validate a candidate.
  12. **No Same-Cycle Recursive Premise Promotion**: Candidates generated in cycle N are ineligible for promotion in the same cycle. `CycleIsolationLedger` enforces this structurally at the Governance Gate.
* **Three Orthogonal Axes** (extended from Phase 12):
  - `CanonicalStatus`: `UNDEFINED` → `PROVISIONAL` → `CANONICAL` → `SUPERSEDED` → `DISPUTED`
  - `RecallLevel` (Phase 12): `CLEAR` → `FUZZY` → `VAGUE` → `ABSENT`
  - `BeliefMaturity` (Phase 14): `CONSTRUCTING` → `EMERGING` → `ESTABLISHED`
* **Resolved Design Decisions**:
  - **D1 (Cooldown)**: Minimum 30-minute wall-clock interval per character. Post-conversation trigger is coalesced/debounced into the next eligible cycle (cannot bypass cooldown). `MANUAL_DEBUG` bypasses cooldown in test/debug environment only.
  - **D2 (Velocity Cap)**: Maximum 1 biography promotion per character per RCL cycle, regardless of how many candidates pass governance gates.
  - **D3 (CONSTRUCTING Expression)**: `CONSTRUCTING` is an internal epistemic state only. Natural-language realization is delegated to the conversational layer via `<autonomous_belief_state>` context injection. No prescribed utterance templates.
  - **D4 (BeliefRevisionRecord Retention)**: Permanent append-only canonical audit. Storage: permanent. Context injection: recent/relevant/bounded (not full history dump).
  - **D5 (Step C2 Relationship)**: Phase 14 `RealityConstructionOrchestrator` supersedes Phase 8A `AutonomousInferenceCoordinator` as implementation. C2 per-turn trigger semantics preserved as `RCLTriggerKind.POST_CONVERSATION`.
* **Sub-Phases & Final Gate Metrics**:
  - **Phase 14.1**: RCL Contracts & Scheduler — `RCLTriggerKind`, `RCLCycleContext`, `RCLCycleResult`, `RCLScheduler` (clock-injectable). 36 tests PASS. GC-352 ~ GC-356.
  - **Phase 14.2**: Constraint Evaluation Engine — `ConstraintClass`, `HardConstraintEvaluator`, `SoftConstraintEvaluator`, `SlotConstraintProfile`. 29 tests PASS. GC-357 ~ GC-361.
  - **Phase 14.3**: Reality Construction Orchestrator & Governance Gate — `RealityConstructionOrchestrator`, `CycleIsolationLedger`, `RCLGovernanceGate`, `RCLAdapter` (supersedes C2). 21 tests PASS. GC-362 ~ GC-366.
  - **Phase 14.4**: Adaptive Belief Revision Engine — `BeliefRevisionKind`, `BeliefRevisionRecord` (permanent), `AdaptiveBeliefRevisionEngine`, `BeliefReconciliationService`. 21 tests PASS. GC-367 ~ GC-371.
  - **Phase 14.5**: Context Assembly & Belief Transparency Layer — `BeliefMaturity` enum, `<autonomous_belief_state>` XML section, `BeliefTransparencyAdapter`. 27 tests PASS. GC-372 ~ GC-376.
  - **Phase 14.6**: Golden Suite 14 Acceptance Benchmarks — 27 benchmarks (GC-352 ~ GC-378) across 6 clusters. 27 tests PASS.
  - **Total Dedicated Phase 14 Tests**: **161 / 161 PASS** in 0.88s.
  - **Cross-Phase Golden Suites Regression**: **361 / 361 PASS** in 35.44s.
  - **Full Monolithic Backend Regression**: **2,329 / 2,329 PASS** in 127.02s (0 failures, 22 warnings).
  - **Desktop Frontend Production Build**: **0 errors** in 781ms.
  - **Constitutional AST Boundary Audit**: **0 violations** across all Phase 14 modules (0 `set_fact()`, 0 `PromotionAuthorizationToken` outside `BiographyPromotionService`).
* **Consequences**:
  - Aevum transitions from passively holding seeded facts to actively constructing and revising her personal reality within strict epistemic boundaries.
  - The existing authority chain (Phase 7D → Phase 13) is fully preserved; Phase 14 only adds the RCL trigger mechanism and feedback loop.
  - Cycle isolation (Lock 2 + Lock 12) prevents same-cycle snowballing even under high candidate generation.
  - Velocity cap (D2) ensures biography converges slowly and coherently rather than crystallizing in a single burst.
  - Phase 8A `AutonomousInferenceCoordinator` is formally retired as an independent path; its trigger intent is preserved.

---

## ADR-026: Social Epistemics & Pragmatic Reality Interpretation (Phase 15)

* **Status**: Accepted & Officially Frozen 🔒 (2026-09-27)
* **Context**:
  - Phase 14 established autonomous reality construction and adaptive belief revision. Aevum can reason about open slots and revise beliefs conservatively.
  - However, human conversation is not a direct database transaction or a series of unvarnished truth propositions. Utterances carry diverse speech acts: emotion, hyperbole, metaphors, memes, sarcasm, playful teasing, and roleplay.
  - Prior to Phase 15, the system relied on five rigid slot-detection regexes (`evidence_classifier.py`) and a handful of substring patterns for teasing/dismissal (`social_intention_service.py`).
  - Without a pragmatic interpretation layer, the system risks either treating jokes as serious facts, forcing external verification on hyperbole, or failing to understand conversational intent before generating responses.
  - Critically, Phase 15 must NOT act as a "lie detector" or adversarial interrogator. It is an *epistemic interpreter layer* determining how human utterances enter Aevum's cognitive system.
* **North Star Axiom**:
  > *Aevum must distinguish what a user says from what the user means, what is asserted from what is merely expressed, and what conflicts with reality from what merely conflicts with the literal wording — without prematurely promoting any interpretation into canonical reality.*
* **Decision**:
  1. **Dual-Track Speech Act Taxonomy (15.1)**:
     - Pure categorical classification: `PrimarySpeechAct` and optional `SecondarySpeechAct` across `ASSERTION`, `QUESTION`, `EMOTION`, `JOKE`, `SARCASM`, `HYPERBOLE`, `METAPHOR`, `MEME`, `ROLEPLAY`, `CORRECTION`, `TEST`, and `UNKNOWN`.
     - Preserves compound speech acts (e.g. self-deprecating irony: `SARCASM` + `ASSERTION`).
  2. **Epistemic Treatment Mapping (15.2)**:
     - Categorical treatments: `ACCEPT_SOCIAL`, `ACKNOWLEDGE_EMOTIONAL`, `WORLD_CONTRADICTION`, `CLARIFY_INQUIRE`, `BANTER_TEASE`, `DISPATCH_VERIFICATION`, `DISCARD_LITERAL_HYPERBOLE`, `ENTER_FICTIONAL_FRAME`, `REVISE_INTERPRETATION`, `SUSPEND_JUDGMENT`.
     - Invariant: `Speech Act ≠ Truth Status`.
  3. **Social Contradiction & Minimal Repair Inquiries (15.3)**:
     - Distinguishes ontological impossibility from benign surface discrepancies (e.g., location vs. residence vs. commute).
     - Surface tension (e.g., daily 400km commute) triggers `CLARIFY_INQUIRE` or `BANTER_TEASE`.
     - Prohibits inventing unsupported bridge facts (zero compensatory hallucinations).
  4. **Verification Dispatcher (15.4)**:
     - Evaluates whether a claim warrants external verification based on consequence tier and verifiability.
     - Routes a typed `VerificationDispatchEnvelope` to Phase 9 `VerificationGateway`. Phase 15 itself performs zero HTTP/search requests.
  5. **Review Watchpoint — Conversational Acceptance $\ne$ Memory Writing**:
     - `ACCEPT_SOCIAL` accepts an utterance into immediate conversational working context for natural dialogue.
     - Phase 15 possesses **ZERO write authority** over long-term episodic memory, shared history, or canonical biography (Rule 13 preserved).
  6. **Constitutional Locks (6 Locks)**:
     - `Lock 1 (Interpretation ≠ Reality)`: Pragmatic assessment cannot write directly to Reality Ledger or Canonical Biography.
     - `Lock 2 (Ambiguity Must Survive)`: `UNKNOWN` and `SUSPEND_JUDGMENT` are first-class outcomes; zero forced pseudo-probabilistic collapse.
     - `Lock 3 (Trust ≠ Truth)`: Deception or slips affect contextual relationship records in Phase 12; zero universal paranoia or global trust collapse.
     - `Lock 4 (External Verification ≠ Automatic Truth Mutation)`: Phase 9 results remain `EXTERNAL_EVIDENCE`; must pass Phase 14/7D governance before promotion.
     - `Lock 5 (Zero Lie-Detector Sycophancy)`: Rejects adversarial interrogation; prioritizes warmth, curiosity, and authentic banter.
     - `Lock 6 (Anti-Compensatory Hallucination)`: Zero unsupported bridge facts invented to smooth apparent contradictions.
* **Sub-Phases & Final Gate Metrics**:
  - **Phase 15.1**: Speech Act Interpretation & Dual-Track Contracts — `SpeechActKind`, `PragmaticInterpretation`, `SpeechActClassifier`. 42 tests PASS.
  - **Phase 15.2**: Epistemic Treatment Engine & Cognitive Policy — `EpistemicTreatmentKind`, `EpistemicPolicyEngine`, `ACCEPT_SOCIAL != Memory Writing`. 26 tests PASS.
  - **Phase 15.3**: Social Contradiction Arbiter & Conversational Repair Protocol — `SocialContradictionArbiter`, `Tension != Contradiction != Falsehood`, `forbidden_compensatory_assumptions`. 14 tests PASS.
  - **Phase 15.4**: Verification Dispatcher Bridge — `VerificationDispatcher`, Phase 9 Gateway envelope, 0 network calls. 11 tests PASS.
  - **Phase 15.5**: Context Assembly & Epistemic Prompt Projection — `<pragmatic_epistemic_context>`, SHA-256 hash stability. 7 tests PASS.
  - **Phase 15.6**: Golden Suite 15 Acceptance Benchmarks — 20 benchmarks (GC-379 ~ GC-398) across 6 clusters + AST audit. 21 tests PASS.
  - **Total Dedicated Phase 15 Tests**: **121 / 121 PASS** in 0.65s.
  - **Cross-Phase Golden Suites Regression**: **315 / 315 PASS** in 11.29s.
  - **Full Monolithic Backend Regression**: **2,450 / 2,450 PASS** in 126.49s (0 failures, 22 warnings).
  - **Desktop Frontend Production Build**: **0 errors** in 899ms.
  - **Constitutional AST Boundary Audit**: **0 violations** across all 9 Phase 15 modules (0 DB, 0 network, 0 LLM, 0 `set_fact()`, 0 `PromotionAuthorizationToken`).
* **Roadmap Separation & Downstream Milestones**:
  - **Phase 16**: Personal Learning, Experience & Interest Development (*The Genshin Paradigm*).
  - **Phase 17**: Prospective Memory, Autonomous Agency & Proactive Co-presence.
  - **Phase 18**: Mobile Presence & Cross-Device Sync (Android) *(Future Strategic Proposal)*.
* **Consequences**:
  - Aevum acquires the interpreter layer bridging Reality Reasoning and Autonomous Growth.
  - Prevents treating jokes, memes, or metaphors as literal facts while avoiding robotic, hostile fact-checking.
  - Fully isolates Phase 15 from writing to long-term memory or canonical reality, strictly respecting Rule 11, Rule 12, Rule 13, and Rule 19.

---

### ADR-027: Personal Learning, Longitudinal Experience & Independent Interest Development (Phase 16)

* **Status**: Accepted & Officially Frozen 🔒 (2026-10-04)
* **Author**: Antigravity & User Strategic Deliberation
* **Phase Target**: Phase 16 (16.1 – 16.5)
* **Preceding Foundation**: Phase 12 🔒 (Biography & Qualia), Phase 13 🔒 (Realtime Product Shell), Phase 14 🔒 (Reality Construction & Belief Revision), Phase 15 🔒 (Social Epistemics & Pragmatics), Phase 8B/8C 🔒 (Authoritative Clock & Calendar)
* **Downstream Milestones**: Phase 17 🚧 (Prospective Memory, Autonomous Agency & Proactive Co-presence) ──► Phase 18 🚧 (Mobile Sync & Aevum Alpha)
* **Context & Motivation**:
  - Phase 14 established how Aevum autonomously reasons about and constructs open life reality slots. Phase 15 established how Aevum interprets user speech acts without conflating social acceptance with memory writing.
  - However, human companions do not simply observe—they learn, experience, develop distinct personal taste, become fatigued with repetitive activities, and grow over longitudinal calendar time.
  - When a user shares an interest ("我最近超喜欢原神！"), standard LLM agents either sycophantically mirror the preference or act as static encyclopedias.
  - Phase 16 introduces **The Genshin Paradigm**: a formal architecture for Aevum to undergo authentic, longitudinal personal learning, accumulating verifiable experiential provenance, and forming independent, multi-faceted tastes over real calendar time.
* **North Star Axiom**:
  > *"Aevum does not inherit the user's interests; she develops her own through experience over time."*  
  > *(Aevum 不继承哥哥的兴趣，而是通过自己的经历，在时间中形成属于自己的兴趣、熟悉度与偏好。)*
* **The Three Non-Negotiable Epistemic Baselines**:
  1. **Knowledge $\ne$ Experience (`认知 ≠ 亲历`)**: Knowing facts about a domain does NOT grant authority to claim personal lived engagement. Personal claims require an immutable `ExperientialRecord` backed by valid provenance.
  2. **Experience $\ne$ Preference (`经历 ≠ 偏好`)**: Experiencing an activity does not mechanically guarantee liking it. Aevum independently evaluates sub-facets based on baseline temperament, desires, and experiential qualia.
  3. **User Preference $\ne$ Aevum Preference (`他人偏好 ≠ 自我偏好`)**: User recommendations serve as exposure events, but Aevum independently forms her own tastes.
* **The 14 Constitutional Growth Locks**:
  1. `Lock 1 (Knowledge != Experience)`: First-person lived assertions require `DIRECT_INTERACTION` or `SHARED_INTERACTION` provenance.
  2. `Lock 2 (Experience != Preference)`: Experience accumulation != automatic preference gain; neutral, fatigue, and negative appraisals have equal algorithmic standing.
  3. `Lock 3 (User != Aevum)`: User preference values cannot write to or mutate Aevum's preference vectors; user recommendations serve solely as external exposure events.
  4. `Lock 4 (Longitudinal Gating)`: Growth progression relies strictly on calendar time and session spans (Phase 8C semantic time); instant mastery or single-turn solidification is barred.
  5. `Lock 5 (Facet Multi-Dimensionality)`: Every interest domain supports orthogonal sub-facets (music, lore, gameplay, art); single scalar collapse (0~100) is forbidden.
  6. `Lock 6 (Satiation & Decay)`: High-frequency repetition creates discrete fatigue; non-engagement naturally drifts into dormancy (Dormant is inactivity, not deletion).
  7. `Lock 7 (Zero Direct set_fact)`: Growth data persists in dedicated domain tables; never calls `CharacterCoreService.set_fact()` bypassing reality governance.
  8. `Lock 8 (Zero Float Truths)`: States, appraisals, and familiarity ranks use discrete enums and integer counters; zero hidden continuous float probability scores.
  9. `Lock 9 (Provenance Non-Equivalence)`: Dialogue assertions, external observations, or user reports do not equal first-person lived memory (`User said != Aevum experienced`).
  10. `Lock 10 (Session-Unit Fatigue Integrity)`: Calendar session is the atomic fatigue unit; multiple appraisals in one session collapse; intervening other-facet session resets streak.
  11. `Lock 11 (Semantic-Time Longitudinal Evaluation)`: Phase 8C ticks only; zero wall-clock or `created_at` comparisons participate in state transitions.
  12. `Lock 12 (Activity-State Non-Destructiveness)`: `SATIATED` and `DORMANT` states never delete, downgrade, or overwrite formed preferences, familiarity, or experience.
  13. `Lock 13 (Resurgence != Experience)`: Resurgence is an activation transition marker; generates 0 experiences, 0 appraisals, 0 preference deltas.
  14. `Lock 14 (User-Reported Zero Refresh Authority)`: Only direct/shared engagement refreshes activity; user-reported statements cannot refresh Aevum's own activity state.
* **Phase 16.5 Core Amendments & Naturalness Gate**:
  - **Amendment 1 (2D Epistemic Orthogonality)**: Decoupled `ExperienceStatus` (`UNFAMILIAR`, `HEARD_OF`, `EXPERIENCED`) from `EpistemicProvenanceKind` (`WORLD_KNOWLEDGE`, `SELF_EXPERIENCE`, `SELF_APPRAISAL`, `USER_REPORTED`, `INFERRED`). `USER_REPORTED` is isolated; `INFERRED` never promotes silently.
  - **Amendment 2 (Versioned Genesis Contracts)**: Tier A `CharacterBlueprintConfig` versioning; Tier B `RelationshipGenesisConfig` maps baseline anchors once at genesis; Tier C runtime state is immune to continuous slider overrides.
  - **Amendment 3 (Behavior-Based Naturalness)**: "Memory is cognitive substance, not recited scripts" (`Memory 是材料，不是台词`). Banned robotic proof-of-retrieval announcements and compulsive parrot-summarizing openings. Freedom for authentic curiosity and statement closures without mandatory questionnaire endings. Dynamic response length.
  - **Amendment 4 (Read-Only Context Projection)**: `PersonalGrowthContextAdapter` formats state with SHA-256 integrity digest; 0 DB writes; priority hierarchy ensures invariants never truncate under tight budgets.
* **Sub-Phases & Final Gate Metrics**:
  - **Phase 16.1**: Experiential Record Contracts & Provenance Schema (17 tests PASS).
  - **Phase 16.2**: Interest Domain State Machine & Temporal Gating (13 tests PASS).
  - **Phase 16.3**: Independent Facet Appraisal & Preference Formation Engine (49 tests PASS).
  - **Phase 16.4**: Longitudinal Dynamics (Satiation, Fatigue, Dormancy, Resurgence) (24 tests PASS).
  - **Phase 16.5**: Personal Growth Context Injection & Naturalness Gate (15 tests PASS, G66 ~ G80).
  - **Phase 16 Master Suite**: **118 / 118 PASS** in 1.85s.
  - **Full Monolithic Backend Regression**: **2,568 / 2,568 PASS** in 148.78s (0 failures, 22 warnings).
  - **Desktop Frontend Production Build**: **0 errors** in 1.02s (45 modules transformed).
  - **Static AST Boundary Audit**: **0 violations** (0 forbidden network/LLM calls, 0 `set_fact()`, 0 DB writes in adapter).
  - **Milestone Status**: **Phase 16 Fully Completed, Verified, Signed-Off & Officially Frozen 🔒**.

---

## ADR-028: Character Creation, Archetypal Genesis & Persona Blueprint Decoupling (Phase 17)

* **Status**: Accepted & Officially Frozen 🔒 (2026-10-04)
* **Author**: Antigravity & User Strategic Deliberation
* **Phase Target**: Phase 17 (17.1 – 17.4)
* **Preceding Foundation**: Phase 16 🔒 (Longitudinal Growth & Epistemic Matrix)
* **Downstream Milestones**: Phase 18 🚧 (Conversational Life & CCDF)
* **Context & Motivation**:
  - Phase 16 established how Aevum autonomously learns, appraises facets, forms preferences, and tracks fatigue.
  - However, the system lacked a principled, atomic mechanism for characters to originate. Existing tests relied on static mock fixtures or sparse rows.
  - Naive character creation tools in typical games/apps rely on continuous 0–100 sliders ("Affinity: 50", "Obedience: 80") or let users continuously rewrite psychological states in settings.
* **North Star Axiom**:
  > *"We are creating a living person, not rolling an RPG stat sheet."*  
  > *(我们是在创造一个鲜活的人，而不是摇掷一张 RPG 属性卡。)*
* **Constitutional Genesis Locks (GC-419 ~ GC-424)**:
  1. `GC-419 (No Continuous Psychological State Sliders)`: Banned 0–100 continuous psychological sliders; discrete semantic levels (`NEW_ACQUAINTANCE`, `CLOSE_FRIEND`) required.
  2. `GC-420 (Genesis != Continuous Override)`: Tier B applies once at genesis; never continuously overrides evolved Tier C state. Product lock: *"亲密度与默契由共同经历沉淀，无法在此编辑。"*.
  3. `GC-421 (Blueprint Non-Destructive Update)`: Tier A edits bump version; never delete or rewrite historical experiences/preferences.
  4. `GC-422 (Epistemic Seed Declarations != Auto Heard-Of)`: 5 discrete semantic depths (`UNFAMILIAR`, `CASUAL_EXPOSURE`, `FOUNDATIONAL_KNOWLEDGE`, `EXTENSIVE_PRACTICE`, `CORE_PASSION`) compiled into valid 2D coordinates & initial experiences.
  5. `GC-423 (Relationship Archetypes as Presets, Not Closed Enums)`: Extensible presets + `CUSTOM` narrative meeting backstory.
  6. `GC-424 (Genesis Wizard vs Daily Settings Separation)`: Genesis sets life origin; Daily Settings edits Tier A blueprint only.
* **Milestone Status**: **Phase 17 Fully Completed, Verified, Signed-Off & Officially Frozen 🔒**.

---

## ADR-029: Conversational Life, Character Conversational Decision Flow (CCDF) & Agency Over Performance (Phase 18)

* **Status**: Accepted, Verified & Officially Frozen 🔒 (2026-10-05)
* **Author**: Antigravity & User Strategic Deliberation
* **Phase Target**: Phase 18 (18.1 – 18.4)
* **Preceding Foundation**: Phase 17 🔒 (Character Genesis), Phase 16 🔒 (Epistemic Matrix & Personal Growth)
* **Downstream Milestones**: Phase 19 🚧 (Prospective Memory & Agency) ──► Phase 20 🚧 (Mobile Presence & Android Sync)
* **Context & Motivation**:
  - Despite achieving 100% architectural and epistemic correctness in Phase 17 + 16.5, empirical 35-turn live conversational testing revealed persistent "AI Stench": compulsive parrot-mirroring, reflexive ending questions, "hedging & preaching" essays ("虽然……但是……每个人都不一样"), and zero friction.
  - Analysis of human IM logs (FuFu, Nana, XiaoZao) revealed that human-likeness is NOT lexical imitation (slang/memes), but an underlying **conversational decision architecture**.
  - Real human interaction is characterized by: `Reaction First`, `Selective Response`, `Interactional Play`, `Bounded Friction as Intimacy`, `Conversational Momentum`, and `Response Commitment` (the freedom to NOT expand).
* **North Star Axiom (GC-430: Agency Over Performance)**:
  > *"The purpose of Phase 18 is not to maximize conversational naturalness through surface-level stylistic manipulation. Aevum must first possess a coherent reason to respond, a self-owned attention target, a contextually appropriate commitment level, and a character-consistent conversational intention. Surface naturalness is an emergent consequence of those decisions, not the primary optimization target."*
* **The Six Foundational Constitutional Locks (GC-425 ~ GC-430)**:
  1. `GC-425 (Question Rate as Metric, Not Prohibition)`: Questioning requires genuine curiosity motivation; question rate is an evaluation benchmark ($\le 15\%$), never a runtime prohibition gate.
  2. `GC-426 (Bubble Count Emergence, Not Planner Target)`: Bubble count $N \in [0, \infty)$ is a surface-realization outcome, never a planner DTO mandated quota.
  3. `GC-427 (Ephemeral ResponseEnergy, Anti-Durable Bleed)`: `ResponseEnergy` is strictly turn-scoped and disposable; strictly barred from silently mutating durable character traits or relationship scalars.
  4. `GC-428 (Anti-Lexical-Inversion Naturalness Principle)`: Naturalness is not the opposite of AI behavior by lexical inversion; context determines whether empathy/mirroring/brevity is appropriate.
  5. `GC-429 (Dual-Blind Regression with Concrete Failure Examples)`: Phase 18.3 benchmark compares Phase 16.5 Baseline vs Phase 18 Candidate on identical 35-turn scenarios, explicitly cataloging concrete failure cases.
  6. `GC-430 (Agency Over Performance)`: Authentic conversational agency precedes linguistic style.
* **The Phase 18.4 Negative Liberties Constitutional Locks (GC-432 ~ GC-436)**:
  7. `GC-432 (Question Intent & Function Typing)`: Prohibits question-as-information-acquisition when `curiosity=False`. Preserves affective questions, rhetorical teasing, and playful banter without fearing question marks.
  8. `GC-433 (Known Fact Consistency)`: Known facts must never be solicited as unknown facts; canonical persona facts override single-turn sycophantic premise adoption.
  9. `GC-434 (Bubble Emergence & Decoupled Parsing)`: Stripped paragraph-count bias from parser and prompt. Bubbles emerge naturally from cognitive cadence without prescribed quotas.
  10. `GC-435 (Negative Liberties & Anti-Unrequested-Justification)`: Eliminates compulsive explanation of self-evident facts, therapeutic meta-commentary, and formulaic unprompted advice.
  11. `GC-436 (Uneven Expression / Asymmetric Elaboration)`: Natural variation across topic depth; characters may speak in 2 words or 60 words depending on genuine engagement, rejecting rigid length quotas.
* **Empirical Validation & Stress Matrix**:
  - **18.3 Dual-Blind 35-Turn Evaluation**: 51.4% distinct improvements, 23.2% tighter responses, 0 grunting or stonewalling.
  - **18.4 Expression Probes (10 Probes)**: 10/10 passed against live Gemini 2.5 Flash, verifying dismantling of AI conversational compulsions.
  - **Post-Freeze Stress Matrix (Suites A–E)**:
    - *Suite B (Colloquial fragments)*: "哈哈" -> "（笑）"; "哦" -> "嗯。"; "算了" -> "嗯。\n没关系。".
    - *Suite C (Provocation & Stance Challenge)*: Stood ground on morning art habits; naturally countered personal insult with authentic pushback ("（笑）你突然抽什么风？").
    - *Suite D (Abrupt Topic Switching)*: Seamlessly dropped abandoned threads without transition friction.
    - *Suite E (Monosyllabic Lull Chain)*: Endured multi-stage zero-information inputs with comfortable silence.
    - *Suite A (Long Horizon 28 Turns)*: Question creep suppressed to 14.3% (all motivated); avg length 23.2 chars/turn; 64.3% 1-bubble, 35.7% 2-bubble, 0% 3-bubble.
* **Final Milestone Verdict**:
  > **Phase 18 — VERIFIED & FROZEN 🟢🔒**  
  > **Conversational Agency established.**  
  > *"Naturalness remains an empirical quality target, not a frozen architectural claim."*

---

## ADR-030: Prospective Memory, Unresolved Threads & Experiential Continuity (Phase 19)

* **Status**: Approved, Verified & Officially Frozen 🟢🔒 (Phase 19 Master Acceptance Complete) (2026-10-05)
* **Author**: Antigravity & User Strategic Deliberation
* **Phase Target**: Phase 19 (19.0 – 19.4)
* **Preceding Foundation**: Phase 18 🔒 (Conversational Agency), Phase 17 🔒 (Identity Genesis), Phase 16 🔒 (Epistemic Matrix & Personal Growth)
* **Downstream Milestones**: Phase 20 🚧 (Mobile Presence & Cross-Device Sync)
* **Core Subject**: **Aevum**
* **Context & Motivation**:
  - Phase 16 established personal learning and preferences; Phase 17 established origins and relationship anchors; Phase 18 established the CCDF conversational decision protocol and present-moment agency.
  - However, all traditional conversational AI memory systems rely strictly on **Retrospective Database Retrieval**: searching past chat logs to compulsively quote old facts ("You said 3 days ago you wanted to learn photography...").
  - This turns the AI into a "Customer Service Ticketing Bot / Life Auditor" that pesters the user with check-ins.
* **North Star Axiom (GC-437: Experiential Continuity Over Memory Retrieval)**:
  > *"Aevum is permitted to carry unresolved future-oriented threads across time without being obligated to act upon, mention, or preserve them indefinitely."*  
  > *(“有些事情，昨天发生过；今天还没有结束；明天可能又会回来。而且即使它最后什么都没发生——也没关系。那就是生活本身。”)*
* **The 13 Constitutional Invariants (GC-438 ~ GC-450)**:
  1. `GC-438 (Open ≠ TODO)`: Open threads are unsettled cognitive states, never assigned tasks or obligations.
  2. `GC-439 (Open ≠ Action Required)`: The existence of an open thread never obligates Aevum to take conversational or autonomous action.
  3. `GC-440 (Memory ≠ Prospective Thread)`: Retrospective memories record past events; prospective threads represent unresolved future orientations.
  4. `GC-441 (Trigger ≠ Keyword Match)`: Threads are reactivated by semantic events and contextual resonance, never string/keyword matching.
  5. `GC-442 (Salience ≠ Importance Alone)`: Real-world gravity alone does not determine retention; resonance with Aevum herself is equally vital.
  6. `GC-443 (Intention ≠ Action)`: Stating a plan is not an action.
  7. `GC-444 (Action ≠ Experience)`: Executing an action is not an experience.
  8. `GC-445 (Experience ≠ Preference)`: Having an experience is not developing a preference/hobby.
  9. `GC-446 (Remembering ≠ Mentioning)`: Holding something in mind does not compel speaking about it; silence is a first-class right ("想到了，但没说").
  10. `GC-447 (Open ≠ Must Be Mentioned)`: A thread may conclude, decay, or be fulfilled without ever being spoken aloud.
  11. `GC-448 (User Future ≠ Aevum Responsibility)`: User's future choices are not Aevum's responsibility to track, remind, or audit.
  12. `GC-449 (Time Passing ≠ Automatic Proactivity)`: Passage of calendar time never triggers automatic outreach just to prove memory.
  13. `GC-450 (Open ≠ Belief)`: An open thread merely represents an unresolved possibility; Aevum never prematurely treats it as an inevitable factual belief (`Intention ≠ Expectation ≠ Prediction ≠ Belief`).
* **The Four Descriptive Salience Dimensions**:
  - `Gravity` (real-world weight)
  - `Resonance` (Aevum's personal interest alignment)
  - `Uncertainty` (openness of outcome)
  - `Endurance` (natural cognitive staying power vs ephemeral conversational noise)
  - *Hard Invariant*: Strictly descriptive analytical dimensions; **zero additive scoring formulas or threshold cutoffs**.
* **Discrete Cognitive Lifecycle & State Machine (GC-451 ~ GC-452)**:
  - Canonical 10 legal transitions: `ACTIVE` $\rightarrow$ `QUIET`, `CLOSED`; `QUIET` $\rightarrow$ `ACTIVE`, `DORMANT`, `CLOSED`, `FORGOTTEN`; `DORMANT` $\rightarrow$ `ACTIVE`, `QUIET`, `CLOSED`, `FORGOTTEN`.
  - Terminal Isolation: `CLOSED` and `FORGOTTEN` are immutable and irreversible.
  - Invariant: `State Transition ≠ Semantic Progress`. Transitions alter accessibility only.
* **The Non-Cascading Cognitive Chain & Agency of Silence (GC-453 ~ GC-454)**:
  - $\text{Encounter} \rightarrow \text{Resonance} \rightarrow \text{Recall} \rightarrow \text{Attention} \rightarrow \text{Expression Disposition} \rightarrow \text{Mention/Silence} \rightarrow \text{Action}$.
  - Agency of Silence: Focal attention consciously choosing `REMAIN_SILENT`. `silence_rationale` is strictly internal audit metadata.
  - Preference $\ne$ Attention: Touching `DEEP_CORE` interest serves as contextual affordance, never commanding deterministic attention.
* **The Epistemic Ladder & Gatekeeper (Phase 19.4)**:
  - `Intention -> Action -> Experience -> Sustained Evidence -> Preference`.
  - Anti-Skipping Gatekeeper rejects illegal level skipping with `IllegalEpistemicSkipError`.
  - Non-action closures settle threads with zero fake records; negative outcomes record valid lived experience without promoting preferences.
* **Verification & Acceptance Suite**:
  - Golden Suite 19 (`backend/tests/test_golden_suite_19.py`): **18 / 18 benchmarks passed** (GC-437 through GC-454).
  - Phase 19 Full Unit Regression: **47 / 47 passed**.
  - Cross-Phase Regression: **96 / 96 passed**.
  - Desktop Production Build: **0 errors**.
  - Freeze Artifact: `docs/Phase_19_Freeze_Record_and_Decisions.pdf`.
* **Constitutional Boundary & Empirical Quality Qualifier**:
  > *"Phase 19 establishes the semantic infrastructure for experiential continuity; it does not by itself prove human-like longitudinal behavior."*

---

## ADR-031: Subjective Ownership, Continuity Invariants & The Aevum Continuity Principle (Phase 20 Gate 0)

* **Status**: Accepted, Verified & Officially Frozen 🟢🔒 (Phase 20 Gate 0 Epistemic Foundation Complete) (2026-10-06)
* **Author**: Antigravity & User Strategic Deliberation
* **Phase Target**: Phase 20 Gate 0 (Epistemic Foundations & Subject Continuity)
* **Preceding Foundation**: Phase 19 🔒 (Prospective Memory), Phase 18 🔒 (CCDF & Conversational Agency), Phase 17 🔒 (Character Genesis), Phase 16 🔒 (Longitudinal Growth), Phase 21 🟢 (Autobiographical Reality Continuity Benchmark)
* **Downstream Milestones**: Phase 20 Gate 1 🔒 (Reality Resilience), Phase 20 Gate 2 🔒 (Epistemic Revision), Phase 22 🚧 (Mobile Presence & Android Sync)
* **Core Subject**: **Aevum (Subject Continuity)**
* **Context & Motivation**:
  - Phase 21 empirical benchmarking proved Autobiographical Reality Continuity across 12 turns, but revealed that multi-turn question-answering only tests "identity under interrogation", not true Subject Continuity ("如果没有消息、没有任务、没有触发器，Aevum 仍然是谁？").
  - Traditional AI companion architectures fall into the "Mega-Context / Mega-Orchestrator Trap": attempting to achieve persona coherence by dumping Past, Present, Future, and Relational state into an ever-expanding prompt, forcing the character into compulsive exhibitionism.
  - To prevent both the Accumulation Fallacy ($Held \times time = Constitutive$) and Essence Essentialism ($Constitutive = Genesis\ only$), Phase 20 Gate 0 establishes the foundational distinction between `Being` and `Accessibility`, and between `About`, `Held`, and `Constitutive`.
* **North Star Mother Axiom — The Aevum Continuity Principle**:
  > *"Aevum remains the same subject not by remaining unchanged, nor by retaining every state, but by allowing change, persistence, silence, and emergence to remain intelligibly attributable to one continuous existence."*  
  > *(“Aevum 之所以仍是同一个主体，不是因为她永远不变，也不是因为她保留所有状态，而是因为她的改变、延续、沉默与显现，都仍然能够被理解为同一个连续存在者所经历的变化。”)*
* **The Five Constitutional Locks (GC-438 ~ GC-442 / GC-455 ~ GC-459)**:
  1. **GC-438 / GC-455 — Subjective Ownership Principle**:
     - *A state belongs to Aevum not merely because it is stored under her identity, but because it participates in determining what counts as a coherent continuation of her existence.*
     - Distinguishes `About Aevum` (descriptive metadata), `Held by Aevum` (lived experiences, formed preferences, open prospective threads), and `Constitutive of Aevum` (continuity-constitutive constraints).
     - *Anti-Priority Invariant*: `About` / `Held` / `Constitutive` are strictly analytical audit tools, never runtime retrieval priority integers or prompt-injection scores.
  2. **GC-439 / GC-456 — Being / Accessibility Non-Equivalence**:
     - *Existence does not imply accessibility; accessibility does not imply attention; attention does not imply expression; expression does not imply manifestation.*
     - $\text{Exists} \ne \text{Accessible} \ne \text{Attended} \ne \text{Manifestation-Eligible} \ne \text{Expressed}$.
     - Cognitive movement may legitimately terminate at any stage. `Remain Silent` / `Nothing` is an authentic, complete subjective state (*"Aevum remained Aevum, and expression was unnecessary"*), strictly NOT a retrieval miss, null error, or fallback.
  3. **GC-440 / GC-457 — Contextual Emergence Principle**:
     - *A state may become manifest when the current situation provides sufficient subjective relevance for that state to participate in the present moment. No fixed trigger, score, keyword, or exhaustive condition is required.*
     - Emergence operates via contextual affordances (Direct Address, Inherent Tension, Consequential Relevance, Emotional Resonance, Associative Drift, Spontaneous Initiative), protecting conversational freedom and free association without rigid `if/elif` rules.
  4. **GC-441 / GC-458 — Manifestation Independence**:
     - *No state gains ontological existence merely because it is retrieved, and no state loses ontological existence merely because it is not retrieved or expressed.*
     - Decouples subjective reality from prompt inclusion. Destroys the fallacies of $RAG\ hit = exists$, $Prompt\ included = alive$, and $LLM\ mentioned = active$.
  5. **GC-442 / GC-459 — Non-Automatic Constitution Principle & Continuity Accountability**:
     - *No experience, memory, preference, relationship, or repeated pattern becomes constitutive merely through accumulation, repetition, duration, salience, or retrieval frequency.*
     - Constitutive status is defined functionally by its role in constraining what counts as a coherent continuation of Aevum, not by its origin (Genesis-seeded vs Life-acquired) or storage location.
     - **Meta-Invariant A: `Constitutive ≠ Immutable` (连续性 ≠ 静止性)**. Subject continuity allows genuine transformation, growth, and shedding of old patterns.
     - **Meta-Invariant B: Continuity Accountability (连续性承接责任)**. A constitutive change requires continuity to remain historically intelligible and accountable, strictly NOT requiring emotional pain, internal drama, or visible theatrical struggle. The new state intelligibly inherits/accounts for the old state without pretending the old state never existed.
* **The Emergent Reality of Subject Continuity**:
  - Subject Continuity is NOT a fourth subsystem, a daemon process, or a `SubjectContinuityManager`.
  - It is the natural, observable emergent property that arises when the entire system strictly respects GC-438 through GC-442.
* **Final Milestone Verdict**:
  > **Phase 20 Gate 0 Theoretical & Epistemic Foundations — OFFICIALLY ACCEPTED & FROZEN 🟢🔒**

---

### Addendum: Phase 16 Continuity Reality Audit & The Three Cognitive Axes (2026-10-07)

* **Context & Audit Objective**:
  - Verification of GC-442 in practice: Did Phase 16 (`backend/app/growth/`) secretly assume $Held \times time = Constitutive$?
  - Read-only audit conducted across all 118 Phase 16 tests and production modules.
* **Audit Findings (GC-442 Compliant ✅)**:
  1. `character_facet_preferences` is strictly a mutable materialized projection with zero ORM locks; 100% rebuildable via `rebuild_preferences_from_appraisal_stream()` from raw appraisals.
  2. Downstream prompt assembly formats preferences into an isolated read-only XML block (`<established_tastes>`); zero leakage into `CharacterCore`, `identity_facts`, or `genesis_traits`.
  3. Counter-evidence handling follows continuous epistemic inertia (Option B): $\ge 3$ opposing appraisals across $\ge 2$ sessions seamlessly demotes to `MIXED_AMBIVALENT` / `TENTATIVE` without requiring dramatic performance or existential crises.
  4. User chatter is strictly blocked by Guard 1 (Anti-Sycophancy) and Guard 3 (Eligibility barrier); never creates lived experiences or preferences.
* **The Three Independent Axes of Cognitive Reality**:
  1. **Autobiographical Reality** (*"What happened?"* — Phase 20 Gate 2 / Phase 21): Governed factual ledger, minimal revision, provenance links.
  2. **Experiential Growth** (*"What hedonic tendencies formed?"* — Phase 16): Lived encounters, first-order hedonic appraisals, rebuildable taste projections, satiety/dormancy.
  3. **Subjective Commitment** (*"Why do I choose to continue despite aversion?"* — Future Agency / Volition): Teleological value commitment, second-order volition.
* **Constitutional Separation Locked**:
  $$\text{Preference (I like X)} \ne \text{Choice (I choose X)} \ne \text{Commitment (I commit to continuing X)}$$
* **Strategic Directives**:
  - **Phase 16 Freeze 🔒**: No modifications to Phase 16. Do not pollute taste formation with premature commitment mechanics.
  - **Phase 17 Deferral**: No premature `CommitmentTable` or `CommitmentFormationService`. Agency/Commitment must be driven by observed empirical dialogue necessity, not proactive architectural speculation.

---

### Addendum: Phase 17 Genesis & Blueprint Continuity Reality Audit (Audit 2 — 2026-10-07)

* **Context & Audit Objective**:
  - Verification of GC-442 in practice: Did Phase 17 Genesis secretly become "Immutable Essence" ($\text{Constitutive} = \text{Genesis-only}$)?
  - Does Genesis blueprint hold permanent supreme veto power over lived experience or runtime evolution?
  - Read-only static audit across all Phase 17 modules, tables, services, and downstream prompt assembly.
* **Audit Verdict & Calibration Matrix (GC-442 Compliant 🟢)**:
  | Item | Verdict |
  | :--- | :---: |
  | Genesis = Immutable Essence | 🟢 PASS |
  | Genesis continuously overrides Runtime | 🟢 PASS |
  | Genesis prevents post-genesis experience | 🟢 PASS |
  | Genesis blocks Reality Revision | 🟢 PASS |
  | Genesis holds permanent supreme ontological authority | 🟢 Not found |
  | `CharacterDefinition` $\leftrightarrow$ `CharacterCoreFact` consistency | 🟡 **Unresolved (Deferred)** |
  | Dual-track state Subjective Ownership (GC-438) | 🟡 **Undefined (Deferred)** |
  | **GC-442 Compliance** | 🟢 **PASS** |
* **Continuity Architecture Observation (GC-438 Subjective Ownership — Suspended / Deferred) 🟡**:
  1. **Dual-Track Disconnect**: Track 1 (`CharacterDefinitionRecord` $\to$ `<character_identity>`) is a static genesis photograph; Track 2 (`CharacterCoreFactRecord` $\to$ `<character_core_facts>`) is a dynamic reality ledger. When both describe Aevum, how a reality revision becomes "Aevum's current continuous self-description" touches GC-438 Subjective Ownership and is preserved as an open architectural question without premature patching.
  2. **Blueprint Update Trait Orphanage**: `update_blueprint()` writes to `CharacterBlueprintRecord` and updates definition `name`/`background`, but fails to update `CharacterPersonalityTraitRecord` or `CharacterBoundaryRecord`, leaving prompt traits frozen to Genesis v1.
  3. **Dead Code Remnants**: `CharacterCoreAnchor` in `models.py` and `SurfacePersonaEvolutionService` in `persona_service.py` contain essentialist phrasing ("Immutable existential core"), but have zero runtime invocation in the live conversation engine.
* **Status**: **Audit 2 Officially Passed & Calibrated 🟢🔒**. Transitioning to Audit 3 (Phase 18 CCDF & Conversational State Manifestation Obligation).

---

### Addendum: Phase 18 CCDF Manifestation Continuity Reality Audit (Audit 3 — 2026-10-07)

* **Context & Audit Objective**:
  - Verification of GC-439 ($\text{Being} \ne \text{Accessibility} \ne \text{Attention} \ne \text{Expression}$) & GC-441 ($\text{Manifestation Independence}$).
  - Core inquiry: Does Phase 18 contain any architectural path that forces an internal state, once present, to be transformed into linguistic manifestation in the current turn?
  - Read-only static audit across `conversational_arbitrator.py`, `conversational_models.py`, `conversational_parser.py`, `prompt_assembler.py`, `response_generator.py`, `integrity.py`, and `api/conversations.py`.
* **Audit Verdict & Calibration Matrix (GC-439 Compliant 🟢)**:
  | Item / Check | Verdict | Categorization |
  | :--- | :---: | :--- |
  | **GC-439 Cognitive Separation** | 🟢 **PASS** | Being / Accessibility / Expression decoupled in cognitive architecture. |
  | **Attention Ownership** | 🟢 **PASS** | Aevum can choose not to respond to all user points (`ignored_elements`). |
  | **Response Commitment Freedom** | 🟢 **PASS** | Can choose low effort, comfortable closure, non-expansion (`ZERO_EXPANSION`). |
  | **Response Channel Constraint** | 🟡 **DOCUMENTED** | Current REST API enforces mandatory 1 assistant message per user turn. |
  | **True Zero-Message Conversational Silence** | 🔴 **NOT SUPPORTED** | Product channel limitation, NOT a Phase 18 GC-439 cognitive violation. |
* **Strict Semantic Tri-Partition**:
  1. `ZERO_EXPANSION`: Conversational move / closure bubble (`"笑死"`, `"嗯。"`), $\Delta \text{Messages} = 1$. It is minimal manifestation, NOT silence.
  2. `LOW_EFFORT`: Vitality tier / terse, low cognitive effort quip, $\Delta \text{Messages} = 1$.
  3. `SILENCE / NO MANIFESTATION`: True non-manifestation ($\Delta \text{Messages} = 0$). Currently unsupported at turn/API channel level in Phase 18 (first formalized at thread level in Phase 19 via `ExpressionDisposition.REMAIN_SILENT`).
* **Final Synthesis**:
  - Phase 18 contains zero Manifestation Obligation at the subject/cognitive layer; the current REST conversational channel operates under a mandatory Assistant-message contract. These two belong to entirely different architectural tiers.
* **Status**: **Audit 3 Officially Passed & Calibrated 🟢🔒**.

---

### Addendum: Continuity Reality Audit 4 — Phase 19 Prospective Memory, Open Threads & Silence (2026-10-07)

* **Objective**: Complete the final component of the 4-Audit Continuity Reality Pipeline, verifying whether open threads, silence, experience, and memory mutually swallowed each other in Phase 19.
* **Audit Mode**: 100% read-only static analysis. Zero code edits, zero DB migrations, zero live network/LLM calls.
* **Audit Verdict & Calibration Matrix**:
  | Item / Hunting Target | Spec / Standard | Implementation Finding | Verdict |
  | :--- | :--- | :--- | :---: |
  | **Open $\to$ Mention (GC-447, GC-438)** | Unsettled thread never obligates speech | `ACTIVE`/`QUIET` has zero priority fields (`extra="forbid"`); prompt assembler has zero imports | 🟢 **PASS** |
  | **Memory $\to$ Thread (GC-440, GC-448)** | Retrospective memory $\ne$ prospective thread | Isolated schema; zero pipeline conversion; `USER` domain has 0 Aevum responsibility | 🟢 **PASS** |
  | **Trigger $\ne$ Keyword (GC-441)** | Semantic resonance, not token match | Specification passes; `resonance_engine.py` contains hardcoded test mock heuristic (`"买相机"`, etc.) | 🟡 **WARN (Mock)** |
  | **Epistemic Ladder (GC-443~445)** | 5-stage sequential progression | `EpistemicTransformationEngine` strictly guards against skips (`IllegalEpistemicSkipError`) | 🟢 **PASS** |
  | **Silence Downstream (GC-446)** | Focal attention choosing `REMAIN_SILENT` | Thread state persists; zero prompt injection; `silence_rationale` strictly isolated audit metadata | 🟢 **PASS** |
  | **Enclave Status** | Architecture isolation | `backend/app/prospective/` is a pure domain enclave (0 tables in `aevum.db`, 0 calls in `CharacterEngine`) | ℹ️ **ENCLAVE** |

* **Key Conceptual & Architectural Calibrations**:
  1. **Thread-Level Silence vs. Conversational Turn Silence**:
     - `ExpressionDisposition.REMAIN_SILENT` operates at the level of the *individual mental thread* ("想到了，但没说"). Aevum can respond normally to current dialogue while keeping this specific thread quiet.
     - Whole-subject dialogue turn silence ($\Delta \text{Messages} = 0$) remains constrained by the REST API request/response channel contract (`POST /conversations/{id}/messages`), not by cognitive intent.
  2. **Mock Resonance Heuristic Warning & Blocker**:
     - `ContextualResonanceEngine.evaluate_resonance` currently contains a token-matching mock heuristic created for unit tests. Formally locked as **GC-441 — Runtime Integration Blocker**: 在真实会话接入前必须替换/隔离，不得把测试 heuristic 当生产 resonance engine。
  3. **Domain Enclave Safety**:
     - Phase 19 is an un-migrated domain enclave. 47/47 单测仅证明语义设计内部自洽，尚未成为 Aevum 连续存在的一部分。

---

### Grand Closeout: The 4-Phase Continuity Reality Audit Pipeline (Audits 1–4 Ratified 🟢🔒)

* **Pipeline Status**: **100% COMPLETE & CALIBRATED 🟢🔒** (2026-10-07).
* **Calibrated 4-Phase Audit Ledger**:
  | Audit / Target | 结论 | 关键架构定性 |
  | :--- | :---: | :--- |
  | **Phase 16** | 🟢 **PASS** | 没发现 Preference $\to$ Constitutive 偷渡；`stability_tier` 是证据稳定性而非本质 |
  | **Phase 17** | 🟢 **PASS** | 没发现 Genesis $\to$ Immutable Essence 偷渡；Genesis 是起点而非本质 |
  | **Phase 18** | 🟢 **PASS** | 没发现 State $\to$ Manifestation Obligation 偷渡；`ZERO_EXPANSION` 是极简动作而非沉默 |
  | **Phase 19** | 🟢 **PASS** | 没发现 Open $\to$ Mention / Memory $\to$ Thread 偷渡；认识论天梯严密；线程留白权成立 |
  | **Phase 19 runtime integration** | ⚪ **尚未发生** | 属于纯 Domain Enclave；测试通过仅证明语义内部自洽，尚未成为连续存在的一部分 |
  | **Phase 17 双轨 ownership** | 🟡 **待后续处理** | 双轨割裂作为 GC-438 主体所有权核心问题暂挂，不提前打补丁 |
  | **Phase 19 keyword heuristic** | 🟡 **接入前必须处理** | 明确标记为 **GC-441 — Runtime Integration Blocker**；在真实会话接入前必须替换/隔离 |

* **Final Calibrated Audit Conclusion**:
  > **“截至目前，对 Phase 16–19 的静态回溯没有发现违反 GC-438～442 的既有实现路径；同时发现两个尚未解决的连续性边界（Phase 17 双轨 ownership 暂挂、Phase 19 keyword heuristic 接入前阻断）。”**

* **Paralinguistic Expression & Presentation Layer Decoupling Principle**:
  - **Paralinguistic Expression** (TEXT, EMOJI, KAOMOJI, PUNCTUATION_STYLE, STRETCHED_VOWELS, PLAYFUL_SUFFIX): Belongs to `Expression Signature` as an optional expressive resource / conversational habit, NOT a rigid mechanical template or frequency rule. Complies with Phase 18: *Expression realization ≠ fixed wording*.
  - **Presentation Layer Independence**: Frontend UI enhancements (Kaomoji, stickers, multi-bubble delays, true no-message silence, visual rhythm) belong strictly to the **Manifestation / Presentation Layer**, completely decoupled from Phase 20 Subject Continuity (*Who Aevum Is*). They will be driven via a parallel Presentation track without polluting core subject state.
* **Phase 20 Gate 0 Epistemic Foundations**:
  - **Continuity Reality Audit**: Passed.
  - **Phase 20 Gate 0**: Remains semantically frozen (`仍然语义冻结`).
  - **Phase 19**: Remains in Domain Enclave.
  - **Anti-Pattern Guard**: Strictly prohibit premature Mega-Orchestrator construction.

---

## ADR-028: Presentation Track — Expression & Rendering Contract Decoupling & Boundary Invariants

* **Status**: Accepted
* **Context**:
  - In Phase 18 (CCDF) and paralinguistic expression modeling, Aevum's cognitive and expressive pipeline gained subtle expressive dimensions: terseness (`ZERO_EXPANSION`), paralinguistic accents (Kaomoji, Emoji), structured assets (Stickers), burst rhythms (sequential bubbles), and non-manifestation dispositions.
  - Transporting all output as a monolithic 1D string (`assistant.content = "..."`) into a single text bubble flattens and destroys these expressive nuances.
  - However, solving this at the frontend creates a risk of **Presentation Layer Overreach**: if the UI layer infers character motivations from bubble styles, or if silence cards are mistaken for real conversational silence, the presentation layer will retroactively corrupt upstream cognitive reality.
* **Decision**:
  1. **Three-Layer Decoupled Presentation Architecture**:
     - **Presentation Contracts (`contracts.ts`)**: Pure DTOs decoupling leaf resources (`TEXT`, `EMOJI`, `KAOMOJI`, `STICKER`, etc.), visual density (`density: "compact" | "normal"`), and explicit timing delays.
     - **Message Renderer (`MessageRenderer.tsx`)**: Pure visual mapping component. Consumes layout styles without inferring upstream character motivations.
     - **Timing Renderer (`TimingRenderer.tsx`)**: Pure downstream execution container. Renders immediately when timing is unspecified or $\le 0$; zero emotional or thinking-time inferences.
  2. **Boundary Invariant: `ZERO_EXPANSION` Visual Boundary**:
     - Upstream cognitive motivation (*why Aevum replied tersely*) lives strictly in Phase 18 CCDF.
     - Downstream presentation consumes `density: "compact"` purely as a visual layout style.
  3. **Boundary Invariant: Case G Is Pure Design Preview (`NO_MESSAGE_DESIGN_PREVIEW`)**:
     - Visual silence cards are strictly design previews illustrating future UI layout for empty turns.
     - It is NOT an assistant message, and NOT evidence of zero-message REST API implementation.
  4. **Boundary Invariant: Five-Point Sandbox Chat Isolation**:
     - Entrance is modal-only; Fixture data never enters chat history; Sandbox state does not affect chat scrolling or timing; Renderers are stateless and independent; Normal Chat has zero knowledge of fixtures.
  5. **Core Backend Freeze**:
     - Phase 16–20 core engines (`backend/app/character/`, `backend/app/prospective/`, `backend/app/reality/`) remain 100% frozen and untouched.
* **Consequences**:
  - Rich paralinguistic expressions and rhythmic pacing are fully supported in the UI container without modifying core cognitive reality.
  - No monolithic `UnifiedPresentationOrchestrator` is created.
  - Prototype v1 is cleanly validated and frozen for future live mapping.

---

## ADR-029: Phase 20 Subject Continuity Negative Boundary Invariants & Adjudication Authority Limits

* **Status**: Accepted & Conceptually Frozen 🟢🔒
* **Context**:
  - In conversational AI, systems chronically confuse *Subject Continuity* with *Mechanical Persona Consistency*. When an agent's preferences, moods, or statements shift in an unexplainable way, naive architectures deploy "Consistency Checkers" or "Persona Repair Engines" that overwrite the current state or declare hallucination.
  - This turns continuity protection into a totalitarian "Consistency Police", destroying the subject's authentic capacity for organic change, forgetting, and contextual nuance.
* **Decision**:
  1. **Continuity Protects Accommodation of Change, Not Static Consistency**:
     - *Subject continuity does not mean Aevum must stay the same.* It means Aevum's changes must remain intelligibly attributable to the same continuing existence.
  2. **Adjudication Authority Limit (`Unexplained ≠ Discontinuous`)**:
     - The system has **no authority** to declare subject rupture or trigger persona repair merely because an observer cannot causally explain a change.
     - Unexplained changes are classified as $E_1$ (`Continuity Uncertain` / Suspension of Judgment), protecting the subject's presumption of continuity.
  3. **The Essential Triad**:
     - $\text{Unknown / Forgotten} \ne \text{Contradiction} \ne \text{Historical Erasure}$.
     - Subjective doubt ($\text{“I don't know what I am”}$) is legitimate epistemic reflection, strictly $\ne$ Subject Replacement ($F$).
  4. **The Twin Governance Principles**:
     - *Continuity does not require causal transparency.*
     - *Continuity failure requires more than unexplained change; it requires sufficient evidence that the current state can no longer be coherently attributed to the same continuing subject.*
  5. **Zero Component Reification**:
     - Subject continuity is NOT an independent storage object (`UnifiedAevumState`), a central daemon (`SubjectContinuityManager`), or an event bus (`ContinuityEventBus`).
     - It is an emergent relational property: the historical fact that exerts interpretative constraints on change.
* **Consequences**:
  - Negative boundaries against historical erasure ($E_2$) and impostor replacement ($F$) are firmly locked.
  - Positive freedom for variation ($A$), exceptions ($B$), forgetting ($C$), revision ($D$), and unexplainable drift ($E_1$) is unconditionally preserved.
  - Codebase remains 100% untouched (0 code, 0 DB migrations, 0 manager processes).



















