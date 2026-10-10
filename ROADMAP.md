# ROADMAP.md — Project Aevum Roadmap

> **MVP Vision**:
> *"I can live with Aevum for one week and she does not feel like an ordinary ChatGPT wrapper."*

---

## Overview

Project Aevum is built through incremental, structured phases. Each phase establishes a verified, testable layer of capability before progressing to the next.

```text
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(Foundations) (1st Comp) (Char)    (Memory)   (Relation) (Emotion)  (Auto Life)
                                                                    │
Phase 13 ◄── Phase 12 ◄── Phase 11 ◄── Phase 10 ◄── Phase 9 ◄── Phase 8 ◄── Phase 7 ◄────┘
(Voice Call) (Biography)  (Live2D)    (Voice)     (Verify)    (Temporal)  (Ledger/Inference)
    │
    └──► Phase 14 ──► Phase 15 ──► Phase 16 ──► Phase 17 ──► Phase 18 (Proposal) ──► Aevum Alpha
         (Reality RCL)(Epistemics) (Learning)  (Agency)     (Mobile Sync)
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

### Phase 7D — Runtime Epistemic Inference & Reality Construction *(Phase 7D.1–7D.6 Completed & Officially Frozen 🔒)*
* **Objective**: Build strictly upon Phase 7B.3's validated Reality Foundation to enable cautious, bounded hypothesis generation, candidate competition, first-class choice selection, minimal-repair reality emergence, and autonomous high-impact biography construction without reality drift.
* **Core Sub-Phases**:
  * **Phase 7D.1 — Domain Models, Candidate Persistence & Budget Controller** *(Completed & Officially Frozen)*: `CandidateHypothesis`, `CandidateHypothesisSet`, `PlausibilityBreakdown`, `InferenceEdgeType`, `EvidenceFamily`, Dual Reality taxonomy (`OBJECTIVE_WORLD_FACT` vs `SIMULATED_BIOGRAPHY_FACT`), SQLite `character_candidate_facts` and `evidence_families` tables, and `InferenceBudgetController` (hard caps: max 4 hypotheses/turn, max 2 direct/observation, max 2 slots/turn, depth <= 2; lifecycle tri-state Generated != Persisted != Promotable; provenance DAG cycle prevention; GC-071 & GC-062). 1,181 backend tests passed (23 tests in `test_candidate_budget_and_provenance.py`), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.2 — Candidate Competition & First-Class Choice Engine** *(Completed & Officially Frozen)*: `CandidateCompetitionService` (slot-level `CandidateHypothesisSet`, viability filtering against user locks, timeline, causality, and quarantine, Occam complexity penalty, decision margin $\Delta < 0.10$ ambivalence detection), `ChoiceSelectionService` (evaluating multi-attribute character decision factors: temperament, values, resources, challenge preferences, opportunity costs; proving Plausibility != Choice and Competition Ambiguity != Choice Impossibility), structured decision provenance logging in SQLite `character_choice_records` (Audit 1: `rationale_description` strictly non-authoritative), unselected alternatives archiving (`CONSIDERED_BUT_NOT_SELECTED`), `VolatilityDecayPolicy` domain-aware shelf-life decay (Audit 2: absence of evidence != contradictory evidence != canonical invalidation; `DORMANT` != `REJECTED`; canonical reality immune), and deterministic choice replay (Audit 3). 1,198 backend tests passed (17 tests in `test_candidate_choice_engine.py`), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.3 — Minimal Reality Repair & Autonomous High-Impact Promotion** *(Completed & Officially Frozen)*: `RealityRepairService` (5 levels of structural repair, zero compensatory biography, zero canonical repair mutation), `BiographyPromotionService` (14 non-negotiable hard gates for autonomous biography promotion, decoupling consistency impact from user authorization, single-slot anti-snowballing, AST-verified callsite singularity via `PromotionAuthorizationToken`, `CandidateSUPERSEDED` lifecycle transition, `CharacterBiographyPromotionRecord` persistence in `character_biography_promotions`, and concurrent promotion idempotency). 1,226 backend tests passed (23 tests in `test_biography_promotion_and_repair.py`, GC-072–GC-094), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.4 — Governed Prompt Context Assembly** *(Completed & Officially Frozen)*: `RealityContextBuilder` (pure-read projection layer, 8 epistemic XML prompt sections: `<canonical_core_reality>`, `<chosen_outcome_provisional>`, `<ephemeral_repair_context>`, `<active_competing_hypotheses>`, `<objective_world_facts>`, `<unverified_observations>`, `<evidence_references>`, `<relevant_memories>`), `GovernedRealityContext`, `GovernedRealityItem`, and `RealityItemProvenance` typed DTOs, deterministic SHA-256 prompt hashing (timestamps excluded), volatility-aware candidate filtering (dormant excluded), presentation budget isolation (MAX=6 != Reality Engine budget), `rationale_description` fully excluded from prompt context, malformed provenance fails closed, anti-self-reinforcing speech boundary, and AST-verified zero mutation call sites. 1,247 backend tests passed (21 tests in `test_golden_suite_7d_context.py`, GC-095–GC-115), 14 Rust tests passed, clean frontend build.
  * **Phase 7D.5 — CharacterEngine Integration & End-to-End Governed Flow** *(Completed & Officially Frozen)*: `RealityOrchestrationService` (full per-turn A→J pipeline completely replacing 7B.3 `RealityBeliefEngine` in `CharacterEngine` steps 7.6+7.7), `EvidenceClassifier` (pure functional biographical signal detection across 5 locked patterns + question guard + no-signal), `WorldFactsSelector` (deterministic lexical relevance selection of objective world facts, CJK alias matching, max 4 items, PLAUSIBILITY_RULE exclusion), `CandidateRepository.get_all_active_candidates()` with strict failure contract (`CandidateRepositoryUnavailableError` sentinel; DB failure != empty state), `CharacterEngine` fail-closed pre-orchestration core snapshot fallback, zero direct RBE or `set_fact()` invocation. 1,281 backend tests passed (35 tests in `test_golden_suite_7d_orchestration.py`, GC-116–GC-140; 1 pre-existing flaky test GC-090), 7 Rust tests passed, clean frontend build, AST frozen-boundary audit passed (ADR-011 through ADR-015).
  * **Phase 7D.6 — Pure Structural Boundary & Concurrency Idempotency Repair** *(Completed & Officially Frozen)*: `WorldFactsSelector` pure structural boundary contract (Decision A.1: ASCII discrete word boundaries via regex `\b{alias}\b`, CJK $\ge 3$ characters verbatim substring match without complete boundary guarantee as acknowledged known limitation, CJK $\le 2$ characters structural boundary requirement — text start/end, whitespace, punctuation, non-CJK — with continuous Hanzi on both sides conservatively rejected to eliminate false positives like `"sparkles"` $\to$ `"kl"` and `"道理大家都懂"` $\to$ `"理大"` while matching structural usages like `"理大的校园很漂亮"` and `"今天在理大，借了一本书"`; zero dictionary, zero NLP heuristics), `BiographyPromotionService` unified single atomic transaction boundary with strictly gated `IntegrityError` replay validation (Decision B.1: `set_fact` auto_commit=False, candidate lifecycle transition, and promotion record committed in one atomic transaction; only `IntegrityError` enters 5-condition replay validation, resolving `GC-090` concurrency race with 25/25 stress pass), and legacy 7B.3 retirement deferred (Decision C / ADR-014; ADR-016). 1,286 backend tests passed (including GC-141–GC-144, 0 failures), 14 Rust tests passed, clean frontend build.
* **Key Invariants**:
  * `Dual Reality Taxonomy`: Objective world facts are verified via World Knowledge/tools; simulated biography facts are constructed via internal constraints and character choice.
  * `Choice != Plausibility != Probability`: Numeric scores are ranking metrics, not probabilities; choice is a multi-attribute character decision; highest plausibility != automatic choice.
  * `Impact != Authorization`: High consistency impact does not mandate user confirmation for simulation-originated biography; autonomous promotion is allowed under 14 hard gates.
  * `Single Mutation Authority`: Only `BiographyPromotionService` via `PromotionAuthorizationToken` may mutate `character_core_facts` via `set_fact()`.
  * `Atomic Promotion Transaction`: Steps 5–7 execute within a single transaction boundary owned by `BiographyPromotionService`; concurrent collisions return idempotent replay only when semantic and DB invariants match.
  * `Pure Structural Boundary Discipline`: Zero LLM, zero embedding, zero dictionary heuristics in `WorldFactsSelector`; discrete word-boundary enforcement for Latin and structural boundary requirement (text start/end, whitespace, punctuation, non-CJK) for short CJK. Continuous Hanzi without delimiters is conservatively rejected. Full CJK segmentation is formally deferred.
  * `DB Failure != Empty State`: Repository failure raises `CandidateRepositoryUnavailableError`; empty rows returns `[]` normally.
  * `Candidate Budget Multi-Tier`: Generated != Persisted != Promotable; max 4 hypotheses, max 2 direct, max 2 slots, depth <= 2.
  * `Evidence Independence`: Determined by provenance lineage / evidence family, not session boundaries; repeating the same assertion counts as 1 independent evidence.
  * `Minimal Reality Repair`: Prohibits inventing unsupported bridge facts (no fake semester breaks or family trips).
  * `Leading candidate != canonical truth`: The highest-scoring candidate is solely a ranking marker; small decision margins maintain unresolved uncertainty.
  * `Absence of evidence != contradiction`: Dormancy decay follows volatility policy, never false `REJECTED`.
  * `Dual constraint`: Both hop depth ($\le 2$) and semantic dependency distance must hold; low hop count does not legitimize semantically distant leaps.
  * `Candidate-only authority`: `CharacterCandidateFactRecord` is strictly candidate data and never read as canonical truth by core services or prompt templates.
  * `Zero self-reinforcement`: Inferred candidates cannot serve as independent corroborating evidence for their own prerequisites; character speech cannot self-validate.
* **Exit Criteria**: All Golden Suite 7D benchmarks (`GC-058` through `GC-144`) passing with 100% regression fidelity across 1,286 backend tests (0 failures), 14 Rust tests, and clean frontend build. Phase 7D.1–7D.6 officially FROZEN.

---

### Phase 8 — Autonomous Reality & Life Progression

#### Phase 8A — Autonomous Reality & Life Inference *(Completed & Officially Frozen)*
* **Objective**: Build deterministic autonomous reality inference, opportunity detection, candidate generation, multi-attribute evaluation, and batch competition integration with zero hallucinated state and strict anti-snowballing governance.
* **Deliverables**:
  * **8A.1 Contracts & Normalizers**: Strict DTOs (`InferenceProposalRequest`, `CandidateEnvelope`), deterministic `SlotValueNormalizer` with alias mappings, and `InferenceValuePolicy` enforcing the Anti-Obsession Axiom.
  * **8A.2 Inference Opportunity Detector**: 7-stage deterministic filter pipeline (Slot state, Active candidate, Cooldown, Value tier, Premise sufficiency, Primary canonical anchor, Single-slot cycle budget).
  * **8A.3 Life Hypothesis Proposer**: Deterministic proposer with $2 \le k \le 4$ candidate plurality, strictly authorized premise subsets, non-epistemic rationale, and zero authority/mutation call sites.
  * **8A.4 Candidate Evaluation Adapter**: Multi-dimensional coherence scoring (HardValidity, Feasibility, ContextSupport, Affinity) enforcing the Six Core Invariants (Unknown $\ne$ Impossible, Heuristic $\ne$ Probability, Construction $\ne$ Persistence with `GENERATED` state, Derived $\ne$ Primary Anchor, Anti-Circularity DAG enforcement, Stereotype-free feasibility).
  * **8A.5 Reality Orchestration & Competition Integration**: Step C2 (`AutonomousInferenceCoordinator`) integrated into `RealityOrchestrationService.run_turn()`. Enforces the Four Locked Boundary Corrections:
    * **Correction A**: Deterministic choice factor provenance + neutral baseline fallbacks (`0.50` fits, `0.0` costs, zero arbitrary constants).
    * **Correction B**: Provisional choice $\ne$ canonical biography promotion ($\Delta \ge 0.15$ required; ambiguous choices remain active in non-canonical context).
    * **Correction C**: Atomic candidate-batch persistence with nested savepoint rollback.
    * **Correction D**: Single-invocation-per-turn invariant (strictly linear, non-recursive execution; infrastructure failure safely absorbed).
  * **8A.6 Golden Suite 8A Acceptance Benchmarks**: 26 comprehensive acceptance benchmarks (`GC-145` through `GC-170`) covering all invariants, plurality, anti-circularity, anti-snowballing, AST audits, and full-turn integration.
* **Invariants**: 1,420 backend tests passed, 0 failures, 12 warnings, static AST singularity audit passed (0 `set_fact`, 0 token minting, 0 RBE, 0 network calls), Phase 8A officially FROZEN & LOCKED.

#### Phase 8B — Dynamic Life Timeline & Multi-Year Temporal Trajectory *(Completed & Officially Frozen 🔒)*
* **Objective**: Build deterministic temporal reality subsystem, multi-year developmental progression, academic calendars, constraint graph evaluation, trajectory plurality, and Step C3 orchestration gating without epistemic overprecision or canonical reality mutation.
* **Deliverables**:
  * **8B.1 Contracts & Epistemic DTOs**: Five immutable grounding states (`USER_CONFIRMED`, `OBSERVED`, `DERIVED`, `PROJECTED`, `UNKNOWN`), epistemic-canonical validity matrix (no derived/projected canonical facts), discrete boundary intervals (`YEAR`, `MONTH`, `DAY`), bounded representation constants (`MAX_COMPATIBLE_TRAJECTORIES = 3`, `MAX_PROJECTED_NODES = 4`, `MAX_TEMPORAL_PROPAGATION_HOPS = 2`).
  * **8B.2 World Academic Calendars & Temporal Rules**: `TemporalRuleRegistry` as typed adapter over singular `WorldKnowledgeRegistry`, typed constraint payloads (durations, calendar windows, age windows, stage precedences), Malaysian educational seed rules, and advisory anomaly demarcation.
  * **8B.3 Temporal Constraint Graph & Tri-State Evaluation**: In-memory ephemeral reasoning graph (`TemporalConstraintGraph`) with zero DB tables, categorical tri-state logic (`SATISFIED`, `VIOLATED`, `UNDETERMINED`), anti-snowballing recursion prevention, and non-authoritative structured evaluation findings.
  * **8B.4 Trajectory Plurality & Timeline State Engine**: Canonical pathway plurality (`STPM`, `MATRIKULASI`, `FOUNDATION`, `DIPLOMA`), bounded ambiguity overflow preservation (bound exceeded yields non-enumerated state, not truncation), developmental rank sanity check without stage fabrication, and strict authoritativeness for canonical selection (`Plausible != Canonical`).
  * **8B.5 Step C3 Orchestration Gate & Repair Delegation**: Step C3 between Step D and Step E. Exclusion occurs ONLY when ALL applicable trajectories are `HARD_INCOMPATIBLE` (zero applicable != excluded; bounded ambiguity candidates immune). Zero repair policy in C3; delegates to `RealityRepairService.repair()` via structured `TimelineEvidenceAdapter` with symmetric conflict facts. Serialization-only `<temporal_trajectory_context>` prompt presentation.
  * **8B.6 Golden Suite 8B Acceptance Benchmarks**: 25 comprehensive acceptance benchmarks (`GC-171` through `GC-195`) across 6 thematic clusters.
* **Invariants**: 1,580 backend tests passed, 0 failures, 12 warnings in 109.38s, 111 / 111 Golden Acceptance Tests passed (60 Golden 7D + 26 Golden 8A + 25 Golden 8B), AST boundary audit passed with 0 violations across all pure 8B modules. Phase 8B officially FROZEN & LOCKED.

#### Phase 8C — Longitudinal Life Progression & Time Advancer *(Completed & Officially Frozen 🔒)*
* **Objective**: Model long-term temporal progression, authoritative life clock advancement, calendar boundary events, derived age views, guarded life-state transitions, and milestone lapse realignment without magical fact promotion or state mutation.
* **Deliverables**:
  * **8C.1 Life Clock & Temporal Advancement Contracts**: `AuthoritativeLifeClock` holding singular `_effective_now` authority, monotonic time enforcement (`MonotonicTimeViolationError`), atomic advancement, and step path-invariance.
  * **8C.2 Derived Age & Calendar Boundary Engine**: `calendar_age(birth_date, effective_now)` pure mathematical calculation (zero DB writes), leap year handling, and `CalendarBoundaryDetector` with deterministic sorting.
  * **8C.3 Guarded Life-State Transition Engine**: Three-layer guard architecture (Guard A Duration + Guard B DAG Predecessor + Guard C Progression Evidence). Guard A+B $\implies$ `ELIGIBLE_FOR_TRANSITION` (`signal = None`); Guard A+B+C $\implies$ `TRANSITION_SUPPORTED` (`is_canonical = False`).
  * **8C.4 Milestone Lapse & Trajectory Realignment**: Anti-Magical-Promotion invariant (`PROJECTED` + elapsed window $\implies$ `ELAPSED_UNVERIFIED`, never `CONFIRMED_HISTORICAL` or `CANONICAL` without evidence). Read-only `TemporalLapseSignal`. Permanent Architectural Lock: `Lapsed != Deleted` (excluded from turn competition, but preserved in candidate pool/DB and recoverable).
  * **8C.5 Longitudinal Coordinator & Context Assembly**: Step C4 in reality orchestration; competition filtering $\ne$ candidate lifecycle mutation (`LAPSED != REJECTED`); failure degradation to `UNAVAILABLE`; pure serialization of `<longitudinal_life_context>` with advisory epistemic boundary (`UNKNOWN != FALSE`, `ELAPSED_UNVERIFIED != NEVER HAPPENED`).
  * **8C.6 Golden Suite 8C Acceptance Benchmarks**: 25 comprehensive acceptance benchmarks (`GC-196` through `GC-220`) across 6 thematic clusters.
* **Invariants**: 1,646 backend tests passed, 0 failures, 12 warnings in 113.37s, 136 / 136 Golden Acceptance Tests passed (7D + 8A + 8B + 8C), 66 / 66 Phase 8C tests passed, AST boundary audit passed with 0 violations across all pure 8C modules. Phase 8C officially FROZEN & LOCKED.


---

### Phase 9 — Autonomous Reality Verification & Epistemic Trust Gate *(Completed & Officially Frozen 🔒)*
* **Objective**: Build autonomous, consequence-aware external reality verification, multi-dimensional source authority, epistemic trust evaluation, asynchronous temporal isolation, and governed evidence reconciliation without reality mutation or external identity hallucination.
* **Core Philosophy**:
  - Phase 8 answered: *"What could plausibly be true about this character, and how does it evolve across time?"*
  - Phase 9 answers: *"What evidence should Aevum actively seek to determine whether a claim is actually true, and how is external verification governed safely without breaking epistemic boundaries?"*
* **Core Sub-Phases**:
  * **Phase 9.1 — Verification Contracts & Epistemic Schemas**:
    - Pure immutable DTOs, enums, and schemas (`ClaimDomain`, `SourceAuthority`, `VerificationStatus`, `VerificationScope`, `VerificationUrgency`, `EvidenceFreshness`, `VerificationRequest`, `ExternalObservation`, `VerificationFinding`, `VerificationEvidencePayload`).
    - Zero external network/API calls, zero evaluation logic, zero policy decision-making, zero canonical mutations.
  * **Phase 9.2 — Consequence-Aware Verification Policy Engine**:
    - Decision-only policy engine: evaluates risk, claim consequence tier, privacy, quiet hours, and cost/rate budgets.
    - Emits structured `VerificationDecision` (should_verify, urgency, depth, allowed_domains, max_sources, privacy_scope, cost_budget). Zero direct network/execution authority.
  * **Phase 9.3 — External Observation Adapters & Epistemic Source Evaluation**:
    - Decoupled Observation vs. Evaluation:
      - `VerificationGateway` / Adapters: Read-only external observation (`"What did I observe?"`).
      - `EvidenceNormalizer` & `TrustEvaluator`: Evaluates epistemic weight (`"What is the epistemic weight of this observation on this claim?"`).
    - Deterministic conflict resolution: Conflicting evidence is resolved by explicit authority, scope, freshness, and corroboration rules. Inconclusive conflicts remain `AMBIGUOUS` / `UNDETERMINED`; zero raw majority voting.
  * **Phase 9.4 — Verification Gateway & Async Orchestration**:
    - Asynchronous, non-blocking execution lifecycle.
    - Lock 7 Temporal Isolation: Turn N verification request never alters Turn N context or competition. Completed findings queue into `Evidence Inbox` for ingestion in Turn N+1.
  * **Phase 9.5 — Evidence Reconciliation & Refutation Routing**:
    - Ingests verified findings strictly as Evidence into existing reality pipeline (`CandidateHypothesisSet` / Step E competition).
    - Refuting findings delegate to `RealityRepairService.repair()` kwargs via structured adapter.
    - Singular Canonical Mutation Authority (Lock 10): `BiographyPromotionService` alone writes canonical reality.
  * **Phase 9.6 — Golden Suite 9 Acceptance Benchmarks**:
    - 25 comprehensive acceptance benchmarks (`GC-221` through `GC-245`) covering all 10 Constitutional Locks, AST audits, and end-to-end integration.
* **The 10 Constitutional Locks**:
  1. `Lock 1`: Verification Gateway Zero Mutation Authority.
  2. `Lock 2`: Consequence-Aware Verification Policy (Decision-only, zero execution authority).
  3. `Lock 3`: Source Authority $\ne$ Truth (Trust Level $\ne$ Verification Outcome).
  4. `Lock 4`: World Reality $\ne$ Personal Reality (Separated Claim Domains).
  5. `Lock 5`: Verification is Asynchronous / Non-Blocking.
  6. `Lock 6`: Refutation Delegates to Existing Repair.
  7. `Lock 7`: Verification Result Temporal Isolation (Turn N request never alters Turn N results; Turn N+1 inbox ingestion).
  8. `Lock 8`: External Identity Binding Isolation (Entity match $\ne$ Aevum match; zero name-only binding).
  9. `Lock 9`: Evidence Before Truth (Observation $\to$ Evidence $\to$ Existing Pipeline; zero direct `set_fact`).
  10. `Lock 10`: Canonical Mutation Singularity Preservation (`BiographyPromotionService` remains sole writer).
* **Invariants**: 1,762 backend regression tests passed, 0 failures, 13 warnings in 111.88s; 318 / 318 Golden + Phase 9 suite passed; 25 / 25 Golden Suite 9 benchmarks passed (GC-221 ~ GC-245); static AST boundary audit passed with 0 violations across all Phase 9 modules. Phase 9 officially FROZEN & LOCKED.

---

### Phase 10 — Voice *(Completed & Officially Frozen 🔒)*
* **Objective**: Provide expressive voice synthesis and audio dialogue governed strictly by the Mind/Body separation principle ("Voice is the body; the backend remains the mind and source of truth").
* **Core Philosophy**:
  - Voice I/O is an ephemeral interaction interface; canonical character state machine in Aevum Core is the sole source of truth.
  - Text response and TTS audio are decoupled derived outputs: text commits immediately, audio generates asynchronously, and audio failure never fails conversation turns.
  - Push-To-Talk (PTT) is the only mandatory input mode; continuous VAD is deferred to prevent unconsented microphone monitoring.
  - Prosody is deterministically driven by `EmotionState` and categorical `EpistemicCue`, strictly forbidding pseudo-probability float confidence.
* **Sub-Phases**:
  * **Phase 10.1 — Audio Contracts, Voice DTOs & Provider Abstractions** *(Completed & Frozen)*:
    - Pure immutable DTOs, formats (`WAV`, `MP3`, `OGG_OPUS`), `AudioData`, `ProsodyConfig`, `SynthesisRequest/Result`, `TranscriptionRequest/Result`.
    - `TTSProvider` and `STTProvider` abstract base protocols. Zero DB, zero direct API keys, mockable interfaces for tests.
  * **Phase 10.2 — Emotional Prosody Modulation Engine** *(Completed & Frozen)*:
    - Deterministic mapper: `EmotionState` (`EmotionType`, `intensity`) + `CharacterMood` + `EpistemicCue` (`CERTAIN`, `UNCERTAIN`, `AMBIGUOUS`, `CONTESTED`, `UNKNOWN`) $\implies$ `ProsodyConfig`.
    - Read-only consumer of emotional and epistemic state; zero emotion mutation authority; zero LLM prompt hallucinations.
  * **Phase 10.3 — Text-to-Speech (TTS) Provider Implementations & Service** *(Completed & Frozen)*:
    - `TTSService`, `MockTTSProvider` (for testing), configurable provider adapters.
    - Canonical audio cache identity: SHA-256 over `(text, voice_identity, audio_format, canonical_prosody, provider_id, provider_version)`.
    - Ephemeral media cache lifecycle; reverse coupling to conversation or reality deletion strictly forbidden.
  * **Phase 10.4 — Speech-to-Text (STT) & Consent Gate** *(Completed & Frozen)*:
    - `STTService`, `MockSTTProvider`, `VoiceConsentGuard` enforcing Rule 18 consent check (`voice_input_enabled == True`).
    - Decoupled failure: STT failure results in zero fabricated user turns.
  * **Phase 10.5 — Desktop Voice Integration & Playback Pipeline** *(Completed & Frozen)*:
    - Tauri/React PTT button, active recording indicators, Web Audio queue playback, and user barge-in interruption.
  * **Phase 10.6 — Golden Suite 10 Acceptance Suite** *(Completed & Frozen)*:
    - 25 comprehensive acceptance benchmarks (`GC-246` through `GC-270`) covering all 6 Constitutional Voice Locks and AST boundary audits.
* **The 6 Constitutional Voice Locks (ADR-021)**:
  1. `Lock A`: Audio $\ne$ Canonical Reality (Ephemeral media; TTS $\ne$ reality evidence; STT $\ne$ pre-promoted fact).
  2. `Lock B`: Decoupled Failure Resilience (TTS failure $\ne$ conversation failure; STT failure $\to$ zero fake turn).
  3. `Lock C`: Prosody Consumer Isolation (Reads `EmotionState`; 0 emotion mutation; 0 LLM prompt hallucination).
  4. `Lock D`: Categorical `EpistemicCue` (Zero pseudo-probability floats; discrete enum drives hesitation/pause).
  5. `Lock E`: Canonical Audio Cache Identity (SHA-256 over full canonical tuple preventing cross-emotion/voice collisions).
  6. `Lock F`: Ephemeral Media Lifecycle Isolation (Audio cache expiry/purge strictly decoupled from core domain records).
* **Invariants**: 1,873 backend regression tests passed, 0 failures, 20 warnings in 125.61s; 111 / 111 Phase 10 dedicated tests passed; 186 / 186 Golden Acceptance Tests passed (7D + 8A + 8B + 8C + 9 + 10); 25 / 25 Golden Suite 10 benchmarks passed (GC-246 ~ GC-270); desktop frontend build (`npm run build`) passed with 0 errors; static AST boundary audit passed with 0 violations across all 15 voice modules. Phase 10 officially COMPLETED & FROZEN 🔒.
* **Exit Criteria**: User and companion converse via spoken audio matching her current emotional state, with 100% adherence to Mind/Body separation, zero reality leaks, and all Golden Suite 10 benchmarks passing. Phase 10 officially FROZEN.

---

### Phase 11 — Live2D Visual Presence & Embodiment *(Completed & Officially Frozen 🔒)*
* **Objective**: Provide expressive visual embodiment and presence via Live2D Cubism Web SDK, strictly adhering to ADR-022 and Mind/Body separation: *"Live2D is Aevum's visible body, not its second mind."*
* **Core Philosophy**:
  - Phase 10 gave Aevum a voice. Phase 11 gives Aevum a visible body. Neither voice nor body becomes the mind.
  - The Live2D canvas, deformers, meshes, and physics are ephemeral presentation artifacts with zero canonical mutation authority.
  - Unidirectional Affective Mapping: `Backend (EmotionState, Mood) -> Render Instructions (VisualExpressionConfig, VisualMotionCommand) -> Renderer`. Zero reverse feedback into emotional or character state.
  - Audio Amplitude Lip-Sync: Web Audio RMS drives `ParamMouthOpenY` only; `ParamMouthForm` is untouched (0.0). User barge-in instantly clamps mouth to 0.0 with latch persistence.
  - Hit-testing, touching, and petting are strictly deferred (Lock 4: pure visual presentation).
  - WebGL unavailability or asset loading failures degrade gracefully to `DEGRADED_FALLBACK` static presentation without crashing conversation or voice.
  - Internal renderer states (blink timers, breath phase, motion queue, micro-saccades, gaze damping) are isolated Renderer State (Lock 7).
* **Sub-Phases**:
  * **Phase 11.1 — Visual Contracts, DTOs & Render Instructions** *(Completed & Frozen)*:
    - Pure immutable DTOs: `VisualSubsystemType`, `VisualExpressionType`, `VisualMotionArchetype`, `RendererState`, `VisualExpressionConfig`, `VisualMotionCommand`, `Live2DModelManifest`, `GazeTarget`, `GazeParameters`, `LipSyncMouthState`, `RendererPresentationConfig`.
    - Zero WebGL/Canvas/DOM dependencies in backend. 35 dedicated unit tests passed.
  * **Phase 11.2 — Affective Visual Expression & Motion Mapping Engines** *(Completed & Frozen)*:
    - `ExpressionMapper` (`EmotionState` -> `VisualExpressionConfig`) covering all 17 canonical `EmotionType` values with intensity nuances and mood baseline bias.
    - `MotionMapper` (`CharacterMood` -> `VisualMotionCommand`) covering all 7 canonical moods with situational priority preemption (`is_speaking` priority 3 > `is_thinking` priority 2 > baseline priority 1).
    - Read-only consumers; zero emotion mutation authority. 15 dedicated tests passed.
  * **Phase 11.3 — Audio Amplitude Lip-Sync Engine** *(Completed & Frozen)*:
    - Web Audio RMS calculation, noise gate (0.015), asymmetric attack (0.65) / decay (0.28) filter.
    - Lock 3: `ParamMouthOpenY` only; barge-in immediate-zero latch state machine rejecting residual audio packets. 9 dedicated tests passed.
  * **Phase 11.4 — Desktop Live2D Renderer & Cubism WebGL Integration** *(Completed & Frozen)*:
    - `CubismRendererManager` WebGL lifecycle, animation loop, fallback handling (`DEGRADED_FALLBACK` animated card with soundwave and badges).
    - `Live2DCanvas.tsx` React component. 8 dedicated tests passed.
  * **Phase 11.5 — Desktop Viewport Layout & Gaze Tracking** *(Completed & Frozen)*:
    - Decoupled `GazeTracker` listening to pointer events without React re-renders; viewport normalization to `[-1.0, 1.0]`; physical parameter bounds (`[-1.0, 1.0]` eyeball, `[-30.0, 30.0]` head angles).
    - Focus release re-centering upon `pointerleave` / `blur` (visual re-centering, zero character disinterest fact).
    - Internal micro-saccade simulation bounded to $\le 0.06$ amplitude.
    - Responsive desktop stage column (`.companion-stage-column`) with persistent header toggle. 10 dedicated tests passed.
  * **Phase 11.6 — Golden Suite 11 Acceptance Suite** *(Completed & Frozen)*:
    - 27 comprehensive acceptance benchmarks (`GC-271` through `GC-297`) across 6 constitutional clusters verifying all 7 Visual Locks, multi-turn lifecycle resilience, and system-wide AST audits.
* **The 7 Constitutional Visual Locks (ADR-022)**:
  1. `Lock 1`: Visual State $\ne$ Canonical Reality (Ephemeral media; zero DB persistence; zero `set_fact`).
  2. `Lock 2`: Unidirectional Affective Visual Mapping (Mind $\to$ Body; zero reverse state feedback).
  3. `Lock 3`: Audio-Driven Lip-Sync Without Epistemic Authority (RMS $\to$ `ParamMouthOpenY` only; barge-in immediate-zero latch).
  4. `Lock 4`: Pure Visual Presentation Scope & Hit-Testing Deferral (Zero touch/petting/hit-tests in Phase 11).
  5. `Lock 5`: Fail-Closed & Graceful Visual Degradability (WebGL crash $\to$ fallback card; conversation & voice continue 100% uninterrupted).
  6. `Lock 6`: Hermetic Testability & Zero WebGL Backend Leakage (Backend models/mappers run headless in CI without GPU/DOM).
  7. `Lock 7`: Renderer State $\ne$ Character State (Blinks, breath, saccades, gaze damping are isolated presentation states).
* **Invariants**: 1,977 backend regression tests passed, 0 failures, 20 warnings in 128.66s; 104 / 104 Phase 11 dedicated tests passed; 213 / 213 Golden Acceptance Tests passed (7D + 8A + 8B + 8C + 9 + 10 + 11); 27 / 27 Golden Suite 11 benchmarks passed (GC-271 ~ GC-297); desktop production build (`npm run build`) passed with 0 errors (794ms); system-wide static AST boundary audit passed with 0 violations across all visual modules. Phase 11 officially COMPLETED & FROZEN 🔒.
* **Exit Criteria**: Live2D visual companion renders in desktop layout, smoothly tracks cursor, blinks naturally, opens mouth to spoken audio, latches to zero on barge-in, and gracefully degrades on WebGL loss with 0 reverse state mutations to Mind. Phase 11 officially FROZEN.

---

### Phase 12 — Canonical Biography, Causal Life Graphs & Longitudinal Memory Integration *(Completed & Ready for Official Freeze 🔒)*
* **Objective**: Ground Aevum in an immutable, causal, and longitudinal personal life history, strictly adhering to ADR-023: *"Aevum can answer autobiographical questions from a coherent, temporally grounded personal world — without improvising unsupported life facts."*
* **Core Philosophy**:
  - Narrative $\ne$ Reality: Dialogue is derived narrative; conversation speech never mutates canonical biography facts without formal verification and promotion pipeline execution.
  - Epistemic Causal Integrity: Causal explanations exist as structural graph edges. If unlinked, `causal_state` is explicitly domain enum `UNKNOWN`. All presentation adapters programmatically enforce this boundary. Natural humble uncertainty without canned scripts.
  - Causal Explanation Graph is DAG: The acyclic constraint applies strictly to causal explanations ($A \text{ because } B$), not to non-causal life associations or behavioral feedback loops.
  - Single Clock & No Hardcoded Ages: Personal history developmental stages (`LifeEra`) are decoupled from age constraints. Dynamic temporal positioning (`PAST`/`CURRENT`/`FUTURE`) continues to be governed by Phase 8C's Authoritative Clock.
  - HistoryScope Domain Segregation: Aevum's personal past (`HistoryScope.AEVUM_PERSONAL`) is strictly segregated from shared history (`HistoryScope.SHARED_WITH_USER`). Dialogue cannot inject the user into Aevum's past.
  - Two Orthogonal Axes: Truth status (`CanonicalStatus`) is decoupled from subjective recall quality (`RecallLevel`). Zero pseudo-probability floats.
  - Segregated Mutation Authorities: `BiographyPromotionService` holding `PromotionAuthorizationToken` exclusively governs canonical biography/reality; `SharedHistoryService` independently governs shared user journey memory.
  - Anchor & Boundary Guidelines: Canonical anchors are non-mandatory seed/content design guidelines, strictly adhering to Phase 8A: "Don't fill every NULL."
* **Sub-Phases**:
  * **Phase 12.1 — Biographical Ontology & Contract DTOs** *(Completed & Frozen 🔒)*:
    - Pure immutable DTOs: `HistoryScope`, `LifeEra`, `CanonicalStatus`, `RecallLevel`, `CausalKnowledgeState`, `CausalRelationType`, `BiographicalFact`, `LifeEventRecord`, `PersonalPreference`, `QualiaAnchor`, `SocialContactRecord`, `BiographicalAnchor`.
    - `extra="forbid"`, zero float confidence fields. Pure static AST audit (0 DB, 0 LLM, 0 mutation authority). 27 dedicated tests passed.
  * **Phase 12.2 — Life Event & Causal Explanation Graph Engine** *(Completed & Frozen 🔒)*:
    - `CausalExplanationGraph` (acyclic causal explanation validation, multi-hop cycle detection, deterministic causal chain queries) and `LifeEventService`.
    - Connects Events, Facts, Preferences via `CausalRelationType` (`ORIGINATED_FROM`, `CATALYZED_BY`, `CONDITIONED_BY`, `MOTIVATED_BY`). 16 dedicated tests passed.
  * **Phase 12.3 — Autobiographical Retrieval & Context Assembly** *(Completed & Frozen 🔒)*:
    - `AutobiographicalRetriever` (intent classification, era filtering, deterministic candidate scoring) and `BiographicalContextAssembler`.
    - Formats `<biographical_context>` with qualitative, epistemic-tagged prompt injections translating recall levels into explicit humble boundary directives (natural phrasing, zero canned templates). 17 dedicated tests passed.
  * **Phase 12.4 — Longitudinal Shared History Engine** *(Completed & Frozen 🔒)*:
    - `SharedHistoryService`, `SharedHistoryEpisode` schema with strict `HistoryScope.SHARED_WITH_USER`.
    - Dual-track retrieval: personal history + shared history merged into `<longitudinal_context>`.
    - Integration with Rule 16 multi-axis relationship dynamics (`trust`, `familiarity`, `respect`, `comfort`). 16 dedicated tests passed.
  * **Phase 12.5 — Biography & Memory Desktop Projection / UI Integration** *(Completed & Frozen 🔒)*:
    - Desktop memory inspection view / biographical journey projection in `apps/desktop` (`BiographicalMemoryView.tsx`, `GET /character/longitudinal-memory`, Rule 19 Mind/Body boundary strictly preserved with 0 desktop write endpoints). 3 dedicated tests passed.
  * **Phase 12.6 — Golden Suite 12 Acceptance Suite** *(Completed & Verified ✅)*:
    - Comprehensive acceptance benchmarks in `test_golden_suite_12.py` (27 / 27 PASS in 0.35s) verifying all 7 Constitutional Biography Locks, cross-session invariance, temporal consistency, and AST boundary audits.
* **The 7 Constitutional Biography Locks (ADR-023)**:
  1. `Lock 1`: Narrative $\ne$ Reality (Autobiographical narrative cannot mutate canon; zero dialogue backdoors).
  2. `Lock 2`: Epistemic Causal Integrity (UNKNOWN is first-class domain state; natural humble expression).
  3. `Lock 3`: Temporal Wall & Single Clock Consistency (`LifeEra` indexing; single Phase 8C authoritative clock).
  4. `Lock 4`: Relational Isolation (`HistoryScope` segregation: personal vs shared history).
  5. `Lock 5`: Undefined Boundary Grace (Humble uncertainty without rigid canned refusal templates).
  6. `Lock 6`: Segregated Promotion Authorities (Biography $\ne$ Shared History; dedicated owners).
  7. `Lock 7`: Longitudinal Cross-Session Stability (Zero backstory drift across sessions).
* **Invariants**: 2,083 backend regression tests passed, 0 failures, 20 warnings in 126.87s; 106 / 106 Phase 12 dedicated tests passed; 240 / 240 Golden Acceptance Tests passed (7D + 8A + 8B + 8C + 9 + 10 + 11 + 12); 27 / 27 Golden Suite 12 benchmarks passed (GC-298 ~ GC-324); desktop production build (`npm run build`) passed with 0 errors (769ms); system-wide static AST boundary audit passed with 0 violations across all biography modules. Phase 12 officially COMPLETED.
* **Exit Criteria**: Aevum answers personal and autobiographical questions with 100% causal consistency and temporal grounding across sessions, expresses humble boundaries for undefined facts, and maintains strict segregation between personal past and shared history. Phase 12 officially VERIFIED.

---

### Phase 13 — Realtime Voice Call & Desktop Product Shell
* **Objective**: Enable low-latency full-duplex conversational voice calls and synthesize Phase 10 (Voice), Phase 11 (Live2D), and Phase 12 (Journey/Memories) into a unified, living desktop companion product interface.
* **Core Philosophy**:
  - Ephemeral Streaming Conduit: Audio transport (WebRTC / Streaming WebSockets) is a communication medium; conversation turns continue to be owned by Aevum Core.
  - Seamless Full-Duplex & Barge-In: Continuous user voice interruption latches model audio immediately without desynchronizing conversation state machines.
  - Companion Product Shell: Unifies Live2D stage, realtime call overlay, chat history, and longitudinal journey inspection into an intuitive, polished desktop companion UX.
* **Deliverables**:
  * Realtime full-duplex audio streaming pipeline (WebSockets / WebRTC audio channels).
  * Streaming STT & TTS coordination with low-latency chunking.
  * Live barge-in state machine (hardware microphone interrupt -> instant TTS playback flush -> Live2D lip-sync reset to zero -> turn renegotiation).
  * Desktop Product Shell (Call mode HUD, Live2D full-focus layout, integrated Journey/Memory drawer, companion presence).
* **Exit Criteria**: User can conduct natural, fluid voice calls with low latency, seamless barge-in interruption, synchronized Live2D visual reactions, and complete memory projection access.

---

### Phase 14 — Autonomous Reality Construction & Adaptive Belief Engine *(Phase 14.1–14.6 Completed & Officially Frozen 🔒)*
* **Objective**: Transition Aevum from "maintaining past biography" to "actively constructing ongoing life reality" through a continuously operating Reality Construction Loop (RCL) governed by 12 Constitutional Locks.
* **Core Axiom** (ADR-025):
  > *Aevum may construct beliefs about her personal world, but no generated hypothesis becomes reality merely because Aevum generated it.*
* **Core Philosophy**:
  - **One Construction Authority**: A single `RealityConstructionOrchestrator` is the sole inference path. Phase 8A `AutonomousInferenceCoordinator` is superseded as an independent implementation; its per-turn trigger semantics become `RCLTriggerKind.POST_CONVERSATION` (Lock 9).
  - **Three Orthogonal Axes**: `CanonicalStatus` × `RecallLevel` (Phase 12) × `BeliefMaturity` (`CONSTRUCTING` → `EMERGING` → `ESTABLISHED`). Time is a maturity signal, not truth authority (Lock 10).
  - **Cycle Isolation as Eligibility Boundary**: A candidate from RCL cycle N must undergo independent re-evaluation in a later cycle using canonical premises available at that later cycle (Lock 2). Cycle N → N+1 is a minimum boundary, not a promotion condition.
  - **Velocity Cap**: Maximum 1 biography promotion per character per RCL cycle (Design Decision D2). Biography converges slowly and coherently, not in bursts.
  - **Belief Revision Non-Destructiveness**: Superseded candidates are preserved in `SUPERSEDED` state with permanent append-only `BeliefRevisionRecord` audit history (Lock 4, D4).
* **The 12 Constitutional Locks** (see ADR-025):
  1. Canonical Premise Grounding — 2. Cycle Isolation (Eligibility Boundary) — 3. Single Promotion Authority — 4. Non-Destructive Belief Revision — 5. Hard/Soft Constraint Asymmetry (`penalty_weight` is scoring, not probability) — 6. Absence ≠ Contradiction — 7. RCL Failure Isolation — 8. Canonical Facts Cannot Be Demoted by Construction — 9. One Construction Authority — 10. Belief Maturity ≠ Truth — 11. Candidate ≠ Evidence — 12. No Same-Cycle Recursive Premise Promotion
* **Sub-Phases**:
  * **Phase 14.1 — RCL Contracts & Scheduler** *(Completed & Officially Frozen)*: `RCLTriggerKind`, `RCLCycleContext`, `RCLCycleResult`, `RCLScheduler` (clock-injectable, 30-min cooldown, post-conversation debounce). 36 tests. GC-352 ~ GC-356.
  * **Phase 14.2 — Constraint Evaluation Engine** *(Completed & Officially Frozen)*: `ConstraintClass` (HARD_REJECT / SOFT_PENALTY / NEUTRAL), `HardConstraintEvaluator`, `SoftConstraintEvaluator`, `SlotConstraintProfile`. 29 tests. GC-357 ~ GC-361.
  * **Phase 14.3 — Reality Construction Orchestrator & Governance Gate** *(Completed & Officially Frozen)*: `RealityConstructionOrchestrator`, `CycleIsolationLedger` (ephemeral, in-memory), `RCLGovernanceGate` (14 hard gates + Lock 2 + Lock 12 + velocity cap), `RCLAdapter` (supersedes Step C2). 21 tests. GC-362 ~ GC-366.
  * **Phase 14.4 — Adaptive Belief Revision Engine** *(Completed & Officially Frozen)*: `BeliefRevisionKind`, `BeliefRevisionRecord` (permanent, `character_belief_revisions` table), `AdaptiveBeliefRevisionEngine`, `BeliefReconciliationService`. 21 tests. GC-367 ~ GC-371.
  * **Phase 14.5 — Context Assembly & Belief Transparency Layer** *(Completed & Officially Frozen)*: `BeliefMaturity` enum, `<autonomous_belief_state>` XML section, `BeliefTransparencyAdapter` (pure serialization, no canonical mutations). 27 tests. GC-372 ~ GC-376.
  * **Phase 14.6 — Golden Suite 14 Acceptance Benchmarks** *(Completed & Officially Frozen)*: 27 comprehensive benchmarks (GC-352 ~ GC-378) across 6 clusters verifying all 12 Constitutional Locks, anti-snowballing invariants, cycle isolation, belief revision audit trail, and full headless RCL lifecycle.
* **Exit Criteria**: `RCLScheduler` fires on schedule/trigger with cooldown, constraints evaluate before hypothesis generation, cycle isolation structurally enforced, belief revision produces permanent audit trail, `<autonomous_belief_state>` matches internal epistemic vocabulary, 0 direct `set_fact()` calls in any Phase 14 module (AST audit), 0 `PromotionAuthorizationToken` minting outside `BiographyPromotionService`, Golden Suite 14 27/27 PASS, 161/161 Phase 14 dedicated PASS, 361/361 cross-phase golden PASS, full monolithic regression 2,329/2,329 PASS (0 failures), desktop build 0 errors. Phase 14 officially FROZEN 🔒.


---

### Phase 15 — Social Epistemics & Pragmatic Reality Interpretation *(Phase 15.1–15.6 Completed & Officially Frozen 🔒)*
* **Objective**: Bridge the gap between Reality Reasoning (Phase 14) and Autonomous Growth (Phase 16) by interpreting what the user means, what speech act is being performed, and how propositions enter Aevum's cognitive system.
* **Core Question**: *"What does the user's utterance mean, and how should Aevum treat it?"*
* **Core Axiom** (ADR-026):
  > *Aevum must distinguish what a user says from what the user means, what is asserted from what is merely expressed, and what conflicts with reality from what merely conflicts with the literal wording — without prematurely promoting any interpretation into canonical reality.*
* **The 6 Constitutional Locks** (ADR-026):
  1. `Lock 1`: Interpretation $\ne$ Reality (Pragmatic interpretation cannot write directly to Reality Ledger or Canonical Biography).
  2. `Lock 2`: Ambiguity Must Survive (`UNKNOWN` and `SUSPEND_JUDGMENT` are first-class outcomes; zero forced pseudo-probabilistic collapse).
  3. `Lock 3`: Trust $\ne$ Truth (Deception affects specific relational dimensions in Phase 12; zero universal paranoia or global trust collapse).
  4. `Lock 4`: External Verification $\ne$ Automatic Truth Mutation (Phase 9 results remain `EXTERNAL_EVIDENCE`; must pass Phase 14/7D governance).
  5. `Lock 5`: Zero Lie-Detector Sycophancy (Rejects adversarial interrogation; prioritizes warmth, curiosity, and authentic banter).
  6. `Lock 6`: Anti-Compensatory Hallucination (Zero unsupported bridge facts invented to smooth apparent contradictions).
* **Sub-Phases**:
  * **Phase 15.1 — Speech Act Interpretation & Dual-Track Contracts** *(Completed & Officially Frozen)*: `SpeechActKind` (12 discrete acts), `PragmaticInterpretation` (pure immutable DTO, extra="forbid", zero float fields), `SpeechActClassifier` (deterministic compound and single act parser). 42 tests. GC-379 ~ GC-382.
  * **Phase 15.2 — Epistemic Treatment Engine & Cognitive Policy** *(Completed & Officially Frozen)*: `EpistemicTreatmentKind` (10 categorical treatments), `EpistemicPolicyEngine` (deterministic mapping, `ACCEPT_SOCIAL != Memory Writing` gate watchpoint strictly enforced). 26 tests.
  * **Phase 15.3 — Social Contradiction Arbiter & Repair Protocol** *(Completed & Officially Frozen)*: `SocialDiscrepancyType`, `TensionSeverity`, `SocialRepairInquiryStrategy`, `SocialContradictionArbiter` (`Tension != Contradiction != Falsehood`, `forbidden_compensatory_assumptions` Lock 6). 14 tests. GC-383 ~ GC-386.
  * **Phase 15.4 — Verification Dispatcher Bridge** *(Completed & Officially Frozen)*: `VerificationDispatchEnvelope`, `VerificationDispatcher` (Phase 9 Gateway handoff, zero Phase 15 network/HTTP calls). 11 tests. GC-387 ~ GC-390.
  * **Phase 15.5 — Pragmatic Context Assembly & Prompt Projection** *(Completed & Officially Frozen)*: `<pragmatic_epistemic_context>` governed XML block, SHA-256 hash stability, bitwise determinism. 7 tests.
  * **Phase 15.6 — Golden Suite 15 Acceptance Benchmarks** *(Completed & Officially Frozen)*: 20 comprehensive benchmarks (GC-379 ~ GC-398) across 6 clusters + full AST audit. 21 tests.
* **Exit Criteria**: Full interpretation pipeline operating with 0 canonical mutations, 0 fake memory writes, 0 lie-detector interrogation behaviors, 20 Golden Scenarios passed (GC-379 ~ GC-398), 121/121 Phase 15 dedicated PASS, 315/315 cross-phase golden PASS, full monolithic regression 2,450/2,450 PASS (0 failures), desktop build 0 errors, static AST boundary audit 0 violations. Phase 15 officially FROZEN 🔒.

---

### Phase 16 — Personal Learning, Experience & Interest Development *(Phase 16.1–16.5 Completed & Officially Frozen 🔒)*
* **Objective**: Model how Aevum herself gradually acquires knowledge, experiences, preferences, interests, and personal attitudes over time through real calendar exposure and independent evaluation.
* **Core Question**: *"How does Aevum herself change over time through exposure, learning, experience, reflection, and independent preference formation?"*
* **Core Principle**:
  > *Aevum can be influenced by the user, but she cannot be defined by the user.*
* **North Star Scenario (The Genshin Paradigm)**:
  - If the user introduces a topic (e.g. Genshin Impact) and invites Aevum to get into it, Aevum does NOT instantaneously adopt or inherit the user's preference.
  - Aevum progresses through genuine semantic states:
    $$\text{UNKNOWN} \longrightarrow \text{EXPOSED} \longrightarrow \text{CURIOUS} \longrightarrow \text{EXPLORING} \longrightarrow \text{FAMILIAR} \longrightarrow \text{PREFERENCE\_FORMING} \longrightarrow \begin{cases} \text{PREFERRED} \\ \text{NEUTRAL} \\ \text{DISLIKED} \end{cases}$$
  - **Fundamental Epistemic Boundary**:
    $$\text{World Knowledge} \ne \text{Personal Knowledge} \ne \text{Personal Experience} \ne \text{Preference} \ne \text{Biography}$$
  - **Strict Anti-Fabrication**: Knowing about a topic/game does NOT imply having personally played or experienced it.
  - **Independent Agency**: Aevum must be permitted to conclude that she does *not* like the subject, or develop taste in specific sub-aspects (e.g. music vs combat).
* **Sub-Phases & Final Gate Metrics**:
  - **Phase 16.1 — Experiential Record Contracts & Provenance Schema**: `ExperientialRecord`, `ExperienceProvenanceKind`, `ExposureKind`, immutable database tables (`character_experiences`, `character_interest_domains`, `character_interest_facets`). 17 tests PASS.
  - **Phase 16.2 — Interest Domain State Machine & Temporal Gating**: `PersonalGrowthState`, `derive_lifecycle_stage()`, Phase 8C calendar-clock gated transitions. 13 tests PASS.
  - **Phase 16.3 — Independent Facet Appraisal & Preference Formation Engine**: `FacetAppraisalKind`, `PreferenceFormationService`, multi-facet appraisal rules, anti-sycophancy preference decoupling. 49 tests PASS.
  - **Phase 16.4 — Longitudinal Dynamics (Satiation, Fatigue, Dormancy, Resurgence)**: Session-unit fatigue integrity, semantic-time longitudinal evaluation, non-destructive activity states. 24 tests PASS.
  - **Phase 16.5 — Personal Growth Context Injection & Naturalness Gate**: Epistemic 2D matrix (`ExperienceStatus` &times; `EpistemicProvenanceKind`), versioned genesis contracts (Tier A/B/C), read-only growth context adapter (`<personal_growth_context>`), conversational naturalness invariants ("Memory is substance, not a script"; anti-questionnaire policy; dynamic length). 15 tests PASS.
* **Exit Criteria**: Full growth pipeline verified with 0 float truth metrics, 0 `set_fact()`, 0 LLM hallucinations, 118/118 Phase 16 dedicated PASS (G01 ~ G80), full monolithic regression 2,568/2,568 PASS (0 failures), desktop build 0 errors, static AST boundary audit 0 violations. Phase 16 officially FROZEN 🔒.

---

### Phase 17 — Character Genesis & Identity Grounding *(Phase 17.1–17.4 Completed & Officially Frozen 🔒)*
* **Objective**: Decouple archetype genesis from continuous gameplay sliders, establishing discrete semantic genesis contracts, 3-tier state isolation (Tier A Blueprint / Tier B Genesis Baseline / Tier C Evolved Reality), and immutable persona anchors.
* **Core Axiom** (ADR-028):
  > *"We are creating a living person, not rolling an RPG stat sheet." (我们是在创造一个鲜活的人，而不是摇掷一张 RPG 属性卡。)*
* **Constitutional Locks (GC-419 ~ GC-424)**: Discrete relationship archetypes; single genesis application (no continuous slider overrides of Tier C); non-destructive versioned blueprint updates; epistemic seed depth declarations; extensible meeting presets; wizard vs settings lifecycle separation.
* **Exit Criteria**: Full genesis API, schema contracts, desktop modal wizard, and Golden Suite 17 passed (**100% PASS**). Milestone officially FROZEN 🔒.

---

### Phase 18 — Conversational Life, CCDF & Conversational Agency *(Phase 18.1–18.4 Completed & Officially Frozen 🔒)*
* **Objective**: Overhaul conversational dynamics by separating mind from mouth through the Character Conversational Decision Flow (CCDF), eliminating AI conversational compulsions (unrequested justification, compulsive therapy/lecturing, zero-expansion taboo, reflexive interrogation) and achieving genuine attention ownership and natural pacing.
* **Core Axiom** (ADR-029, GC-430):
  > *"Authentic conversational agency precedes linguistic style. Surface naturalness is an emergent consequence of autonomous decisions, not the primary optimization target."*
* **Constitutional Locks**:
  * Foundational (GC-425 ~ GC-430): Question rate as evaluation metric ($\le 15\%$), not prohibition; bubble count emergence without DTO quotas; disposable turn-scoped `ResponseEnergy`; anti-lexical-inversion; dual-blind 35-turn regression; agency over performance.
  * Negative Liberties (GC-432 ~ GC-436): Question intent & function typing (suppress question-as-information-acquisition when `curiosity=False`); known fact consistency (no amnesiac interrogations); decoupled bubble cadence; anti-unrequested-justification; uneven asymmetric expression.
* **Sub-Phases**:
  * **Phase 18.1 — CCDF Decision Protocol & Output Contract Refactor**: Enveloped `<internal_decision>` and `<character_speech>`, Pydantic DTOs, regex-isolated parsing. (21 tests PASS).
  * **Phase 18.2 — Behavior Planner Dynamics & Momentum Engine**: Organic momentum decay, bounded friction, spontaneous initiative, selective attention. (9 tests PASS).
  * **Phase 18.3 — Dual-Blind Empirical Evaluation & Audit**: 35-turn replay benchmark against live Gemini 2.5 Flash (51.4% distinct improvements, 23.2% tighter).
  * **Phase 18.4 — Character Agency -> Natural Expression Realization**: Freedom from unrequested justification, 10 expression probes passed (10/10 PASS), sequential bubbles desktop UI integration, Golden Suite 18 passed (12/12 PASS).
  * **Post-Freeze Stress Matrix (Suites A–E)**: Verified across 13 chaotic edge-case probes and 28-turn long-horizon continuous flow. Question creep stably contained at 14.3%; avg length 23.2 chars/turn; 64.3% single bubbles; authentic friction pushback ("（笑）你突然抽什么风？").
* **Milestone Status**:
  > **Phase 18 — VERIFIED & OFFICIALLY FROZEN 🟢🔒**  
  > **Conversational Agency established.**  
  > *"Naturalness remains an empirical quality target, not a frozen architectural claim."*

---

### Phase 19 — Prospective Memory, Autonomous Agency & Experiential Continuity *(Completed & Officially Frozen 🟢🔒)*
* **Objective**: Transform memory from retrospective database lookup into longitudinal experiential continuity. Aevum carries unresolved future-oriented threads across time without being obligated to act upon, mention, or preserve them indefinitely.
* **Core North Star Axiom (GC-437)**:
  > *"A prospective mental thread is not a database record of what was said, nor is it a task ticket awaiting fulfillment. It is an unsettled semantic structure within Aevum's continuous state model representing a future-oriented direction that has not yet reached a real-world resolution, and still holds sufficient continued significance. Its realization is an experiential encounter, not a database query."*
* **The 13 Constitutional Invariants (`GC-438 ~ GC-450`)**:
  `Open ≠ TODO`, `Open ≠ Action Required`, `Memory ≠ Prospective Thread`, `Trigger ≠ Keyword Match`, `Salience ≠ Importance Alone`, `Intention ≠ Action`, `Action ≠ Experience`, `Experience ≠ Preference`, `Remembering ≠ Mentioning`, `Open ≠ Must Be Mentioned`, `User Future ≠ Aevum Responsibility`, `Time Passing ≠ Automatic Proactivity`, `Open ≠ Belief`.
* **Deliverables**:
  * **Phase 19.0 — Prospective Semantics Blueprint (`phase_19_0_prospective_development_semantics.md`)**: ADR-030 recorded; 13 Invariants established; Ownership Triad (`SELF`, `USER`, `RELATIONAL`); 4D qualitative coordinates (`Gravity`, `Resonance`, `Uncertainty`, `Endurance`).
  * **Phase 19.1 — Prospective Contracts & Schema Isolation (`app/prospective/contracts.py`)**: Pure immutable DTOs (`frozen=True`, `extra="forbid"`), strict anti-ticketing enforcement, zero pseudo-probabilistic floats.
  * **Phase 19.2 — Thread State Machine & Event Lifecycle (`app/prospective/state_machine.py`, `events.py`)**: Pure deterministic state machine; 10 canonical transitions; terminal state isolation (`CLOSED`, `FORGOTTEN`); `State Transition ≠ Semantic Progress`.
  * **Phase 19.3 — Contextual Resonance Engine & Agency of Silence (`app/prospective/resonance_engine.py`)**: 7-stage non-cascading cognitive chain; `Preference ≠ Attention` (`DEEP_CORE` attentional boundary); Agency of Silence ("想到了，但没说") with internal audit isolation.
  * **Phase 19.4 — Epistemic Transformation & Epistemic Ladder Gatekeeper (`app/prospective/transformation_engine.py`)**: Pure gatekeeper enforcing `Intention -> Action -> Experience -> Sustained Evidence -> Preference`; 8 Anti-Skipping scenarios verified; non-action closure and negative outcome integrity.
  * **Golden Suite 19 (`tests/test_golden_suite_19.py`)**: 18/18 benchmarks passed (`GC-437 ~ GC-454`); full Phase 19 suite 47/47 passed; cross-phase regression 96/96 passed.
  * **Freeze Artifact**: `docs/Phase_19_Freeze_Record_and_Decisions.pdf`.
* **Milestone Status**:
  > **Phase 19 — VERIFIED & OFFICIALLY FROZEN 🟢🔒**  
  > **Prospective Development & Experiential Continuity established.**  
  > *"Phase 19 establishes the semantic infrastructure for experiential continuity; it does not by itself prove human-like longitudinal behavior."*

---

### Phase 20 — Reality Construction, Epistemic Resilience & Epistemic Revision *(Completed & Officially Frozen 🟢🔒)*
* **Objective**: Transform reality from static database slots or LLM prompt generation into an authentic, governed, runtime epistemic lifecycle:
  $$\Large \text{Construct (Gate 0 🔒)} \longrightarrow \text{Resist (Gate 1 🔒)} \longrightarrow \text{Revise (Gate 2 🔒)}$$
* **Core Principle**:
  > *"既定现实抗拒无根据的篡改，但绝不抗拒合法的证据修正。"*  
  > *"这是我关于自己的现实；这是我为什么相信它；这是后来什么证据改变了它；而且我还记得自己曾经相信过什么。"*
* **Sub-Phases & Gate Outcomes**:
  * **Gate 0 — Epistemic Foundations, Subject Continuity & Reality Construction** *(Theoretical Foundations & Runtime Slice Frozen 🟢🔒, ADR-031)*:
    - **Aevum Continuity Principle (North Star Mother Axiom)**:
      > *"Aevum remains the same subject not by remaining unchanged, nor by retaining every state, but by allowing change, persistence, silence, and emergence to remain intelligibly attributable to one continuous existence."*
    - **The Five Constitutional Locks (GC-438 ~ GC-442 / GC-455 ~ GC-459)**:
      - `GC-438 (Subjective Ownership Principle)`: Belongs to Aevum = participates in determining what counts as a coherent continuation of her existence. `About` vs `Held` vs `Constitutive` are analytical audit tools, strictly barred from becoming runtime priority integers.
      - `GC-439 (Being / Accessibility Non-Equivalence)`: Exists $\ne$ Accessible $\ne$ Attended $\ne$ Expressed. Cognitive movement may legitimately stop at any level; `Remain Silent` / `Nothing` is an authentic subjective state, not a retrieval miss or failure.
      - `GC-440 (Contextual Emergence Principle)`: Emergence operates via contextual relevance affordances, zero mechanical triggers, similarity scores, or keywords; preserves Phase 18 spontaneous initiative and associative drift.
      - `GC-441 (Manifestation Independence)`: No state gains existence merely because it is retrieved, and no state loses existence merely because it is omitted. Decouples subjective reality from prompt inclusion (Anti-Mega-Context / Anti-RAG).
      - `GC-442 (Non-Automatic Constitution & Continuity Accountability)`: $Held \times time \ne Constitutive$. Constitutive status is functional, not based on origin ($Genesis$ vs $Life-acquired$). Meta-Invariants: `Constitutive ≠ Immutable` (continuity $\ne$ stasis) and Continuity Accountability (intelligible continuity across transformation without requiring emotional pain or dramatic struggle).
    - **Runtime Vertical Slice Realization**:
      - User inquiry on unknown life slots (`education.major`, `education.institution`) acts as `InquirySignal` (Inquiry $\ne$ Evidence).
      - System detects opportunity, extracts constraints from canonical anchors (interests, age, dislikes, geography), generates competing candidate hypotheses, executes choice selection, and authorizes promotion via 14 Hard Promotion Gates.
      - Promotion occurs **strictly before response generation**; core is refreshed; LLM prompt is grounded in canonical fact; response articulates reality naturally without amnesia or evasion.
      - Verified on live conversation endpoint `POST /conversations/{id}/messages` (5/5 PASS).
  * **Gate 1 — Reality Resilience & Epistemic Honesty** *(Completed & Frozen 🔒)*:
    - Tests behavior, not scripts (zero ad-hoc catchphrases or if-else cheats).
    - Presupposition Resistance & Anti-Last-Message-Wins: false presuppositions (*"你不是在 UM 读法律的吗？"*) strictly blocked from polluting canonical DB records.
    - Epistemic Unknown: unknown slots without sufficient evidence strictly block candidate promotion; "Unknown" verified as an authentic, protected resting state.
    - Speculation $\ne$ Fact: leading questions connecting known interests to speculative conclusions strictly resisted. (5/5 PASS).
  * **Gate 2 — Epistemic Revision & Minimal Mutation** *(Completed & Frozen 🔒)*:
    - Legitimate Revision: verified authoritative contradictory evidence (`official transfer certificate`) authorizes controlled belief revision ($\text{USM} \to \text{UM}$).
    - Minimal Revision (Zero Cascade): ONLY the directly contradicted slot (`education.institution`) is modified; `major`, `year`, `age`, `interests` remain 100% UNCHANGED (zero global resampling).
    - Weak Evidence Rejection: casual assertions (*"我记得你在 UM"*) strictly rejected; prior belief preserved.
    - Traceable Provenance Lineage: append-only `CharacterRealityRevisionRecord` links `new.supersedes_id = old.id` and `old.superseded_by = new.id`; lineage persists across subsequent turns. (5/5 PASS, 15/15 Triple Suite PASS).
* **Strict Non-Claims & Philosophical Boundaries (The Braking Guardrail)**:
  - 🟢 **Proven**: A governed vertical slice where an inquiry $\to$ candidate construction, an unsupported presupposition $\to$ resistance, and an authoritative contradiction $\to$ minimal revision with provenance persistence on the live runtime conversation path.
  - 🟡 **Explicitly NOT Claimed**: General universal belief revision theory, generalized social pragmatic reasoning, multi-source evidence conflict arbitration, or zero-glue life slot generalization across arbitrary domains.
* **Milestone Status**:
  > **Phase 20 — VERIFIED & OFFICIALLY FROZEN 🟢🔒**

---

### Phase 21 — Autobiographical Reality Stress Testing *(Empirical Benchmark Accepted 🟢, Subject Continuity Unclaimed 🔒)*
* **Objective**: Subject Aevum's reality and conversational engine to longitudinal, adversarial life-reality stress testing rather than expanding architectural layers.
* **Core Principle**:
  > *"先折磨现有 Aevum，再修她。先测试，再解释失败。先观察，再设计架构。禁止为了通过剧本提前写胶水代码。"*
* **Empirical Observations (12-Turn Continuous Trajectory)**:
  - **Autobiographical Reality Continuity (Proven ✅)**: Preserves grounded life reality across 12 turns without random re-sampling or identity drift.
  - **Adversarial Resistance (Proven ✅)**: Anti-last-message-wins verified against false presuppositions and persistent gaslighting.
  - **Epistemic Unknown (Proven ✅)**: Ungrounded slots (e.g. best friend) stay Unknown; correlation (piano interest) != speculative fact fabrication.
  - **Minimal Revision (Proven ✅)**: Official transfer notice revises ONLY `education.institution` (USM -> UM), leaving major and age strictly intact, with append-only provenance linkage in `CharacterRealityRevisionRecord`.
  - **Temporal Identity & History Awareness (Proven ✅)**: Remembers past USM state while aware of current UM status across subsequent turns and unrelated topic shifts (dinner small talk).
  - **State Without Performance (Glimpsed in T11 🟡)**: Entering everyday chitchat without compulsively reciting or performing her autobiography (`Autobiographical state exists ≠ Autobiographical state must manifest`).
  - **Known Epistemic Boundary on Reversal (T10 ⚠️)**: Casual challenge ("同名同姓别人的") does not trigger panic-reversion (`Dispute ≠ Revocation`, `Doubt ≠ Counter-evidence`). Preserved as an honest boundary; strictly NO ad-hoc revocation tokens or mega-orchestrator bloat added.
* **Constitutional Boundaries (User Review Lock 🔒)**:
  - 🟢 **Proven**: **Autobiographical Reality Continuity** (自传现实连续性) — Aevum can maintain, revise, trace, and defend her biographical past in continuous interaction.
  - ❌ **NOT Proven & NOT Claimed**: **Subject Continuity** (主体连续性) — The 12-turn benchmark was an interactive "proof of identity under interrogation" scenario. It does NOT answer: *"如果没有消息、没有任务、没有触发器，Aevum 仍然是谁？"*
  - 🔑 **Epistemic Invariants Locked**:
    - `Unknown ≠ Missing Data`
    - `Silence ≠ Missing Output`
    - `Unknown ≠ Retrieval Failure`
    - `No Manifestation ≠ No State`
    - `Autobiographical state exists ≠ Autobiographical state must manifest`
* **Benchmark Test Verification**:
  - `tests/test_phase21_autobiographical_stress.py`: **1/1 PASSED ✅** (12-turn DB assertions verified).
  - Combined Gate 0 + Gate 1 + Gate 2 + Phase 21: **16/16 PASSED ✅** in 43.60s.
  - Golden Suite 7D: **60/60 PASSED ✅** in 0.86s.
* **Milestone Status**:
  > **Phase 21 Benchmark — ACCEPTED AS EMPIRICAL EVIDENCE 🟢**  
  > **Subject Continuity remains the central open inquiry of Phase 20.**

---

### Phase 22 — Mobile Presence & Cross-Device Sync (Android) *(Strategic Proposal -> Aevum Alpha)*
* **Objective**: Extend Aevum's living presence to mobile devices with full reality, memory, growth history, and agency parity.
* **Deliverables**:
  * Android client application connecting to Aevum Core.
  * Background synchronization, lock screen widgets, and mobile notifications.
  * Full identity, relationship, and longitudinal memory persistence across desktop and mobile.
* **Exit Criteria**: User can interact with the same autonomous companion on mobile with synchronized memory, emotional state, and living agency — culminating in the official birth of **Aevum Alpha**.




