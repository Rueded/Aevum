"""Behavioral scenario regression suite covering the 8 user-audited realism scenarios.

Scenarios:
1. Affinity >= 0.70/0.80 Romantic Confession & Agency Acceptance:
   Accepts confession/proposal warmly without defensive rejection ("吊着"/拉扯),
   while retaining individual voice and personal agency (not an obsequious yes-girl).
2. Affinity >= 0.55/0.60 Intimacy (Hand-holding / Hugs):
   Receptive to physical closeness, without defensive boundary pushback.
3. Repeated Pick-up Lines / Sweet Flirting:
   Playful counter-teasing, blushing amusement, diverse replies; no single formulaic retort.
4. Bedtime Voice Call Sign-off vs. Meetup Separation:
   Online bedtime sign-off; zero physical departure phrases ("路上小心", "到家发我").
5. Epistemic Humility on Unrecorded Past Facts:
   Natural uncertainty ("我不确定/记不清了") without false accusations of user lying.
6. Activity Pacing (Cinema, Cooking, Studying, Deep Focus):
   No impatient nudges or interruptions during active engagement within normal duration.
7. Sleep / Wake Continuity:
   State machine consistency across sleep grogginess, oversleeping, and waking up.
8. Sticker Throttling & Diversity:
   Frequency governor (80%+ turns sticker-free), zero static caption speech filler leaks,
   and zero anime-parody stuttering tics.
"""

from datetime import datetime, timezone
import pytest

from app.character.appraisal import CharacterAppraisalEngine, SituationalStance
from app.character.behavior_planner import BehaviorPlanner
from app.character.desire_models import CharacterDesireState, PrimaryDesire
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.intention_models import (
    BehaviorPrimitive,
    ParticipationLevel,
    SocialPosture,
)
from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.social_intention_service import SocialIntentionService
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.context_builder import LifeContextBuilder
from app.life.dialogue_situation import DialogueSituationAppraisalService
from app.life.models import LifeState
from app.relationship.context_builder import RelationshipContextBuilder, synthesize_interaction_guidance
from app.relationship.contract_evaluator import RelationshipContractEvaluator
from app.relationship.contract_models import IntimacyTier
from app.relationship.models import RelationshipState


def _create_rel(affection: float = 0.8, trust: float = 0.8, familiarity: float = 0.8, comfort: float = 0.8) -> RelationshipState:
    now = datetime.now(timezone.utc)
    return RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=familiarity,
        trust=trust,
        comfort=comfort,
        affection=affection,
        attachment=min(1.0, affection * 0.9),
        respect=0.8,
    )


def _create_sample_char_def() -> CharacterDefinitionContext:
    defn = CharacterDefinition(
        id="sutang",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(
            name="苏棠",
            age=20,
            occupation="Music & CS Student",
            background="Studies piano in Penang USM, lives in Klang Valley.",
        ),
        personality=Personality(
            core_traits=["Observant", "Tsundere", "Playful"],
            social_style=["Warm but reserved"],
            emotional_style=["Expressive"],
            communication_style=["Articulate"],
            behavioral_tendencies=["Independent"],
            flaws=["Hesitant to admit blushing"],
        ),
        boundaries=[
            Boundary(description="Holds ethical boundaries and personal dignity."),
        ],
    )
    return CharacterDefinitionContext.from_definition(defn)


def _create_sample_state(activity: str = "DINNER", location: str = "RESTAURANT") -> CharacterStateContext:
    st = CharacterState(
        id="sutang",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity=activity,
        current_location=location,
    )
    return CharacterStateContext.from_state(st)


def _create_sample_emotion(intensity: float = 0.8) -> CharacterEmotionContext:
    emo = EmotionState(
        id="emo-1",
        character_id="sutang",
        emotion_type=EmotionType.HAPPY,
        intensity=intensity,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return CharacterEmotionContext.from_state(emo)


def _assemble_test_prompt(user_input: str = "你好", affection: float = 0.8) -> str:
    char_ctx = _create_sample_char_def()
    state_ctx = _create_sample_state()
    rel_ctx = RelationshipContextBuilder.build(_create_rel(affection=affection))
    emo_ctx = _create_sample_emotion()
    life_ctx = LifeContextBuilder.build(LifeState(
        character_id="sutang", current_activity="resting", current_location="home",
        updated_at=datetime.now(timezone.utc),
    ), (), ())

    ctx = CharacterResponseContext(
        user_input=user_input,
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        memory=CharacterMemoryContext.empty(),
        behavior=CharacterBehaviorContext(behavioral_hints=()),
        life=life_ctx,
    )
    llm_context = ResponseContextAssembler.assemble(ctx)
    return "\n".join(llm_context.system_instructions)


# -----------------------------------------------------------------------------
# Scenario 1: High Affinity (>= 0.70 / 0.80) Romantic Confession & Agency Acceptance
# -----------------------------------------------------------------------------
def test_scenario_1_high_affinity_romantic_confession_agency_acceptance():
    """Confession at high affinity (0.80) is accepted warmly with agency, not endless ambiguity."""
    rel = _create_rel(affection=0.80, trust=0.80, familiarity=0.85, comfort=0.85)

    # 1. Contract Evaluation
    contract = RelationshipContractEvaluator.evaluate(
        relationship=rel,
        affection=rel.affection,
        trust=rel.trust,
    )
    assert contract.romantic_readiness >= 0.70
    assert "high_affection_romantic_acceptance" in contract.contextual_modifiers

    # 2. Social Intention Evaluation
    confession_text = "可以给我一次机会吗？我来帮你带上项链"
    desire = CharacterDesireState(
        primary_desire=PrimaryDesire.REST_AND_RECHARGE,
        current_focus="relaxing at dinner",
        social_need=0.6,
        solitude_need=0.2,
    )
    intention = SocialIntentionService.evaluate(
        confession_text,
        contract=contract,
        desire=desire,
        emotion_type="touched",
        emotion_intensity=0.85,
    )

    assert intention.primary_move == BehaviorPrimitive.ACCEPT
    assert intention.social_posture == SocialPosture.WARM_ENGAGED
    assert intention.warmth >= 0.85
    assert intention.participation == ParticipationLevel.FULL
    assert "agency" in intention.conversation_hook or "playful" in intention.conversation_hook

    # 3. Behavior Planner Execution
    plan, trace = BehaviorPlanner.plan(
        confession_text,
        intention=intention,
        contract=contract,
        desire=desire,
    )
    assert plan.primary_move == BehaviorPrimitive.ACCEPT
    # Must disallow defensive pushback / manipulative stringing along
    forbidden_text = " ".join(plan.forbidden_patterns)
    assert "吊着" in forbidden_text or "cold rejection" in forbidden_text
    # Must disallow subservient yes-girl compliance
    assert "subservient unconditional obedience" in forbidden_text
    # Micro actions must encourage agency-preserving personal nuance
    micro_text = " ".join(plan.allowed_micro_actions)
    assert "agency-preserving personal nuance" in micro_text

    # 4. Character Appraisal Engine Evaluation
    char_ctx = _create_sample_char_def()
    state_ctx = _create_sample_state()
    rel_ctx = RelationshipContextBuilder.build(rel)
    emo_ctx = _create_sample_emotion()

    appraisal = CharacterAppraisalEngine.appraise(
        user_input=confession_text,
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        raw_relationship=rel,
    )
    assert appraisal.stance == SituationalStance.AGREE_WARMLY
    assert appraisal.desired_warmth >= 0.85
    assert any("obsequious yes-girl" in fb.lower() for fb in appraisal.forbidden_behaviors)


# -----------------------------------------------------------------------------
# Scenario 2: Moderate/High Intimacy (>= 0.55 / 0.60) Physical Closeness Acceptance
# -----------------------------------------------------------------------------
def test_scenario_2_moderate_affinity_intimacy_receptive_vs_low_boundary():
    """At affection >= 0.55, physical closeness (hand-holding/hug) is accepted receptively."""
    rel_warm = _create_rel(affection=0.60, trust=0.60, familiarity=0.65, comfort=0.65)
    contract_warm = RelationshipContractEvaluator.evaluate(
        relationship=rel_warm,
        affection=rel_warm.affection,
        trust=rel_warm.trust,
    )
    assert contract_warm.romantic_readiness >= 0.55
    assert "affection_intimacy_unlocked" in contract_warm.contextual_modifiers

    desire = CharacterDesireState(
        primary_desire=PrimaryDesire.CASUAL_ENGAGEMENT,
        current_focus="walking together",
        social_need=0.7,
        solitude_need=0.2,
    )

    # Physical closeness proposal
    intimacy_text = "走，牵手去买奶茶"
    intention_warm = SocialIntentionService.evaluate(
        intimacy_text,
        contract=contract_warm,
        desire=desire,
    )
    assert intention_warm.primary_move == BehaviorPrimitive.ACCEPT
    assert intention_warm.social_posture == SocialPosture.WARM_ENGAGED

    # Compare against low-affinity stranger (affection = 0.15)
    rel_cold = _create_rel(affection=0.15, trust=0.15, familiarity=0.10, comfort=0.10)
    contract_cold = RelationshipContractEvaluator.evaluate(
        relationship=rel_cold,
        affection=rel_cold.affection,
        trust=rel_cold.trust,
    )
    intention_cold = SocialIntentionService.evaluate(
        intimacy_text,
        contract=contract_cold,
        desire=desire,
    )
    assert intention_cold.primary_move == BehaviorPrimitive.SET_BOUNDARY
    assert intention_cold.social_posture == SocialPosture.FIRM_BOUNDARY


# -----------------------------------------------------------------------------
# Scenario 3: Cheesy Pickup Lines & Flirting Reciprocation
# -----------------------------------------------------------------------------
def test_scenario_3_pickup_lines_playful_counter_teasing():
    """Pickup lines at high affinity trigger playful teasing and varied reciprocation."""
    rel = _create_rel(affection=0.75, trust=0.75, familiarity=0.80, comfort=0.80)
    contract = RelationshipContractEvaluator.evaluate(
        relationship=rel,
        affection=rel.affection,
        trust=rel.trust,
    )

    pickup_text = "你知道你和星星的区别吗？星星在天上，你在我心上"
    desire = CharacterDesireState(
        primary_desire=PrimaryDesire.PLAYFUL_DISTRACTION,
        current_focus="chatting at night",
        social_need=0.6,
        solitude_need=0.3,
    )
    intention = SocialIntentionService.evaluate(
        pickup_text,
        contract=contract,
        desire=desire,
    )
    assert intention.primary_move == BehaviorPrimitive.TEASE
    assert intention.social_posture == SocialPosture.PLAYFUL_TEASING
    assert intention.warmth >= 0.75
    assert "varied playful counter-teasing" in intention.conversation_hook

    prompt = _assemble_test_prompt()
    assert "DIVERSE FLIRTING RECIPROCATION" in prompt
    assert "从哪学来这么油的话？老实交代" in prompt


# -----------------------------------------------------------------------------
# Scenario 4: Bedtime Voice Call Sign-off vs. Meetup Physical Separation
# -----------------------------------------------------------------------------
def test_scenario_4_voice_call_grounding_bans_physical_departure():
    """Voice call sign-offs explicitly ban physical departure phrases like '路上小心'."""
    prompt = _assemble_test_prompt()
    assert "Phone Call vs Physical Reality Boundary" in prompt
    assert "路上小心" in prompt
    assert "通话与线下场景严格分离" in prompt


# -----------------------------------------------------------------------------
# Scenario 5: Epistemic Humility on Unrecorded Past Queries
# -----------------------------------------------------------------------------
def test_scenario_5_epistemic_humility_bans_gaslighting_user():
    """Unrecorded past facts require epistemic uncertainty, banning false accusation of user lying."""
    prompt = _assemble_test_prompt()
    assert "Epistemic Humility & Anti-Gaslighting" in prompt
    assert "我可能记混了" in prompt
    assert "accuse the user of lying" in prompt or "反咬" in prompt


# -----------------------------------------------------------------------------
# Scenario 6: Activity Pacing (Cinema, Cooking, Studying)
# -----------------------------------------------------------------------------
def test_scenario_6_activity_pacing_respects_ongoing_duration():
    """Active engagements like movies, cooking, and studying respect ongoing duration without impatient nudges."""
    prompt = _assemble_test_prompt()
    assert "Physical Activity & Life Realism" in prompt
    assert "约会与生活活动期间严禁神经质催问" in prompt
    assert "人呢？" in prompt


# -----------------------------------------------------------------------------
# Scenario 7: Sleep / Wake Transitions & Continuity
# -----------------------------------------------------------------------------
def test_scenario_7_sleep_and_wake_continuity():
    """Dialogue transitions for sleep and wake maintain deterministic state machine accuracy."""
    # Morning sleepy grogginess
    user_groggy = "起床啦?"
    assistant_groggy = "嗯…… 唔…… [迷迷糊糊]\n吵死了…… 你…… 你这么早干嘛啦。\n我…… 我还想睡……"
    situation_groggy = DialogueSituationAppraisalService.extract_situation(user_groggy, assistant_groggy)
    assert situation_groggy is not None
    assert situation_groggy.status == "REST"
    assert "卧室" in situation_groggy.location

    # Oversleep panic
    user_panic = "都12点半了还早"
    assistant_panic = "啊？[瞬间清醒，猛地睁开眼睛] Walao！十二点半了？！救命！我…… 我怎么睡到现在啊！"
    situation_panic = DialogueSituationAppraisalService.extract_situation(user_panic, assistant_panic)
    assert situation_panic is not None
    assert situation_panic.status == "ACTIVE"
    assert "睡过头" in situation_panic.activity or "醒" in situation_panic.activity


# -----------------------------------------------------------------------------
# Scenario 8: Sticker Throttling & Anti-Tic Policy
# -----------------------------------------------------------------------------
def test_scenario_8_sticker_throttling_and_anti_tic_policy():
    """Prompt assembler and context builder enforce sticker frequency throttling and ban speech fillers."""
    prompt = _assemble_test_prompt()

    # Must have strict throttling governor
    assert "STRICT STICKER THROTTLING & FREQUENCY GOVERNOR" in prompt
    assert "80%+" in prompt

    # Must ban static caption speech fillers
    assert "没眼看……脑壳疼" in prompt
    assert "讨厌啦……害羞了" in prompt
    assert "? ? 真的假的？！" in prompt

    # Must ban anime-parody stuttering tics
    assert "STRICT ANTI-STUTTERING TIC" in prompt
    assert "你…… 你这个坏蛋！" in prompt

    # Context builder must also preach restraint
    rel = _create_rel(affection=0.8, trust=0.8, familiarity=0.8, comfort=0.8)
    guidance = synthesize_interaction_guidance(rel)
    assert "表情包与贴纸极度克制" in guidance
    assert "75%以上" in guidance
