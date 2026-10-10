"""Unit and behavioral contract test suite for Phase 18.4 (Expression Realization).

Covers:
- GC-432: Question Intent & Function (distinguish information-seeking vs affective/rhetorical).
- GC-433: Known Fact Consistency (Known Fact -> never solicit as Unknown Fact; persona persistence over social pressure).
- GC-434: Bubble Emergence without Prescribed Quotas.
- GC-435: Negative Liberties & Anti-Unrequested-Justification.
- GC-436: Uneven Expression / Asymmetric Elaboration.
"""

import pytest

from app.character.conversational_arbitrator import ConversationalArbitrator
from app.character.conversational_models import (
    FrictionTier,
    ResponseCommitmentTier,
    ResponseEnergyTier,
    TurnConversationalDecision,
)
from app.character.conversational_parser import ConversationalResponseParser
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
    MemoryExperienceContext,
)
from app.life.context_models import CharacterLifeContext
from app.character.integrity import OutputBoundaryGuard
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.state_models import CharacterMood
from app.emotion.emotion_models import EmotionType
from app.character.models import (
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.core.time import now_utc
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.contract_models import IntimacyTier, RelationshipContract
from app.relationship.models import DEFAULT_RELATIONSHIP_ID, DEFAULT_USER_ID, RelationshipState


@pytest.fixture
def base_context() -> CharacterResponseContext:
    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=now_utc(),
        identity=CharacterIdentity(name="昔涟", age=21, occupation="Student", background="Art and music."),
        personality=Personality(
            core_traits=("independent", "thoughtful"),
            social_style=("reflective", "warm"),
            emotional_style=("calm", "perceptive"),
            communication_style=("direct", "natural"),
            behavioral_tendencies=("observant", "measured"),
            flaws=("mildly stubborn",),
        ),
    )
    state = CharacterStateContext(
        mood=CharacterMood.CALM,
        energy=0.75,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="在书房整理草图",
        current_location="书房",
    )
    now = now_utc()
    rel_state = RelationshipState(
        id=DEFAULT_RELATIONSHIP_ID,
        user_id=DEFAULT_USER_ID,
        created_at=now,
        updated_at=now,
    )
    contract = RelationshipContract(tier=IntimacyTier.FAMILIAR)
    emotion = CharacterEmotionContext(
        emotion_type=EmotionType.CALM,
        intensity=0.4,
        summary="平静而专注",
    )
    mem = CharacterMemoryContext(
        memories=(),
        context_block="",
        experience=MemoryExperienceContext.synthesize(None),
    )
    return CharacterResponseContext(
        user_input="今天午休去食堂，鸡扒难吃死了。",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=state,
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=emotion,
        memory=mem,
        contract=contract,
        behavior=CharacterBehaviorContext.synthesize(state, emotion),
        life=CharacterLifeContext(
            current_location_summary="书房",
            current_activity_summary="整理草图",
            recent_experience_summary=(),
            life_guidance=(),
        ),
    )


def test_gc432_question_intent_invariants(base_context):
    """GC-432: Prompt assembler must contain Question Intent typing distinguishing info-seeking from affective/rhetorical."""
    llm_ctx = ResponseContextAssembler.assemble(base_context)
    full_prompt = "\n".join(llm_ctx.system_instructions)

    assert "GC-432" in full_prompt
    assert "Information-seeking questions require genuine curiosity" in full_prompt
    assert "affective, rhetorical, and teasing questions" in full_prompt
    assert "Do not fear question marks, but eliminate unmotivated conversational maintenance interrogatives" in full_prompt
    assert "When curiosity is 'false', character_speech MUST NOT contain unmotivated information-seeking questions" in full_prompt


def test_gc433_known_fact_consistency_invariants(base_context):
    """GC-433: Invariant 1 and 23 enforce persona persistence and anti-amnesia."""
    llm_ctx = ResponseContextAssembler.assemble(base_context)
    full_prompt = "\n".join(llm_ctx.system_instructions)

    assert "GC-433" in full_prompt
    assert "Never invert, alter, or discard your established personal habits, routines, or tastes under user leading questions or social pressure" in full_prompt
    assert "Known Fact Consistency & Anti-Amnesia" in full_prompt
    assert "Never treat a known fact as an unknown fact" in full_prompt
    assert "amnesiac re-inquiries are strictly forbidden" in full_prompt


def test_gc434_bubble_emergence_no_prescribed_quota():
    """GC-434: Single phrases/bursts naturally extract as 1 bubble, while explicit <msg> tags extract cleanly."""
    # Case A: Natural single concise sentence (1 bubble)
    single_turn = "啊……难吃成这样也是没谁了。"
    bubbles_single = ConversationalResponseParser.extract_bubbles(single_turn)
    assert len(bubbles_single) == 1
    assert bubbles_single[0] == "啊……难吃成这样也是没谁了。"

    # Case B: Multi-burst with explicit tags
    multi_tagged = "<msg>笑死</msg><msg>你居然把它吃完了？！</msg>"
    bubbles_tagged = ConversationalResponseParser.extract_bubbles(multi_tagged)
    assert len(bubbles_tagged) == 2
    assert bubbles_tagged[0] == "笑死"
    assert bubbles_tagged[1] == "你居然把它吃完了？！"

    # Case C: Natural two-burst paragraph split
    multi_split = "香菜？达咩。\n\n我是一口都受不了。"
    bubbles_split = ConversationalResponseParser.extract_bubbles(multi_split)
    assert len(bubbles_split) == 2
    assert bubbles_split[0] == "香菜？达咩。"
    assert bubbles_split[1] == "我是一口都受不了。"


def test_gc435_negative_liberties_and_anti_unrequested_justification(base_context):
    """GC-435: Invariant 22 & 25 forbid unrequested justification, therapeutic explainers, and formulaic closures."""
    llm_ctx = ResponseContextAssembler.assemble(base_context)
    full_prompt = "\n".join(llm_ctx.system_instructions)

    assert "GC-435" in full_prompt
    assert "Freedom from Unrequested Justification" in full_prompt
    assert "do NOT systematically produce [Opinion] -> [Because reason] -> [Therefore conclusion]" in full_prompt
    assert "Freedom from Therapeutic Articulation & Polite Closure" in full_prompt
    assert "Never deconstruct your empathy into analytical psychological explanations" in full_prompt
    assert "Never append formulaic blessings, polite closures, or philosophical sublimations" in full_prompt


def test_gc436_uneven_expression_invariants(base_context):
    """GC-436: Invariant 24 enforces asymmetric elaboration across topics based on personal interest."""
    llm_ctx = ResponseContextAssembler.assemble(base_context)
    full_prompt = "\n".join(llm_ctx.system_instructions)

    assert "GC-436" in full_prompt
    assert "Uneven Expression & Asymmetric Elaboration" in full_prompt
    assert "You are NOT required to give uniform depth across different topics" in full_prompt
    assert "Embrace conversational unevenness" in full_prompt


def test_arbitrator_agency_guidance_includes_gc433_to_gc436(base_context):
    """ConversationalArbitrator includes Anti-Unrequested-Justification, Uneven Expression, and Known Fact Integrity."""
    guidance = ConversationalArbitrator.format_agency_guidance(
        state=base_context.character_state,
        emotion=base_context.emotion,
        contract=base_context.contract,
        max_friction=FrictionTier.PLAYFUL_TEASE,
    )

    assert "Anti-Unrequested-Justification" in guidance
    assert "Uneven Expression: Let your investment fluctuate unevenly based on personal interest" in guidance
    assert "Known Fact Integrity: Never re-inquire about facts the user already clearly stated" in guidance


def test_e2e_envelope_parsing_with_gc434_and_gc435():
    """Ensure parser extracts concise 1-bubble speech and compact decision without CoT bloat."""
    raw_response = (
        "<character_turn>\n"
        "<internal_decision>\n"
        "attention: 鸡扒难吃\n"
        "reaction: 感到好笑和同情\n"
        "commitment: LOW_EFFORT\n"
        "energy: NORMAL\n"
        "motivation: COMMISERATE_VENT\n"
        "friction: POLITE_DISTANT\n"
        "curiosity: false\n"
        "</internal_decision>\n"
        "<character_speech>\n"
        "呕，这鸡扒也太惨了……光听着就窒息。\n"
        "</character_speech>\n"
        "</character_turn>"
    )

    parsed = ConversationalResponseParser.parse(raw_response)
    assert parsed.decision is not None
    assert parsed.decision.curiosity is False
    assert parsed.decision.commitment == ResponseCommitmentTier.LOW_EFFORT
    assert len(parsed.speech_bubbles) == 1
    assert parsed.speech_bubbles[0] == "呕，这鸡扒也太惨了……光听着就窒息。"

    clean_speech = OutputBoundaryGuard.verify_and_clean(raw_response, character_name="昔涟")
    assert clean_speech == "呕，这鸡扒也太惨了……光听着就窒息。"
