"""Service managing reality promotion and policy gating (Phase 7B.3).

Evaluates candidate facts and belief claims against impact policies,
anti-snowballing constraints, and validation results to determine whether
they can be promoted into canonical Character Core reality.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.character.core_service import CharacterCoreService

from app.reality.candidate_models import CandidateFact, InferenceScope, RealityImpact
from app.reality.belief_models import BeliefClaim
from app.reality.contradiction_models import ContradictionResolution, ContradictionType
from app.reality.history_service import RealityHistoryService
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.promotion_models import PromotionDecision, PromotionType
from app.reality.validators import ValidationResult

logger = logging.getLogger(__name__)


class RealityPromotionService:
    """Evaluates candidate facts and promotes eligible claims into canonical reality."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        core_service: Optional["CharacterCoreService"] = None,
        history_service: Optional[RealityHistoryService] = None,
    ) -> None:
        self._session = session
        if core_service is not None:
            self._core_service = core_service
        elif session is not None:
            from app.character.core_service import CharacterCoreService
            self._core_service = CharacterCoreService(session)
        else:
            self._core_service = None
        self._history_service = history_service or RealityHistoryService(session)

    def evaluate_promotion(
        self,
        candidate: CandidateFact,
        belief: Optional[BeliefClaim] = None,
        validation: Optional[ValidationResult] = None,
        contradiction: Optional[ContradictionResolution] = None,
    ) -> PromotionDecision:
        """Evaluate whether a candidate fact is eligible for canonical reality promotion."""
        # 1. Contradiction gates
        if contradiction is not None and contradiction.contradiction_type != ContradictionType.NONE:
            if contradiction.contradiction_type == ContradictionType.ANOMALOUS_HIGH_IMPACT:
                return PromotionDecision(
                    fact_key=candidate.fact_key,
                    value=candidate.value,
                    promotion_type=PromotionType.MANUAL_USER_GATED,
                    promotion_score=0.0,
                    authority=FactAuthority.SYSTEM_BASELINE,
                    status=FactStatus.CANDIDATE,
                    rationale="High impact anomalous claim demands verification before reality adoption (GC-024).",
                )
            if contradiction.contradiction_type == ContradictionType.USER_FACTUAL_ERROR:
                return PromotionDecision(
                    fact_key=candidate.fact_key,
                    value=candidate.value,
                    promotion_type=PromotionType.REJECT,
                    promotion_score=0.0,
                    authority=FactAuthority.SYSTEM_BASELINE,
                    status=FactStatus.FALSIFIED,
                    rationale="User factual error rejected from physical reality (GC-022).",
                )
            if contradiction.contradiction_type == ContradictionType.GENUINE_MISSPEAK:
                return PromotionDecision(
                    fact_key=candidate.fact_key,
                    value=candidate.value,
                    promotion_type=PromotionType.REJECT,
                    promotion_score=0.0,
                    authority=FactAuthority.SYSTEM_BASELINE,
                    status=FactStatus.FALSIFIED,
                    rationale="Misspeak rejected from canonical reality (GC-020).",
                )

        # 2. Anti-snowballing boundary: speculative claims can never auto-promote
        if candidate.inference_scope == InferenceScope.SPECULATIVE:
            return PromotionDecision(
                fact_key=candidate.fact_key,
                value=candidate.value,
                promotion_type=PromotionType.REJECT,
                promotion_score=0.15,
                authority=FactAuthority.AEVUM_CANONICAL,
                status=FactStatus.CANDIDATE,
                rationale="Speculative facts cannot be promoted into reality (Anti-Snowballing Boundary).",
            )

        # 3. Multi-validator gate
        passed_validators: list[str] = []
        if validation is not None:
            if not validation.is_valid:
                return PromotionDecision(
                    fact_key=candidate.fact_key,
                    value=candidate.value,
                    promotion_type=PromotionType.REJECT,
                    promotion_score=0.1,
                    authority=FactAuthority.AEVUM_CANONICAL,
                    status=FactStatus.CANDIDATE,
                    rationale=f"Validation failed: {', '.join(validation.reasons)}",
                )
            passed_validators.extend(validation.reasons)

        # 4. Systemic reality impact tier gate
        if candidate.impact in (RealityImpact.HIGH, RealityImpact.VERY_HIGH):
            # High-impact claims (e.g. major life trauma, core family history) require manual gating
            return PromotionDecision(
                fact_key=candidate.fact_key,
                value=candidate.value,
                promotion_type=PromotionType.MANUAL_USER_GATED,
                promotion_score=0.5,
                validators_passed=tuple(passed_validators),
                authority=FactAuthority.USER_CONFIGURED,
                status=FactStatus.CANDIDATE,
                rationale=f"High impact fact ({candidate.impact.value}) requires explicit user gating or confirmation.",
            )

        # 5. Low-impact grounded facts (e.g. study beverage, commute mode)
        if candidate.impact == RealityImpact.LOW:
            conf = belief.confidence if belief is not None else 0.95
            return PromotionDecision(
                fact_key=candidate.fact_key,
                value=candidate.value,
                promotion_type=PromotionType.DIRECT_CANONICAL,
                promotion_score=conf,
                validators_passed=tuple(passed_validators),
                authority=FactAuthority.AEVUM_CANONICAL,
                status=FactStatus.CANONICAL,
                rationale="Grounded low-impact emergent fact promoted directly to canonical reality.",
            )

        # 6. Medium-impact facts (e.g. university pathway, pre-u choice, casual activities)
        if candidate.impact == RealityImpact.MEDIUM:
            if candidate.evidence_count >= 1:
                conf = belief.confidence if belief is not None else 0.90
                return PromotionDecision(
                    fact_key=candidate.fact_key,
                    value=candidate.value,
                    promotion_type=PromotionType.DIRECT_CANONICAL,
                    promotion_score=conf,
                    validators_passed=tuple(passed_validators),
                    authority=FactAuthority.AEVUM_CANONICAL,
                    status=FactStatus.CANONICAL,
                    rationale="Medium-impact candidate promoted to canonical reality after grounding check.",
                )
            return PromotionDecision(
                fact_key=candidate.fact_key,
                value=candidate.value,
                promotion_type=PromotionType.CANDIDATE_ACCUMULATION,
                promotion_score=0.6,
                validators_passed=tuple(passed_validators),
                authority=FactAuthority.AEVUM_CANONICAL,
                status=FactStatus.CANDIDATE,
                rationale="Medium-impact fact accumulating evidence.",
            )

        return PromotionDecision(
            fact_key=candidate.fact_key,
            value=candidate.value,
            promotion_type=PromotionType.CANDIDATE_ACCUMULATION,
            promotion_score=0.5,
            validators_passed=tuple(passed_validators),
            authority=FactAuthority.AEVUM_CANONICAL,
            status=FactStatus.CANDIDATE,
            rationale="Default candidate accumulation pending further evidence.",
        )

    async def promote_fact(
        self,
        decision: PromotionDecision,
        character_id: str = "aevum",
    ) -> Optional[CoreFactItem]:
        """Apply promotion decision to persistent Character Core and append history revision."""
        if decision.promotion_type != PromotionType.DIRECT_CANONICAL:
            return None

        # Record temporal history revision
        await self._history_service.record_revision(
            character_id=character_id,
            fact_key=decision.fact_key,
            value=decision.value,
        )

        if self._core_service is not None:
            # Promote into persistent Character Core facts
            return await self._core_service.set_fact(
                character_id=character_id,
                fact_key=decision.fact_key,
                value=decision.value,
                source=FactSource.AEVUM_INFERRED,
                authority=decision.authority,
                status=decision.status,
                explanation=decision.rationale,
                confidence=decision.promotion_score,
            )

        return None

    async def apply_user_profile_patch(
        self,
        character_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply user profile editor updates seamlessly across reality states (GC-018)."""
        normalized_updates: dict[str, Any] = {}
        for raw_key, value in patch.items():
            key = raw_key
            if raw_key == "age":
                key = "identity.age"
            normalized_updates[key] = value

            # Record temporal revision
            await self._history_service.record_revision(
                character_id=character_id,
                fact_key=key,
                value=value,
            )

            if self._core_service is not None:
                await self._core_service.set_fact(
                    character_id=character_id,
                    fact_key=key,
                    value=value,
                    source=FactSource.USER_CONFIGURED,
                    authority=FactAuthority.USER_CONFIGURED,
                    status=FactStatus.CANONICAL,
                    explanation="User profile editor synchronization",
                )

        return normalized_updates
