# Phase 7D.5 — Integration Map v2
## Architecture Gate Decisions + World-Facts Provider Audit

> **Investigation + Architecture Gate only. No code has been modified.**  
> v2 updated: 2026-09-20  
> Architecture Gate decisions recorded from user review.

---

## 0. Architecture Gate Decisions (All 5 Locked)

| Gate | Decision |
|:---|:---|
| **Q1 — Candidate Generation** | **Included.** Per-turn evidence extraction + classification → `CandidateHypothesis` creation via generation policy. Evidence ≠ Candidate: not every turn creates a candidate; a candidate-generation policy guards the threshold. |
| **Q2 — RealityBeliefEngine** | **Remove from CharacterEngine end-to-end path.** Not parallel dual-running. Dependency is broken at the `CharacterEngine` call site. Old module is NOT physically deleted in 7D.5 — legacy code remains but is no longer called in the governed path. |
| **Q3 — Biography Promotion** | **Synchronous, before response generation.** A promotable candidate promoted in this turn must enter the same turn's `GovernedRealityContext` as canonical. `BiographyPromotionService` remains the sole authority; `CharacterEngine` / orchestration service only coordinates, never bypasses the 7D.3 gate. |
| **Q4 — Contradiction Detection** | **Reuse `ContradictionResolver` as detector / signal producer.** Its output feeds `RealityRepairService` (7D.3) as repair authority. `ContradictionResolver` → signal; `RealityRepairService` → L1–L5 repair decision. `ContradictionResolver` never directly mutates reality. |
| **Q5 — world_facts** | **Deferred: provider semantics audit completed below (§3). Final provider assignment pending your approval before implementation.** |

> [!IMPORTANT]
> **Core Invariant for 7D.5**: `RealityContextBuilder` remains a pure assembly boundary. It must not become a new orchestration god object. Orchestration lives entirely in `RealityOrchestrationService`.

---

## 1. Target Architecture (Post-7D.5)

```
POST /conversations/{id}/messages
    │
    ▼
CharacterEngine.build_response_context()
    │
    ├── (2–7.5) All existing context gathering unchanged
    │   (Definition, State, Relationship, Emotion, Memory, Life, PersonalWorld,
    │    Core, Bible, Ledger, Desire, Contract, SocialIntention, BehaviorPlan)
    │
    ├── (7.6) ~~RealityBeliefEngine.process_turn()~~  ← REMOVED from this path
    │         belief_claim, contradiction_resolution, promotion_decision
    │         fields in CharacterResponseContext remain (not deleted),
    │         but are left None / sourced from orchestration result instead
    │
    └── (7.7) RealityOrchestrationService.run_turn(
                 user_input, character_id, core, session
              )
              │
              ├─ [1] Evidence extraction + classification
              │       → EvidenceGenerationPolicy.should_create_candidate(user_input, core)
              │       → [if yes] CandidateRepository.record_evidence(source_type, cluster_key)
              │       → [if yes] build CandidateHypothesis (GENERATED lifecycle)
              │       → [if yes] CandidateRepository.save_candidate(candidate)
              │
              ├─ [2] Load existing DB candidates
              │       → CandidateRepository.get_all_active_candidates(character_id) [NEW READ METHOD]
              │
              ├─ [3] Per-slot competition
              │       → CandidateCompetitionService.evaluate_competition(hypothesis_set, core)
              │
              ├─ [4] Per-slot choice (if viable candidates exist)
              │       → ChoiceSelectionService.select(competition_result, core, bible)
              │       → CandidateRepository.save_choice_decision(choice)
              │
              ├─ [5] Contradiction detection + Repair
              │       → ContradictionResolver.resolve(user_input, core, ...)  ← signal only
              │       → [if contradiction] RealityRepairService.repair(...)
              │       → repair_result (L1–L5, ephemeral, zero canonical mutation)
              │
              ├─ [6] Biography Promotion (synchronous, pre-response)
              │       → [if choice is PROMOTABLE and 14 gates pass]
              │       → BiographyPromotionService.evaluate_promotion_eligibility(candidate, choice, core)
              │       → [if eligible] BiographyPromotionService.promote_candidate(...)
              │       → Refreshes core (canonical facts updated in DB before context assembly)
              │
              └─ [7] Context Assembly
                      → RealityContextBuilder.build_context(
                           core=core,              ← post-promotion refresh
                           candidates=candidates,
                           choices=choices,
                           repair_result=repair_result,
                           world_facts=world_facts,  ← see §3
                           unverified_user_claims=user_claims,
                           evidence_references=evidence_families,
                           memories=memories,
                        )
                      → GovernedRealityContext (all 8 sections populated)
    │
    └── CharacterResponseContext.governed_reality = GovernedRealityContext
    │
    ▼
ResponseContextAssembler → LLMContext → LLM
```

---

## 2. The Single Governed Reality Path

```
User Input
    │
    ▼
RealityOrchestrationService
    │
    ├─ Evidence        (record EvidenceFamily if factual claim detected)
    ├─ Candidate       (create CandidateHypothesis via generation policy)
    ├─ Competition     (CandidateCompetitionService — pure scoring, no mutation)
    ├─ Choice          (ChoiceSelectionService — SELECTED_BUT_NOT_PROMOTED)
    ├─ Contradiction   (ContradictionResolver — detector/signal only)
    ├─ Repair          (RealityRepairService — L1–L5, ephemeral)
    ├─ Promotion       (BiographyPromotionService — 14 gates, PromotionAuthorizationToken)
    │
    ▼
RealityContextBuilder.build_context()   ← pure assembly, no orchestration
    │
    ▼
GovernedRealityContext (8 epistemic sections)
    │
    ▼
ResponseContextAssembler → LLM
```

> [!IMPORTANT]
> `RealityContextBuilder` receives **only data**. It does NOT call any service, load from DB, or make decisions. This boundary is frozen (7D.4) and must not be widened.

---

## 3. World-Facts Provider Semantics Audit (Q5 Complete)

Three distinct "world knowledge" systems currently exist. They are **not interchangeable**.

### Provider A: `WorldKnowledgeRegistry` (`reality/world_knowledge.py`)

| Attribute | Value |
|:---|:---|
| Authority | **OBJECTIVE_WORLD_FACT** — immutable external reality |
| Lifecycle | **Static / compile-time** — seeded at module load, no DB |
| Contents | Physical facts (sun rises East), geography (USM in Penang), educational priors (STPM duration), game lore (Xianlian = HSR) |
| Kinds | `STATIC_FACT`, `PLAUSIBILITY_RULE`, `ENTITY_RELATION`, `TEMPORAL_RULE` |
| Current usage | Used exclusively by `WorldKnowledgeValidator` during candidate validation. Never entered prompt context. |
| Volatility | `IMMUTABLE_CORE` |
| Semantic scope | **External physical / cultural world — not about Aevum** |

### Provider B: `PersonalWorldService` / `WorldFact` (`world/service.py`, `world/models.py`)

| Attribute | Value |
|:---|:---|
| Authority | **SIMULATED_BIOGRAPHY_FACT** — Aevum's personal preferences and environmental facts |
| Lifecycle | **DB-persisted** (`character_world_facts` table), seeded on first boot |
| Contents | Aevum's personal tastes: music preferences, entertainment, reading, social dislikes, routine dislikes |
| Current usage | Loaded in step 6.7 of `CharacterEngine` via `PersonalWorldService.get_personal_world_context()`, formatted into `<personal_world>` XML block in `prompt_assembler.py` |
| Volatility | `PREFERENCE_INTEREST` or `BIOGRAPHICAL_MAJOR` depending on item |
| Semantic scope | **Aevum's subjective personal world — preferences, tastes, social facts** |

### Provider C: `PersonalWorldService` / `BiographyFact` (`world/models.py`)

| Attribute | Value |
|:---|:---|
| Authority | **USER_LOCKED or AEVUM_CANONICAL** — epistemic directives about what is ESTABLISHED / NONEXISTENT / UNKNOWN / PRIVATE |
| Lifecycle | **DB-persisted** (`character_biography` table) |
| Contents | Romantic history (NONEXISTENT), pets (NONEXISTENT), supernatural powers (NONEXISTENT), family background (ESTABLISHED), ancestry (UNKNOWN) |
| Current usage | Part of `PersonalWorldContext`, rendered via `PersonalWorldContextBuilder.format_context()` into `<personal_world>` + `<epistemic_grounding>` blocks |
| Volatility | `BIOGRAPHICAL_MAJOR` or `IMMUTABLE_CORE` |
| Semantic scope | **Authoritative negative/positive epistemic boundaries about Aevum's life** |

### Semantic Verdict

```
RealityContextBuilder.build_context(world_facts=...)
                 ↑
    Parameter type: dict[str, Any]

Which provider matches this parameter?

Provider A (WorldKnowledgeRegistry):
    ✅ Correct semantic match — it IS "objective world facts"
    ✅ Already tagged as OBJECTIVE_WORLD_FACT in RealityContextBuilder
    ✅ Already used by validators for plausibility checking
    ❌ Never yet piped into RealityContextBuilder.build_context()

Provider B (WorldFact — personal tastes):
    ❌ Wrong semantic match — these are Aevum's subjective preferences,
       NOT objective world facts
    ❌ Already handled separately by PersonalWorldContextBuilder in prompt_assembler
    ❌ Would create duplication if also fed into governed_reality

Provider C (BiographyFact — epistemic directives):
    ❌ Wrong semantic match — these are authoritative epistemic boundaries,
       NOT objective external world facts
    ❌ Already handled by EpistemicResolver + PersonalWorldContextBuilder
```

### Q5 Resolution

> [!IMPORTANT]
> **`world_facts` parameter in `RealityContextBuilder.build_context()` should be populated exclusively from `WorldKnowledgeRegistry` (Provider A).**
>
> Specifically: filter `WorldKnowledgeRegistry._REGISTRY` to `STATIC_FACT` and `ENTITY_RELATION` items that are relevant to the current conversation context. Do NOT feed `PLAUSIBILITY_RULE` items (those are validator heuristics, not prompt facts).
>
> `PersonalWorldContext` (Providers B + C) continues to flow through the existing `PersonalWorldContextBuilder` → `<personal_world>` + `<epistemic_grounding>` path in `prompt_assembler.py`. These paths are independent and must NOT be merged.

### World-Facts Integration Decision

```
WorldKnowledgeRegistry
    │
    │  Filter: STATIC_FACT + ENTITY_RELATION only
    │  Key selection: contextually relevant keys (topic-aware filter)
    │             or: load all STATIC_FACT items (max 4, already capped by MAX_CONTEXT_WORLD_ITEMS=4)
    │
    └─► world_facts: dict[str, Any]  →  RealityContextBuilder.build_context(world_facts=...)
                                         → <objective_world_facts> section in GovernedRealityContext

PersonalWorldService
    │
    └─► PersonalWorldContext  →  PersonalWorldContextBuilder.format_context()
                                 → <personal_world> + <epistemic_grounding> in prompt_assembler.py
                                 (unchanged — this path stays as-is)
```

---

## 4. Candidate Generation Policy (Q1 Detail)

### The Critical Boundary: Evidence ≠ Candidate

Not every user message should create a `CandidateHypothesis`. The generation policy must gate candidate creation.

**Candidate creation threshold criteria (proposed, for plan review):**

| Condition | Creates Candidate? |
|:---|:---:|
| User makes explicit biographical assertion about Aevum (e.g., "你不是在槟城读书吗") | ✅ Yes |
| User's message implies an inferable biographical fact via 1-hop reasoning | ✅ Yes (with `DEPENDENT` inference edge) |
| User asks a question (no assertion) | ❌ No |
| User makes a world-fact claim contradicted by `WorldKnowledgeRegistry.STATIC_FACT` | ✅ Yes, as REJECTED candidate |
| Casual chitchat with no biographical signal | ❌ No |
| `InferenceScope.SPECULATIVE` (multi-hop ungrounded) | ❌ No — budget guard, MANDATORY QUARANTINE |
| Already-canonical fact asserted again | ❌ No — consult core, skip candidate creation |

### Candidate Generation Signal Detection

The existing `ContradictionResolver` does partial stimulus classification. For 7D.5, `RealityOrchestrationService` needs an `EvidenceClassifier` (new, lightweight) that reads user input and outputs:

- `has_biographical_assertion: bool`
- `candidate_slot_name: Optional[str]` — which fact key is being asserted
- `claimed_value: Optional[Any]`
- `inference_scope: InferenceScope`

This classifier can initially reuse pattern matching similar to `RealityBeliefEngine._formulate_candidate_from_stimulus()` (the existing trigger patterns from 7B.3), but wraps it in the 7D.1 `CandidateHypothesis` model instead of `CandidateFact`.

---

## 5. What 7D.5 Does NOT Change (Hard Boundary)

```
✅ FROZEN — not touched in 7D.5:
  character/reality_context_builder.py
  character/reality_context_models.py
  reality/candidate_models.py         (models only — no CandidateLifecycleState changes)
  reality/competition_service.py
  reality/choice_service.py
  reality/choice_models.py
  reality/repair_service.py
  reality/repair_models.py
  reality/biography_promotion_service.py
  reality/biography_promotion_models.py
  character/engine_models.py
  character/prompt_assembler.py

✅ UNCHANGED — not touched in 7D.5:
  world/service.py (PersonalWorldService)
  world/context_builder.py (PersonalWorldContextBuilder)
  world/epistemic_resolver.py
  reality/contradiction_models.py
  api/conversations.py  (no HTTP contract changes)
```

---

## 6. Required Code Changes (Updated)

| Change Type | File | Scope |
|:---|:---|:---|
| **NEW** | `reality/reality_orchestration_service.py` | Per-turn pipeline: evidence → candidate → competition → choice → contradiction/repair → promotion → context assembly |
| **NEW** | `reality/evidence_classifier.py` | Lightweight biographical signal detector (wraps existing trigger patterns in 7D.1 model) |
| **ADD (read-only method only)** | `reality/candidate_repository.py` | `get_all_active_candidates(character_id)` — load all non-terminal candidates across slots in one query |
| **MODIFY (surgical — step 7.6 + 7.7 only)** | `character/engine.py` | Remove step 7.6 `RealityBeliefEngine` call; replace step 7.7 with `RealityOrchestrationService.run_turn()` |
| **NEW** | `tests/test_golden_suite_7d_orchestration.py` | GC-116 ~ GC-122+ |

---

## 7. Risks and Open Items (Updated)

### Risk 1: Candidate Generation Over-triggering ✅ Addressed
Gate defined in §4. Classification policy reviewed before implementation.

### Risk 2: 7B.3 RealityBeliefEngine Overlap ✅ Addressed
Dependency removed from CharacterEngine. Physical module preserved but not called.

### Risk 3: Promotion Timing ✅ Addressed
Synchronous, pre-response. Core refreshed after promotion before context assembly.

### Risk 4: Contradiction Detection Source ✅ Addressed
`ContradictionResolver` = signal/detector. `RealityRepairService` = authority.

### Risk 5: world_facts Provider ✅ Addressed
`WorldKnowledgeRegistry` (STATIC_FACT + ENTITY_RELATION only). Personal world continues via existing path.

### Remaining Open Item

> [!NOTE]
> **Candidate generation scope for 7D.5**: The pattern-matching approach from `RealityBeliefEngine._formulate_candidate_from_stimulus()` covers ~5 known fact patterns. The 7D.5 `EvidenceClassifier` should replicate these patterns (GC-013–GC-017 scenarios) to prove the new pipeline handles them correctly. This is a scope definition question: are these 5 patterns sufficient for 7D.5, or should more patterns be added? Recommend starting with the same 5 patterns + one "no signal" path, and expanding in 7D.6+.

---

## 8. Recommended Implementation Sequence (Updated)

```
Phase 7D.5 Implementation — Step Sequence

Step 1: Add get_all_active_candidates() to CandidateRepository (read-only addition, ~30 lines)
Step 2: Create EvidenceClassifier (wraps existing trigger patterns in 7D.1 models, ~100 lines)
Step 3: Create RealityOrchestrationService with full 7-step pipeline (~300 lines)
Step 4: Modify CharacterEngine steps 7.6 + 7.7 (remove RealityBeliefEngine call; wire orchestration)
Step 5: Wire WorldKnowledgeRegistry → world_facts in RealityOrchestrationService
Step 6: Write Golden Suite 7D.5 (GC-116 ~ GC-122)
Step 7: Full regression (1,247 baseline + new GC tests)
Step 8: Freeze review.
```

---

## 9. Freeze Status After 7D.5

```
Phase 7D.1 — FROZEN  (CandidateHypothesis foundation)
Phase 7D.2 — FROZEN  (Competition & Choice)
Phase 7D.3 — FROZEN  (Reality Repair & Biography Promotion)
Phase 7D.4 — FROZEN  (Prompt Context Assembly)
Phase 7D.5 — [TARGET] Governed Reality End-to-End Integration
```

---

*End of Architecture Gate v2 — Awaiting approval before Implementation Plan.*
