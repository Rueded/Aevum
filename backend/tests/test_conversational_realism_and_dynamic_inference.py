"""Targeted test suite for Scheme A (Authentic Conversational Prompting)
and Scheme B (Dynamic Autobiographical Inference & Locking).

Validates:
1. Scheme A:
   - Autobiographical truth (USM, Music Performance, Sembreak in KL, middle-class family) is directly anchored into the LLM system prompt.
   - High intimacy/familiarity drops all customer service and preachy counseling language.
   - Banter, light roasting (互怼), and spontaneous slice-of-life sharing directives are active.
2. Scheme B:
   - When encountering undefined personal reality questions (parents' occupation, childhood background, transit, beverage), RealityInquiryDetector detects the slot.
   - DeterministicLifeHypothesisProposer generates cohesive candidates grounded in her middle-class, doctor/professor parents background.
   - Candidates are normalized, evaluated, and promoted to canonical CharacterCore.
   - Once canonical, subsequent turns identify the slot as known, preventing contradiction.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.state_models import CharacterMood, CharacterState
from app.character.core_service import CharacterCoreService
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.models import LifeState
from app.life.context_builder import LifeContextBuilder
from app.reality.candidate_models import CandidateLifecycleState
from app.reality.inquiry_detector import RealityInquiryDetector
from app.reality.proposer import DeterministicLifeHypothesisProposer
from app.reality.inference_models import InferenceProposalRequest
from app.reality.slot_normalizer import SlotValueNormalizer
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState


def _create_sample_character_definition() -> CharacterDefinition:
    return CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(
            name="Aevum",
            age=21,
            occupation="University Student",
            background="Studies piano and composition.",
        ),
        personality=Personality(
            core_traits=["Observant", "Introspective"],
            social_style=["Warm but reserved"],
            emotional_style=["Measured"],
            communication_style=["Articulate"],
            behavioral_tendencies=["Prefers quiet spaces"],
            flaws=["Hesitant to initiate"],
        ),
        boundaries=[
            Boundary(description="Maintains clear personal boundaries."),
        ],
    )


# ==============================================================================
# Scheme A: Conversational Realism, Biography Prompt & High Intimacy Tone Tests
# ==============================================================================


def test_scheme_a_prompt_anchors_authoritative_biography():
    """Verify that authoritative biography facts (USM, KL, Music Performance, Sembreak) are anchored."""
    char_def = _create_sample_character_definition()
    char_ctx = CharacterDefinitionContext.from_definition(char_def)

    state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="resting at home",
        current_location="bedroom",
    )
    state_ctx = CharacterStateContext.from_state(state)

    rel_state = RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        familiarity=0.75,
        trust=0.70,
        comfort=0.70,
        affection=0.50,
        attachment=0.50,
        respect=0.80,
    )
    rel_ctx = RelationshipContextBuilder.build(rel_state)

    emo = EmotionState(
        id="emo-1",
        character_id="aevum",
        emotion_type=EmotionType.HAPPY,
        intensity=0.6,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    emo_ctx = CharacterEmotionContext.from_state(emo)
    life_state = LifeState(
        character_id="aevum",
        current_activity="practicing piano",
        current_location="home piano room",
        updated_at=datetime.now(timezone.utc),
    )
    life_ctx = LifeContextBuilder.build(life_state, (), ())

    ctx = CharacterResponseContext(
        user_input="你平时都在忙什么呀？",
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        memory=CharacterMemoryContext.empty(),
        behavior=CharacterBehaviorContext(behavioral_hints=("Be yourself.",)),
        life=life_ctx,
    )

    llm_context = ResponseContextAssembler.assemble(ctx)
    prompt_text = "\n".join(llm_context.system_instructions)

    # 1. Authoritative biography anchors present
    assert "Universiti Sains Malaysia" in prompt_text or "USM" in prompt_text
    assert "音乐表演系" in prompt_text
    assert "Sembreak" in prompt_text
    assert "雪隆" in prompt_text or "吉隆坡" in prompt_text
    assert "晚晚" in prompt_text

    # 2. High intimacy & anti-preachiness instructions present
    assert "HIGH INTIMACY & CLOSE FRIEND MODE" in prompt_text
    assert "零客服腔、零说教味" in prompt_text
    assert "互怼" in prompt_text
    assert "生活琐碎" in prompt_text
    assert "微信中括号表情包" in prompt_text


def test_scheme_a_high_familiarity_banter_and_anti_assistant_instructions():
    """Verify that close relationship state triggers banter, light roasting, and anti-assistant guidance."""
    rel_state = RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        familiarity=0.85,
        trust=0.80,
        comfort=0.85,
        affection=0.70,
        attachment=0.65,
        respect=0.85,
    )
    ctx = RelationshipContextBuilder.build(rel_state)
    guidance = ctx.interaction_guidance

    assert "HIGH INTIMACY & CLOSE FRIEND MODE" in guidance
    assert "零客服腔、零说教味" in guidance
    assert "请问还有什么可以帮您" in guidance  # listed in forbidden phrases
    assert "接梗、互怼与口嗨" in guidance
    assert "主动分享生活琐碎" in guidance


# ==============================================================================
# Scheme B: Dynamic Autobiographical Inference & Locking Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_scheme_b_detects_undefined_family_and_lifestyle_inquiries(test_session: AsyncSession):
    """RealityInquiryDetector identifies inquiries on undefined autobiographical slots."""
    core_service = CharacterCoreService(test_session)
    core = await core_service.get_core("aevum")

    # 1. Parents' occupation
    sig_parents = RealityInquiryDetector.detect_inquiry("你爸妈是做什么工作的呀？", core=core)
    assert sig_parents is not None
    assert sig_parents.target_slot == "family.parents_occupation"

    # 2. Childhood piano background
    sig_childhood = RealityInquiryDetector.detect_inquiry("你几岁开始学琴的？从小就学钢琴吗？", core=core)
    assert sig_childhood is not None
    assert sig_childhood.target_slot == "family.childhood_background"

    # 3. Transit lifestyle
    sig_transit = RealityInquiryDetector.detect_inquiry("你平时出门都坐什么车？", core=core)
    assert sig_transit is not None
    assert sig_transit.target_slot == "lifestyle.transit"

    # 4. Beverage preference
    sig_beverage = RealityInquiryDetector.detect_inquiry("你平时喜欢喝什么奶茶或者饮料？", core=core)
    assert sig_beverage is not None
    assert sig_beverage.target_slot == "lifestyle.beverage"


@pytest.mark.asyncio
async def test_scheme_b_proposer_generates_grounded_candidates():
    """DeterministicLifeHypothesisProposer synthesizes realistic middle-class candidates."""
    proposer = DeterministicLifeHypothesisProposer()

    # Request for parents' occupation
    req_parents = InferenceProposalRequest(
        target_slot="family.parents_occupation",
        domain="family",
        authorized_premise_keys=("family.background", "identity.background"),
        premise_snapshots={
            "family.background": "Grew up in a supportive family environment.",
            "identity.background": "Undergraduate student.",
        },
        inference_cycle_id="cycle-parents-test",
    )
    envelopes_parents = await proposer.propose_hypotheses(req_parents)
    assert len(envelopes_parents) >= 2
    raw_vals = [e.raw_value for e in envelopes_parents]
    assert any("大学数理学院教授" in v and "医生" in v for v in raw_vals)

    # Request for childhood background
    req_childhood = InferenceProposalRequest(
        target_slot="family.childhood_background",
        domain="family",
        authorized_premise_keys=("family.background", "interests"),
        premise_snapshots={
            "family.background": "Grew up in a supportive family environment.",
            "interests": ["acoustic piano and guitar"],
        },
        inference_cycle_id="cycle-childhood-test",
    )
    envelopes_childhood = await proposer.propose_hypotheses(req_childhood)
    assert len(envelopes_childhood) >= 2
    childhood_vals = [e.raw_value for e in envelopes_childhood]
    assert any("古典钢琴" in v for v in childhood_vals)


@pytest.mark.asyncio
async def test_scheme_b_lock_and_subsequent_inquiry_avoids_re_inference(test_session: AsyncSession):
    """Once an inferred reality fact is canonicalized in core, subsequent inquiries are identified as already known."""
    core_service = CharacterCoreService(test_session)
    core = await core_service.get_core("aevum")

    # Before setting fact, inquiry is detected
    sig1 = RealityInquiryDetector.detect_inquiry("你父母是做什么职业的？", core=core)
    assert sig1 is not None
    assert sig1.target_slot == "family.parents_occupation"

    # Promote and lock fact into authoritative CharacterCore
    chosen_parents = "父亲是大学数理学院教授，母亲是公立综合医院专科医生"
    norm_res = SlotValueNormalizer.normalize("family.parents_occupation", chosen_parents)
    assert norm_res.is_valid

    await core_service.set_fact(
        character_id="aevum",
        fact_key="family.parents_occupation",
        value=norm_res.normalized_value,
    )

    # Reload refreshed core
    refreshed_core = await core_service.get_core("aevum")
    assert refreshed_core.get_fact_value("family.parents_occupation") == chosen_parents

    # Now the detector recognizes it is already CANONICAL, returning None (no re-inference, stable reality!)
    sig2 = RealityInquiryDetector.detect_inquiry("你父母是做什么职业的？", core=refreshed_core)
    assert sig2 is None
