# ROADMAP.md — Project Aevum Roadmap

> **MVP Vision**:
> *"I can live with Aevum for one week and she does not feel like an ordinary ChatGPT wrapper."*

---

## Overview

Project Aevum is built through incremental, structured phases. Each phase establishes a verified, testable layer of capability before progressing to the next.

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(Foundations) (1st Companion) (Character) (Memory) (Relationship) (Emotion) (Auto Life)
                                                                            │
Phase 12 ◄── Phase 11 ◄── Phase 10 ◄── Phase 9 ◄── Phase 8 ◄── Phase 7 ◄────┘
(Android)    (Call)       (Live2D)     (Voice)    (Desktop)    (Events)
```

---

## Phase Breakdown

### Phase 0 — Foundation *(Current Phase)*
* **Objective**: Establish repository blueprints, design architecture, development rules, and decision records.
* **Deliverables**:
  * Repository structure (`apps/`, `backend/`, `tests/`, `docs/`).
  * Core documentation: `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`.
  * Specialized documentation outlines in `docs/`.
* **Exit Criteria**: All foundational documentation committed; consensus on architectural direction; no premature application code.

---

### Phase 1 — First Companion
* **Objective**: Establish the basic client-server communication loop and LLM abstraction.
* **Deliverables**:
  * Backend initialization with FastAPI, SQLite, and SQLAlchemy.
  * LLM Provider Interface with Google Gemini API implementation.
  * Tauri 2 + React desktop shell with basic messaging interface.
  * Bi-directional communication over WebSocket with streaming text.
  * Basic session persistence.
* **Exit Criteria**: User can exchange messages with the companion via the desktop client, powered by Gemini via the provider interface, with raw session logging.

---

### Phase 2 — Character Engine
* **Objective**: Introduce grounded character identity, traits, and baseline configuration independent of prompt-tuning.
* **Deliverables**:
  * Character schema (personality traits, baseline temperament, speaking quirks, values).
  * System prompt compilation pipeline that grounds LLM prompts with character parameters.
  * Boundary enforcement mechanisms (ability to say "no", express distinct preferences).
* **Exit Criteria**: Character identity remains strictly consistent across conversations and rejects contradictory prompts.

---

### Phase 3 — Memory
* **Objective**: Build human-like memory decoupled from raw chat history.
* **Deliverables**:
  * Memory distillation pipeline: extracts entities, facts, and emotional moments from dialogue.
  * Multi-tier storage: Working memory, Episodic memory, Semantic memory.
  * Imperfect recall: Confidence scoring, relevance weighting, and graceful uncertainty handling ("I think you mentioned... but I don't recall exactly").
* **Exit Criteria**: Companion recalls past conversations days later with appropriate confidence, without injecting entire transcripts into context.

---

### Phase 4 — Relationship
* **Objective**: Implement multidimensional relationship modeling and progression.
* **Deliverables**:
  * Phase 4.1 — Relationship Foundation *(Completed)*: Persistent `RelationshipState` model, optimistic concurrency, relational storage, and default bootstrap seeding.
  * Phase 4.2 — Relationship Interaction Signal Foundation *(Completed)*: Extraction of structured behavioral signals from conversation dialogue with deterministic application policy, bounds clamping, aggregate capping, and strict affection isolation.
  * Phase 4.3 — Relationship Context Integration *(Completed)*: Qualitative semantic translation of relationship state via `RelationshipContextBuilder`, injecting `<relationship_context>` into `LLMContext.system_instructions` without raw metrics.
  * Phase 4.4 — Relationship Experience / History Foundation *(Completed)*: Structured recording and persistence of relationship-relevant historical experiences (`RelationshipExperienceRecord`) decoupled from continuous state metrics and memory.
* **Exit Criteria**: Relationship starts at neutral acquaintance level and requires natural, consistent interaction over time to deepen, grounding language generation without exposing internal mechanics.

---

### Phase 5 — Emotion
* **Objective**: Implement causal emotional simulation and internal drives.
* **Deliverables**:
  * Phase 5.1 — Emotion Model Foundation *(Completed)*: Persistent `EmotionState` domain model, non-romantic `EmotionType` vocabulary (17 states), single dominant affective state representation ($0.0 \le \text{intensity} \le 1.0$), `emotion_states` SQLite table with cascade to `character_definitions`, deterministic bootstrap baseline (`NEUTRAL`, `0.50`), and `EmotionService` with optimistic concurrency control.
  * Phase 5.2 — Emotion Cause / Event Foundation *(Completed)*: Persistent `EmotionEvent` domain model, `EmotionEventType` vocabulary (7 types), `emotion_events` SQLite table with cascade to `character_definitions`, and `EmotionEventService` with deterministic duplicate protection and reverse-chronological retrieval.
  * Phase 5.3 — Emotion Influence Foundation *(Completed)*: Persistent `EmotionInfluence` domain model, `EmotionInfluenceDirection` (`POSITIVE`, `NEGATIVE`), `emotion_influences` SQLite table linked to `character_definitions` and `emotion_events`, and `EmotionInfluenceService` with deterministic duplicate protection and reverse-chronological retrieval.
  * Phase 5.4 — Emotion Transition Proposal Foundation *(Completed)*: Pure, deterministic `EmotionTransitionEvaluator` and immutable `EmotionTransitionProposal` model calculating bounded proposed transitions without mutating or persisting authoritative state.
  * Phase 5.5 — Emotion State Application Foundation *(Completed)*: `EmotionStateApplicationService` and `EmotionStateApplicationResult` model establishing the controlled boundary to apply proposals to authoritative `EmotionState` with optimistic concurrency and stale proposal protection.
  * Phase 5.6 — Emotion Engine Foundation *(Completed)*: `EmotionEngine` internal orchestration layer connecting influence evaluation and authoritative state application without cross-domain coupling or psychology rule duplication.
  * Deterministic state transition engine (reactions to conversation topics, events, fatigue).
  * Baseline decay curves (moods naturally settle back to temperament baseline over time).
* **Exit Criteria**: Companion's emotional state changes for identifiable reasons and influences dialogue tone and responsiveness.

---

### Phase 6 — Autonomous Life & Character Engine
* **Objective**: Give the companion her own life, schedule, and internal engine orchestration for response decisions.
* **Deliverables**:
  * Phase 6.1 — Character Engine Foundation *(Completed)*: Read-only internal orchestration boundary (`CharacterEngine`) that gathers `CharacterDefinition`, `CharacterState`, `RelationshipState`, `EmotionState`, and relevant `Memory` into an immutable `CharacterResponseContext` without exposing raw database records, without LLM dependencies, and with zero state mutations.
  * Phase 6.2 — Response Generation Foundation *(Completed)*: `ResponseGenerator` service and `ResponseContextAssembler` that bridge `CharacterResponseContext` to the LLM Provider abstraction, enforcing strict prompt isolation, deterministic assembly, and zero domain mutations.
  * Phase 6.3 — First Playable Conversation Foundation *(Completed)*: Vertical slice wiring UI, API router, character engine, LLM provider, and message persistence.
  * Phase 6.4 — Character Intelligence *(In progress)*: Establish human-likeness acceptance criteria before extending life simulation. This phase introduces a Golden Conversation regression corpus, then incrementally connects Character Bible, relationship behavior semantics, current desires, behavioral planning, transient expression, and curated memory promotion. It does not replace existing Emotion, Relationship, Memory, Life, or Appraisal foundations.
  * Circadian clock and daily routine simulation (sleeping, studying, hobbies, chores).
  * Simulated social graph (friends, acquaintances, family references).
  * Availability state machine (available, busy, away, sleeping) affecting response behavior.
* **Exit Criteria**: Companion can be busy with her own life, share what she did while the user was away, and not exist purely on standby.

---

### Phase 7 — Character Cognition & Autonomous Life Simulation

#### Phase 7A — Dynamic Personal World & Epistemic Separation *(Completed)*
* **Objective**: Establish personal world facts, social circle, and epistemic separation between user statements, character reality, and world knowledge.
* **Deliverables**:
  * `PersonalWorldService`, `CharacterWorldFactRecord`, `CharacterSocialRecord`, and `CharacterBiographyRecord`.
  * Epistemic boundaries preventing user prompt injection from corrupting character ground truth.

#### Phase 7B — Character Cognition Foundation *(Completed & Officially Frozen)*
* **Objective**: Build Aevum's cognitive core, ensuring identity grounding, relational permissions, structured behavior planning, and personal reality formation.
* **Deliverables**:
  * **7B.0 Golden Suite v2 Benchmark**: 30 comprehensive test cases across 3 chains (Social Behavior, Emergent Reality, Reality Integrity). Frozen fixture.
  * **7B.1 Character Core & Reality Ledger**: Immutable `CharacterCore`, `CharacterBible` priors, user profile editor API, and 3-tier Reality Ledger projection (`USER_EDITABLE`, `AEVUM_EMERGENT`, `SYSTEM_INTEGRITY`).
  * **7B.2 Desire, Contract & Behavior Planning**: `CharacterDesireState` (psychological needs vs tasks), `RelationshipContract` (baseline intimacy + contextual adjustment), `SocialIntention` (universal `BehaviorPrimitive` + `SocialPosture`), and `BehaviorPlanner` with negative constraints and explainable `BehaviorDecisionTrace`.
  * **7B.3 Reality & Belief Engine**: `EvidenceRecord`, `BeliefClaim`, `CandidateFact` with `InferenceScope` anti-snowballing boundary, `WorldKnowledgeRegistry`, multi-validator pass, `ContradictionResolver` (GC-019 ~ GC-024), policy-gated `RealityPromotionService`, and append-only `RealityHistoryService` with point-in-time temporal queries (`get_revision_at_time`).
* **Invariants**: 1072 tests passed, 0 failures, 4 warnings, frontend clean build, 7-item architecture audit passed, 10 core invariants frozen.

#### Phase 7C — Autonomous Life & World Simulation

##### Phase 7C.1 — Deterministic Life Engine & State Machine *(Completed & Frozen)*
* **Objective**: Establish deterministic temporal simulation, unidirectional idempotent state machines for activities/plans, and atomic reconciliation without synthetic phantom event fabrication.
* **Deliverables**:
  * `SimulationClock` protocol with `RealTimeClock` and `DeterministicSimulationClock` (`advance`, `set_time`).
  * `LifeStateMachine` strictly enforcing persisted schema status transitions (`ONGOING` -> `COMPLETED`/`CANCELLED` and `PLANNED` -> `IN_PROGRESS` -> `COMPLETED`/`CANCELLED`) with `InvalidStateTransitionError`.
  * Idempotent event creation and lookup via unique `idempotency_key`.
  * Atomic multi-pass reconciliation in `LifeSimulator` with authoritative settlement (`completed_at = planned_end_at`).
  * Golden Suite F benchmarks: `GC-031` (Activity Idempotency & Duplicate Prevention) and `GC-032` (Offline Gap Elapsed Time - No Synthetic Events).
* **Invariants**: 1085 tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 11-12 enforced.

##### Phase 7C.2 — Needs, Circadian & State Evolution *(Completed & Frozen)*
* **Objective**: Connect Character Bible priors to circadian modifiers and physiological/need state dynamics with explainable audit history and dynamic baseline bounded recovery.
* **Deliverables**:
  * `CircadianEngine`: Generates `circadian_modifier` from generic rhythm priors without direct state mutation (Invariant 20).
  * `CharacterPhysiologicalState`: Decoupled vitality, wear, sleep drive, and tension (`energy`, `fatigue`, `stress`, `sleep_pressure`).
  * `ActivityPhysiologicalProfile`: 7 canonical archetypes (`RESTORATIVE`, `LIGHT/MODERATE/INTENSE_COGNITIVE`, `PHYSICAL_LIGHT/MODERATE`, `SLEEP`).
  * `StateDynamicsEngine`: Sole authoritative writer of physiological state (Invariants 13 & 16), enforcing single-interval attribution without double-counting (Invariant 17).
  * `PhysiologicalBand`: One-way derived qualitative presentation layer (`REFRESHED`, `STEADY`, `DROWSY`, `FATIGUED`, `OVERLOADED`) (Invariant 18).
  * `DesireEvaluationEngine`: Direct bridge translating physical wear and sleep drive into `PrimaryDesire`, `attention_availability`, and `solitude_need`.
  * `StateTransitionRecord`: Deterministic audit log with `rule_id`, diffs, and zero ungrounded LLM text.
  * Conversation Isolation: Chat never mutates numbers directly (Invariant 19).
  * Golden Suite F benchmarks: `GC-033-A` (No Double Counting), `GC-033-B` (Conversation Isolation & Prompt Immunity), `GC-033-C` (Dynamic Baseline Stability & Responsiveness), `GC-033-D` (Decoupled Sleep Pressure vs Fatigue).
* **Invariants**: 1098 tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 16–20 enforced.

##### Phase 7C.3 — Autonomous Activity Selection & Goal Engine *(Completed & Frozen)*
* **Objective**: Enable dynamic activity selection driven by multi-factor utility context and continuous goal progression.
* **Deliverables**:
  * `ActivityTemplate` catalog: 11 canonical grounded archetypes across `UNIVERSAL`, `PREFERENCE_GROUNDED`, `CONTEXT_REQUIRED`, `GOAL_REQUIRED`. Bounded to generic location archetypes (`HOME`, `PARK`, `LIBRARY`, `CAFE`) with zero named geography fabrication (Invariant 21).
  * `HardEligibilityGate`: Prunes ungrounded and physiologically impossible candidates; enforces unified sleep threshold (`sleep_pressure >= 0.50`, Patch A) and circadian solar start windows before utility scoring (Invariant 23).
  * `ActivityUtilityEvaluator`: Deterministic utility scoring (NeedFit, CircadianFit, GoalFit, PreferenceFit, CostPenalty, RepetitionPenalty) and canonical goal tie-breaking `(-effective_goal_fit, -importance, progress, id)` (GC-034-G).
  * `AutonomousActivitySelector`: Evaluates viable candidates ($U > 0$) strictly at authoritative decision points (`can_select`: `IDLE`/`None`, zero ongoing activities, Invariant 24) with graceful idle fallback when none eligible ($U \le 0 \rightarrow None$, Patch D).
  * Concurrency Safety & Instantiation Atomicity: Enforced via SQLite partial unique index `ix_life_activities_character_ongoing ON life_activities(character_id) WHERE status = 'ONGOING'` (Standard 27); atomic `INSERT` + `UPDATE LifeState` with rollback on `IntegrityError` (Standard 28).
  * Goal Engine & Single-Settlement Idempotency: Explicit `goal_id` linkage (zero guessing, zero goal fabrication, Invariant 22). Advances goal by its canonical `progress_per_completion` strictly once upon first `ONGOING -> COMPLETED` transition (Standard 26) within a single atomic DB transaction (Standard 25).
  * Conversation & Prompt Integration: `CharacterLifeContext` integrates factual activity and recent experiences into `<life_context>`; prompt injections cannot corrupt reality (GC-035).
  * Golden Suite F benchmarks passed: `GC-034-A` through `GC-034-H`, `GC-035`, `GC-036-A` through `GC-036-D`.
* **Invariants**: 1123 tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 21–24 & Standards 25–28 enforced and frozen.

##### Phase 7C.4 — Social World & Emergent Life *(Completed & Frozen)*
* **Objective**: Expand character life to campus/social graph using role templates and formal reality promotion without retroactive fabrication (Invariant 15).
* **Deliverables**:
  * `SocialCandidateRecord` (`social_candidates`): Dedicated provisional evidence accumulation layer isolating unpromoted entities from canonical reality (Invariant 15.3).
  * `SocialEncounterRecord` (`social_encounters`): Immutable, auditable historical ledger of what actually took place during encounters (Invariant 15.8).
  * `NPCFactRecord` (`npc_facts`): Append-only grounded NPC facts with supersession pointers (`ACTIVE`, `SUPERSEDED`, `supersedes_id`, `superseded_by`), preventing destructive updates and narrative snowballing (Lock-in Item 1 & Invariant 15.7).
  * `SocialDynamics`: Immutable 4-axis orthogonal relationship metrics (`familiarity`, `comfort`, `respect`, `trust`) strictly bounded in $[0.0, 1.0]$ with independent deltas (Invariant 15.5 & Rule 16).
  * `SocialRoleTemplate` & `SocialOpportunityProfile`: Contextual affordance architecture evaluating encounter eligibility from location, activity, and wear (`HOME` $\rightarrow$ `NONE`, `LIBRARY` + study $\rightarrow$ `HIGH`, `fatigue >= 0.85` $\rightarrow$ `NONE`) (Invariant 15.1, 15.4, Lock-in Item 4).
  * Emergent Identity Generation: Anonymous encounter slots progressing via `ANONYMOUS` $\rightarrow$ `RECOGNIZED` $\rightarrow$ `IDENTIFIED` (Lock-in Item 2).
  * Stratified Soft Social Capacity: Dunbar-style capacity (Close: 2–4, Regular: 5–10, Weak: flexible) derived from character priors (Standard 30).
  * `SocialPromotionPolicy`: Multi-factor evaluation (`encounter_count`, `temporal_consistency`, `identity_consistency`, `interaction_depth`, `mutual_recognition`) with role-differentiated promotion targets (e.g. `RECURRING_FAMILIAR_PRESENCE`, `STUDY_PEER`, `KNOWN_ACADEMIC_CONTACT`).
  * Epistemic Resolver Grounding: User claims about unverified contacts resolve as `UNVERIFIED`, generating natural human confusion/inquiry rather than crude binary rejection (Invariant 15.6).
  * Golden Suite F benchmarks passed: `GC-037` (Encounter Grounding & Social Opportunity), `GC-038` (Identity Stability & Multidimensional Dynamics), `GC-039` (Multi-Factor Reality Promotion & History Integrity), `GC-040` (Prompt Immunity & Epistemic Security), `GC-041` (NPC Reality Integrity), `GC-042` (Social Causality & Orthogonal Dynamics), `GC-043` (Concurrency Safety & Idempotent Reconciliation).
* **Invariants**: 1130 tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 15.1–15.8 & Standards 29–32 enforced and frozen.

---

### Phase 8 — Desktop Integration *(Completed & Officially Frozen)*

##### Phase 8.1 — Core Settings, Intent Domain & Gate Engine *(Completed & Frozen)*
* **Objective**: Establish user privacy boundaries, explicit IANA timezone semantics, deterministic 6-gate reach-out filter, and decouple ProactiveIntent from LifeEvent facts.
* **Deliverables**:
  * `DesktopUserSettingsRecord` (`desktop_user_settings`): Persistent configuration with explicit `timezone` (IANA-validated, Lock-in 8), `proactive_enabled` (default `False`, Invariant 25), `quiet_hours` (default `23:00` -> `08:00`), `max_daily_reach_outs` (3), `min_cooldown_minutes` (120), `idle_awareness_enabled` (False, Rule 18).
  * `ProactiveNotificationRecord` (`proactive_notifications`): Immutable schema container with `conversation_message_id`, `claimed_by`, `claimed_at`, and audit `suppression_reason`.
  * `ProactiveIntentEngine`: Translates internal desire, social/solitude need, relationship comfort/trust, and attention availability into `ProactiveIntent`. Enforces Lock-in 1: A `LifeEvent` alone never triggers an unsolicited reach-out.
  * `ProactiveGateEngine`: Pure deterministic 6-gate filter (Master Switch, DND terminal suppression, Timezone-Aware Quiet Hours with midnight wrap, Daily Cap counting only DELIVERED, Cooldown, Physiological/Sleep).
  * Golden Suite G benchmarks passed: `GC-044` (Zero Unconsented Reach-Out), `GC-045` (Quiet Hours Inviolability & Timezone Wrap), `GC-046` (Daily Cap & Cooldown Hard Gating), `GC-051` (Proactive Intent Grounding & Decoupling).
* **Invariants**: 1134 tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 25, 26 & Lock-ins 1, 8, 9, 10 enforced and frozen.

##### Phase 8.2 — Notification Persistence, Message Identity & Atomic Claim *(Completed & Officially Frozen)*
* **Objective**: Implement `ProactiveNotificationService`, notification lifecycle (`PENDING` -> `DELIVERING` -> `DELIVERED`), atomic database delivery claim (`Standard 35`), deterministic crash recovery lease, message identity stability, and mandatory canonical message binding.
* **Deliverables**:
  * `ProactiveMessageGenerator`: Generates dialogue strictly bounded by `ProactiveContext` and validated via `OutputBoundaryGuard` (Lock-in 6 & 13).
  * `ProactiveNotificationService`: Manages short atomic DB transactions creating `Message` and `ProactiveNotificationRecord(conversation_message_id=msg.id)` atomically (Lock-in 2 & 7).
  * Standard 35 Atomic Claim & Crash Recovery Lease: Multi-worker SQLite conditional update (`rowcount == 1`) reclaiming stale leases (`claimed_at < lease_cutoff`) with zero `asyncio.Lock`.
  * Message Identity & Zero-Regeneration: Failure and retry re-deliver the exact same `conversation_message_id` without re-calling LLM (Lock-in 4 & 9).
  * Schema Hardening: Enforced `conversation_message_id = mapped_column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)` at DB schema level.
  * Golden Suite G benchmarks passed: `GC-048` (Idempotent Reconciliation), `GC-050` (Dual Audit Trail), `GC-052` (True DB Race across independent sessions), `GC-053` (Message Identity Stability), `GC-054` (Mandatory Message Binding), `GC-055` (Concurrent Creation Idempotency), `GC-056` (Stale Lease Recovery), `GC-057` (No Regeneration After Failure).
* **Invariants**: 1142 tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 27, 28, Standard 35 enforced and frozen.

##### Phase 8.3 — Contextual Awareness & Zero-Persistence Telemetry *(Completed & Officially Frozen)*
* **Objective**: Connect desktop availability heartbeat with explicit consent gate, zero-storage policy when disabled (`Lock-in 4`), strictly subordinated context-only availability semantics (`Lock-in 5`, `Invariant 27`), and ephemeral in-memory lifecycle management (`Additional Lock-ins A & B`).
* **Deliverables**:
  * `DesktopAvailabilityContext`: Strictly in-memory transient value object with explicit 120s TTL and automatic expiration eviction (`is_expired()`). Zero ORM model, zero SQLite persistence, zero recovery across restarts.
  * `DesktopService`: Manages configuration, consent verification, heartbeat processing, in-memory transient context, and dual audit trail queries.
  * Consent Revocation: Calling `update_settings(idle_awareness_enabled=False)` immediately purges transient context from memory; unconsented heartbeats strip telemetry in-memory immediately.
  * Subordinated Telemetry: Desktop telemetry strictly forbidden from altering `CharacterCore` facts, emotions, mood, or relationship metrics (`trust`, `intimacy`, `respect`).
  * Time Authority: Server time (`now`) is strictly authoritative for observation, DND, and TTL evaluation; `client_timestamp` is strictly diagnostic.
  * Desktop REST API: `/desktop/settings`, `/desktop/settings/dnd`, `/desktop/heartbeat`, `/desktop/context`, `/desktop/notifications/history`.
  * Golden Suite G benchmarks passed: `GC-047` (Physiological & Sleep Gating Regression), `GC-049` (Cases A–D: Privacy Consent Revocation, In-Memory TTL, Ephemeral Restart Reset, Zero-Persistence), and `Invariant 27` (Telemetry Subordination — Zero Psychological Drift).
* **Invariants**: 1,148 backend tests passed, 0 failures, 4 warnings, frontend clean build, Invariants 25–29, Lock-ins 4 & 5, Additional Lock-ins A & B enforced and frozen.

##### Phase 8.4 — Tauri Tray, Native Shell, Settings UI & Windows Verification *(Completed & Officially Frozen)*
* **Objective**: Tauri v2 system tray, close-to-tray window management, native desktop notification dispatch, click-to-existing-message navigation, React Settings/Audit UI, and manual Windows native verification.
* **Deliverables**:
  * Step 1: Deterministic Windows Toast XML `<toast launch="aevum://notification/{id}" activationType="protocol">` via WinRT, single-instance protocol activation, zero focus heuristics.
  * Step 2: Tauri Rust Backend Supervisor with Windows Job Object (`KILL_ON_JOB_CLOSE`), console attach graceful shutdown (`CTRL_BREAK_EVENT` with lifespan engine disposal), continuous 250ms crash watchdog without auto-restart loop, and system tray menu.
  * Step 3: Authoritative 24-hour expiration suppression (`EXPIRED`), atomic lease claim (`Standard 35`), complete, release, and interact (`CLICKED`/`DISMISSED`) REST endpoints.
  * Step 4: React Desktop Settings modal, independent decoupled notification worker (12s) and heartbeat worker (30s), crash warning banner, and deterministic conversation scroll & message highlighting.
* **Invariants**: 1,157 backend tests passed, 14 Tauri Rust tests passed, clean frontend build (`tsc && vite build`), zero LLM regeneration, zero focus-heuristic false positives. Formal freeze audit verified at-least-once external side effect delivery and immutable terminal interaction states.

---

### Phase 7D — Runtime Epistemic Inference & Reality Construction *(Phase 7D.1–7D.5 Completed & Officially Frozen 🔒)*
* **Objective**: Build strictly upon Phase 7B.3's validated Reality Foundation to enable cautious, bounded hypothesis generation, candidate competition, first-class choice selection, minimal-repair reality emergence, and autonomous high-impact biography construction without reality drift.
* **Core Sub-Phases**:
  * **Phase 7D.1 — Domain Models, Candidate Persistence & Budget Controller** *(Completed & Officially Frozen)*: `CandidateHypothesis`, `CandidateHypothesisSet`, `PlausibilityBreakdown`, `InferenceEdgeType`, `EvidenceFamily`, Dual Reality taxonomy (`OBJECTIVE_WORLD_FACT` vs `SIMULATED_BIOGRAPHY_FACT`), SQLite `character_candidate_facts` and `evidence_families` tables, and `InferenceBudgetController` (hard caps: max 4 hypotheses/turn, max 2 direct/observation, max 2 slots/turn, depth <= 2; lifecycle tri-state Generated != Persisted != Promotable; provenance DAG cycle prevention; GC-071 & GC-062). 1,181 backend tests passed (23 tests in `test_candidate_budget_and_provenance.py`), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.2 — Candidate Competition & First-Class Choice Engine** *(Completed & Officially Frozen)*: `CandidateCompetitionService` (slot-level `CandidateHypothesisSet`, viability filtering against user locks, timeline, causality, and quarantine, Occam complexity penalty, decision margin $\Delta < 0.10$ ambivalence detection), `ChoiceSelectionService` (evaluating multi-attribute character decision factors: temperament, values, resources, challenge preferences, opportunity costs; proving Plausibility != Choice and Competition Ambiguity != Choice Impossibility), structured decision provenance logging in SQLite `character_choice_records` (Audit 1: `rationale_description` strictly non-authoritative), unselected alternatives archiving (`CONSIDERED_BUT_NOT_SELECTED`), `VolatilityDecayPolicy` domain-aware shelf-life decay (Audit 2: absence of evidence != contradictory evidence != canonical invalidation; `DORMANT` != `REJECTED`; canonical reality immune), and deterministic choice replay (Audit 3). 1,198 backend tests passed (17 tests in `test_candidate_choice_engine.py`), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.3 — Minimal Reality Repair & Autonomous High-Impact Promotion** *(Completed & Officially Frozen)*: `RealityRepairService` (5 levels of structural repair, zero compensatory biography, zero canonical repair mutation), `BiographyPromotionService` (14 non-negotiable hard gates for autonomous biography promotion, decoupling consistency impact from user authorization, single-slot anti-snowballing, AST-verified callsite singularity via `PromotionAuthorizationToken`, `CandidateSUPERSEDED` lifecycle transition, `CharacterBiographyPromotionRecord` persistence in `character_biography_promotions`, and concurrent promotion idempotency). 1,226 backend tests passed (23 tests in `test_biography_promotion_and_repair.py`, GC-072–GC-094), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.4 — Governed Prompt Context Assembly** *(Completed & Officially Frozen)*: `RealityContextBuilder` (pure-read projection layer, 8 epistemic XML prompt sections: `<canonical_core_reality>`, `<chosen_outcome_provisional>`, `<ephemeral_repair_context>`, `<active_competing_hypotheses>`, `<objective_world_facts>`, `<unverified_observations>`, `<evidence_references>`, `<relevant_memories>`), `GovernedRealityContext`, `GovernedRealityItem`, and `RealityItemProvenance` typed DTOs, deterministic SHA-256 prompt hashing (timestamps excluded), volatility-aware candidate filtering (dormant excluded), presentation budget isolation (MAX=6 != Reality Engine budget), `rationale_description` fully excluded from prompt context, malformed provenance fails closed, anti-self-reinforcing speech boundary, and AST-verified zero mutation call sites. 1,247 backend tests passed (21 tests in `test_golden_suite_7d_context.py`, GC-095–GC-115), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.5 — CharacterEngine Integration & End-to-End Governed Flow** *(Completed & Officially Frozen)*: `RealityOrchestrationService` (full per-turn A→J pipeline completely replacing 7B.3 `RealityBeliefEngine` in `CharacterEngine` steps 7.6+7.7), `EvidenceClassifier` (pure functional biographical signal detection across 5 locked patterns + question guard + no-signal), `WorldFactsSelector` (deterministic lexical relevance selection of objective world facts, CJK alias matching, max 4 items, PLAUSIBILITY_RULE exclusion), `CandidateRepository.get_all_active_candidates()` with strict failure contract (`CandidateRepositoryUnavailableError` sentinel; DB failure != empty state), `CharacterEngine` fail-closed pre-orchestration core snapshot fallback, zero direct RBE or `set_fact()` invocation. 1,281 backend tests passed (35 tests in `test_golden_suite_7d_orchestration.py`, GC-116–GC-140; 1 pre-existing flaky test GC-090), 7 Rust tests passed, clean frontend build, AST frozen-boundary audit passed (ADR-011 through ADR-015).
* **Key Invariants**:
  * `Dual Reality Taxonomy`: Objective world facts are verified via World Knowledge/tools; simulated biography facts are constructed via internal constraints and character choice.
  * `Choice != Plausibility != Probability`: Numeric scores are ranking metrics, not probabilities; choice is a multi-attribute character decision; highest plausibility != automatic choice.
  * `Impact != Authorization`: High consistency impact does not mandate user confirmation for simulation-originated biography; autonomous promotion is allowed under 14 hard gates.
  * `Single Mutation Authority`: Only `BiographyPromotionService` via `PromotionAuthorizationToken` may mutate `character_core_facts` via `set_fact()`.
  * `DB Failure != Empty State`: Repository failure raises `CandidateRepositoryUnavailableError`; empty rows returns `[]` normally.
  * `Candidate Budget Multi-Tier`: Generated != Persisted != Promotable; max 4 hypotheses, max 2 direct, max 2 slots, depth <= 2.
  * `Evidence Independence`: Determined by provenance lineage / evidence family, not session boundaries; repeating the same assertion counts as 1 independent evidence.
  * `Minimal Reality Repair`: Prohibits inventing unsupported bridge facts (no fake semester breaks or family trips).
  * `Leading candidate != canonical truth`: The highest-scoring candidate is solely a ranking marker; small decision margins maintain unresolved uncertainty.
  * `Absence of evidence != contradiction`: Dormancy decay follows volatility policy, never false `REJECTED`.
  * `Dual constraint`: Both hop depth ($\le 2$) and semantic dependency distance must hold; low hop count does not legitimize semantically distant leaps.
  * `Candidate-only authority`: `CharacterCandidateFactRecord` is strictly candidate data and never read as canonical truth by core services or prompt templates.
  * `Zero self-reinforcement`: Inferred candidates cannot serve as independent corroborating evidence for their own prerequisites; character speech cannot self-validate.
* **Exit Criteria**: All Golden Suite 7D benchmarks (`GC-058` through `GC-140`) passing with 100% regression fidelity across 1,281 backend tests, 7 Rust tests, and clean frontend build. Phase 7D.1–7D.5 officially FROZEN.



---

### Phase 9 — Voice
* **Objective**: Provide expressive voice synthesis and audio dialogue.
* **Deliverables**:
  * Text-to-Speech (TTS) integration with emotional prosody modulation.
  * Speech-to-Text (STT) for user voice input.
  * Audio playback pipeline within the desktop client.
* **Exit Criteria**: User and companion can converse via spoken audio matching her current emotional state.

---

### Phase 10 — Live2D
* **Objective**: Bring visual presence to life with an interactive Live2D avatar.
* **Deliverables**:
  * Live2D WebGL canvas integrated into the Tauri client.
  * Parameter mapping: sync facial expressions, gaze, and idle breathing to the Emotion Engine.
  * Lip-sync tied to TTS audio output.
* **Exit Criteria**: Visual avatar visually displays emotions, eye contact, and natural idle movements matching her internal state.

---

### Phase 11 — Realtime Call
* **Objective**: Enable low-latency full-duplex conversational voice calls.
* **Deliverables**:
  * Realtime audio streaming over WebRTC or streaming WebSockets.
  * Interruption handling (barge-in capability).
  * Low-latency speech pipeline.
* **Exit Criteria**: User can conduct natural, fluid voice calls with low latency and natural turn-taking.

---

### Phase 12 — Android
* **Objective**: Extend the companion's presence to mobile devices.
* **Deliverables**:
  * Android client application connecting to Aevum Core.
  * Mobile notifications and background sync.
  * Seamless identity and memory persistence across desktop and mobile.
* **Exit Criteria**: User can interact with the same companion on mobile while on the go, with fully synchronized memory and relationship state.
