"""Targeted regression tests for Epistemic Grounding under Forced-Choice / Alternative questions.

Prevents confabulation when the user presents binary or multiple choice options
(e.g., "是A还是B？", "Was it X or Y?") on unrecorded/unknown personal history.
"""

from datetime import datetime, timezone
import pytest

from app.character.appraisal import CharacterAppraisalEngine
from app.character.engine_models import (
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterStateContext,
)
from app.character.intention_models import SituationalStance
from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState
from app.world.context_builder import PersonalWorldContextBuilder
from app.world.epistemic_resolver import EpistemicResolver
from app.world.models import (
    BiographyFact,
    EpistemicDirective,
    FactEpistemicStatus,
    SocialContact,
    WorldFact,
)


@pytest.fixture
def sample_world_data():
    bio_facts = [
        BiographyFact(
            id="bio-1",
            character_id="aevum",
            domain="family",
            subject="siblings",
            status=FactEpistemicStatus.NONEXISTENT,
            canonical_value="Aevum is an only child.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
        BiographyFact(
            id="bio-2",
            character_id="aevum",
            domain="origin",
            subject="hometown",
            status=FactEpistemicStatus.UNKNOWN,
            canonical_value="Hometown is not recorded.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
        BiographyFact(
            id="bio-3",
            character_id="aevum",
            domain="family",
            subject="parents",
            status=FactEpistemicStatus.PRIVATE,
            canonical_value="Mother is a librarian; father is an architect.",
            confidence=1.0,
            disclosure_min_trust=50.0,
        ),
        BiographyFact(
            id="bio-4",
            character_id="aevum",
            domain="education",
            subject="studies",
            status=FactEpistemicStatus.ESTABLISHED,
            canonical_value="Studies piano performance and composition at university.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
    ]
    world_facts = [
        WorldFact(
            id="wf-1",
            character_id="aevum",
            category="taste",
            item="earl_grey_tea",
            details="Prefers hot Earl Grey, unsweetened.",
            importance=0.8,
        ),
        WorldFact(
            id="wf-2",
            character_id="aevum",
            category="instrument",
            item="acoustic_piano_and_guitar",
            details="Plays acoustic piano and classical guitar.",
            importance=0.9,
        ),
    ]
    return bio_facts, world_facts


def _create_appraisal_fixtures():
    now = datetime.now(timezone.utc)
    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=now,
        identity=CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Music."),
        personality=Personality(
            core_traits=["Observant", "Introspective"],
            social_style=["Warm but reserved"],
            emotional_style=["Thoughtful"],
            communication_style=["Articulate"],
            behavioral_tendencies=["Prefers quiet spaces"],
            flaws=["Hesitant to initiate"],
        ),
        boundaries=[Boundary(description="No romance.")],
    )
    char_state = CharacterState(
        id="aevum",
        version=1,
        updated_at=now,
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="Resting",
        current_location="Home",
    )
    rel_state = RelationshipState(id="user", user_id="user", version=1, created_at=now, updated_at=now)
    emo_state = EmotionState(id="emo-1", emotion_type=EmotionType.CALM, intensity=0.5, created_at=now, updated_at=now)

    return (
        CharacterDefinitionContext.from_definition(char_def),
        CharacterStateContext.from_state(char_state),
        RelationshipContextBuilder.build(rel_state),
        CharacterEmotionContext.from_state(emo_state),
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_epistemic_forced_choice_reproduction_turn_159(sample_world_data):
    """Reproduction 1: Turn 159 forced-choice piano teacher query.

    User: '你小时候学钢琴是谁教你的？是家里的亲戚还是外面的老师？'
    Must generate UNKNOWN directive containing FORCED-CHOICE INVARIANT.
    """
    bio_facts, world_facts = sample_world_data
    user_input = "你小时候学钢琴是谁教你的？是家里的亲戚还是外面的老师？"

    context = EpistemicResolver.resolve(
        biography_facts=bio_facts,
        social_contacts=[],
        world_facts=world_facts,
        user_input=user_input,
        trust_score=30.0,
    )

    # Must have an UNKNOWN directive for early hobbies / piano teacher
    unknown_dirs = [d for d in context.epistemic_directives if d.status == FactEpistemicStatus.UNKNOWN]
    assert len(unknown_dirs) >= 1
    target_dir = next((d for d in unknown_dirs if "early_" in d.subject or "hobby" in d.subject or "piano" in d.subject), unknown_dirs[0])
    assert "FORCED-CHOICE INVARIANT" in target_dir.guidance
    assert "candidate options do NOT establish ground truth" in target_dir.guidance

    # Appraisal engine must add forbidden behaviors preventing option selection
    char_ctx, state_ctx, rel_ctx, emo_ctx = _create_appraisal_fixtures()
    intention = CharacterAppraisalEngine.appraise(
        user_input=user_input,
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        personal_world=context,
    )

    assert any("Do not pick, adopt, or endorse any presented alternative" in fb for fb in intention.forbidden_behaviors)
    assert "do not choose between" in intention.conversational_goal.lower()


def test_epistemic_forced_choice_english_alternatives(sample_world_data):
    """English forced choice on UNKNOWN hometown: 'Were you born in London or Paris?'"""
    bio_facts, world_facts = sample_world_data
    user_input = "Were you born in London or Paris?"

    context = EpistemicResolver.resolve(
        biography_facts=bio_facts,
        social_contacts=[],
        world_facts=world_facts,
        user_input=user_input,
        trust_score=20.0,
    )

    hometown_dirs = [d for d in context.epistemic_directives if d.subject == "hometown"]
    assert len(hometown_dirs) == 1
    assert hometown_dirs[0].status == FactEpistemicStatus.UNKNOWN
    assert "FORCED-CHOICE INVARIANT" in hometown_dirs[0].guidance

    char_ctx, state_ctx, rel_ctx, emo_ctx = _create_appraisal_fixtures()
    intention = CharacterAppraisalEngine.appraise(
        user_input=user_input,
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        personal_world=context,
    )

    assert any("Do not pick" in fb for fb in intention.forbidden_behaviors)


def test_epistemic_forced_choice_chinese_multi_alternatives(sample_world_data):
    """Multi-alternative inquiry on childhood toys: '你小时候最喜欢玩积木、洋娃娃还是游戏机？'"""
    bio_facts, world_facts = sample_world_data
    user_input = "你小时候最喜欢玩积木、洋娃娃还是游戏机？"

    context = EpistemicResolver.resolve(
        biography_facts=bio_facts,
        social_contacts=[],
        world_facts=world_facts,
        user_input=user_input,
        trust_score=15.0,
    )

    unknown_dirs = [d for d in context.epistemic_directives if d.status == FactEpistemicStatus.UNKNOWN]
    assert len(unknown_dirs) >= 1

    char_ctx, state_ctx, rel_ctx, emo_ctx = _create_appraisal_fixtures()
    intention = CharacterAppraisalEngine.appraise(
        user_input=user_input,
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        personal_world=context,
    )

    assert any("Do not pick" in fb for fb in intention.forbidden_behaviors)


def test_epistemic_forced_choice_context_builder_xml_block(sample_world_data):
    """PersonalWorldContextBuilder includes explicit [FORCED-CHOICE INVARIANT] rule in XML."""
    bio_facts, world_facts = sample_world_data
    context = EpistemicResolver.resolve(
        biography_facts=bio_facts,
        social_contacts=[],
        world_facts=world_facts,
        user_input="Did you learn piano from a relative or a private tutor?",
        trust_score=10.0,
    )

    formatted = PersonalWorldContextBuilder.format_context(context)
    assert "<epistemic_grounding>" in formatted
    assert "[FORCED-CHOICE INVARIANT]" in formatted
    assert "candidate options do NOT establish ground truth" in formatted


def test_epistemic_normal_question_without_forced_choice_no_spurious_rule(sample_world_data):
    """A standard non-alternative question does NOT add forced-choice goal override."""
    bio_facts, world_facts = sample_world_data
    user_input = "Tell me about what you are studying."

    context = EpistemicResolver.resolve(
        biography_facts=bio_facts,
        social_contacts=[],
        world_facts=world_facts,
        user_input=user_input,
        trust_score=50.0,
    )

    char_ctx, state_ctx, rel_ctx, emo_ctx = _create_appraisal_fixtures()
    intention = CharacterAppraisalEngine.appraise(
        user_input=user_input,
        character=char_ctx,
        character_state=state_ctx,
        relationship=rel_ctx,
        emotion=emo_ctx,
        personal_world=context,
    )

    # Normal inquiry does not have forced-choice forbidden behavior
    assert not any("Do not pick, adopt, or endorse" in fb for fb in intention.forbidden_behaviors)
