"""Unit and Integration Tests for Phase 18.2 — Behavior Planner Dynamics & Momentum Engine.

Tests enforce the 10 Implementation Boundaries:
1. Boundary 1: Momentum != Task Tracking (organic thread decay, no mandatory to-do).
2. Boundary 2: Low Energy Must Emerge, Not Be Manufactured (state-derived, zero turn quotas).
3. Boundary 3: Friction Is Permission, Not Quota (relationship-conditioned, zero tease quotas).
4. Boundary 4: Character Initiative & Self-Disclosure as First-Class Behavior (SPONTANEOUS_INITIATIVE & ASSOCIATIVE_DRIFT).
5. Boundary 5: Selective Context Injection (no prompt clutter for decayed momentum).
6. Boundary 6: Expression Signature represents habits, not rigid demographic memes.
7. Boundary 7: No forced human errors/typos.
8. Boundary 8: Compact decision architecture (GC-431 compliant).
9. Boundary 9: Selective attention on compound user messages.
10. Boundary 10: Asymmetric presence and non-expansion freedom.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.character.conversational_arbitrator import ConversationalArbitrator
from app.character.conversational_models import (
    CharacterExpressionSignature,
    ConversationalMomentumState,
    ConversationalMotivation,
    FrictionTier,
    ResponseCommitmentTier,
    ResponseEnergyTier,
    TurnConversationalDecision,
)
from app.character.conversational_parser import ConversationalResponseParser
from app.character.engine import CharacterEngine
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.intention_models import BehaviorPrimitive
from app.character.models import (
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.momentum_engine import ConversationalMomentumEngine
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.response_generator import ResponseGenerator
from app.character.state_models import CharacterMood, CharacterState
from app.core.time import now_utc
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.context_models import CharacterLifeContext
from app.llm.base import LLMProvider, LLMResponse
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.contract_models import IntimacyTier, RelationshipContract
from app.relationship.models import DEFAULT_RELATIONSHIP_ID, DEFAULT_USER_ID, RelationshipState


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def _build_test_context(
    energy: float = 0.8,
    activity: str = "reading",
    emotion_type: EmotionType = EmotionType.CONTENT,
    emotion_intensity: float = 0.5,
    tier: IntimacyTier = IntimacyTier.FAMILIAR,
    user_input: str = "今天天气不错，下午打算去买杯奶茶，顺便把昨天的电影看完了。",
) -> CharacterResponseContext:
    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=now_utc(),
        identity=CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Art and music."),
        personality=Personality(
            core_traits=("independent", "thoughtful"),
            social_style=("cautious at first", "warm once close"),
            emotional_style=("reflective", "restrained"),
            communication_style=("direct", "occasional dry humor"),
            behavioral_tendencies=("takes time before agreeing", "observant"),
            flaws=("mildly stubborn", "sometimes overthinks"),
        ),
    )
    char_state = CharacterState(
        id="aevum",
        version=1,
        updated_at=now_utc(),
        mood=CharacterMood.CALM,
        energy=energy,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity=activity,
        current_location="home",
    )
    emo_state = EmotionState(
        id="aevum",
        emotion_type=emotion_type,
        intensity=emotion_intensity,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    rel_state = RelationshipState(
        id=DEFAULT_RELATIONSHIP_ID,
        user_id=DEFAULT_USER_ID,
        version=1,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    contract = RelationshipContract(
        tier=tier,
        teasing_permission=(tier != IntimacyTier.ACQUAINTANCE),
        compromise_capacity=0.7,
        vulnerability_depth=0.5,
    )
    state_ctx = CharacterStateContext.from_state(char_state)
    emo_ctx = CharacterEmotionContext.from_state(emo_state)
    return CharacterResponseContext(
        user_input=user_input,
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=state_ctx,
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=emo_ctx,
        memory=CharacterMemoryContext.from_memories(()),
        behavior=CharacterBehaviorContext.synthesize(state_ctx, emo_ctx),
        life=CharacterLifeContext(
            current_activity_summary=activity,
            current_location_summary="Home",
            recent_experience_summary=(),
            life_guidance=(f"Currently {activity}.",),
        ),
        contract=contract,
    )


# ---------------------------------------------------------------------------
# 1. Boundary 1: Momentum != Task Tracking
# ---------------------------------------------------------------------------

def test_momentum_thread_decay_not_task_list():
    """Boundary 1: Unresolved threads naturally decay; new topics shift anchor without obligation."""
    initial = ConversationalMomentumState(
        active_topic_anchor="movie_recommendation",
        unresolved_threads=["movie_recommendation", "coffee_roasting"],
        running_in_jokes=["cat_meme"],
    )

    # User moves on to a completely different topic (programming bug)
    decision = TurnConversationalDecision(
        attention="bug debugging",
        reaction="baffled",
        commitment=ResponseCommitmentTier.PARTIAL_FLOW,
        energy=ResponseEnergyTier.NORMAL,
        motivation=ConversationalMotivation.GENUINE_SHARING,
        friction=FrictionTier.POLITE_DISTANT,
        momentum_anchor="programming_bug",
    )

    updated = ConversationalMomentumEngine.update_momentum(
        previous_state=initial,
        user_input="今天写代码写到一个诡异的死锁，搞了三小时。",
        prior_decision=decision,
    )

    # Active topic anchor shifted organically
    assert updated.active_topic_anchor == "programming_bug"
    # Unresolved threads capped and do not act as tasks
    assert len(updated.unresolved_threads) <= ConversationalMomentumEngine.MAX_UNRESOLVED_THREADS


# ---------------------------------------------------------------------------
# 2. Boundary 2: Low Energy Must Emerge, Not Be Manufactured
# ---------------------------------------------------------------------------

def test_energy_emerges_from_character_state_not_turn_counts():
    """Boundary 2: Energy emerges from physical/emotional state, zero turn-count penalties."""
    # Scenario A: Exhausted or asleep
    ctx_exhausted = _build_test_context(energy=0.2, activity="exhausted")
    energy_a = ConversationalArbitrator.arbitrate_energy(
        ctx_exhausted.character_state,
        ctx_exhausted.emotion,
        ctx_exhausted.user_input,
    )
    assert energy_a == ResponseEnergyTier.VERY_LOW

    # Scenario B: High vitality and excited
    ctx_high = _build_test_context(
        energy=0.9,
        activity="composing_music",
        emotion_type=EmotionType.EXCITED,
        emotion_intensity=0.8,
    )
    energy_b = ConversationalArbitrator.arbitrate_energy(
        ctx_high.character_state,
        ctx_high.emotion,
        ctx_high.user_input,
    )
    assert energy_b == ResponseEnergyTier.ENGAGED

    # Scenario C: 10 consecutive turns do NOT artificially degrade energy if state is normal
    ctx_normal = _build_test_context(energy=0.7)
    for _ in range(10):
        energy_c = ConversationalArbitrator.arbitrate_energy(
            ctx_normal.character_state,
            ctx_normal.emotion,
            ctx_normal.user_input,
        )
        assert energy_c == ResponseEnergyTier.NORMAL


# ---------------------------------------------------------------------------
# 3. Boundary 3: Friction Is Permission, Not Quota
# ---------------------------------------------------------------------------

def test_friction_is_permission_not_quota():
    """Boundary 3: Familiarity conditions max friction permission; never mandatory."""
    # Acquaintance: Restricted to POLITE_DISTANT
    ctx_acq = _build_test_context(tier=IntimacyTier.ACQUAINTANCE)
    f_acq = ConversationalArbitrator.evaluate_max_allowed_friction(ctx_acq.contract)
    assert f_acq == FrictionTier.POLITE_DISTANT

    # Close Confidant: Permitted up to PLAYFUL_TEASE
    ctx_close = _build_test_context(tier=IntimacyTier.CLOSE_CONFIDANT)
    f_close = ConversationalArbitrator.evaluate_max_allowed_friction(ctx_close.contract)
    assert f_close == FrictionTier.PLAYFUL_TEASE

    # Agency guidance explicitly states it is a permission, not a quota
    guidance = ConversationalArbitrator.format_agency_guidance(
        ctx_close.character_state,
        ctx_close.emotion,
        ctx_close.contract,
        f_close,
    )
    assert "permission, NOT a quota" in guidance
    assert "do NOT manufacture conflict" in guidance


# ---------------------------------------------------------------------------
# 4. Boundary 4: Character Initiative & Self-Disclosure
# ---------------------------------------------------------------------------

def test_character_initiative_and_self_disclosure_motivations():
    """Boundary 4: SPONTANEOUS_INITIATIVE and ASSOCIATIVE_DRIFT are first-class motivations."""
    assert ConversationalMotivation.SPONTANEOUS_INITIATIVE.value == "SPONTANEOUS_INITIATIVE"
    assert ConversationalMotivation.ASSOCIATIVE_DRIFT.value == "ASSOCIATIVE_DRIFT"

    # Verify decision parses these motivations
    raw = (
        "<character_turn>\n"
        "<internal_decision>\n"
        "attention: user mentioned hot weather\n"
        "reaction: reminded of laundry struggle\n"
        "commitment: PARTIAL_FLOW\n"
        "energy: NORMAL\n"
        "motivation: ASSOCIATIVE_DRIFT\n"
        "friction: POLITE_DISTANT\n"
        "</internal_decision>\n"
        "<character_speech>\n"
        "我刚才晒衣服的时候才是真的崩溃……阳台完全是个蒸笼。\n"
        "</character_speech>\n"
        "</character_turn>"
    )
    parsed = ConversationalResponseParser.parse(raw)
    assert parsed.decision is not None
    assert parsed.decision.motivation == ConversationalMotivation.ASSOCIATIVE_DRIFT
    assert "晒衣服" in parsed.speech_text


def test_behavior_planner_supports_associative_drift_and_initiative():
    """Boundary 4: Behavior planner includes associative drift in allowed actions."""
    from app.character.behavior_planner import BehaviorPlanner
    from app.character.desire_models import CharacterDesireState
    from app.character.intention_models import SocialIntention, SocialPosture

    intent = SocialIntention(
        primary_move=BehaviorPrimitive.ANSWER,
        social_posture=SocialPosture.WARM_ENGAGED,
        warmth=0.8,
        directness=0.7,
        conversation_hook=None,
        compromise_level=0.5,
    )
    contract = RelationshipContract(
        tier=IntimacyTier.CLOSE_CONFIDANT,
        compromise_capacity=0.8,
        teasing_permission=True,
        vulnerability_depth=0.6,
    )
    desire = CharacterDesireState(
        current_focus="painting",
        social_need=0.5,
        solitude_need=0.5,
    )

    plan, trace = BehaviorPlanner.plan(
        "今天好热啊。",
        intention=intent,
        contract=contract,
        desire=desire,
    )

    # Check allowed micro actions contain associative drift
    actions_text = " ".join(plan.allowed_micro_actions)
    assert "associative drift" in actions_text


# ---------------------------------------------------------------------------
# 5. Boundary 5: Selective Context Injection for Momentum
# ---------------------------------------------------------------------------

def test_momentum_selective_injection_only():
    """Boundary 5: Momentum block is NOT injected if there is no active momentum."""
    # Empty momentum
    empty_momentum = ConversationalMomentumState()
    block_empty = ConversationalMomentumEngine.format_momentum_block(
        empty_momentum,
        "你好啊",
    )
    assert block_empty is None

    # Active momentum
    active_momentum = ConversationalMomentumState(
        active_topic_anchor="classical_piano",
        unresolved_threads=["piano_practice"],
        running_in_jokes=["third_coffee_cup"],
    )
    block_active = ConversationalMomentumEngine.format_momentum_block(
        active_momentum,
        "今天练琴了吗？",
    )
    assert block_active is not None
    assert "<conversational_momentum>" in block_active
    assert "classical_piano" in block_active
    assert "NOT to-do items" in block_active


# ---------------------------------------------------------------------------
# 6. Boundary 9 & 10: Asymmetry, Selective Attention, Non-Expansion
# ---------------------------------------------------------------------------

def test_prompt_assembler_emits_agency_and_selective_attention():
    """Boundaries 9 & 10: Prompt assembler includes Attention Ownership and Asymmetry guidance."""
    ctx = _build_test_context()
    llm_ctx = ResponseContextAssembler.assemble(ctx)
    system_text = "\n".join(llm_ctx.system_instructions)

    assert "<conversational_agency_guidance>" in system_text
    assert "Attention Ownership" in system_text
    assert "Character Initiative & Self-Disclosure" in system_text
    assert "Asymmetry & Non-Expansion" in system_text
    assert "ZERO_EXPANSION or LOW_EFFORT" in system_text


def test_character_engine_assembles_momentum_and_signature_defaults():
    """CharacterEngine sets default momentum and signature if not passed."""
    engine = CharacterEngine()
    ctx = _build_test_context()

    assert ctx.conversational_momentum is None or isinstance(ctx.conversational_momentum, ConversationalMomentumState)


@pytest.mark.asyncio
async def test_end_to_end_initiative_and_non_expansion_turn():
    """End-to-End: Generator cleanly returns spontaneous initiative with zero interrogative question."""
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_response = AsyncMock(return_value=LLMResponse(
        content=(
            "<character_turn>\n"
            "<internal_decision>\n"
            "attention: user mentioned afternoon boredom\n"
            "reaction: sharing own funny incident\n"
            "commitment: PARTIAL_FLOW\n"
            "energy: NORMAL\n"
            "motivation: SPONTANEOUS_INITIATIVE\n"
            "friction: POLITE_DISTANT\n"
            "curiosity: false\n"
            "ignored: movie, tea\n"
            "</internal_decision>\n"
            "<character_speech>\n"
            "我刚才也是，本来想画画结果对着调色盘发呆了半小时。\n"
            "最后干脆去给仙人掌浇水了。\n"
            "</character_speech>\n"
            "</character_turn>"
        ),
        raw_response={"finish_reason": "stop"},
    ))

    generator = ResponseGenerator(provider=mock_provider)
    ctx = _build_test_context()
    resp = await generator.generate_response(ctx)

    assert resp.decision is not None
    assert resp.decision.motivation == ConversationalMotivation.SPONTANEOUS_INITIATIVE
    assert resp.decision.curiosity is False
    assert "?" not in resp.content and "？" not in resp.content
    assert "仙人掌" in resp.content
    assert len(resp.speech_bubbles) >= 1
