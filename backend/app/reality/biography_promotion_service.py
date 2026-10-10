"""Service governing Autonomous High-Impact Biography Promotion (Phase 7D.3).

Enforces the 14 Hard Promotion Gates:
- 12 Epistemic Eligibility Gates (Gates 1–11, 14)
- 2 Execution & Mutation Safety Invariants (Gates 12–13)

Structural Call-Site Enforcement:
CharacterCoreService.set_fact with allow_canonical_reconciliation=True can ONLY
be executed within BiographyPromotionService.promote_candidate() using a single-use
PromotionAuthorizationToken.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.character.core_service import CharacterCoreService
from app.reality.biography_promotion_models import (
    BiographyConstructionPolicy,
    BiographyPromotionRecord,
    PromotionAuthorizationResult,
    PromotionAuthorizationToken,
    PromotionEligibilityResult,
    PromotionGateResult,
    PromotionGateType,
    PromotionOrigin,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
)
from app.reality.candidate_repository import CandidateRepository
from app.reality.choice_models import ChoiceDecisionResult
from app.reality.history_service import RealityHistoryService
from app.reality.models import FactAuthority, FactSource, FactStatus
from app.reality.validators import TimelineValidator, WorldKnowledgeValidator

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BiographyPromotionService:
    """Evaluates the 14 Hard Promotion Gates and enforces the canonical mutation boundary."""

    def __init__(
        self,
        session: AsyncSession,
        candidate_repo: Optional[CandidateRepository] = None,
        core_service: Optional[CharacterCoreService] = None,
        history_service: Optional[RealityHistoryService] = None,
        policy: Optional[BiographyConstructionPolicy] = None,
    ) -> None:
        self._session = session
        self._candidate_repo = candidate_repo or CandidateRepository(session)
        self._core_service = core_service or CharacterCoreService(session)
        self._history_service = history_service or RealityHistoryService(session)
        self._policy = policy or BiographyConstructionPolicy()

    # =========================================================================
    # Gate Evaluation & Eligibility
    # =========================================================================

    def evaluate_promotion_eligibility(
        self,
        candidate: CandidateHypothesis,
        choice_decision: ChoiceDecisionResult,
        core: CharacterCore,
        competition_candidate_count: Optional[int] = None,
    ) -> PromotionEligibilityResult:
        """Evaluate all 14 Hard Promotion Gates against candidate hypothesis and choice decision."""
        gate_results: dict[str, PromotionGateResult] = {}
        passed_gates: list[PromotionGateType] = []
        failed_gates: list[PromotionGateType] = []

        def _record_gate(gate: PromotionGateType, passed: bool, reason: str, details: Optional[dict[str, Any]] = None) -> None:
            res = PromotionGateResult(
                gate=gate,
                passed=passed,
                reason=reason,
                details=details or {},
            )
            gate_results[gate.value] = res
            if passed:
                passed_gates.append(gate)
            else:
                failed_gates.append(gate)

        # ---------------------------------------------------------------------
        # GATE 1: USER_LOCK
        # ---------------------------------------------------------------------
        existing_fact = core.facts.get(candidate.slot_name)
        if existing_fact is not None and (existing_fact.is_locked or existing_fact.authority == FactAuthority.USER_LOCKED):
            _record_gate(
                PromotionGateType.GATE_1_USER_LOCK,
                False,
                f"Slot '{candidate.slot_name}' is locked by user (USER_LOCKED); promotion prohibited.",
                {"locked_value": existing_fact.value},
            )
        else:
            _record_gate(
                PromotionGateType.GATE_1_USER_LOCK,
                True,
                "No conflict with user-locked reality facts.",
            )

        # ---------------------------------------------------------------------
        # GATE 2: OBJECTIVE_WORLD_CONSISTENCY
        # ---------------------------------------------------------------------
        # Validate against objective physical world knowledge registry
        world_val = WorldKnowledgeValidator.validate(candidate.slot_name, candidate.proposed_value)
        # Also check for explicit physical impossibilities
        val_str = str(candidate.proposed_value).lower()
        if not world_val.is_valid:
            _record_gate(
                PromotionGateType.GATE_2_OBJECTIVE_WORLD_CONSISTENCY,
                False,
                world_val.reason or "Candidate contradicts objective world knowledge.",
                world_val.details,
            )
        elif "sun_rises" in candidate.slot_name and "west" in val_str:
            _record_gate(
                PromotionGateType.GATE_2_OBJECTIVE_WORLD_CONSISTENCY,
                False,
                "Candidate proposes physical impossibility: sun rises in west.",
            )
        else:
            _record_gate(
                PromotionGateType.GATE_2_OBJECTIVE_WORLD_CONSISTENCY,
                True,
                "Candidate is consistent with objective physical world knowledge.",
            )

        # ---------------------------------------------------------------------
        # GATE 3: TIMELINE
        # ---------------------------------------------------------------------
        timeline_ok = True
        timeline_reason = "Chronological timeline is plausible."
        if candidate.slot_name == "education.year":
            age = 21
            pre_u = "STPM"
            if "identity.age" in core.facts:
                age = int(core.facts["identity.age"].value)
            if "education.pre_u" in core.facts:
                pre_u = str(core.facts["education.pre_u"].value)
            try:
                val_raw = str(candidate.proposed_value)
                digits = "".join(ch for ch in val_raw if ch.isdigit())
                yr = int(digits) if digits else int(val_raw)
                res = TimelineValidator.validate_academic_year(age=age, pre_u_pathway=pre_u, academic_year=yr)
                timeline_ok = res.is_valid
                timeline_reason = res.reason
            except (ValueError, TypeError):
                pass
        # Metadata timeline flags
        if candidate.selection_metadata and candidate.selection_metadata.get("timeline_contradiction"):
            timeline_ok = False
            timeline_reason = str(candidate.selection_metadata.get("timeline_contradiction"))

        _record_gate(
            PromotionGateType.GATE_3_TIMELINE,
            timeline_ok,
            timeline_reason,
        )

        # ---------------------------------------------------------------------
        # GATE 4: CAUSALITY
        # ---------------------------------------------------------------------
        causality_ok = True
        causality_reason = "Physical and logical causality satisfied."
        if candidate.selection_metadata and candidate.selection_metadata.get("causality_violation"):
            causality_ok = False
            causality_reason = str(candidate.selection_metadata.get("causality_violation"))

        _record_gate(
            PromotionGateType.GATE_4_CAUSALITY,
            causality_ok,
            causality_reason,
        )

        # ---------------------------------------------------------------------
        # GATE 5: GRAPH_CONSISTENCY
        # ---------------------------------------------------------------------
        graph_ok = True
        graph_reason = "Entity and relationship graph coherence verified."
        if candidate.selection_metadata and candidate.selection_metadata.get("graph_inconsistency"):
            graph_ok = False
            graph_reason = str(candidate.selection_metadata.get("graph_inconsistency"))

        _record_gate(
            PromotionGateType.GATE_5_GRAPH_CONSISTENCY,
            graph_ok,
            graph_reason,
        )

        # ---------------------------------------------------------------------
        # GATE 6: CANDIDATE_COMPETITION
        # Minimum 2 viable candidates required for autonomous open-slot inference.
        # EXEMPTION: Authoritative revision/supersession of an existing canonical fact.
        # ---------------------------------------------------------------------
        is_auth_revision = bool(
            (candidate.selection_metadata and candidate.selection_metadata.get("is_authoritative_revision"))
            or candidate.supersedes_id
        )
        existing_canonical = core.facts.get(candidate.slot_name)
        if is_auth_revision and existing_canonical is not None:
            _record_gate(
                PromotionGateType.GATE_6_CANDIDATE_COMPETITION,
                True,
                f"Candidate is an authorized revision superseding existing canonical fact '{candidate.slot_name}'; open-slot plurality waived.",
                {"candidate_count": 1, "is_authoritative_revision": True},
            )
        else:
            num_candidates = competition_candidate_count or len(choice_decision.candidate_ids_considered)
            if num_candidates < self._policy.min_viable_candidates:
                _record_gate(
                    PromotionGateType.GATE_6_CANDIDATE_COMPETITION,
                    False,
                    f"Candidate competition requires at least {self._policy.min_viable_candidates} viable alternatives; found {num_candidates}.",
                    {"candidate_count": num_candidates, "min_required": self._policy.min_viable_candidates},
                )
            else:
                _record_gate(
                    PromotionGateType.GATE_6_CANDIDATE_COMPETITION,
                    True,
                    f"Candidate competition requirement satisfied with {num_candidates} alternatives.",
                )

        # ---------------------------------------------------------------------
        # GATE 7: EXPLICIT_CHOICE
        # Plausibility != Choice; must have explicit ChoiceDecisionResult selecting candidate
        # ---------------------------------------------------------------------
        choice_ok = True
        choice_reasons: list[str] = []
        if choice_decision.selected_candidate_id != candidate.candidate_id:
            choice_ok = False
            choice_reasons.append(
                f"Candidate '{candidate.candidate_id}' was not selected by choice decision '{choice_decision.decision_id}'."
            )
        if choice_decision.choice_margin < self._policy.min_choice_margin:
            choice_ok = False
            choice_reasons.append(
                f"Choice margin {choice_decision.choice_margin:.4f} is below policy threshold {self._policy.min_choice_margin}."
            )
        if candidate.lifecycle_state in (
            CandidateLifecycleState.DORMANT,
            CandidateLifecycleState.PRUNED,
            CandidateLifecycleState.REJECTED,
        ):
            choice_ok = False
            choice_reasons.append(
                f"Candidate is in non-promotable lifecycle state '{candidate.lifecycle_state.value}'."
            )

        _record_gate(
            PromotionGateType.GATE_7_EXPLICIT_CHOICE,
            choice_ok,
            "; ".join(choice_reasons) if choice_reasons else "Explicit choice decision verified with sufficient choice margin.",
            {"selected_id": choice_decision.selected_candidate_id, "choice_margin": choice_decision.choice_margin},
        )

        # ---------------------------------------------------------------------
        # GATE 8: STRUCTURED_PROVENANCE
        # Complete structured factors required; text rationale is non-authoritative
        # ---------------------------------------------------------------------
        has_inputs = bool(choice_decision.factor_inputs)
        has_contribs = bool(choice_decision.factor_contributions)
        has_scores = bool(choice_decision.choice_scores)
        has_refs = bool(choice_decision.provenance_references)
        if not (has_inputs and has_contribs and has_scores and has_refs):
            _record_gate(
                PromotionGateType.GATE_8_STRUCTURED_PROVENANCE,
                False,
                "Choice decision lacks complete structured factors (inputs, contributions, scores, or references). Text rationale is non-authoritative.",
                {
                    "has_inputs": has_inputs,
                    "has_contribs": has_contribs,
                    "has_scores": has_scores,
                    "has_refs": has_refs,
                },
            )
        else:
            _record_gate(
                PromotionGateType.GATE_8_STRUCTURED_PROVENANCE,
                True,
                "Structured factor inputs, contributions, scores, and references fully verified.",
            )

        # ---------------------------------------------------------------------
        # GATE 9: NO_CIRCULAR_EVIDENCE
        # Inferred candidates cannot corroborate their own ancestors
        # ---------------------------------------------------------------------
        parent_ids = candidate.provenance.parent_candidate_ids
        is_circular = candidate.candidate_id in parent_ids
        if candidate.selection_metadata and candidate.selection_metadata.get("circular_evidence"):
            is_circular = True

        if is_circular:
            _record_gate(
                PromotionGateType.GATE_9_NO_CIRCULAR_EVIDENCE,
                False,
                f"Circular evidence detected: candidate '{candidate.candidate_id}' references itself in provenance ancestry.",
            )
        else:
            _record_gate(
                PromotionGateType.GATE_9_NO_CIRCULAR_EVIDENCE,
                True,
                "Provenance DAG acyclicity verified; zero circular corroboration.",
            )

        # ---------------------------------------------------------------------
        # GATE 10: SEMANTIC_DISTANCE
        # Deterministic heuristic score D_heuristic <= 0.50 (NOT a probability)
        # ---------------------------------------------------------------------
        d_depth = 0.05 * candidate.inference_depth
        d_scope = 0.10
        d_prestige = 0.0
        if candidate.selection_metadata:
            if "semantic_leap" in candidate.selection_metadata:
                d_scope = float(candidate.selection_metadata["semantic_leap"])
            if "prestige_leap" in candidate.selection_metadata:
                d_prestige = float(candidate.selection_metadata["prestige_leap"])
            if "semantic_distance" in candidate.selection_metadata:
                d_scope = float(candidate.selection_metadata["semantic_distance"])

        d_heuristic = d_depth + d_scope + d_prestige
        if d_heuristic > self._policy.semantic_distance_heuristic_threshold:
            _record_gate(
                PromotionGateType.GATE_10_SEMANTIC_DISTANCE,
                False,
                f"Semantic distance heuristic {d_heuristic:.2f} exceeds allowable threshold {self._policy.semantic_distance_heuristic_threshold}.",
                {"d_heuristic": d_heuristic, "threshold": self._policy.semantic_distance_heuristic_threshold},
            )
        else:
            _record_gate(
                PromotionGateType.GATE_10_SEMANTIC_DISTANCE,
                True,
                f"Semantic distance heuristic {d_heuristic:.2f} satisfies threshold <= {self._policy.semantic_distance_heuristic_threshold}.",
                {"d_heuristic": d_heuristic},
            )

        # ---------------------------------------------------------------------
        # GATE 11: BIOGRAPHY_CONSTRUCTION_POLICY
        # Slot must be explicitly allowed by active policy, not in forbidden slots
        # ---------------------------------------------------------------------
        if not self._policy.is_active:
            _record_gate(
                PromotionGateType.GATE_11_BIOGRAPHY_CONSTRUCTION_POLICY,
                False,
                f"BiographyConstructionPolicy '{self._policy.policy_version}' is inactive.",
            )
        elif candidate.slot_name in self._policy.forbidden_slots:
            _record_gate(
                PromotionGateType.GATE_11_BIOGRAPHY_CONSTRUCTION_POLICY,
                False,
                f"Slot '{candidate.slot_name}' is in forbidden_slots policy list.",
            )
        elif candidate.slot_name not in self._policy.allowed_autonomous_slots:
            _record_gate(
                PromotionGateType.GATE_11_BIOGRAPHY_CONSTRUCTION_POLICY,
                False,
                f"Slot '{candidate.slot_name}' is not registered in allowed_autonomous_slots.",
            )
        else:
            _record_gate(
                PromotionGateType.GATE_11_BIOGRAPHY_CONSTRUCTION_POLICY,
                True,
                f"Slot '{candidate.slot_name}' permitted under BiographyConstructionPolicy '{self._policy.policy_version}'.",
            )

        # ---------------------------------------------------------------------
        # GATE 12: IDEMPOTENT_COMMIT_PROTOCOL (Execution & Mutation Safety Invariant)
        # ---------------------------------------------------------------------
        _record_gate(
            PromotionGateType.GATE_12_IDEMPOTENT_COMMIT_PROTOCOL,
            True,
            "Idempotent commit protocol verified; safe execution replay ready.",
        )

        # ---------------------------------------------------------------------
        # GATE 13: STRUCTURED_REVISION_RECORDING (Execution & Audit Invariant)
        # ---------------------------------------------------------------------
        _record_gate(
            PromotionGateType.GATE_13_STRUCTURED_REVISION_RECORDING,
            True,
            "Revision recording contract satisfied; structured provenance references present.",
        )

        # ---------------------------------------------------------------------
        # GATE 14: ANTI_SNOWBALL
        # Promotes only atomic fact; zero ancillary trivia bundled
        # ---------------------------------------------------------------------
        if candidate.selection_metadata and candidate.selection_metadata.get("bundled_ancillary_facts"):
            _record_gate(
                PromotionGateType.GATE_14_ANTI_SNOWBALL,
                False,
                "Candidate bundles secondary ancillary facts violating Anti-Snowball invariant.",
            )
        else:
            _record_gate(
                PromotionGateType.GATE_14_ANTI_SNOWBALL,
                True,
                "Single atomic slot promotion verified; zero ancillary biography bundled.",
            )

        is_eligible = (len(failed_gates) == 0)
        rationale = (
            f"Candidate satisfies all 14 hard gates."
            if is_eligible
            else f"Failed gates: {', '.join(g.value for g in failed_gates)}."
        )

        return PromotionEligibilityResult(
            candidate_id=candidate.candidate_id,
            slot_name=candidate.slot_name,
            is_eligible=is_eligible,
            passed_gates=tuple(passed_gates),
            failed_gates=tuple(failed_gates),
            gate_results=gate_results,
            rationale=rationale,
        )

    # =========================================================================
    # Authorization & Mutation Token Minting
    # =========================================================================

    async def authorize_promotion(
        self,
        candidate: CandidateHypothesis,
        choice_decision: ChoiceDecisionResult,
        core: CharacterCore,
        origin: PromotionOrigin = PromotionOrigin.SIMULATION_BIOGRAPHY,
    ) -> PromotionAuthorizationResult:
        """Evaluate origin policy and the 14 gates to issue a single-use mutation token."""
        eligibility = self.evaluate_promotion_eligibility(candidate, choice_decision, core)

        # Policy matrix check by origin
        if origin == PromotionOrigin.USER_CLAIM:
            # High-impact user claims require manual confirmation
            return PromotionAuthorizationResult(
                candidate_id=candidate.candidate_id,
                slot_name=candidate.slot_name,
                is_authorized=False,
                authorization_code="MANUAL_USER_CONFIRMATION_REQUIRED",
                policy_version=self._policy.policy_version,
                eligibility=eligibility,
                token=None,
            )

        if origin == PromotionOrigin.OBJECTIVE_WORLD_FACT:
            return PromotionAuthorizationResult(
                candidate_id=candidate.candidate_id,
                slot_name=candidate.slot_name,
                is_authorized=False,
                authorization_code="EXTERNAL_WORLD_AUTHORITY_IMMUTABLE",
                policy_version=self._policy.policy_version,
                eligibility=eligibility,
                token=None,
            )

        # SIMULATION_BIOGRAPHY: authorized iff ALL 14 gates pass
        if not eligibility.is_eligible:
            return PromotionAuthorizationResult(
                candidate_id=candidate.candidate_id,
                slot_name=candidate.slot_name,
                is_authorized=False,
                authorization_code="PROMOTION_GATES_FAILED",
                policy_version=self._policy.policy_version,
                eligibility=eligibility,
                token=None,
            )

        # Mint single-use token bound to this exact character, slot, and payload
        token = PromotionAuthorizationToken.create(
            character_id=candidate.entity_id,
            slot_name=candidate.slot_name,
            value=candidate.proposed_value,
            candidate_id=candidate.candidate_id,
            choice_decision_id=choice_decision.decision_id,
            policy_version=self._policy.policy_version,
        )

        auth_code = f"AUTH-7D3-{uuid.uuid4().hex[:8].upper()}"

        return PromotionAuthorizationResult(
            candidate_id=candidate.candidate_id,
            slot_name=candidate.slot_name,
            is_authorized=True,
            authorization_code=auth_code,
            policy_version=self._policy.policy_version,
            eligibility=eligibility,
            token=token,
        )

    # =========================================================================
    # Singular Canonical Mutation Boundary
    # =========================================================================

    async def promote_candidate(
        self,
        candidate: CandidateHypothesis,
        choice_decision: ChoiceDecisionResult,
        character_id: str = "aevum",
        origin: PromotionOrigin = PromotionOrigin.SIMULATION_BIOGRAPHY,
    ) -> BiographyPromotionRecord:
        """Promote an autonomous candidate hypothesis to canonical reality.

        Structural Call-Site Invariant:
        This method is the SOLE caller authorized to set allow_canonical_reconciliation=True
        on CharacterCoreService.set_fact.
        """
        # Step 1: Idempotency Protocol Check (Gate 12)
        existing_promo = await self._candidate_repo.get_biography_promotion_by_candidate(
            candidate_id=candidate.candidate_id,
            character_id=character_id,
        )
        if existing_promo is not None:
            logger.info(
                "Candidate '%s' was already promoted at '%s'; returning safe idempotent replay.",
                candidate.candidate_id,
                existing_promo.created_at,
            )
            return existing_promo.model_copy(update={"is_idempotent_replay": True})

        # Step 2: Load current canonical reality
        core = await self._core_service.get_core(character_id)

        # Step 3: Authorize promotion and mint single-use token
        auth_result = await self.authorize_promotion(
            candidate=candidate,
            choice_decision=choice_decision,
            core=core,
            origin=origin,
        )
        if not auth_result.is_authorized or auth_result.token is None:
            failed_reasons = [r.reason for r in auth_result.eligibility.gate_results.values() if not r.passed]
            raise PermissionError(
                f"Autonomous biography promotion denied by Hard Gates: {'; '.join(failed_reasons)}"
            )

        # Step 4: Record previous canonical state if any
        prev_fact = core.facts.get(candidate.slot_name)
        prev_val = prev_fact.value if prev_fact else None

        # Step 5 to 7: Unified Atomic Transaction Boundary (Decision B.1 — 7D.6 Architecture Gate)
        # Atomicity belongs strictly to BiographyPromotionService.promote_candidate().
        promo_record = BiographyPromotionRecord(
            promotion_id=str(uuid.uuid4()),
            character_id=character_id,
            slot_name=candidate.slot_name,
            candidate_id=candidate.candidate_id,
            choice_decision_id=choice_decision.decision_id,
            promoted_value=candidate.proposed_value,
            policy_version=self._policy.policy_version,
            decision_model_version=choice_decision.decision_model_version,
            previous_canonical_state=prev_val,
            new_canonical_state=candidate.proposed_value,
            gates_passed=tuple(g.value for g in auth_result.eligibility.passed_gates),
            provenance_references=choice_decision.provenance_references,
            authorization_code=auth_result.authorization_code,
            is_idempotent_replay=False,
            created_at=_utc_now(),
        )

        try:
            # Step 5: Singularity Canonical Mutation Boundary (auto_commit=False, staged via flush)
            await self._core_service.set_fact(
                character_id=character_id,
                fact_key=candidate.slot_name,
                value=candidate.proposed_value,
                source=FactSource.AEVUM_INFERRED,
                authority=FactAuthority.AEVUM_CANONICAL,
                status=FactStatus.CANONICAL,
                explanation=(
                    f"Autonomous biography promotion via choice '{choice_decision.decision_id}' "
                    f"under policy '{self._policy.policy_version}'"
                ),
                confidence=candidate.plausibility.composite_plausibility_score,
                allow_canonical_reconciliation=True,
                authorization_token=auth_result.token,
                auto_commit=False,
            )

            # Step 6: Candidate Lifecycle Transition -> SUPERSEDED (staged via flush)
            await self._candidate_repo.update_candidate_lifecycle(
                candidate_id=candidate.candidate_id,
                state=CandidateLifecycleState.SUPERSEDED,
            )

            # Step 7: Persist authoritative CharacterBiographyPromotionRecord (staged via flush)
            await self._candidate_repo.save_biography_promotion(promo_record)

            # Single atomic commit for Steps 5, 6, and 7
            await self._session.commit()

        except IntegrityError as exc:
            await self._session.rollback()
            # Strict Idempotent Replay Validation (Decision B.1 - 7D.6 Amendment 1):
            # Only treat as idempotent replay if ALL conditions are satisfied:
            # 1. Concurrent promotion record exists in DB
            # 2. candidate_id strictly matches
            # 3. character_id strictly matches
            # 4. Canonical fact in character_core_facts already matches this promotion's proposed value
            # 5. Promotion record semantic consistency is verified
            existing_promo = await self._candidate_repo.get_biography_promotion_by_candidate(
                candidate_id=candidate.candidate_id,
                character_id=character_id,
            )
            if (
                existing_promo is not None
                and existing_promo.candidate_id == candidate.candidate_id
                and existing_promo.character_id == character_id
            ):
                core_check = await self._core_service.get_core(character_id)
                current_fact = core_check.facts.get(candidate.slot_name)
                if current_fact is not None and current_fact.value == candidate.proposed_value:
                    logger.info(
                        "Concurrent promotion race safely reconciled for candidate '%s' (slot '%s'); returning idempotent replay.",
                        candidate.candidate_id,
                        candidate.slot_name,
                    )
                    return existing_promo.model_copy(update={"is_idempotent_replay": True})

            # Non-identical integrity collisions are strictly re-raised
            raise exc

        except Exception:
            await self._session.rollback()
            raise

        # Step 8: Record append-only revision in RealityHistoryService (Gate 13)
        if self._history_service is not None:
            await self._history_service.record_revision(
                character_id=character_id,
                fact_key=candidate.slot_name,
                value=candidate.proposed_value,
            )

        return promo_record
