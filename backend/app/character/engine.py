"""Character engine for Aevum Core.

Orchestrates the gathering of character, relational, emotional, and memory state
needed to make a response decision:
User Input
    ↓
CharacterEngine
├── CharacterDefinition
├── CharacterState
├── Relevant Memory Context
├── Relationship Context
└── Emotion Context
    ↓
CharacterResponseContext

Guarantees:
- Read-only orchestration: Zero mutations to CharacterState, CharacterDefinition, RelationshipState, EmotionState, or Memory.
- Pure context assembly: Zero LLM generation, zero prompt execution, zero database writes.
- Deterministic output: Equivalent inputs and domain states always yield equivalent response contexts.
- Explicit failures: Missing or invalid required domain states fail explicitly rather than silently fabricating data.
- Domain encapsulation: Context objects expose no raw database ORM records, SQL objects, version numbers, or retrieval scores.
"""

from collections.abc import Sequence
import logging
from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.models import CharacterDefinition
from app.character.service import CharacterDefinitionService
from app.character.state_models import CharacterState
from app.character.state_service import CharacterStateService
from app.emotion.emotion_models import EmotionState
from app.emotion.service import EmotionService
from app.memory.embedding_provider import EmbeddingProvider
from app.memory.hybrid_retrieval_service import HybridMemoryRetrievalService
from app.memory.models import HybridMemoryResult, HybridMemoryRetrievalQuery, Memory
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState
from app.relationship.service import RelationshipService
from app.life.models import LifeState, LifeEvent, LifeGoalStatus
from app.life.services import LifeService
from app.life.context_builder import LifeContextBuilder
from app.world.models import PersonalWorldContext
from app.world.service import PersonalWorldService
from app.character.appraisal import CharacterAppraisalEngine
from app.character.bible_models import CharacterBible
from app.character.bible_service import CharacterBibleService
from app.character.core_models import CharacterCore
from app.character.core_service import CharacterCoreService
from app.character.reality_context_models import GovernedRealityContext
from app.reality.ledger_models import RealityLedgerProjection
from app.reality.ledger_service import RealityLedgerService
from app.character.desire_models import CharacterDesireState
from app.character.desire_service import DesireEvaluationEngine
from app.relationship.contract_models import RelationshipContract
from app.relationship.contract_evaluator import RelationshipContractEvaluator
from app.character.intention_models import SocialIntention
from app.character.social_intention_service import SocialIntentionService
from app.character.behavior_plan_models import BehaviorDecisionTrace, BehaviorPlan
from app.character.behavior_planner import BehaviorPlanner
from app.reality.belief_models import BeliefClaim
from app.reality.contradiction_models import ContradictionResolution
from app.reality.promotion_models import PromotionDecision
from app.character.conversational_models import (
    CharacterExpressionSignature,
    ConversationalMomentumState,
)
from app.reality.deception_models import CognitiveGrievanceContext
# RealityBeliefEngine (Phase 7B.3) removed from governed path in Phase 7D.5.
# The module is preserved for reference but is no longer called here.
# See: reality_orchestration_service.py for the replacement pipeline.


logger = logging.getLogger(__name__)


class CharacterEngine:
    """Orchestrates gathering domain context for response decision making."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider

    async def build_response_context(
        self,
        user_input: str,
        character_id: str = "aevum",
        user_id: str = "user",
        character_definition: Optional[CharacterDefinition] = None,
        character_state: Optional[CharacterState] = None,
        relationship_state: Optional[RelationshipState] = None,
        emotion_state: Optional[EmotionState] = None,
        memories: Optional[Sequence[Union[HybridMemoryResult, Memory]]] = None,
        life_state: Optional[LifeState] = None,
        recent_events: Optional[Sequence[LifeEvent]] = None,
        personal_world: Optional[PersonalWorldContext] = None,
        core: Optional[CharacterCore] = None,
        bible: Optional[CharacterBible] = None,
        ledger: Optional[RealityLedgerProjection] = None,
        desire: Optional[CharacterDesireState] = None,
        contract: Optional[RelationshipContract] = None,
        social_intention: Optional[SocialIntention] = None,
        behavior_plan: Optional[BehaviorPlan] = None,
        decision_trace: Optional[BehaviorDecisionTrace] = None,
        belief_claim: Optional[BeliefClaim] = None,
        contradiction_resolution: Optional[ContradictionResolution] = None,
        promotion_decision: Optional[PromotionDecision] = None,
        prior_turn_slip: Optional[str] = None,
        override_desire: Optional[str] = None,
        context_notes: Optional[str] = None,
        governed_reality: Optional[GovernedRealityContext] = None,
        conversational_momentum: Optional[ConversationalMomentumState] = None,
        expression_signature: Optional[CharacterExpressionSignature] = None,
        user_country: Optional[str] = None,
        deception_grievance: Optional[CognitiveGrievanceContext] = None,
        elapsed_time_description: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ) -> CharacterResponseContext:
        """Gather all relevant domain contexts into a structured CharacterResponseContext.

        Args:
            user_input: Current user input statement or query.
            character_id: Identifier of the character (default "aevum").
            user_id: Identifier of the user (default "user").
            character_definition: Optional pre-loaded CharacterDefinition.
            character_state: Optional pre-loaded CharacterState.
            relationship_state: Optional pre-loaded RelationshipState.
            emotion_state: Optional pre-loaded EmotionState.
            memories: Optional pre-retrieved memory sequence.

        Returns:
            An immutable CharacterResponseContext.

        Raises:
            ValueError: If user_input is empty or whitespace.
            RuntimeError: If required domain state cannot be loaded due to missing session or missing record.
        """
        # 1. Validate user input
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must not be empty or whitespace.")
        cleaned_user_input = user_input.strip()

        # 2. Character definition context
        if character_definition is None:
            if self._session is None:
                raise RuntimeError("Cannot load character_definition without a database session.")
            char_def_service = CharacterDefinitionService(self._session)
            character_definition = await char_def_service.get_character(character_id)
            if character_definition is None:
                raise RuntimeError(f"Character definition '{character_id}' not found.")

        char_ctx = CharacterDefinitionContext.from_definition(character_definition)

        # 3. Character state context
        if character_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load character_state without a database session.")
            char_state_service = CharacterStateService(self._session)
            character_state = await char_state_service.get_state(character_id)
            if character_state is None:
                raise RuntimeError(f"Character state for '{character_id}' not found.")

        state_ctx = CharacterStateContext.from_state(character_state)

        # 4. Relationship context
        if relationship_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load relationship_state without a database session.")
            rel_service = RelationshipService(self._session)
            relationship_state = await rel_service.get_relationship_state(relationship_id=user_id)
            if relationship_state is None:
                raise RuntimeError(f"Relationship state for user '{user_id}' not found.")

        rel_ctx = RelationshipContextBuilder.build(relationship_state)

        # 5. Emotion context
        if emotion_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load emotion_state without a database session.")
            emotion_service = EmotionService(self._session)
            emotion_state = await emotion_service.get_emotion_state(character_id)
            if emotion_state is None:
                raise RuntimeError(f"Emotion state for '{character_id}' not found.")

        emotion_ctx = CharacterEmotionContext.from_state(emotion_state)

        # 6. Memory context
        if memories is None:
            if self._session is not None:
                try:
                    retrieval_service = HybridMemoryRetrievalService(
                        session=self._session,
                        embedding_provider=self._embedding_provider,
                    )
                    retrieval_res = await retrieval_service.retrieve(
                        HybridMemoryRetrievalQuery(text=cleaned_user_input, limit=5)
                    )
                    memories = retrieval_res.memories
                except Exception as exc:
                    logger.warning("Memory retrieval failed during character engine context building: %s", exc)
                    memories = ()
            else:
                memories = ()

        mem_ctx = CharacterMemoryContext.from_memories(memories)

        # 6.5 Life Context
        if life_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load life_state without a database session.")
            life_service = LifeService(self._session)
            life_state = await life_service.get_life_state(character_id)
            if life_state is None:
                raise RuntimeError(f"Life state for '{character_id}' not found.")
                
        if recent_events is None:
            if self._session is not None:
                life_service = LifeService(self._session)
                recent_events = await life_service.list_events(character_id, limit=3)
            else:
                recent_events = ()

        active_goals = ()
        if self._session is not None:
            try:
                life_service = LifeService(self._session)
                all_goals = await life_service.list_goals(character_id)
                active_goals = tuple(g for g in all_goals if g.status == LifeGoalStatus.ACTIVE)
            except Exception as exc:
                logger.warning("Active goals loading failed: %s", exc)
                active_goals = ()
                
        life_ctx = LifeContextBuilder.build(life_state, recent_events, active_goals)

        # 6.7 Personal World & Epistemic context
        if personal_world is None:
            if self._session is not None:
                try:
                    world_service = PersonalWorldService(self._session)
                    trust_score = (relationship_state.trust * 100.0) if relationship_state else 0.0
                    personal_world = await world_service.get_personal_world_context(
                        character_id=character_id,
                        user_input=cleaned_user_input,
                        trust_score=trust_score,
                    )
                except Exception as exc:
                    logger.warning("Personal world context resolution failed: %s", exc)
                    personal_world = PersonalWorldContext()
            else:
                personal_world = PersonalWorldContext()

        # 6.8 Character Core and Bible Context (Phase 7B.1)
        if core is None:
            if self._session is not None:
                try:
                    core_service = CharacterCoreService(self._session)
                    core = await core_service.get_core(character_id)
                except Exception as exc:
                    logger.warning("Character core loading failed: %s", exc)
                    core = None

        if bible is None:
            bible = CharacterBibleService.get_bible()

        if ledger is None:
            if self._session is not None:
                try:
                    ledger_service = RealityLedgerService(self._session)
                    ledger = await ledger_service.get_ledger(character_id)
                except Exception as exc:
                    logger.warning("Reality ledger loading failed: %s", exc)
                    ledger = None

        # 7. Appraisal & Behavior synthesis
        turn_intention = CharacterAppraisalEngine.appraise(
            user_input=cleaned_user_input,
            character=char_ctx,
            character_state=state_ctx,
            relationship=rel_ctx,
            emotion=emotion_ctx,
            life=life_ctx,
            personal_world=personal_world,
            raw_relationship=relationship_state,
        )
        behavior_ctx = CharacterBehaviorContext.synthesize(
            state=state_ctx,
            emotion=emotion_ctx,
            intention=turn_intention,
        )

        # 7.5 Phase 7B.2: Desire, Relationship Contract, Social Intention & Behavior Planning
        if desire is None:
            desire = DesireEvaluationEngine.evaluate(
                current_activity=state_ctx.current_activity,
                current_location=state_ctx.current_location,
                energy=state_ctx.energy,
                stress=state_ctx.stress,
                social_energy=state_ctx.social_energy,
                loneliness=state_ctx.loneliness,
                mood=state_ctx.mood.value,
                override_desire=override_desire,
                context_notes=context_notes,
            )

        if contract is None:
            contract = RelationshipContractEvaluator.evaluate(
                relationship=relationship_state,
                user_text=cleaned_user_input,
                energy=state_ctx.energy,
            )

        if social_intention is None:
            social_intention = SocialIntentionService.evaluate(
                cleaned_user_input,
                contract=contract,
                desire=desire,
                emotion_type=emotion_ctx.emotion_type.value,
                emotion_intensity=emotion_ctx.intensity,
                context_notes=context_notes,
                core_facts=core.facts if core else None,
            )

        if behavior_plan is None:
            behavior_plan, trace = BehaviorPlanner.plan(
                cleaned_user_input,
                intention=social_intention,
                contract=contract,
                desire=desire,
            )
            if decision_trace is None:
                decision_trace = trace

        # 7.6–7.7 Phase 7D.5: Governed Reality Orchestration
        # Replaces Phase 7B.3 legacy RealityBeliefEngine dependency.
        # INVARIANT: RealityBeliefEngine is NEVER called here or in any fallback path.
        if governed_reality is None and core is not None:
            from app.reality.reality_orchestration_service import RealityOrchestrationService
            orchestration = RealityOrchestrationService(self._session)
            try:
                orch_result = await orchestration.run_turn(
                    user_input=cleaned_user_input,
                    core=core,
                    memories=memories,
                    character_id=character_id,
                    current_location=getattr(life_ctx, "current_location", None)
                    if life_ctx else None,
                    prior_turn_slip=prior_turn_slip,
                    bible=bible,
                )
                governed_reality = orch_result.governed_reality
                # Back-fill legacy context fields for model compatibility (not rendered by assembler)
                if contradiction_resolution is None:
                    contradiction_resolution = orch_result.contradiction
            except Exception as exc:
                # Fail-closed: assemble sparse context from pre-orchestration canonical snapshot.
                # `core` here is the snapshot loaded at step 6.8, before run_turn() was called.
                # This is NOT a rollback — if promotion occurred inside run_turn() before the
                # exception, that promotion remains durable in DB. The next turn will reload
                # the updated canonical state.
                # INVARIANT: RealityBeliefEngine is NEVER called here.
                logger.error(
                    "RealityOrchestrationService.run_turn() failed for character '%s': %s. "
                    "Falling back to sparse canonical context (pre-orchestration snapshot). "
                    "If biography promotion occurred before the failure, it remains durable in DB.",
                    character_id, exc,
                )
                from app.character.reality_context_builder import RealityContextBuilder
                governed_reality = RealityContextBuilder.build_context(
                    character_id=character_id,
                    core=core,      # pre-orchestration canonical snapshot — not a rollback
                    memories=memories,
                )

        # Phase 16.5: Personal Growth Context Assembly (Read-Only)
        personal_growth_xml = None
        try:
            from app.growth.growth_context_adapter import PersonalGrowthContextAdapter
            growth_ctx = await PersonalGrowthContextAdapter.assemble_async(
                session=self._session,
                character_id=character_id,
                salient_topics=[cleaned_user_input],
            )
            personal_growth_xml = growth_ctx.xml_block
        except Exception as exc:
            logger.debug("Personal growth context assembly omitted: %s", exc)

        if expression_signature is None:
            expression_signature = CharacterExpressionSignature()

        if conversational_momentum is None:
            from app.character.momentum_engine import ConversationalMomentumEngine
            conversational_momentum = ConversationalMomentumEngine.update_momentum(
                previous_state=None,
                user_input=cleaned_user_input,
            )

        if user_country is None and self._session:
            try:
                from app.desktop.service import DesktopService
                d_svc = DesktopService(self._session)
                d_rec = await d_svc.get_settings(character_id)
                user_country = getattr(d_rec, "user_country", "MY") or "MY"
            except Exception:
                user_country = "MY"
        elif user_country is None:
            user_country = "MY"

        if deception_grievance is None and self._session:
            try:
                from app.reality.deception_service import DeceptionService
                dec_svc = DeceptionService(self._session)
                deception_grievance = await dec_svc.process_incoming_turn(
                    user_input=cleaned_user_input,
                    character_id=character_id,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.debug("Automatic deception grievance processing skipped: %s", exc)

        sticker_candidates_prompt = None
        if self._session:
            try:
                from app.stickers.service import StickerService
                st_svc = StickerService(self._session)
                emo_type = str(getattr(emotion_ctx, "emotion_type", "neutral"))
                candidates = await st_svc.get_contextual_candidates(
                    current_emotion=emo_type,
                    dialogue_snippet=cleaned_user_input,
                    limit=8,
                )
                if candidates:
                    sticker_candidates_prompt = StickerService.format_candidates_prompt(candidates)
            except Exception as exc:
                logger.debug("Sticker candidate retrieval skipped: %s", exc)

        return CharacterResponseContext(
            user_input=cleaned_user_input,
            character=char_ctx,
            character_state=state_ctx,
            relationship=rel_ctx,
            emotion=emotion_ctx,
            memory=mem_ctx,
            behavior=behavior_ctx,
            life=life_ctx,
            personal_world=personal_world,
            core=core,
            bible=bible,
            ledger=ledger,
            desire=desire,
            contract=contract,
            social_intention=social_intention,
            behavior_plan=behavior_plan,
            decision_trace=decision_trace,
            belief_claim=belief_claim,
            contradiction_resolution=contradiction_resolution,
            promotion_decision=promotion_decision,
            governed_reality=governed_reality,
            personal_growth=personal_growth_xml,
            conversational_momentum=conversational_momentum,
            expression_signature=expression_signature,
            user_country=user_country,
            deception_grievance=deception_grievance,
            elapsed_time_description=elapsed_time_description,
            conversation_summary=conversation_summary,
            sticker_candidates_prompt=sticker_candidates_prompt,
        )

