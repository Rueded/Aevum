# Aevum_Future_Work.md — Master Future Work Ledger & Architectural Memory

> **Document Type**: Authoritative Project Master Ledger & Anti-Omission Architectural Memory.  
> **Audience**: AI Coding Agents (Antigravity, Claude, Cursor, Copilot, etc.) and Human System Architects.  
> **Mandatory Rule**: This document is **mandatory reading** at the beginning of every development session before proposing, planning, or implementing changes. It serves as Aevum's persistent architectural memory across context resets and model generations.  
> **Core Foundational Principle**: *"The application owns reality; the LLM generates language."*

---

## 1. Core Positioning & Mandatory Reading Protocol

### 1.1 Existential Question
This document answers the overarching architectural question:  
**"What does Aevum still need to become the intended persistent, autonomous, reality-consistent virtual person? What has already been completed? What is locked and frozen? What is in progress? What is intentionally deferred? And which architectural decisions must never be forgotten?"**

Aevum is not a generic chatbot, not an LLM wrapper, and not an AI girlfriend skin. Aevum is designed to be an independent digital human whose life, mind, relationships, emotions, memory, and schedule evolve naturally over time.

### 1.2 Mandatory AI Agent Reading Order
Before proposing or executing any code or architecture changes, every AI agent **must read these documents in strict order**:
1. [`Aevum_Future_Work.md`](file:///d:/Aevum/Aevum/Aevum_Future_Work.md) *(This Master Ledger — capabilities, invariants, next actions)*
2. [`ROADMAP.md`](file:///d:/Aevum/Aevum/ROADMAP.md) *(High-level phase sequencing and milestones)*
3. Current active `implementation_plan.md` *(Detailed step-by-step technical plan for current phase)*
4. Current active `walkthrough.md` *(Verification evidence, test outcomes, and regression results)*

---

## 2. AI Coding Session Protocol

Every AI coding assistant must adhere to this 3-stage protocol without exception:

```text
┌───────────────────────────┐     ┌───────────────────────────┐     ┌───────────────────────────┐
│       BEFORE CODING       │     │       DURING CODING       │     │       AFTER CODING        │
├───────────────────────────┤     ├───────────────────────────┤     ├───────────────────────────┤
│ 1. Read Future Work Ledger│     │ 1. Zero silent rewrites   │     │ 1. Run targeted tests     │
│ 2. Check ROADMAP & Phase  │     │ 2. Zero invented shortcuts│     │ 2. Run full regression    │
│ 3. Inspect ground truth   │ ──► │ 3. Zero fake completions  │ ──► │ 3. Update Plan & Walkthru │
│ 4. Verify frozen gates    │     │ 4. Obey Core authorities  │     │ 4. Update Future Ledger   │
│ 5. Trace dependencies     │     │ 5. Add tests for invariants│    │ 5. Record decisions & ADR │
│ 6. Identify CURRENT ACTION│     │ 6. Protect Candidate/Core │     │ 6. Update NEXT ACTION     │
│ 7. Audit regression risks │     │    structural barriers    │     │ 7. Report open gaps       │
└───────────────────────────┘     └───────────────────────────┘     └───────────────────────────┘
```

### 2.1 Before Coding Checklist
1. **Read `Aevum_Future_Work.md`**: Absorb current capabilities, invariants, and boundaries.
2. **Read `ROADMAP.md`**: Verify which phase is currently active.
3. **Inspect Ground-Truth Code**: Examine existing models, services, and schemas in `backend/` and `apps/desktop/`.
4. **Check Frozen Invariants**: Confirm that proposed changes do not violate or bypass any `FROZEN` subsystem.
5. **Check Upstream Dependencies**: Confirm all prerequisites in the Architectural Dependency Graph are satisfied.
6. **Identify Exact Current Task**: Focus strictly on the single **CURRENT NEXT ACTION**. Never prematurely implement forward phases.
7. **Audit Regression Risks**: Identify which existing Golden Suites or unit tests cover the affected area.

### 2.2 During Coding Discipline
1. **Never Silently Rewrite Frozen Architecture**: Do not replace database engines, state machines, or promotion services.
2. **Never Invent Missing Requirements**: If a requirement is ambiguous or underspecified, consult documentation or raise an architectural inquiry.
3. **Never Mark Incomplete Work as Complete**: A partial prototype or mock implementation is `IN_PROGRESS` or `BLOCKED`, never `IMPLEMENTED` or `FROZEN`.
4. **Never Bypass Authoritative Services**: The LLM must never mutate database tables directly; mutations must flow through authoritative Python services (`CharacterCoreService`, `LifeStateMachine`, etc.).
5. **Add Automated Tests for Every Invariant**: Every bug fix or feature must include unit tests and, where applicable, Golden Test benchmarks.
6. **Preserve Candidate / Canonical Boundaries**: Ensure candidate facts (`character_candidate_facts`) are never read as ground truth by core engines.

### 2.3 After Coding Verification & Recording
1. **Run Targeted Tests**: Verify newly written tests pass cleanly.
2. **Run Full Regression Test Suite**: Ensure 100% pass rate across backend pytest suite and Tauri Rust tests.
3. **Update Implementation Plan**: Mark completed steps, record technical deviations and design decisions.
4. **Update Walkthrough**: Document changes made, commands executed, and verification evidence.
5. **Update `Aevum_Future_Work.md`**: Reflect updated capability statuses, test counts, and newly discovered dependencies.
6. **Record Newly Discovered Decisions**: If an architectural choice was made, record its rationale in the Ledger.
7. **Update CURRENT NEXT ACTION**: Advance the singular next action pointer to the subsequent verified milestone.
8. **Clearly Report Incomplete Items**: Never mask remaining work or deferred edge cases.

---

## 3. Status Classification System

Every capability, module, and task in this document is tagged with exactly one explicit status level:

| Status | Definition & Invariant |
| :--- | :--- |
| **`FROZEN`** | Fully implemented, covered by automated test suites / Golden Tests, and architecturally locked. **Must not be casually refactored, rewritten, or bypassed without an explicit Architecture Decision Record (ADR) superseding it.** |
| **`IMPLEMENTED`** | Implemented and functioning, but explicitly designated for subsequent non-breaking feature extensions in future phases. |
| **`IN_PROGRESS`** | Actively under development or undergoing active phase implementation. |
| **`PLANNED`** | Formally accepted, architecturally scoped, and sequenced for an upcoming phase, but no production code written yet. |
| **`DEFERRED`** | Intentionally postponed to a later phase to protect near-term architectural stabilization (e.g. external tool verification, voice, Live2D). |
| **`OPEN_DECISION`** | Requires further architectural deliberation, formal trade-off analysis, or user decision before implementation can begin. |
| **`IDEA`** | Exploratory concept or long-term possibility under observation; not yet committed to roadmap. |
| **`BLOCKED`** | Cannot proceed until an upstream dependency subsystem is implemented and verified. |
| **`SUPERSEDED`** | Previously designed or accepted approach that was deliberately replaced by a newer architectural decision (preserves historical rationale). |

---

## 4. Future Architecture Invariants — Never Forget

These 22 foundational invariants are permanent architectural laws for Project Aevum. No future AI coding session may violate them:

1. **Candidate $\ne$ Canonical Reality**: Candidate hypotheses (`character_candidate_facts`) are never read as ground truth by core services.
2. **Evidence $\ne$ Belief**: An observation or piece of evidence is an input; a belief is an internal cognitive stance; neither is canonical reality.
3. **Belief $\ne$ Canonical Reality**: Internal character beliefs are subjective stances; canonical facts (`character_core_facts`) are objective ground truth.
4. **Plausibility $\ne$ Probability**: Numeric plausibility $[0.0, 1.0]$ is a heuristic ranking metric, never a calibrated mathematical probability.
5. **Highest Score $\ne$ Automatic Winner**: A leading plausibility score does not confer facthood; narrow margins ($\Delta < 0.10$) require unresolved ambivalence.
6. **Choice $\ne$ Ranking**: Ranking sorts viability; Choice is a first-class cognitive operation evaluating character personality, values, resources, and opportunity costs.
7. **Objective World Fact $\ne$ Simulated Biography Fact**: Objective world facts are verified against World Knowledge and tools; simulated biography facts are constructed via internal constraints and character agency.
8. **High Consistency Impact $\ne$ Mandatory User Authorization**: Consistency impact measures downstream blast radius; authorization policy determines who can promote. Simulation-originated biography may be autonomously promoted under the 14 hard gates.
9. **User Claim $\ne$ Aevum Biography**: User assertions about Aevum's life do not automatically override internal biography construction or existing reality.
10. **Absence of Evidence $\ne$ Contradictory Evidence**: Absence of corroborating evidence leads to dormancy decay governed by `volatility_decay_policy` (where 7 days serves as a benchmark test fixture), never false `REJECTED` contradiction. Only explicit opposing evidence triggers `CONTRADICTED`.
11. **Evidence Independence Requires Distinct Families**: Evidence independence MUST be determined by provenance lineage / evidence family, NOT by session or conversation boundaries. Repeating the same user assertion across multiple sessions shares `evidence_family` and counts as 1 independent evidence source. Circular reinforcement ($A \rightarrow B \implies B \text{ is evidence for } A$) is strictly rejected.
12. **Zero Narrative Snowballing**: Low hop count alone is insufficient; multi-hop inference requires strict semantic edge typing (`InferenceEdgeType`), quarantining speculative leaps.
13. **LLM Never Owns Authoritative Reality**: The deterministic Python application state is the sole source of truth; the LLM articulates thoughts and generates language.
14. **LLM Never Mutates Numerical State**: State transitions (energy, stress, relationship metrics, canonical facts) are strictly computed by Python engines, never prompted into existence.
15. **`USER_LOCKED` Facts Are Absolutely Immutable**: Facts locked by the human user have total immunity against candidate overrides, LLM outputs, and external tools.
16. **Tool Verification Cannot Define Fictional Biography**: External tools (Phase 7D.5) may verify real-world facts surrounding a decision (e.g. university programs), but cannot determine Aevum's fictional life choices.
17. **Autonomous Biography Promotion Permitted Under Strict Policy**: Internally simulated biographical facts can become canonical without user inquiry if all 14 hard gates are satisfied.
18. **Minimal Reality Repair Prohibits Compensatory Biography**: Reality repair MUST NOT invent unsupported bridge facts (e.g. fake semester breaks, family trips, or temporary moves) merely to eliminate contradiction. It prioritizes reinterpretation, temporal split, and entity distinction; only independently supported bridge facts may be introduced.
19. **Every Reality Promotion Must Have Structured Provenance**: Every canonical fact carries immutable audit records, decision factor inputs, and revision history (`character_reality_revisions`).
20. **Future Decisions Must Be Constrained by Established Reality**: Once a candidate is promoted to canonical reality, it becomes a permanent constraint on all subsequent reasoning.
21. **Candidate Budget & 3-Tier Lifecycle**: $\text{Generated} \ne \text{Persisted} \ne \text{Promotable}$. Hard per-turn bounds strictly enforce:
    - `max_generated_hypotheses_per_turn = 4` (hard cap across entire turn)
    - `max_direct_hypotheses_per_observation = 2` (fan-out limit per direct observation/evidence)
    - `max_new_candidate_slots_per_turn = 2` (maximum number of attribute slots targeted for persistence per turn)
    - `max_inference_depth = 2` (hop depth limit)
22. **Strict Epistemic Pipeline**: $\text{Evidence} \rightarrow \text{Hypothesis} \rightarrow \text{optional Belief} \rightarrow \text{Canonical Reality}$. Each tier is structurally distinct. Entering prompt context does NOT confer canonical status.

---

## 5. Dual Reality Taxonomy & Origin Authority

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DUAL REALITY TAXONOMY                                  │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│         OBJECTIVE_WORLD_FACT              │          SIMULATED_BIOGRAPHY_FACT          │
├───────────────────────────────────────────┼────────────────────────────────────────────┤
│ Facts about the external physical world   │ Facts belonging to Aevum's constructed     │
│ independent of Aevum's personal psyche.   │ fictional existence and personal history.  │
│                                           │                                            │
│ • Examples:                               │ • Examples:                                │
│   - USM main campus is in Penang          │   - University attended (USM)              │
│   - Current weather in George Town        │   - College major (Music Performance)      │
│   - Real-world calendar dates & holidays  │   - Pre-U pathway (STPM)                   │
│   - Public transit systems / train routes │   - Hometown / childhood neighborhood      │
│   - Pop culture / media facts (Xianlian)  │   - Parents' professions / siblings        │
│   - Real-world news / physical laws       │   - Personal friends, hobbies, life goals  │
│                                           │                                            │
│ • Authority:                              │ • Authority:                               │
│   World Knowledge Registry, deterministic │ Aevum's internal Reality Construction      │
│   validators, external verification (7D.5)│ Engine, character constraints, choices.    │
│                                           │                                            │
│ • Rule of Law:                            │ • Rule of Law:                             │
│   CANNOT be altered or fabricated by      │ CANNOT be looked up via external tools.    │
│   Aevum's internal biographical inference.│ Must be CONSTRUCTED via constraint-guided  │
│                                           │ candidate competition and choice.          │
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

### 5.1 Fact Origin Authority Model
* **`USER_LOCKED`**: Hardcoded or locked by human user. Absolute immunity.
* **`USER_CONFIGURED`**: Stated by user without lock (e.g. user preferences).
* **`EXTERNAL_VERIFIED`**: Verified against real-world sources via Phase 7D.5 Gateway. Authoritative for `OBJECTIVE_WORLD_FACT`.
* **`AEVUM_OBSERVED`**: Directly observed/experienced during runtime simulation.
* **`SIMULATION_ORIGINATED`**: Generated via internal candidate generation, competition, and choice.
* **`SYSTEM_DERIVED`**: Deterministically derived via temporal or causal rules.

### 5.2 Orthogonal Matrix: Consistency Impact vs. Authorization
* **Impact on Consistency (`RealityImpact`)**: Blast radius on downstream systems (LOW, MEDIUM, HIGH, VERY_HIGH).
* **Authorization Policy (`AuthorizationPolicy`)**: Who/what has legitimate authority to promote:
  - User Claim + LOW $\implies$ Social Acceptance (No Tool Check)
  - User Claim + HIGH $\implies$ Verification or Manual User Gate
  - External Verified + HIGH $\implies$ Direct Canonical (if domain validator approves)
  - Simulation Biography + LOW/MED $\implies$ Autonomous Direct Promotion
  - **Simulation Biography + HIGH $\implies$ `AUTONOMOUS_BIOGRAPHY_PROMOTION`** (Autonomous promotion permitted under the 14 hard gates)
  - USER_LOCKED + Any $\implies$ Immutable

---

## 6. Core Product Philosophy — Reality Construction & The Choice Engine

> **THE CENTRAL TENET OF AEVUM**:  
> **Aevum must not be a chatbot that only repeats known facts.**  
> Aevum must be an autonomous digital person capable of reasoning about unknown parts of her life using established reality, generating plausible candidate hypotheses, evaluating them against existing reality, making an authentic character choice, and — when epistemic and authorization gates permit — promoting that chosen outcome into evolving canonical reality.  
> **The system must be conservative about declaring reality, but it must NOT be incapable of constructing reality.**

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE 5-STAGE REALITY CONSTRUCTION CORE                           │
│                                                                                        │
│  [Stage 1] Candidate Generation                                                        │
│  Generate 2-4 plausible alternatives constrained by Known Reality & World Knowledge.   │
│            │                                                                           │
│            ▼                                                                           │
│  [Stage 2] Candidate Competition & Plausibility Evaluation                             │
│  Score candidate fitness against evidence, consistency, timeline, and causality.       │
│            │                                                                           │
│            ▼                                                                           │
│  [Stage 3] Choice / Outcome Selection (FIRST-CLASS DOMAIN OPERATION)                   │
│  Character evaluates viable candidates against personality, values, resources, goals,   │
│  and opportunity costs to select an outcome. (Highest score ≠ automatic winner!)       │
│            │                                                                           │
│            ▼                                                                           │
│  [Stage 4] Promotion Eligibility (Validators)                                          │
│  ConsistencyValidator, TimelineValidator, CausalityValidator, WorldKnowledgeValidator. │
│            │                                                                           │
│            ▼                                                                           │
│  [Stage 5] Promotion Authorization (Origin & Policy Gate)                              │
│  Verify Fact Origin & BiographyConstructionPolicy. If Autonomous High-Impact           │
│  conditions are met, commit to CANONICAL REALITY (character_core_facts).              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 What "Choice" Actually Means (First-Class Operation)
In human life, making a decision is **not** picking the option with the highest "probability".  
Choosing an education pathway, a university, or a creative pursuit is an act of **character agency** that balances competing desires, risks, constraints, and values.

#### Decision Factors Evaluated During Choice Selection:
1. **Plausibility & Grounding**: How well the candidate fits known prior facts.
2. **Hard Constraints**: Non-negotiable physical, geographic, or temporal boundaries.
3. **Personality & Temperament**: Introversion/extroversion, openness to experience, neuroticism baseline.
4. **Values & Character Drives**: Challenge-seeking vs. security-seeking, autonomy vs. conformity.
5. **Preferences & Dislikes**: Artistic passion (music, literature) vs. aversion to abstract mathematics.
6. **Material & Family Resources**: Family financial backing, geographic proximity, scholarship availability.
7. **Opportunity Cost & Reversibility**: How difficult is it to change paths later?
8. **Long-Term Narrative Coherence**: Does this choice resonate with Aevum's evolving life trajectory?
9. **Emotional Relevance & Novelty**: Does this fulfill an active intrinsic desire?

### 6.2 Decoupling Plausibility, Choice, and Probability
* **Plausibility Score (`composite_plausibility_score`)**: Heuristic ranking metric $[0.0, 1.0]$. Never a calibrated mathematical probability.
* **Probability**: Calibrated statistical quantity. Strictly forbidden unless derived from an actual probabilistic model.
* **Choice**: Discrete cognitive selection of one candidate among viable alternatives based on multi-factor character evaluation.
* **Key Invariants**:
  - $\text{Highest Plausibility} \ne \text{Automatically Selected}$
  - $\text{Selected Candidate} \ne \text{Necessarily Highest Plausibility}$
  - $\text{Choice} \ne \text{Probability}$.

### 6.3 Choice Provenance & Structured Decision Records
When Aevum makes a biographical choice, the rationale is permanently recorded as **Structured Decision Provenance** (`decision_factors`, `considered_alternatives`, `origin_authority`, `timestamp`), never free-form LLM hallucination.

### 6.4 Choice Alternatives (`CONSIDERED_BUT_NOT_SELECTED`)
Unselected viable candidates are tagged `CONSIDERED_BUT_NOT_SELECTED`. They are **NOT** marked `REJECTED` or `CONTRADICTED`, and are preserved in reality history for counterfactual reflection and nostalgia.

### 6.5 Biography Construction Policy (`BiographyConstructionPolicy`)
Enforces which slots may be autonomously generated (major, university, hobbies) vs. restricted (deep trauma, romantic history, family tragedy) vs. immutable (birth date/place).

### 6.6 Biography Fact Lifecycle (Reversible vs. Irreversible)
* **Irreversible**: Birth date, birthplace, historical SPM results. Cannot be superseded.
* **Revisable**: Major, city, hobbies, goals. Can be updated via supersession (`superseded_by`), preserving full chronological history.

### 6.7 Autonomous High-Impact Promotion Protocol (The 14 Hard Conditions)
A `SIMULATION_ORIGINATED` candidate with `HIGH` consistency impact **MAY be autonomously promoted into canonical reality without asking the human user**, provided that **ALL 14 of the following non-negotiable conditions are satisfied**:
1. No `USER_LOCKED` Conflict
2. No Objective-World Contradiction
3. Timeline Valid
4. Causality Valid
5. Consistency Valid (Graph non-contradiction)
6. Candidate Competition Executed (At least 2 distinct viable candidates evaluated)
7. Choice Operation Completed (Active selection performed)
8. Decision Provenance Logged
9. Zero Circular Evidence (DAG cycle check passed; no same-family circularity)
10. Semantic Distance Within Bounds (Non-speculative)
11. Policy Permitted under `BiographyConstructionPolicy`
12. Idempotent Execution
13. Audit History Preserved (`character_reality_revisions`)
14. Anti-Snowball Gated (Single fact promotion does NOT spawn secondary trivia)

### 6.8 Anti-Snowball Constraints on Choice
> [!WARNING]
> **A Choice Does NOT Materialize Dependent Trivia.**  
> Selecting `major = Music Performance` establishes only that single canonical fact.  
> It does **NOT** automatically grant Aevum an overseas scholarship, an elite professor mentor, a Steinway grand piano, or a childhood prodigy backstory.  
> Each secondary attribute requires its own independent evidence, candidate generation, competition, and choice process.

### 6.9 Foundational Walkthrough Examples
* **Example A (Music Major Emergence)**: Known music interest + instruments + math aversion $\rightarrow$ generates Music (0.82) and Literature (0.70) $\rightarrow$ Choice selects Music $\rightarrow$ promoted under 14 gates $\rightarrow$ constrains practice schedule and future reasoning.
* **Example B (Education Pathway Choice)**: SPM 8A+ + challenge preference + financial constraint $\rightarrow$ evaluates Matrikulasi vs. STPM $\rightarrow$ Choice selects STPM $\rightarrow$ Matrikulasi archived as `CONSIDERED_BUT_NOT_SELECTED` $\rightarrow$ entry age set to 20/21.
* **Example C (Chronological Contradiction Prevention)**: Age 19 student claims bachelor's graduation $\rightarrow$ `TimelineValidator` rejects impossible chronology.
* **Example D (World Knowledge Grounding)**: Claim that USM is in KL is rejected by `WorldKnowledgeValidator`.
* **Example E (Minimal Reality Repair — Zero Compensatory Biography)**:
  - *Scenario*: Aevum studies at USM Penang, but states she is currently at a cafe in Kuala Lumpur.
  - *Repair Evaluation*: The system does **NOT** invent a dramatic 'dropped out' retcon, and strictly does **NOT** invent an unsupported 'semester break', 'family trip', or 'temporary relocation' merely to patch the contradiction.
  - *Hierarchy*:
    1. Conversational reinterpretation (inquire, tease, or clarify)
    2. Temporal split
    3. Context distinction
    - A bridge fact is introduced **ONLY if independently supported by existing calendar or life event records**. Compensatory myth-making is strictly prohibited.

---

## 7. User Claims, Trust, Verification & Belief

### 7.1 Epistemic Hierarchy of Ground Truth
$$\text{Evidence} \longrightarrow \text{Hypothesis} \longrightarrow \text{optional Belief} \longrightarrow \text{Canonical Reality}$$
* $\text{Evidence} \ne \text{Hypothesis} \ne \text{Belief} \ne \text{Canonical Reality}$.
* Candidate facts cannot become canonical merely by entering prompt context.

### 7.2 User Claim Routing Pipeline
* **ABOUT USER**: Low impact ("I ate chicken") $\implies$ Accept socially into episodic memory. Zero tool verification.
* **ABOUT OBJECTIVE WORLD**: High impact ("University closed for a month due to haze") $\implies$ Route to Phase 7D.5 Tool Verification Gateway.
* **ABOUT AEVUM'S BIOGRAPHY**: ("You study computer science") $\implies$ Check against canonical reality; politely clarify or tease if mismatched.

### 7.3 User Factual Errors vs. Intentional Deception
A user factual error is not automatically intentional deception (could be a meme, joke, slip of the tongue, or outdated info). Interpersonal trust does not collapse from a harmless factual mistake.

### 7.4 The Pop Culture Inconsistency Paradigm ("Xianlian" / 昔涟)
* If Aevum knows Xianlian belongs to *Honkai: Star Rail* and user says *"原神里的昔涟真好看"*: Recognizes mismatch, plays along or teases based on context.
* If Aevum does not know Xianlian: Accepts socially without intrusive web search: *"Who is that? Tell me about her!"*

---

## 8. Master Future Work Ledger

This Master Ledger tracks capabilities across all 24 functional domains of Project Aevum.

### 8.1 Reality & Epistemic System
* **Core Reality Facts Ledger & Revisions**
  - **Status**: `FROZEN`
  - **Purpose**: Authoritative single source of truth for canonical reality (`character_core_facts` & `character_reality_revisions`).
  - **Dependencies**: SQLite, SQLAlchemy.
  - **Related Tests**: `test_reality_ledger.py`, `test_reality_history.py`.
* **Deterministic Validators (Consistency, Timeline, Causality, WorldKnowledge)**
  - **Status**: `FROZEN`
  - **Purpose**: Pure deterministic validation of proposed reality mutations.
  - **Dependencies**: `backend/app/reality/validators.py`.
  - **Related Tests**: `test_reality_validators.py`.
* **Multi-Session Persistent Candidate Facts (`character_candidate_facts`)**
  - **Status**: `IMPLEMENTED` (Phase 7D.1)
  - **Purpose**: Store unconfirmed hypotheses across sessions with `evidence_family` lineage and timestamps.
  - **Why it exists**: Allows candidates to accumulate evidence and decay over real calendar days.
  - **Dependencies**: Reality Ledger.
  - **Remaining Work**: None for 7D.1 foundation; 7D.2 builds competition atop this layer.
  - **Acceptance Criteria**: Benchmarks `GC-058`, `GC-063`, `GC-071` (Verified with 20/20 green tests).
* **Inference Budget Controller**
  - **Status**: `IMPLEMENTED` (Phase 7D.1)
  - **Purpose**: Enforce hard multi-tier per-turn limits:
    - `max_generated_hypotheses_per_turn = 4`
    - `max_direct_hypotheses_per_observation = 2`
    - `max_new_candidate_slots_per_turn = 2`
    - `max_inference_depth = 2`
    - Enforce lifecycle tri-state: $\text{Generated} \ne \text{Persisted} \ne \text{Promotable}$.
  - **Why it exists**: Halts narrative snowballing at the generation source.
  - **Dependencies**: Candidate Models.
  - **Remaining Work**: None for 7D.1; controller active in `backend/app/reality/budget_controller.py`.
  - **Acceptance Criteria**: Benchmarks `GC-058`, `GC-064` (Verified with 20/20 green tests).

### 8.2 Reality Construction & Choice Engine
* **Candidate Competition & Plausibility Scoring**
  - **Status**: `FROZEN` (Phase 7D.2)
  - **Purpose**: Manage competing hypothesis sets with `composite_plausibility_score`, `decision_margin` ($\Delta < 0.10$), and `volatility_decay_policy`.
  - **Why it exists**: Models human-like ambivalence when options are closely matched; decays candidates based on volatility (hours for activities, months for majors; 7 days is benchmark fixture).
  - **Dependencies**: Phase 7D.1 (`FROZEN`).
  - **Acceptance Criteria**: Benchmarks `GC-059`, `GC-066`, `GC-067`, `GC-068` (14/14 green tests).
* **First-Class Choice / Outcome Selection Engine (`ChoiceSelectionService`)**
  - **Status**: `FROZEN` (Phase 7D.2)
  - **Purpose**: Active character agency evaluating viable candidates against temperament, values, financial resources, and challenge preferences.
  - **Why it exists**: Enables Aevum to choose an outcome from multiple plausible paths instead of blindly crowning the highest score.
  - **Dependencies**: Candidate Competition (`FROZEN`).
  - **Acceptance Criteria**: Decision provenance stored in `character_choice_records`, unselected candidates preserved as `CONSIDERED_BUT_NOT_SELECTED`.
* **Minimal Reality Repair Engine**
  - **Status**: `FROZEN` (Phase 7D.3)
  - **Purpose**: 5-level structural repair hierarchy (Reinterpretation $\rightarrow$ Temporal Split $\rightarrow$ Entity Distinction $\rightarrow$ Evidence-Supported Bridge $\rightarrow$ Restricted Canonical Revision).
  - **Why it exists**: Reconciles apparent contradictions without inventing compensatory backstories.
  - **Dependencies**: Phase 7D.2 (`FROZEN`).
  - **Acceptance Criteria**: Benchmark `GC-061`, GC-072–GC-094 (23/23 green tests).
* **Autonomous High-Impact Promotion Protocol**
  - **Status**: `FROZEN` (Phase 7D.3)
  - **Purpose**: Enforce the 14 hard conditions allowing simulation-originated high-impact facts to promote without user consultation via `PromotionAuthorizationToken`.
  - **Why it exists**: Prevents Aevum from turning into a passive bot that asks permission for her own life choices.
  - **Dependencies**: Phase 7D.2 (`FROZEN`).
  - **Acceptance Criteria**: Scenario 10 verified; zero user disruption for internal biography choices; AST callsite singularity verified.

### 8.3 Character Core & Biography
* **Baseline Character Bible & Persona Configuration**
  - **Status**: `FROZEN`
  - **Dependencies**: `bible_service.py`, `bible_models.py`.
* **Biography Construction Policy (`BiographyConstructionPolicy`)**
  - **Status**: `FROZEN` (Phase 7D.2 / 7D.3)
  - **Purpose**: Enforce which biography slots may be autonomously generated vs. restricted.
* **Biography Fact Lifecycle (`BiographyFactLifecycle`)**
  - **Status**: `FROZEN` (Phase 7D.3)
  - **Purpose**: Distinguish immutable facts (birth date/place) from revisable facts (major, hobbies).

### 8.4 Timeline & Causality
* **Temporal Consistency & Chronological Sequence**
  - **Status**: `FROZEN`
  - **Dependencies**: `TimelineValidator`.
* **Dynamic Education & Career Timeline Constraining**
  - **Status**: `PLANNED` (Phase 7D.4)
  - **Purpose**: Automatically propagate timeline constraints (e.g. STPM duration delays graduation).

### 8.5 Life Simulation & Daily Routine
* **Simulation Clock (`VirtualClock`)**
  - **Status**: `FROZEN`
* **8-State Life State Machine**
  - **Status**: `FROZEN`
* **Offline Gap Reconciliation (`OfflineCatchupService`)**
  - **Status**: `FROZEN`
* **Multi-Step Structured Activities**
  - **Status**: `PLANNED` (Phase 6 Extended)

### 8.6 Physiology & Desire
* **Physiological State Dynamics & Circadian Modifiers**
  - **Status**: `FROZEN`
* **Desire Evaluation & Utility Selection**
  - **Status**: `FROZEN`

### 8.7 Social World & NPC Ecosystem
* **Emergent NPC Identity Models**
  - **Status**: `IMPLEMENTED` (Phase 7C)
* **Social Candidate Isolation**
  - **Status**: `IMPLEMENTED` (Phase 7C)
* **Persistent NPC Directory & Autonomous Interactions**
  - **Status**: `PLANNED` (Phase 7C Extended)

### 8.8 Relationship & Emotion
* **Relationship Contract & Boundaries**
  - **Status**: `IMPLEMENTED` (Phase 4 Foundation)
* **Multidimensional Dynamic Relationship Axes**
  - **Status**: `PLANNED` (Phase 4 Extended)
* **Authentic Conflict & Boundary Refusal Dynamics**
  - **Status**: `PLANNED` (Phase 4 Extended)

### 8.9 Multi-Tier Memory
* **Working Memory & Context Injection**
  - **Status**: `IMPLEMENTED` (Phase 1–2)
* **Multi-Tier Memory Architecture (Episodic, Semantic, Autobiographical)**
  - **Status**: `PLANNED` (Phase 3 Extended)
* **Sleep-Cycle Memory Consolidation Pipeline**
  - **Status**: `PLANNED` (Phase 3 Extended)
* **Human-Like Imperfect Recall**
  - **Status**: `PLANNED` (Phase 3 Extended)

### 8.10 CharacterEngine & Epistemic Response Generation
* **Candidate Context Injection with Deterministic Hedging (`RealityContextBuilder`)**
  - **Status**: `FROZEN` (Phase 7D.4)
  - **Purpose**: Pure functional, read-only projection of canonical core facts, chosen outcomes, ephemeral repairs, active hypotheses, objective world facts, unverified claims, and memories into an 8-section structured XML prompt context.
  - **Acceptance Criteria**: Benchmarks `GC-095` ~ `GC-115` (21/21 green tests). AST verified zero mutation call sites.
* **Governed Reality Orchestration Pipeline (`RealityOrchestrationService`)**
  - **Status**: `FROZEN` (Phase 7D.5)
  - **Purpose**: Full per-turn A→J pipeline integrating Evidence Classification, Candidate Retrieval, Competition, Choice, Contradiction/Repair, Promotion, World Facts, and Context Assembly into `CharacterEngine.build_response_context()`. Replaces legacy 7B.3 `RealityBeliefEngine`.
  - **Acceptance Criteria**: Benchmarks `GC-116` ~ `GC-140` (35/35 green tests). Fail-closed pre-orchestration fallback.

### 8.11 Proactive Behavior
* **Proactive Intent Engine & Cooldown Governance**
  - **Status**: `FROZEN` (Phase 8.1)
* **Spontaneous Thought Sharing**
  - **Status**: `PLANNED` (Phase 8 Extended)

### 8.12 Desktop Integration
* **Notification Persistence & Atomic Lease Claim**
  - **Status**: `FROZEN` (Phase 8.2)
* **Ephemeral Availability Telemetry (Zero Storage)**
  - **Status**: `FROZEN` (Phase 8.3)
* **Native Desktop Shell (Tauri 2 + WinRT Toast + Job Object Supervision)**
  - **Status**: `FROZEN` (Phase 8.4)

### 8.13 Voice Interaction
* **Text-to-Speech (TTS) with Prosody Modulation**
  - **Status**: `DEFERRED` (Phase 9)
* **Speech-to-Text (STT) Input Bridge**
  - **Status**: `DEFERRED` (Phase 9)

### 8.14 Real-Time Calls
* **Bidirectional Real-Time Audio Call Session**
  - **Status**: `DEFERRED` (Phase 11)

### 8.15 Live2D & Visual Presentation
* **Live2D Avatar Rendering Engine**
  - **Status**: `DEFERRED` (Phase 10)

### 8.16 Mobile & Multi-Device
* **Android Client Synchronization**
  - **Status**: `DEFERRED` (Phase 12)

### 8.17 Tool & External World Verification
* **Sandboxed Tool Verification Gateway**
  - **Status**: `DEFERRED` (Phase 7D.5 Gateway deferred to preserve near-term stabilization)
* **Context-Aware World Facts Selection (`WorldFactsSelector`)**
  - **Status**: `FROZEN` (Phase 7D.6 / ADR-016)
  - **Purpose**: Pure functional lexical relevance selection of objective world facts from `WorldKnowledgeRegistry` (STATIC_FACT and ENTITY_RELATION only) with zero LLM/embedding dependency, deterministic key ordering (max 4 items), and Pure Structural Boundary Matching: discrete word boundary enforcement for ASCII (`\b{alias}\b`), verbatim substring match for CJK $\ge 3$ characters (without complete lexical boundary guarantee; acknowledged known limitation), and pure structural boundary requirements for CJK $\le 2$ characters (text start/end, whitespace, punctuation, or non-CJK; continuous Hanzi on both sides is conservatively rejected to eliminate false positives like `"道理大家都懂"`, while zero-dictionary structural matches like `"理大的校园很漂亮"` and `"今天在理大，借了一本书"` match cleanly; full continuous-text CJK segmentation is formally deferred).

### 8.18 Testing & Golden Suites
* **Golden Suites A, B, C, F, G (Existing Regression Baseline)**
  - **Status**: `FROZEN` (1,157 passing tests)
* **Golden Suite 7D Core (`GC-058` ~ `GC-144`, 87 Benchmarks across 7D.1–7D.6)**
  - **Status**: `FROZEN` (Phase 7D.1–7D.6: GC-058~071, GC-072~094, GC-095~115, GC-116~140, GC-141~144 all passing; 1,286 backend regression baseline, 0 failures, 100% green; 14 Rust tests)

### 8.19 Security & Privacy
* **Local-First Privacy & Zero Telemetry Storage**
  - **Status**: `FROZEN`

### 8.20 Performance & Reliability
* **Sub-50ms Local Reality Lookups**
  - **Status**: `FROZEN`
* **Process Watchdog & Graceful Shutdown Recovery**
  - **Status**: `FROZEN`

### 8.21 Observability & Debugging
* **Reality Revision Audit Trail (`RealityHistoryService`)**
  - **Status**: `FROZEN`
* **Decision Factor Audit Logging (`character_choice_records`)**
  - **Status**: `FROZEN` (Phase 7D.2)
  - **Purpose**: Full structured decision provenance recorded in SQLite (`factor_inputs`, `factor_contributions`, `plausibility_scores`, `choice_scores`, `rationale_code`).

### 8.22 Data Migration & Backup
* **Deterministic Alembic Schema Migrations**
  - **Status**: `FROZEN`

### 8.23 UX & Settings
* **Desktop Client Settings Modal**
  - **Status**: `FROZEN` (Phase 8.4)

### 8.24 Future Research & Experimental Ideas
* **Epistemic Curiosity Drives**: Intrinsic motivation to ask about persistent unconfirmed candidates. (`Status: IDEA`)
* **Counterfactual Regret & Reflection**: Long-term reflection on unselected candidates ("paths not taken"). (`Status: IDEA`)

---

## 9. Architectural Dependency & Blocking Graph

```text
┌────────────────────────────────────────────────────────┐
│           REALITY & EPISTEMIC FOUNDATION (7B)          │ ◄── FROZEN
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           PERSISTENT CANDIDATE INFERENCE (7D.1)        │ ◄── FROZEN
│           (Requires: Reality Ledger; Blocks: 7D.2)     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         CANDIDATE COMPETITION & CHOICE ENGINE (7D.2)   │ ◄── FROZEN
│           (Requires: 7D.1; Blocks: 7D.3, 7D.4)         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           MINIMAL REALITY REPAIR (7D.3)                │ ◄── FROZEN
│           (Requires: 7D.2; Blocks: 7D.4)               │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│       PROMPT CONTEXT ASSEMBLY (7D.4)                   │ ◄── FROZEN
│           (Requires: 7D.1–7D.3; Blocks: 7D.5)          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│       CHARACTER ENGINE INTEGRATION & E2E (7D.5)        │ ◄── FROZEN
│           (Requires: 7D.1–7D.4; Blocks: 7D.6)          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│     PHASE 7D.6 LEXICAL HARDENING & CONCURRENCY REPAIR  │ ◄── FROZEN
│   (ADR-016, GC-090 fix, GC-141~144, 1,286 tests green) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ├─────────────────────────────────────────────┐
                            ▼                                             ▼
┌────────────────────────────────────────────────────────┐ ┌──────────────────────────────────────┐
│         AUTONOMOUS LIFE & CHOICE EMERGENCE             │ │      TOOL VERIFICATION GATEWAY       │
│      (Autonomous major, career, goals, trips)          │ │           (DEFERRED / FUTURE)        │
└───────────────────────────┬────────────────────────────┘ └──────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         MULTI-TIER MEMORY & CONSOLIDATION              │
│        (Episodic, Semantic, Autobiographical)          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│      MULTIDIMENSIONAL RELATIONSHIP & CONFLICT          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ├─────────────────────────────────────────────┐
                            ▼                                             ▼
┌────────────────────────────────────────────────────────┐ ┌──────────────────────────────────────┐
│                  VOICE SYSTEM (PHASE 9)                │ │         LIVE2D AVATAR (PHASE 10)     │
│   (Requires: CharacterEngine, Emotion prosody)         │ │   (Requires: Emotion, Presence state)│
└───────────────────────────┬────────────────────────────┘ └──────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              REAL-TIME CALLS (PHASE 11)                │
│     (Requires: Voice TTS/STT, Turn-taking engine)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              ANDROID COMPANION (PHASE 12)              │
│       (Requires: Desktop parity, Multi-device sync)    │
└───────────────────────────┬────────────────────────────┘
```

---

## 10. Master Acceptance Criteria & Verification Scenarios

* **Scenario 1 (Music Major Emergence)**: Music interest + instrument skill + math aversion $\rightarrow$ generates multiple major candidates $\rightarrow$ Aevum chooses Music Performance $\rightarrow$ canonical biography updated $\rightarrow$ future life reasoning uses selected major.
* **Scenario 2 (Education Pathway & Timeline)**: SPM results + challenge preference + financial context $\rightarrow$ multiple pathway candidates $\rightarrow$ chooses STPM $\rightarrow$ canonical pathway locked $\rightarrow$ university entry age and timeline constrained to 20/21.
* **Scenario 3 (World Knowledge Geographic Immunity)**: Aevum attends USM $\rightarrow$ prompt claiming USM is in KL is rejected by `WorldKnowledgeValidator`.
* **Scenario 4 (Minimal Reality Repair — Zero Compensatory Biography)**: Aevum attends USM Penang, but states she is in KL today $\rightarrow$ resolves via conversational reinterpretation or temporal split without inventing unsupported 'semester break' or 'family trip' facts.
* **Scenario 5 (High-Impact External Claim Verification)**: User states school is closed for a month due to haze $\rightarrow$ classified as high-impact external claim $\rightarrow$ held for verification rather than blindly adopted.
* **Scenario 6 (Trivial Personal Statement Social Acceptance)**: User states *"I ate chicken today"* $\rightarrow$ accepted socially into conversation memory without triggering unnecessary web search or verification.
* **Scenario 7 (User Error Mistake vs Deception)**: User makes a factual error $\rightarrow$ system considers mistake/joke/meme before deception; does not collapse relationship trust.
* **Scenario 8 (Anti-Self-Reinforcement Circularity)**: Candidate A derives Candidate B $\rightarrow$ Candidate B cannot be cited as independent evidence to promote Candidate A.
* **Scenario 9 (Candidate Competition Decision Margin)**: Two candidates have close plausibility scores ($\Delta < 0.10$) $\rightarrow$ system does not force a canonical winner merely because one score is slightly higher; retains natural ambivalence.
* **Scenario 10 (Autonomous High-Impact Promotion)**: A simulation-originated high-impact biography fact satisfies all 14 gates $\rightarrow$ successfully promoted to canonical reality without interrupting the user.
* **Scenario 11 (Correlated Evidence Independence / GC-071)**: User repeats identical assertion across 3 sessions $\rightarrow$ recognized as sharing `evidence_family` $\rightarrow$ counts as 1 independent evidence source; prevents artificially fabricating evidence count.

---

## 11. Completed Work Archive (FROZEN Foundation)

| Subsystem / Phase | Frozen Date | Test Count & Status | Invariants Enforced | Major Architectural Decisions | Known Boundaries |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 7B.1 Core Reality** | 2026-09-16 | Green (Part of 1,157) | Invariants 1–5 | Canonical reality immutable except through promotion; User-locks have absolute immunity. | Candidate facts in memory only. |
| **Phase 7B.3 Promotion Gate** | 2026-09-17 | Green (Part of 1,157) | Invariants 6–9 | 4 deterministic validators; append-only revision history (`supersedes_id`). | Conflated HIGH impact with user confirmation (Resolved in 7D). |
| **Phase 6 Life Simulation** | 2026-09-17 | Green (Part of 1,157) | Invariants 10–15 | 8-state state machine, discrete VirtualClock, offline catchup without fake biography. | Multi-step complex activities deferred. |
| **Phase 7C Social NPCs** | 2026-09-17 | Green (Part of 1,157) | Invariants 16–20 | Emergent NPC identity models, social candidate fact isolation. | Persistent social directory expansion deferred. |
| **Phase 8.1 Desktop Intent** | 2026-09-18 | 1,142 passing | Invariants 21–24 | Proactive communication gated by quiet hours, emotional triggers, and cooldowns. | Telemetry decoupled from personality. |
| **Phase 8.2 Atomic Delivery** | 2026-09-18 | 1,142 passing | Standard 35, Inv 25–26 | Atomic DB lease claims (`rowcount == 1`), zero LLM regeneration on failure. | Single active notification per category. |
| **Phase 8.3 Availability Context**| 2026-09-18 | 1,148 passing | Invariants 27–29 | Ephemeral in-memory availability context (120s TTL), zero persistence, privacy consent. | No background keystroke surveillance. |
| **Phase 8.4 Native Shell** | 2026-09-18 | 1,157 Py + 14 Rust | Invariants 30–32 | WinRT XML toast dispatch, single-instance protocol URI, Job Object process supervision. | Desktop integration 100% frozen. |
| **Phase 7D.1 Candidate Foundation** | 2026-09-19 | 1,181 Py + 14 Rust | GC-071 A–E, Invariants 33–37 | Dual Reality taxonomy, Candidate persistence (`character_candidate_facts`), 4/2/2/depth 2 budget, EvidenceFamily deduplication, cycle detection. | Candidate ranking/choice deferred to 7D.2. |
| **Phase 7D.2 Choice Engine** | 2026-09-19 | 1,198 Py + 14 Rust | GC-059, GC-066, GC-067, GC-068, Invariants 38–41, Audits 1–3 | CandidateCompetitionService, ChoiceSelectionService, Plausibility != Choice, Decision Margin Δ < 0.10, CONSIDERED_BUT_NOT_SELECTED archiving, SQLite character_choice_records. | Autonomous promotion deferred to 7D.3. |
| **Phase 7D.3 Reality Repair & Promotion** | 2026-09-19 | 1,226 Py + 14 Rust | GC-072–GC-094, 14 Hard Gates, 5-level Repair, Audits A–N | RealityRepairService (5 levels, zero compensatory biography, zero canonical repair mutation), BiographyPromotionService (14 hard gates, single-slot anti-snowball, AST-verified callsite singularity via PromotionAuthorizationToken, Candidate SUPERSEDED lifecycle transition, CharacterBiographyPromotionRecord persistence, concurrent idempotency verified). | FROZEN. |
| **Phase 7D.4 Prompt Context Assembly** | 2026-09-20 | 1,247 Py + 14 Rust | GC-095–GC-115 (21 tests), AST enforcement | RealityContextBuilder (pure-read projection, 8 epistemic XML sections), GovernedRealityContext/GovernedRealityItem/RealityItemProvenance typed DTOs, deterministic SHA-256 hashing (timestamps excluded), volatility-aware candidate filtering, presentation budget isolation (MAX=6 ≠ Reality Engine budget), rationale_description fully excluded, malformed provenance fails closed, anti-self-reinforcing speech boundary, AST-verified zero mutation call sites. | FROZEN. |
| **Phase 7D.5 CharacterEngine Integration** | 2026-09-23 | 1,281 passed, 1 failure (GC-090 flaky race) + 7 Rust | GC-116–GC-140 (35 tests), ADR-011–ADR-015 | RealityOrchestrationService (full A→J per-turn pipeline), EvidenceClassifier (5 patterns + question guard + no-signal), WorldFactsSelector (lexical relevance, CJK alias matching, max 4 items, PLAUSIBILITY_RULE exclusion), CandidateRepository.get_all_active_candidates() failure contract (CandidateRepositoryUnavailableError), CharacterEngine fail-closed pre-orchestration snapshot fallback. RealityBeliefEngine disconnected. Single mutation authority chain locked. | FROZEN. CJK alias short token policy & legacy 7B.3 retirement deferred to 7D.6. |
| **Phase 7D.6 Pure Structural Boundary & Idempotency Repair** | 2026-09-23 | 1,286 Py + 14 Rust (0 failures, 100% green) | ADR-016, GC-141~144, GC-090 Concurrency Invariant | `WorldFactsSelector` Pure Structural Boundary Contract; `BiographyPromotionService` unified atomic transaction; strictly gated `IntegrityError` replay validation (25/25 concurrent stress passes). | FROZEN. 7B.3 files preserved; runtime path disconnected. |
| **Phase 8A Minimal Epistemic Reality Foundation** | 2026-09-24 | 1,420 Py (134 Phase 8A) | GC-145–GC-170 (26 tests), ADR-017 | Categorical enums, candidate plurality, choice selection margin, atomic batch persistence, zero floats. | FROZEN. |
| **Phase 8B Multi-Timescale Temporal Continuum Engine** | 2026-09-26 | 1,580 Py (160 Phase 8B) | GC-171–GC-195 (25 tests), ADR-018 | Temporal rules, temporal graph DAG, trajectory engine, timeline orchestration coordinator. | FROZEN. |
| **Phase 8C Authoritative Calendar & Longitudinal Time Flow** | 2026-09-26 | 1,646 Py (66 Phase 8C) | GC-196–GC-220 (25 tests), ADR-019 | Authoritative clock, calendar boundary engine, guarded transition engine, milestone lapse engine, longitudinal coordinator. | FROZEN. |
| **Phase 9 Autonomous Reality Verification & Epistemic Trust Gate** | 2026-09-26 | 1,762 Py (116 Phase 9) | GC-221–GC-245 (25 tests), ADR-020 | Verification contracts, consequence policy, observation adapters, source evaluation, verification gateway, evidence reconciler. | FROZEN. |
| **Phase 10 Desktop Companion Voice** | 2026-09-26 | 1,873 Py (111 Phase 10) | GC-246–GC-270 (25 tests), ADR-021 | Voice contracts, prosody engine, TTS/STT services, PTT-only input boundary, decoupled audio caching. | FROZEN. |
| **Phase 11 Live2D Visual Presence & Embodiment Architecture** | 2026-09-27 | 1,977 Py (104 Phase 11) | GC-271–GC-297 (27 tests), ADR-022 | Visual contracts, expression/motion mappers, RMS lip-sync, barge-in latch, gaze damping, micro-saccades, desktop stage. | FROZEN. |
| **Phase 12 Canonical Biography & Longitudinal Memory** | 2026-09-27 | 2,083 Py (106 Phase 12) | GC-298–GC-324 (27 tests), ADR-023 | Biographical ontology, causal explanation graph DAG, autobiographical retrieval, shared history engine, desktop projection. | FROZEN. |
| **Phase 13 Realtime Voice Call & Desktop Product Shell** | 2026-09-27 | 2,168 Py (85 Phase 13) | GC-325–GC-351 (27 tests), ADR-024 | Ephemeral streaming audio conduit, full-duplex low-latency pipeline, client-local hardware barge-in, unified Live2D product shell. | FROZEN. |
| **Phase 14 Autonomous Reality Construction & Adaptive Belief Engine** | 2026-09-27 | 2,329 Py (161 Phase 14) | GC-352–GC-378 (27 tests), ADR-025 | RCL cycle isolation (Lock 2 + 12), constraint evaluation engine (Lock 5), adaptive belief revision (Lock 4 + 11), 3-axis epistemic vocabulary (`CanonicalStatus` × `RecallLevel` × `BeliefMaturity`), velocity cap (D2). | FROZEN. |
| **Phase 15 Social Epistemics & Pragmatic Reality Interpretation** | 2026-09-28 | 2,450 Py (121 Phase 15) | GC-379–GC-398 (20 tests), ADR-026 | SpeechAct dual-track, EpistemicTreatment (`ACCEPT_SOCIAL != Memory Writing`), SocialContradictionArbiter (`Tension != Contradiction != Falsehood`), VerificationDispatcher (Phase 9 bridge), 6 Constitutional Locks. | FROZEN. |
| **Phase 16 Personal Learning, Experience & Interest Development** | 2026-09-29 | 2,568 Py (118 Phase 16) | G01–G80, ADR-027 | "Aevum can be influenced by the user, but cannot be defined by the user." ExperientialRecord contracts, 7-stage growth lifecycle, multi-facet appraisal, anti-sycophancy preference decoupling, `<personal_growth_context>`. | FROZEN. |
| **Phase 17 Character Genesis & Identity Grounding** | 2026-09-30 | 2,610 Py (42 Phase 17) | GC-419–GC-424, ADR-028 | "We are creating a living person, not rolling an RPG stat sheet." 3-tier state isolation (Tier A Blueprint / Tier B Genesis Baseline / Tier C Evolved Reality), single genesis application, wizard vs settings lifecycle separation. | FROZEN. |
| **Phase 18 Conversational Life, CCDF & Conversational Agency** | 2026-10-02 | 2,660 Py (50 Phase 18) | GC-425–GC-436, ADR-029 | Character Conversational Decision Flow (`<internal_decision>` + `<character_speech>`), question rate control ($\le 15\%$), natural bubble cadence, anti-unrequested-justification, bounded friction pushback. | FROZEN. |
| **Phase 19 Prospective Memory, Autonomous Agency & Experiential Continuity** | 2026-10-05 | 2,707 Py (47 Phase 19) | GC-437–GC-454 (18 Golden), ADR-030 | Prospective thread contracts, 10-state lifecycle, Contextual Resonance Engine, Agency of Silence, Epistemic Ladder Gatekeeper (`Intention -> Action -> Experience -> Sustained Evidence -> Preference`), 13 Constitutional Invariants. | FROZEN. |
| **Phase 20 Reality Construction, Epistemic Resilience & Epistemic Revision** | 2026-10-06 | 2,722 Py (15 Phase 20) | GC-455–GC-469, ADR-031 | Construct (Gate 0) -> Resist (Gate 1) -> Revise (Gate 2). Minimal mutation (only contradicted slot updated, zero cascade), traceable provenance lineage in `CharacterRealityRevisionRecord`, 5 Subject Continuity Axioms. | FROZEN. |
| **Phase 21 Autobiographical Reality Stress Testing** | 2026-10-06 | 2,723 Py (12-turn trajectory) | Empirical Benchmark Accepted | Autobiographical Reality Continuity proven; 0 drift across 12 adversarial turns; Known Epistemic Boundary on Reversal (`Dispute != Revocation`). | FROZEN. |
| **Soul Benchmark (Schemes A ~ G) & Conversational Realism** | 2026-10-09 | 2,736 Py | Rules 1~32, AEVUM_SOUL_AND_PROGRESS | Real-world persona injection (USM Penang/KL), dynamic life inference, high-intimacy natural tone, playful banter & teasing, unconditional bias & emotional cushioning, gaming camaraderie & slacking resonance, sticker meme pipeline & instant dispatch. | ACTIVE & VERIFIED. |

---

## 12. Living Architectural Memory & Superseded Handling

> [!IMPORTANT]
> **The Future Work Ledger is a living architectural memory, not a static TODO list.**

1. **Mandatory Ledger Update**: Whenever implementation reveals an unforeseen capability, architectural dependency, newly discovered invariant, or required Golden Test, **this document must be updated before proceeding**.
2. **Superseded Decisions Preservation**: If an established architectural decision is altered:
   - **DO NOT delete or silently overwrite history.**
   - Mark the original item as **`SUPERSEDED`**.
   - Record `Superseded by`, `Reason`, `Date`, and `Migration Implication`.

*Example Record*:
> **`SUPERSEDED` ADR-014 (HIGH Impact Gating)**: Formerly required all `RealityImpact.HIGH` facts to halt for `MANUAL_USER_GATED` confirmation.  
> *Superseded by*: Phase 7D Dual Reality Taxonomy & Orthogonal Authorization Matrix (2026-09-18).  
> *Reason*: Conflated consistency blast radius with user authorization, paralyzing autonomous biography construction.

---

## 13. Phase 16 Completed Architectural Requirement — Autonomous Personal Learning & Interest Development (The Genshin Paradigm)

> [!NOTE]
> **Status**: `IMPLEMENTED & FROZEN 🔒` (Completed under Phase 16 and verified with Golden Suite G01~G80, ADR-027).

### 13.1 North Star Scenario
If the user says they like a game or subject (e.g. *Genshin Impact*) and hopes Aevum can get into it, Aevum must be able to encounter, learn about, explore, experience, and gradually form her **OWN** relationship with it over real calendar time — rather than instantaneously adopting or inheriting the user's preference.

### 13.2 Semantic State Lifecycle
$$\text{UNKNOWN} \longrightarrow \text{EXPOSED} \longrightarrow \text{CURIOUS} \longrightarrow \text{EXPLORING} \longrightarrow \text{FAMILIAR} \longrightarrow \text{PREFERENCE\_FORMING} \longrightarrow \begin{cases} \text{PREFERRED} \\ \text{NEUTRAL} \\ \text{DISLIKED} \end{cases}$$
* These states are internal semantic states, **NOT** canned dialogue templates.

### 13.3 Critical Architectural Distinctions
* User likes Genshin $\ne$ Aevum likes Genshin.
* Aevum knows Genshin $\ne$ Aevum has played Genshin.
* Aevum has played Genshin $\ne$ Aevum likes Genshin.
* Aevum likes Genshin $\ne$ Aevum must continue liking Genshin forever (decay, boredom, shifts over months).
* **$\text{World Knowledge} \ne \text{Personal Experience} \ne \text{Personal Preference} \ne \text{Biography}$**.

### 13.4 Long-Term Progression Architecture
$$\text{World Knowledge} \longrightarrow \text{Personal Exposure} \longrightarrow \text{Personal Learning} \longrightarrow \text{Personal Experience} \longrightarrow \text{Qualia / Preference Formation} \longrightarrow \text{Biographical Memory} \longrightarrow \text{Future Intention}$$
* Week 1: Aevum knows what the game is (`WorldKnowledgeRegistry`), but has zero personal preference.
* Week 2: Aevum has encountered basic concepts and becomes curious.
* Week 4: Aevum develops authentic specific preferences (e.g. enjoys exploration or music, dislikes tedious farming).
* Month 2: Aevum experiences temporary disinterest or stops engaging.
* Month 4: Aevum returns or reflects on it.
* Aevum MUST be permitted to conclude that she does **NOT** like it, even if the user strongly loves it.

### 13.5 Anti-Fabrication Requirement
* Aevum must never claim to have personally experienced something she did not actually experience.
  - *"I know what Spiral Abyss is"* does NOT imply *"I have played Spiral Abyss"*.
  - *"I know Genshin's world and characters"* does NOT imply *"I have personally played Genshin"*.
* If real external/tool-backed interaction is integrated, verified events become autobiographical with structured provenance. Without such integration, the system must not fabricate fictional gameplay feats.

### 13.6 Core Principle
> **"Aevum can be influenced by the user, but she cannot be defined by the user."**

---

## 14. CURRENT NEXT ACTION

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CURRENT NEXT ACTION                                    │
│                                                                                        │
│  Phases 0 ~ 21 & Soul Benchmarks A~G — FULLY IMPLEMENTED & OFFICIALLY FROZEN 🔒       │
│                                                                                        │
│  Phase 22 — Mobile Presence & Cross-Device Sync (Android Companion -> Aevum Alpha)     │
│                                                                                        │
│  1. Mobile Client Architecture (Android App):                                          │
│     - Connect to Aevum Core with full reality, memory, and agency parity.              │
│     - Background sync protocol, lock screen widgets, and Android push notifications.   │
│     - Zero desktop/mobile split in canonical character state.                          │
│                                                                                        │
│  2. Continuous Soul Calibration & Real-world Persona Deepening:                        │
│     - Monitor natural everyday banter, Malaysian cultural nuances (KL/Penang life).    │
│     - Ensure emotional cushioning and gamer camaraderie remain authentic and unforced.  │
│     - Maintain sticker visual rendering and responsive instant-messaging UX.           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```



