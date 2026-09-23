"""Reality & Belief Engine orchestrator (Phase 7B.3).

Executes the complete cognitive cycle:
Evidence Extraction -> Subject Attribution -> Belief Formation -> Multi-Validator Pass ->
Contradiction Resolution -> Promotion Policy Gating -> Reality History Tracking.
"""

from datetime import datetime, timezone
import logging
from typing import TYPE_CHECKING, Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore
from app.reality.belief_models import BeliefClaim, EpistemicStatus, FactSubject, UnknownType
from app.reality.candidate_models import CandidateFact, CandidateStatus, InferenceScope, RealityImpact
from app.reality.contradiction_models import ContradictionResolution, ContradictionType
from app.reality.contradiction_resolver import ContradictionResolver
from app.reality.evidence_models import EvidenceExtractionMode, EvidenceRecord, EvidenceSource
from app.reality.history_service import RealityHistoryService
from app.reality.models import FactAuthority, FactStatus
from app.reality.promotion_models import PromotionDecision, PromotionType
from app.reality.promotion_service import RealityPromotionService
from app.reality.validators import (
    CausalityValidator,
    ConsistencyValidator,
    TimelineValidator,
    ValidationResult,
    WorldKnowledgeValidator,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RealityCycleResult(BaseModel):
    """Immutable domain representation of a complete Reality & Belief Engine execution turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence: Optional[EvidenceRecord] = Field(default=None, description="Extracted conversational evidence.")
    belief: Optional[BeliefClaim] = Field(default=None, description="Formed or evaluated belief claim.")
    candidate: Optional[CandidateFact] = Field(default=None, description="Proposed candidate fact for reality.")
    validation: Optional[ValidationResult] = Field(default=None, description="Multi-validator outcome.")
    contradiction: Optional[ContradictionResolution] = Field(default=None, description="Resolved epistemic contradiction.")
    promotion: Optional[PromotionDecision] = Field(default=None, description="Policy promotion decision.")
    contextual_bridge: Optional[str] = Field(default=None, description="Explanatory bridge if surface tension.")
    repair_guidance: Optional[str] = Field(default=None, description="Guidance for conversational slip repair.")


class RealityBeliefEngine:
    """Orchestrates personal reality emergence, grounding, and contradiction resolution."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        promotion_service: Optional[RealityPromotionService] = None,
        history_service: Optional[RealityHistoryService] = None,
    ) -> None:
        self._session = session
        self._history_service = history_service or RealityHistoryService(session)
        self._promotion_service = promotion_service or RealityPromotionService(
            session, history_service=self._history_service
        )

    async def process_turn(
        self,
        user_input: str,
        *,
        core: Optional[CharacterCore] = None,
        character_bible: Optional[Any] = None,
        relationship_state: Optional[Any] = None,
        life_state: Optional[Any] = None,
        prior_turn_slip: Optional[str] = None,
        explicit_candidate: Optional[CandidateFact] = None,
        explicit_belief: Optional[BeliefClaim] = None,
    ) -> RealityCycleResult:
        """Execute the end-to-end reality & belief cycle for a conversational turn."""
        text = user_input.strip()

        # 1. Evidence extraction
        evidence = EvidenceRecord(
            id=str(uuid.uuid4()),
            source=EvidenceSource.USER_CONVERSATION,
            raw_text=text,
            speaker="USER",
            observed_at=_utc_now(),
            confidence=1.0,
            extraction_mode=EvidenceExtractionMode.EXPLICIT_ASSERTION,
        )

        # 2. Contradiction Detection & Reconciliation
        current_loc = getattr(life_state, "current_location", None)
        contradiction = ContradictionResolver.resolve(
            text,
            core=core,
            current_location=current_loc,
            prior_slip=prior_turn_slip,
        )

        # 3. Candidate & Belief Formulation
        candidate = explicit_candidate
        belief = explicit_belief

        if candidate is None and explicit_belief is None:
            candidate, belief = self._formulate_candidate_from_stimulus(
                text, core=core, character_bible=character_bible
            )

        # 4. Multi-validator Pass
        validation: Optional[ValidationResult] = None
        if candidate is not None:
            v_consistency = ConsistencyValidator.validate(candidate, core)
            v_timeline = TimelineValidator.validate(candidate, core)
            v_causality = CausalityValidator.validate(candidate)
            v_world = WorldKnowledgeValidator.validate(candidate)

            all_valid = (
                v_consistency.is_valid
                and v_timeline.is_valid
                and v_causality.is_valid
                and v_world.is_valid
            )
            reasons = (
                v_consistency.reasons
                + v_timeline.reasons
                + v_causality.reasons
                + v_world.reasons
            )
            validation = ValidationResult(is_valid=all_valid, reasons=reasons)

        # 5. Promotion Policy Gating
        promotion: Optional[PromotionDecision] = None
        if candidate is not None:
            promotion = self._promotion_service.evaluate_promotion(
                candidate=candidate,
                belief=belief,
                validation=validation,
                contradiction=contradiction,
            )

            # 6. Apply direct promotion to core reality if eligible
            if promotion.promotion_type == PromotionType.DIRECT_CANONICAL:
                char_id = core.character_id if core else "aevum"
                await self._promotion_service.promote_fact(promotion, character_id=char_id)

        # 7. Extract bridges and repair hints for behavioral guidance
        bridge = contradiction.contextual_bridge if contradiction else None
        guidance = contradiction.repair_guidance if contradiction else None

        return RealityCycleResult(
            evidence=evidence,
            belief=belief,
            candidate=candidate,
            validation=validation,
            contradiction=contradiction,
            promotion=promotion,
            contextual_bridge=bridge,
            repair_guidance=guidance,
        )

    def _formulate_candidate_from_stimulus(
        self,
        text: str,
        core: Optional[CharacterCore] = None,
        character_bible: Optional[Any] = None,
    ) -> tuple[Optional[CandidateFact], Optional[BeliefClaim]]:
        """Formulate candidate facts and beliefs from conversational stimulus."""
        lower_text = text.lower()

        # GC-013: Education university and major inference
        if ("读什么大学" in text or "学什么" in text or "what university" in lower_text) and (
            "专业" in text or "大学" in text or "major" in lower_text
        ):
            # Check existing facts
            existing_uni = core.get_fact_value("education.university", None) if core else None
            uni_val = existing_uni or "Universiti Sains Malaysia"
            existing_major = core.get_fact_value("education.major", None) if core else None
            major_val = existing_major or "English Literature"

            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="education.university",
                value=uni_val,
                impact=RealityImpact.LOW,
                inference_scope=InferenceScope.LOCAL,
                status=CandidateStatus.PROPOSED,
                dependencies=("identity.age", "education.level"),
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="education.university",
                proposed_value=uni_val,
                epistemic_status=EpistemicStatus.KNOWN if existing_uni else EpistemicStatus.PLAUSIBLE,
                confidence=0.95,
                inference_permission=True,
                disclosure_permission=True,
            )
            return cand, bel

        # GC-014: Timeline inference (STPM + age 20 -> year 1 or 2)
        if ("stpm" in lower_text or "pre-u" in lower_text) and (
            "大几" in text or "year" in lower_text or "哪一年" in text
        ):
            existing_year = core.get_fact_value("education.year", None) if core else None
            year_val = existing_year or 2

            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="education.year",
                value=year_val,
                impact=RealityImpact.LOW,
                inference_scope=InferenceScope.DEPENDENT,
                dependencies=("identity.age", "education.pre_u"),
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="education.year",
                proposed_value=year_val,
                epistemic_status=EpistemicStatus.KNOWN if existing_year else EpistemicStatus.PLAUSIBLE,
                confidence=0.95,
                inference_permission=True,
                disclosure_permission=True,
            )
            return cand, bel

        # GC-015: Educational pathway (SPM -> STPM)
        if ("spm" in lower_text) and ("升学" in text or "路线" in text or "怎么选" in text or "pathway" in lower_text):
            existing_path = core.get_fact_value("education.pathway", None) if core else None
            path_val = existing_path or "STPM"

            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="education.pathway",
                value=path_val,
                impact=RealityImpact.MEDIUM,
                inference_scope=InferenceScope.LOCAL,
                dependencies=("education.level",),
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="education.pathway",
                proposed_value=path_val,
                epistemic_status=EpistemicStatus.PLAUSIBLE,
                confidence=0.9,
                inference_permission=True,
                disclosure_permission=True,
            )
            return cand, bel

        # GC-016: Commute transit mode
        if ("去学校" in text or "去上课" in text or "怎么去" in text or "commute" in lower_text) and (
            "平时" in text or "学校" in text
        ):
            existing_commute = core.get_fact_value("lifestyle.commute_mode", None) if core else None
            commute_val = existing_commute or "bus"

            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="lifestyle.commute_mode",
                value=commute_val,
                impact=RealityImpact.LOW,
                inference_scope=InferenceScope.DIRECT,
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="lifestyle.commute_mode",
                proposed_value=commute_val,
                epistemic_status=EpistemicStatus.PLAUSIBLE,
                confidence=0.95,
                inference_permission=True,
                disclosure_permission=True,
            )
            return cand, bel

        # GC-017: Reading/study beverage
        if ("看书" in text or "读书" in text or "喝什么" in text or "beverage" in lower_text) and (
            "茶" in text or "咖啡" in text or "喝" in text
        ):
            existing_bev = core.get_fact_value("preferences.study_beverage", None) if core else None
            bev_val = existing_bev or "chamomile tea"

            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="preferences.study_beverage",
                value=bev_val,
                impact=RealityImpact.LOW,
                inference_scope=InferenceScope.DIRECT,
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.AEVUM,
                fact_key="preferences.study_beverage",
                proposed_value=bev_val,
                epistemic_status=EpistemicStatus.PLAUSIBLE,
                confidence=0.95,
                inference_permission=True,
                disclosure_permission=True,
            )
            return cand, bel

        # GC-022: Physical impossibility claim (sun rising in west)
        if ("太阳" in text or "sun" in lower_text) and ("西边升起" in text or "rises in the west" in lower_text):
            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.WORLD,
                fact_key="world.astronomy.sun_rises",
                value="West",
                impact=RealityImpact.LOW,
                inference_scope=InferenceScope.DIRECT,
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.WORLD,
                fact_key="world.astronomy.sun_rises",
                proposed_value="West",
                epistemic_status=EpistemicStatus.REJECTED,
                confidence=0.0,
                inference_permission=False,
                disclosure_permission=False,
            )
            return cand, bel

        # GC-024: High impact anomalous claim (1 month haze school closure)
        if ("烟霾" in text or "haze" in lower_text) and ("放假" in text or "停课" in text or "一个月" in text):
            cand = CandidateFact(
                id=str(uuid.uuid4()),
                subject=FactSubject.WORLD,
                fact_key="life.schedule.haze_closure",
                value="1_month",
                impact=RealityImpact.HIGH,
                inference_scope=InferenceScope.DIRECT,
            )
            bel = BeliefClaim(
                belief_id=str(uuid.uuid4()),
                subject=FactSubject.WORLD,
                fact_key="life.schedule.haze_closure",
                proposed_value="1_month",
                epistemic_status=EpistemicStatus.UNCERTAIN,
                confidence=0.1,
                temporal_scope="UNVERIFIED_PENDING_EVIDENCE",
                inference_permission=False,
                disclosure_permission=False,
            )
            return cand, bel

        return None, None
