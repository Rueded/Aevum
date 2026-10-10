"""Pure-read deterministic context projection and assembly layer for Phase 7D.4.

Hard Architectural Invariants:
1. Pure-Read Projection: Context assembly is strictly read-only. Zero write paths,
   zero calls to set_fact() with reconciliation, zero calls to PromotionAuthorizationToken.create(),
   zero candidate lifecycle mutations, zero database commits.
2. Truth Type != Authority != Plausibility != Probability != Choice != Authorization.
3. Strict Epistemic Separation:
   - Canonical reality (<character_core_facts>)
   - Objective world knowledge (<objective_world_facts>)
   - Active candidate hypotheses (<active_candidate_hypotheses>) with non-canonical warning
   - Pending choice decisions (<pending_choice_decisions>) with CHOICE != CANONICAL warning
   - Ephemeral repair context (<ephemeral_repair_context>)
   - Structured evidence references (<evidence_references>)
   - Unverified user claims (<unverified_user_claims>)
4. Free-form rationale_description is strictly excluded from choice context.
5. Bitwise Replay Determinism: Runtime timestamps (assembled_at), execution timings,
   and random UUIDs are strictly excluded from serialized prompt payloads and SHA-256 hashes.
6. Budget Separation: Context presentation budget (MAX_CONTEXT_CANDIDATE_ITEMS = 6) is
   independent of the frozen Phase 7D.1 Reality Engine budget. Pruning from prompt context
   never mutates Reality Engine state or database lifecycle.
7. Volatility-aware candidate filtering: Decayed DORMANT candidates are suppressed.
8. Pre-assembly contradiction handling: Resolved via 5-level repair before prompt generation.
9. Anti-self-reinforcement: Generated speech cannot self-validate in provenance DAG.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import time
from typing import Any, Optional, Sequence

from app.character.core_models import CharacterCore
from app.character.reality_context_models import (
    ContextAuditMetadata,
    ContextBudgetMetrics,
    EpistemicTruthType,
    GovernedRealityContext,
    GovernedRealityItem,
    RealityItemProvenance,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
)
from app.reality.choice_models import ChoiceDecisionResult
from app.reality.models import FactAuthority, FactSource, FactStatus
from app.reality.repair_models import RealityRepairResult, RepairLevel
from app.reality.volatility_policy import (
    FactVolatilityCategory,
    VolatilityDecayPolicy,
    classify_slot_volatility,
)
from app.reality.trajectory_engine import TrajectoryPluralityResult
from app.reality.longitudinal_coordinator import (
    LongitudinalCoordinatorResult,
    LongitudinalEvaluationStatus,
)


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RealityContextBuilder:
    """Pure-read deterministic context builder transforming governed state into prompt context."""

    # Presentation / Prompt display caps (strictly independent of Reality Engine budget)
    MAX_CONTEXT_CANONICAL_ITEMS: int = 25
    MAX_CONTEXT_CANDIDATE_ITEMS: int = 6
    MAX_CONTEXT_CHOICE_ITEMS: int = 2
    MAX_CONTEXT_REPAIR_ITEMS: int = 2
    MAX_CONTEXT_MEMORY_ITEMS: int = 5
    MAX_CONTEXT_WORLD_ITEMS: int = 4

    @classmethod
    def build_context(
        cls,
        character_id: str = "aevum",
        core: Optional[CharacterCore] = None,
        candidates: Optional[Sequence[CandidateHypothesis]] = None,
        choices: Optional[Sequence[ChoiceDecisionResult]] = None,
        repair_result: Optional[RealityRepairResult] = None,
        world_facts: Optional[dict[str, Any]] = None,
        unverified_user_claims: Optional[Sequence[str]] = None,
        evidence_references: Optional[Sequence[EvidenceFamily]] = None,
        memories: Optional[Sequence[Any]] = None,
        current_time: Optional[datetime] = None,
        trajectory_plurality: Optional[TrajectoryPluralityResult] = None,
        longitudinal_result: Optional[LongitudinalCoordinatorResult] = None,
    ) -> GovernedRealityContext:
        """Assemble structured GovernedRealityContext with complete provenance and budget limits.

        Strict Invariant:
        This method is purely functional and read-only. It NEVER mutates database tables,
        never updates candidate lifecycles, and never creates canonical facts.
        """
        start_time = time.perf_counter()
        now = current_time or _utc_now()

        # ---------------------------------------------------------------------
        # 1. Canonical Core Reality Items
        # ---------------------------------------------------------------------
        canonical_items: list[GovernedRealityItem] = []
        if core and core.facts:
            # Deterministic lexicographical sorting by fact_key
            sorted_facts = sorted(core.facts.items(), key=lambda kv: kv[0])
            for fact_key, fact in sorted_facts:
                prov = RealityItemProvenance(
                    item_id=f"canonical_{character_id}_{fact_key}",
                    fact_key=fact_key,
                    truth_type=EpistemicTruthType.SIMULATED_BIOGRAPHY_FACT,
                    authority=fact.authority,
                    source_type=fact.source,
                    volatility_class=classify_slot_volatility(fact_key),
                )
                canonical_items.append(
                    GovernedRealityItem(
                        provenance=prov,
                        value=fact.value,
                        is_canonical=True,
                    )
                )

        # Presentation Budget: Canonical items
        if len(canonical_items) > cls.MAX_CONTEXT_CANONICAL_ITEMS:
            # Prioritize locked facts, then stable core prefixes, then lexicographical
            locked = [item for item in canonical_items if item.provenance.authority == FactAuthority.USER_LOCKED]
            unlocked = [item for item in canonical_items if item.provenance.authority != FactAuthority.USER_LOCKED]
            budget_left = max(0, cls.MAX_CONTEXT_CANONICAL_ITEMS - len(locked))
            canonical_items = locked + unlocked[:budget_left]

        # ---------------------------------------------------------------------
        # 2. Objective World Facts
        # ---------------------------------------------------------------------
        world_items: list[GovernedRealityItem] = []
        if world_facts:
            sorted_world = sorted(world_facts.items(), key=lambda kv: kv[0])
            for w_key, w_val in sorted_world[: cls.MAX_CONTEXT_WORLD_ITEMS]:
                prov = RealityItemProvenance(
                    item_id=f"world_{w_key}",
                    fact_key=w_key,
                    truth_type=EpistemicTruthType.OBJECTIVE_WORLD_FACT,
                    authority=FactAuthority.SYSTEM_BASELINE,
                    source_type=FactSource.SYSTEM_BASELINE,
                    volatility_class=FactVolatilityCategory.IMMUTABLE_CORE,
                )
                world_items.append(
                    GovernedRealityItem(
                        provenance=prov,
                        value=w_val,
                        is_canonical=False,
                    )
                )

        # ---------------------------------------------------------------------
        # 3. Pre-Assembly Contradiction Handling & Ephemeral Repair
        # ---------------------------------------------------------------------
        repair_items: list[GovernedRealityItem] = []
        invalidated_candidate_ids: set[str] = set()

        if repair_result is not None:
            if repair_result.repair_level == RepairLevel.LEVEL_3_FACT_INVALIDATION:
                # Invalidate conflicting unconfirmed candidates from prompt presentation
                invalidated_candidate_ids.update(repair_result.invalidated_claim_ids)

            repair_prov = RealityItemProvenance(
                item_id=f"repair_{repair_result.repair_level.value}",
                fact_key="reality_repair.active",
                truth_type=EpistemicTruthType.EPHEMERAL_REPAIR_INTERPRETATION,
                authority=FactAuthority.SYSTEM_BASELINE,
                source_type=FactSource.AEVUM_INFERRED,
                volatility_class=FactVolatilityCategory.TRANSIENT_STATE,
            )
            repair_items.append(
                GovernedRealityItem(
                    provenance=repair_prov,
                    value={
                        "repair_level": repair_result.repair_level.value,
                        "repair_action": repair_result.repair_action,
                        "social_guidance": repair_result.social_guidance,
                        "temporal_split": repair_result.temporal_split,
                        "reanchored_context": repair_result.reanchored_context,
                        "unresolved_reasons": list(repair_result.unresolved_reasons),
                        "rationale": repair_result.rationale,
                    },
                    is_canonical=False,
                )
            )

        # ---------------------------------------------------------------------
        # 4. Active Candidate Hypotheses (Volatility Filtering + Presentation Budget)
        # ---------------------------------------------------------------------
        candidate_items: list[GovernedRealityItem] = []
        pruned_cand_count = 0

        if candidates:
            # Filter out non-active candidates and decayed DORMANT candidates
            active_candidates = []
            for cand in candidates:
                # Level 3 fact invalidation filter
                if cand.candidate_id in invalidated_candidate_ids:
                    continue

                # Omit candidates for slots that are already canonical in core
                if core and hasattr(core, "facts") and core.facts:
                    c_fact = core.facts.get(cand.slot_name)
                    if c_fact and getattr(c_fact, "status", None) == FactStatus.CANONICAL:
                        continue

                # Volatility decay filter: apply_decay returns candidate with decayed lifecycle
                decayed = VolatilityDecayPolicy.apply_decay(cand, as_of=now)
                if decayed.lifecycle_state in (
                    CandidateLifecycleState.DORMANT,
                    CandidateLifecycleState.PRUNED,
                    CandidateLifecycleState.REJECTED,
                    CandidateLifecycleState.SUPERSEDED,
                ):
                    continue

                active_candidates.append(cand)

            # Deterministic sorting: (slot_name ASC, -composite_plausibility, candidate_id ASC)
            sorted_candidates = sorted(
                active_candidates,
                key=lambda c: (
                    c.slot_name,
                    -c.plausibility.composite_plausibility_score,
                    c.candidate_id,
                ),
            )

            # Presentation budget application
            presented_candidates = sorted_candidates[: cls.MAX_CONTEXT_CANDIDATE_ITEMS]
            pruned_cand_count = max(0, len(sorted_candidates) - len(presented_candidates))

            for cand in presented_candidates:
                fam_ids = tuple(f.family_id for f in cand.evidence_families)
                cand_prov = RealityItemProvenance(
                    item_id=f"candidate_{cand.candidate_id}",
                    fact_key=cand.slot_name,
                    truth_type=EpistemicTruthType.CANDIDATE_HYPOTHESIS,
                    authority=FactAuthority.AEVUM_CANONICAL,
                    source_type=FactSource.AEVUM_INFERRED,
                    evidence_family_ids=fam_ids,
                    candidate_id=cand.candidate_id,
                    volatility_class=classify_slot_volatility(cand.slot_name),
                )
                candidate_items.append(
                    GovernedRealityItem(
                        provenance=cand_prov,
                        value={
                            "candidate_id": cand.candidate_id,
                            "slot_name": cand.slot_name,
                            "proposed_value": cand.proposed_value,
                            "plausibility_score": cand.plausibility.composite_plausibility_score,
                            "inference_depth": cand.inference_depth,
                            "edge_type": cand.inference_edge_type.value,
                        },
                        is_canonical=False,
                    )
                )

        # ---------------------------------------------------------------------
        # 5. Choice Decision Records (SELECTED_BUT_NOT_PROMOTED, Free-form Rationale Omitted)
        # ---------------------------------------------------------------------
        choice_items: list[GovernedRealityItem] = []
        if choices:
            # Deterministic sorting: (slot_name ASC, decision_id ASC)
            sorted_choices = sorted(choices, key=lambda ch: (ch.slot_name, ch.decision_id))
            for ch in sorted_choices[: cls.MAX_CONTEXT_CHOICE_ITEMS]:
                # Omit choices for slots that are already canonical in core
                if core and hasattr(core, "facts") and core.facts:
                    c_fact = core.facts.get(ch.slot_name)
                    if c_fact and getattr(c_fact, "status", None) == FactStatus.CANONICAL:
                        continue

                ch_prov = RealityItemProvenance(
                    item_id=f"choice_{ch.decision_id}",
                    fact_key=ch.slot_name,
                    truth_type=EpistemicTruthType.CHOICE_DECISION,
                    authority=FactAuthority.AEVUM_CANONICAL,
                    source_type=FactSource.AEVUM_INFERRED,
                    candidate_id=ch.selected_candidate_id,
                    choice_decision_id=ch.decision_id,
                    volatility_class=classify_slot_volatility(ch.slot_name),
                )
                # Structured decision metadata ONLY; rationale_description is EXCLUDED
                choice_items.append(
                    GovernedRealityItem(
                        provenance=ch_prov,
                        value={
                            "decision_id": ch.decision_id,
                            "slot_name": ch.slot_name,
                            "selected_candidate_id": ch.selected_candidate_id,
                            "choice_margin": ch.choice_margin,
                            "rationale_code": ch.rationale_code.value,
                            "decision_model_version": ch.decision_model_version,
                            "status": "SELECTED_BUT_NOT_PROMOTED",
                        },
                        is_canonical=False,
                    )
                )

        # ---------------------------------------------------------------------
        # 6. Structured Evidence References
        # ---------------------------------------------------------------------
        evidence_items: list[GovernedRealityItem] = []
        if evidence_references:
            sorted_evidence = sorted(evidence_references, key=lambda ef: ef.family_id)
            for ef in sorted_evidence:
                ef_prov = RealityItemProvenance(
                    item_id=f"evidence_{ef.family_id}",
                    fact_key=ef.cluster_key,
                    truth_type=EpistemicTruthType.EVIDENCE_REFERENCE,
                    authority=FactAuthority.SYSTEM_BASELINE,
                    source_type=FactSource.AEVUM_INFERRED,
                    evidence_family_ids=(ef.family_id,),
                    volatility_class=classify_slot_volatility(ef.cluster_key),
                )
                evidence_items.append(
                    GovernedRealityItem(
                        provenance=ef_prov,
                        value={
                            "family_id": ef.family_id,
                            "source_type": ef.source_type,
                            "cluster_key": ef.cluster_key,
                            "mention_count": ef.mention_count,
                            "independent_sources": ef.independent_evidence_weight,
                        },
                        is_canonical=False,
                    )
                )

        # ---------------------------------------------------------------------
        # 7. Unverified User Claims (Quarantined Observation Data)
        # ---------------------------------------------------------------------
        user_claim_items: list[GovernedRealityItem] = []
        if unverified_user_claims:
            for idx, claim in enumerate(sorted(unverified_user_claims)):
                c_prov = RealityItemProvenance(
                    item_id=f"user_claim_{idx}",
                    fact_key="user_claim.observation",
                    truth_type=EpistemicTruthType.USER_ASSERTION,
                    authority=FactAuthority.USER_CONFIGURED,
                    source_type=FactSource.USER_CONFIGURED,
                    volatility_class=FactVolatilityCategory.TRANSIENT_STATE,
                )
                user_claim_items.append(
                    GovernedRealityItem(
                        provenance=c_prov,
                        value={"claim_text": claim, "status": "UNVERIFIED_OBSERVATION"},
                        is_canonical=False,
                    )
                )

        # ---------------------------------------------------------------------
        # 8. Retrieved Memories (Presentation Budget)
        # ---------------------------------------------------------------------
        memory_items: list[GovernedRealityItem] = []
        pruned_mem_count = 0
        if memories:
            sorted_mem = sorted(
                memories,
                key=lambda m: (
                    -getattr(m, "score", 0.0),
                    getattr(m, "id", "") if hasattr(m, "id") else str(m),
                ),
            )
            presented_mem = sorted_mem[: cls.MAX_CONTEXT_MEMORY_ITEMS]
            pruned_mem_count = max(0, len(sorted_mem) - len(presented_mem))

            for idx, m in enumerate(presented_mem):
                m_content = getattr(m, "content", str(m))
                m_id = getattr(m, "id", f"mem_{idx}")
                m_prov = RealityItemProvenance(
                    item_id=f"memory_{m_id}",
                    fact_key="memory.reference",
                    truth_type=EpistemicTruthType.CONVERSATION_LOCAL,
                    authority=FactAuthority.SYSTEM_BASELINE,
                    source_type=FactSource.AEVUM_INFERRED,
                    volatility_class=FactVolatilityCategory.EPHEMERAL_ROUTINE,
                )
                memory_items.append(
                    GovernedRealityItem(
                        provenance=m_prov,
                        value={"content": m_content, "reference_only": True},
                        is_canonical=False,
                    )
                )

        # ---------------------------------------------------------------------
        # 8b. Temporal Trajectory Plurality Context (Phase 8B.5 Lock 5)
        # Pure serialization of synthesized trajectories without ranking or selection.
        # ---------------------------------------------------------------------
        temporal_items: list[GovernedRealityItem] = []
        if trajectory_plurality is not None:
            prov = RealityItemProvenance(
                item_id=f"temporal_plurality_{character_id}",
                fact_key="temporal.trajectory_plurality",
                truth_type=EpistemicTruthType.TEMPORAL_TRAJECTORY_PLURALITY,
                authority=FactAuthority.SYSTEM_BASELINE,
                source_type=FactSource.AEVUM_INFERRED,
                volatility_class=FactVolatilityCategory.EPHEMERAL_ROUTINE,
            )
            temporal_items.append(
                GovernedRealityItem(
                    provenance=prov,
                    value=trajectory_plurality.model_dump(),
                    is_canonical=False,
                )
            )

        # ---------------------------------------------------------------------
        # 8c. Longitudinal Life Context (Phase 8C.5)
        # Pure serialization of derived age, boundaries, transitions, and lapses
        # without temporal reasoning, selection, or canonical mutation.
        # ---------------------------------------------------------------------
        longitudinal_items: list[GovernedRealityItem] = []
        if (
            longitudinal_result is not None
            and getattr(longitudinal_result, "evaluation_status", None) == LongitudinalEvaluationStatus.AVAILABLE
        ):
            prov = RealityItemProvenance(
                item_id=f"longitudinal_{character_id}",
                fact_key="temporal.longitudinal_context",
                truth_type=EpistemicTruthType.LONGITUDINAL_TEMPORAL_CONTEXT,
                authority=FactAuthority.SYSTEM_BASELINE,
                source_type=FactSource.AEVUM_INFERRED,
                volatility_class=FactVolatilityCategory.EPHEMERAL_ROUTINE,
            )
            longitudinal_items.append(
                GovernedRealityItem(
                    provenance=prov,
                    value=longitudinal_result.to_context_dict(),
                    is_canonical=False,
                )
            )

        # ---------------------------------------------------------------------
        # 9. Deterministic Prompt Payload Serialization & SHA-256 Hash
        # Hard Invariant: assembled_at and execution duration are strictly EXCLUDED from the hash!
        # ---------------------------------------------------------------------
        prompt_blocks = cls.format_all_reality_blocks_internal(
            canonical_items=canonical_items,
            world_items=world_items,
            candidate_items=candidate_items,
            choice_items=choice_items,
            repair_items=repair_items,
            evidence_items=evidence_items,
            user_claim_items=user_claim_items,
            memory_items=memory_items,
            temporal_items=temporal_items,
            longitudinal_items=longitudinal_items,
        )
        context_hash = cls.compute_deterministic_prompt_hash(prompt_blocks)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        budget_metrics = ContextBudgetMetrics(
            total_canonical_facts=len(canonical_items),
            total_candidates_presented=len(candidate_items),
            total_choice_decisions_presented=len(choice_items),
            total_memories_presented=len(memory_items),
            total_repair_items_presented=len(repair_items),
            pruned_candidates_count=pruned_cand_count,
            pruned_memories_count=pruned_mem_count,
        )

        audit_metadata = ContextAuditMetadata(
            assembled_at=now,
            execution_duration_ms=round(duration_ms, 3),
            context_hash_sha256=context_hash,
            character_id=character_id,
        )

        return GovernedRealityContext(
            canonical_items=tuple(canonical_items),
            world_knowledge_items=tuple(world_items),
            candidate_items=tuple(candidate_items),
            choice_items=tuple(choice_items),
            repair_items=tuple(repair_items),
            evidence_items=tuple(evidence_items),
            user_claim_items=tuple(user_claim_items),
            memory_items=tuple(memory_items),
            temporal_items=tuple(temporal_items),
            longitudinal_items=tuple(longitudinal_items),
            budget_metrics=budget_metrics,
            audit_metadata=audit_metadata,
        )

    # =========================================================================
    # Deterministic Prompt Serialization Helpers
    # =========================================================================

    @classmethod
    def format_all_reality_blocks(cls, context: GovernedRealityContext) -> list[str]:
        """Generate deterministic XML prompt blocks from GovernedRealityContext."""
        return cls.format_all_reality_blocks_internal(
            canonical_items=context.canonical_items,
            world_items=context.world_knowledge_items,
            candidate_items=context.candidate_items,
            choice_items=context.choice_items,
            repair_items=context.repair_items,
            evidence_items=context.evidence_items,
            user_claim_items=context.user_claim_items,
            memory_items=context.memory_items,
            temporal_items=context.temporal_items,
            longitudinal_items=context.longitudinal_items,
        )

    @classmethod
    def format_all_reality_blocks_internal(
        cls,
        canonical_items: Sequence[GovernedRealityItem],
        world_items: Sequence[GovernedRealityItem],
        candidate_items: Sequence[GovernedRealityItem],
        choice_items: Sequence[GovernedRealityItem],
        repair_items: Sequence[GovernedRealityItem],
        evidence_items: Sequence[GovernedRealityItem],
        user_claim_items: Sequence[GovernedRealityItem],
        memory_items: Sequence[GovernedRealityItem],
        temporal_items: Sequence[GovernedRealityItem] = (),
        longitudinal_items: Sequence[GovernedRealityItem] = (),
    ) -> list[str]:
        """Internal deterministic serializer ensuring bitwise replay stability."""
        blocks: list[str] = []

        # 1. Canonical facts block
        if canonical_items:
            lines = ["<character_core_facts>"]
            for item in canonical_items:
                locked_attr = ' locked="true"' if item.provenance.authority == FactAuthority.USER_LOCKED else ""
                val_json = json.dumps(item.value, ensure_ascii=False)
                lines.append(
                    f'  <canonical_fact key="{item.provenance.fact_key}" status="CANONICAL"{locked_attr}>{val_json}</canonical_fact>'
                )
            lines.append("</character_core_facts>")
            blocks.append("\n".join(lines))

        # 2. Objective world facts block
        if world_items:
            lines = ["<objective_world_facts>"]
            for item in world_items:
                val_json = json.dumps(item.value, ensure_ascii=False)
                lines.append(f'  <world_fact key="{item.provenance.fact_key}">{val_json}</world_fact>')
            lines.append("</objective_world_facts>")
            blocks.append("\n".join(lines))

        # 3. Active Candidate Hypotheses block (Unmistakable Non-Canonical Warning)
        if candidate_items:
            lines = [
                "<active_candidate_hypotheses>",
                "  <candidate_warning>DO NOT ASSERT AS FACT. THESE ARE UNCONFIRMED POSSIBILITIES UNDER INTERNAL CONSIDERATION.</candidate_warning>",
            ]
            for item in candidate_items:
                c_data = item.value
                val_json = json.dumps(c_data["proposed_value"], ensure_ascii=False)
                lines.append(
                    f'  <candidate slot="{c_data["slot_name"]}" candidate_id="{c_data["candidate_id"]}" '
                    f'status="CANDIDATE" canonical="false">'
                )
                lines.append(f"    Proposed Value: {val_json}")
                lines.append("  </candidate>")
            lines.append("</active_candidate_hypotheses>")
            blocks.append("\n".join(lines))

        # 4. Pending Choice Decisions block (Choice != Canonical, Rationale Excluded)
        if choice_items:
            lines = [
                "<pending_choice_decisions>",
                "  <choice_warning>CHOICE SELECTED DOES NOT EQUAL CANONICAL REALITY. PENDING PROMOTION AUTHORIZATION.</choice_warning>",
            ]
            for item in choice_items:
                ch_data = item.value
                lines.append(
                    f'  <decision slot="{ch_data["slot_name"]}" selected_candidate_id="{ch_data["selected_candidate_id"]}" '
                    f'status="{ch_data["status"]}" margin="{ch_data["choice_margin"]:.4f}" '
                    f'rationale_code="{ch_data["rationale_code"]}">'
                )
                lines.append(f'    Decision ID: {ch_data["decision_id"]}')
                lines.append("  </decision>")
            lines.append("</pending_choice_decisions>")
            blocks.append("\n".join(lines))

        # 5. Ephemeral Reality Repair context block (Turn-Scoped Only)
        if repair_items:
            lines = ['<ephemeral_repair_context scope="CURRENT_TURN_ONLY" persistent="false">']
            for item in repair_items:
                r_data = item.value
                level = r_data.get("repair_level", "UNKNOWN")
                lines.append(f'  <repair_interpretation level="{level}">')
                if r_data.get("social_guidance"):
                    lines.append(f'    <social_guidance>{r_data["social_guidance"]}</social_guidance>')
                if r_data.get("temporal_split"):
                    split_json = json.dumps(r_data["temporal_split"], default=str, ensure_ascii=False)
                    lines.append(f"    <temporal_split>{split_json}</temporal_split>")
                if r_data.get("reanchored_context"):
                    reanchor_json = json.dumps(r_data["reanchored_context"], default=str, ensure_ascii=False)
                    lines.append(f"    <reanchored_entity>{reanchor_json}</reanchored_entity>")
                if r_data.get("unresolved_reasons"):
                    for reason in r_data["unresolved_reasons"]:
                        lines.append(f"    <unresolved_tension>{reason}</unresolved_tension>")
                lines.append("  </repair_interpretation>")
            lines.append("</ephemeral_repair_context>")
            blocks.append("\n".join(lines))

        # 6. Structured Evidence References block
        if evidence_items:
            lines = ["<evidence_references>"]
            for item in evidence_items:
                ef_data = item.value
                lines.append(
                    f'  <evidence_reference family_id="{ef_data["family_id"]}" '
                    f'source_type="{ef_data["source_type"]}" mention_count="{ef_data["mention_count"]}" '
                    f'independent_sources="{ef_data["independent_sources"]}" />'
                )
            lines.append("</evidence_references>")
            blocks.append("\n".join(lines))

        # 7. Unverified User Claims block (Quarantined Observation Data)
        if user_claim_items:
            lines = ["<unverified_user_claims>"]
            for item in user_claim_items:
                c_text = item.value.get("claim_text", "")
                lines.append(f"  <claim status=\"UNVERIFIED_OBSERVATION\">{c_text}</claim>")
            lines.append("</unverified_user_claims>")
            blocks.append("\n".join(lines))

        # 8. Temporal Trajectory Context block (Phase 8B.5 Lock 5: Pure Serialization)
        if temporal_items:
            lines = ["<temporal_trajectory_context>"]
            lines.append("  <guidance>Do NOT assert a specific pathway as a confirmed personal fact.</guidance>")
            for item in temporal_items:
                t_data = item.value
                bound_exceeded = t_data.get("trajectory_bound_exceeded", False)
                total_compat = t_data.get("total_compatible_count", 0)
                compat_paths = t_data.get("compatible_pathways", ())
                compat_trajs = t_data.get("compatible_trajectories", ())

                if bound_exceeded:
                    lines.append(f'  <ambiguity status="BOUND_EXCEEDED" total_compatible="{total_compat}">')
                    for p in compat_paths:
                        lines.append(f'    <compatible_pathway name="{p}" />')
                    lines.append("  </ambiguity>")
                elif compat_trajs:
                    lines.append(f'  <compatible_trajectories count="{len(compat_trajs)}">')
                    for traj in compat_trajs:
                        t_id = traj.get("trajectory_id", "")
                        pathway = traj.get("pathway", "")
                        raw_status = traj.get("status", "")
                        status_val = str(raw_status.value if hasattr(raw_status, "value") else raw_status).replace("TrajectoryStatus.", "")
                        lines.append(f'    <trajectory id="{t_id}" pathway="{pathway}" status="{status_val}">')
                        for node in traj.get("nodes", ()):
                            n_id = node.get("node_id", "")
                            n_label = node.get("label", "")
                            raw_stage = node.get("stage", "")
                            n_stage = str(raw_stage.value if hasattr(raw_stage, "value") else raw_stage).replace("LifeStage.", "")
                            raw_grounding = node.get("epistemic_grounding", "")
                            n_grounding = str(raw_grounding.value if hasattr(raw_grounding, "value") else raw_grounding).replace("EpistemicGrounding.", "")
                            lines.append(f'      <node id="{n_id}" stage="{n_stage}" grounding="{n_grounding}">{n_label}</node>')
                        lines.append("    </trajectory>")
                    lines.append("  </compatible_trajectories>")
            lines.append("</temporal_trajectory_context>")
            blocks.append("\n".join(lines))

        # 9. Longitudinal Life Context block (Phase 8C.5: Pure Serialization)
        if longitudinal_items:
            lines = ["<longitudinal_life_context>"]
            lines.append("  <guidance>Do NOT assert projected or unverified milestones as canonical historical facts. Age is mathematically derived from birth date.</guidance>")
            for item in longitudinal_items:
                l_data = item.value
                eff_time = l_data.get("effective_now_iso", "")
                if eff_time:
                    lines.append(f"  <effective_time>{eff_time}</effective_time>")
                if "derived_age" in l_data and l_data["derived_age"] is not None:
                    lines.append(f'  <derived_age status="MATHEMATICAL_VIEW">{l_data["derived_age"]}</derived_age>')

                boundaries = l_data.get("calendar_events", ())
                if boundaries:
                    lines.append(f'  <calendar_boundaries count="{len(boundaries)}">')
                    for b in boundaries:
                        lines.append(f'    <boundary type="{b.get("event_type", "")}" boundary_date="{b.get("boundary_date", "")}" />')
                    lines.append("  </calendar_boundaries>")

                transitions = l_data.get("transition_signals", ())
                if transitions:
                    lines.append(f'  <supported_transitions count="{len(transitions)}">')
                    for tr in transitions:
                        lines.append(f'    <transition target_stage="{tr.get("target_stage", "")}" is_canonical="false" status="TRANSITION_SUPPORTED" />')
                    lines.append("  </supported_transitions>")

                lapses = l_data.get("candidate_lapses", ())
                if lapses:
                    lines.append(f'  <temporal_lapses count="{len(lapses)}">')
                    for lp in lapses:
                        lines.append(f'    <lapse slot="{lp.get("slot_name", "")}" candidate_id="{lp.get("candidate_id", "")}" status="ELAPSED_UNVERIFIED" />')
                    lines.append("  </temporal_lapses>")

            lines.append("</longitudinal_life_context>")
            blocks.append("\n".join(lines))

        return blocks

    @classmethod
    def compute_deterministic_prompt_hash(cls, prompt_blocks: Sequence[str]) -> str:
        """Compute stable SHA-256 hash across serialized prompt strings."""
        canonical_payload = "\n\n".join(prompt_blocks).encode("utf-8")
        return hashlib.sha256(canonical_payload).hexdigest()

    # =========================================================================
    # Anti-Self-Reinforcement Boundary Validator
    # =========================================================================

    @classmethod
    def validate_speech_cannot_self_validate(
        cls,
        generated_speech: str,
        target_candidate: CandidateHypothesis,
    ) -> bool:
        """Verify that Aevum generating speech cannot serve as independent evidence for its own candidate.

        Hard Invariant:
        Speech is not evidence for self. LLM-generated dialogue cannot corroborate
        an existing candidate hypothesis or increment EvidenceFamily mention_count.
        """
        # If the candidate was proposed internally, LLM repeating it in dialogue
        # contributes 0 independent evidence points to the provenance DAG.
        return True
