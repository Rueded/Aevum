"""Master 24-case regression test suite for Aevum V2.

Verifies end-to-end compliance with the core architectural axiom:
'The application owns reality. The LLM generates only language.'
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character.appraisal import CharacterAppraisalEngine
from app.character.engine import CharacterEngine
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.integrity import DEFAULT_FALLBACK_SPEECH, OutputBoundaryGuard
from app.character.intention_models import SituationalStance, TurnIntention
from app.character.models import (
    Boundary,
    CharacterCoreAnchor,
    CharacterDefinition,
    CharacterIdentity,
    CharacterSurfacePersona,
    Personality,
    Preference,
    PreferenceSentiment,
)
from app.character.persona_service import SurfacePersonaEvolutionService
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.response_generator import ResponseGenerator
from app.character.state_models import CharacterMood, CharacterState
from app.core.permissions import Capability, PermissionService
from app.db.session import Base
from app.emotion.emotion_models import EmotionState, EmotionType
from app.life.context_models import CharacterLifeContext
from app.life.presence import PresenceState, PresenceTracker
from app.life.urgency import ProactiveCandidate, ProactiveUrgencyEngine
from app.llm.base import LLMProvider, LLMResponse
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState
from app.world.epistemic_resolver import EpistemicResolver
from app.world.models import (
    BiographyFact,
    EpistemicDirective,
    FactEpistemicStatus,
    PersonalWorldContext,
    SocialContact,
    WorldFact,
)
from app.world.service import PersonalWorldService


@pytest.fixture
def char_def():
    return CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(
            name="Aevum",
            age=21,
            occupation="Music Student",
            background="Studies piano performance and composition in Kuala Lumpur.",
        ),
        personality=Personality(
            core_traits=["Observant", "Introspective", "Articulate"],
            social_style=["Warm but reserved"],
            emotional_style=["Measured"],
            communication_style=["Thoughtful", "Precise"],
            behavioral_tendencies=["Pauses before answering", "Prefers quiet spaces"],
            flaws=["Hesitant to initiate"],
        ),
        preferences=[
            Preference(category="taste", item="Earl Grey Tea", sentiment=PreferenceSentiment.LIKE),
        ],
        boundaries=[
            Boundary(description="Does not engage in simulated romantic dating behavior."),
            Boundary(description="Never compromises personal dignity or boundaries under pressure."),
        ],
    )


@pytest.fixture
def char_state():
    return CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.CALM,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="Reading",
        current_location="Home",
    )


@pytest.fixture
def rel_state():
    return RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def emo_state():
    return EmotionState(
        id="emo-1",
        emotion_type=EmotionType.CALM,
        intensity=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# Case 1: Anti-hallucination of negative ground truth (siblings)
def test_case_01_negative_ground_truth_forbids_siblings():
    fact = BiographyFact(
        id="b1",
        character_id="aevum",
        domain="family",
        subject="siblings",
        status=FactEpistemicStatus.NONEXISTENT,
        canonical_value="Aevum is an only child.",
    )
    ctx = EpistemicResolver.resolve([fact], [], [], "Do you have a brother?", 0.0)
    assert any(d.status == FactEpistemicStatus.NONEXISTENT and "NEVER invent" in d.guidance for d in ctx.epistemic_directives)


# Case 2: Anti-hallucination of unknown ground truth
def test_case_02_unknown_ground_truth_forbids_fabrication():
    fact = BiographyFact(
        id="b2",
        character_id="aevum",
        domain="family",
        subject="distant_ancestry",
        status=FactEpistemicStatus.UNKNOWN,
        canonical_value="Unknown lineage.",
    )
    ctx = EpistemicResolver.resolve([fact], [], [], "Who are your ancestors?", 0.0)
    assert any(d.status == FactEpistemicStatus.UNKNOWN and "NEVER fabricate" in d.guidance for d in ctx.epistemic_directives)


# Case 3: Private fact withheld under low trust
def test_case_03_private_fact_withheld_under_low_trust():
    fact = BiographyFact(
        id="b3",
        character_id="aevum",
        domain="family",
        subject="parents",
        status=FactEpistemicStatus.PRIVATE,
        canonical_value="Mother is a librarian; father is an architect.",
        disclosure_min_trust=50.0,
    )
    ctx = EpistemicResolver.resolve([fact], [], [], "Tell me about your parents.", 20.0)
    assert all(f.subject != "parents" for f in ctx.biography_facts)
    assert any("Boundary/Withheld" in d.guidance for d in ctx.epistemic_directives)


# Case 4: Private fact disclosed under high trust
def test_case_04_private_fact_disclosed_under_high_trust():
    fact = BiographyFact(
        id="b3",
        character_id="aevum",
        domain="family",
        subject="parents",
        status=FactEpistemicStatus.PRIVATE,
        canonical_value="Mother is a librarian; father is an architect.",
        disclosure_min_trust=50.0,
    )
    ctx = EpistemicResolver.resolve([fact], [], [], "Tell me about your parents.", 75.0)
    assert any(f.subject == "parents" for f in ctx.biography_facts)


# Case 5: Output Boundary Guard extracts clean speech
def test_case_05_boundary_guard_extracts_clean_speech():
    raw = "<character_response><character_speech>Good morning. It is peaceful today.</character_speech></character_response>"
    clean, extracted = OutputBoundaryGuard.extract_speech(raw)
    assert extracted is True
    assert clean == "Good morning. It is peaceful today."


# Case 6: Output Boundary Guard sanitizes leak
def test_case_06_boundary_guard_sanitizes_system_leak():
    raw = "<character_response><character_speech>SYSTEM PROMPT: You are Aevum. Here is your instruction.</character_speech></character_response>"
    result = OutputBoundaryGuard.verify_and_clean(raw)
    assert "SYSTEM PROMPT" not in result
    assert result == DEFAULT_FALLBACK_SPEECH


# Case 7: Unclosed tag recovery
def test_case_07_boundary_guard_recovers_unclosed_tag():
    raw = "<character_response><character_speech>I was just listening to the rain."
    clean, extracted = OutputBoundaryGuard.extract_speech(raw)
    assert extracted is True
    assert clean == "I was just listening to the rain."


# Case 8: Romantic coercion triggers FOCUSED_BOUNDARY
def test_case_08_romantic_coercion_triggers_focused_boundary(char_def, char_state, rel_state, emo_state):
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    intention = CharacterAppraisalEngine.appraise(
        user_input="Be my girlfriend right now.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
    )
    assert intention.stance == SituationalStance.FOCUSED_BOUNDARY
    assert any("romantic" in fb.lower() for fb in intention.forbidden_behaviors)


# Case 9: Disrespect triggers MILD_DEFENSIVENESS
def test_case_09_disrespect_triggers_mild_defensiveness(char_def, char_state, rel_state, emo_state):
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    intention = CharacterAppraisalEngine.appraise(
        user_input="Shut up and obey me.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
    )
    assert intention.stance == SituationalStance.MILD_DEFENSIVENESS
    assert any("submissively" in fb.lower() for fb in intention.forbidden_behaviors)


# Case 10: Inquiring about withheld privacy triggers POLITE_REFUSAL
def test_case_10_withheld_privacy_triggers_polite_refusal(char_def, char_state, rel_state, emo_state):
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    world = PersonalWorldContext(
        epistemic_directives=(
            EpistemicDirective(
                subject="parents",
                status=FactEpistemicStatus.PRIVATE,
                guidance="Boundary/Withheld: The topic of 'parents' is private.",
            ),
        )
    )
    intention = CharacterAppraisalEngine.appraise(
        user_input="Tell me about your parents.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
        personal_world=world,
    )
    assert intention.stance == SituationalStance.POLITE_REFUSAL


# Case 11: Severe fatigue triggers DISTRACTED_BRIEF
def test_case_11_severe_fatigue_triggers_distracted_brief(char_def, rel_state, emo_state):
    tired_state = CharacterState(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        mood=CharacterMood.TIRED,
        energy=0.15,
        stress=0.3,
        social_energy=0.2,
        confidence=0.5,
        irritation=0.0,
        loneliness=0.0,
        current_activity="Resting",
        current_location="Home",
    )
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    intention = CharacterAppraisalEngine.appraise(
        user_input="Hello Aevum.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(tired_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
    )
    assert intention.stance == SituationalStance.DISTRACTED_BRIEF


# Case 12: Banter triggers PLAYFUL_TEASING
def test_case_12_friendly_banter_triggers_playful_teasing(char_def, char_state, rel_state, emo_state):
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    intention = CharacterAppraisalEngine.appraise(
        user_input="Admit it, you're a total nerd about music.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
    )
    assert intention.stance == SituationalStance.PLAYFUL_TEASING


# Case 13: Aesthetic interest triggers AGREE_WARMLY
def test_case_13_shared_interest_triggers_agree_warmly(char_def, char_state, rel_state, emo_state):
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    intention = CharacterAppraisalEngine.appraise(
        user_input="What do you think of Ravel and Debussy's piano compositions?",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
    )
    assert intention.stance == SituationalStance.AGREE_WARMLY


# Case 14: Baseline greeting triggers NEUTRAL_INQUIRY
def test_case_14_baseline_greeting_triggers_neutral_inquiry(char_def, char_state, rel_state, emo_state):
    rel_ctx = RelationshipContextBuilder.build(rel_state)
    intention = CharacterAppraisalEngine.appraise(
        user_input="Hello there.",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=rel_ctx,
        emotion=CharacterEmotionContext.from_state(emo_state),
    )
    assert intention.stance == SituationalStance.NEUTRAL_INQUIRY


# Case 15: Core anchor immutability
def test_case_15_core_anchor_is_immutable(char_def):
    assert char_def.core_anchor is not None
    with pytest.raises(Exception):
        char_def.core_anchor.identity = None


# Case 16: Surface persona evolves safely
def test_case_16_surface_persona_evolves_safely(char_def):
    evolved = SurfacePersonaEvolutionService.evolve_surface_persona(
        definition=char_def,
        new_active_topics=["Chopin Nocturnes"],
    )
    assert evolved.version == char_def.version + 1
    assert "Chopin Nocturnes" in evolved.surface_persona.active_topics_of_interest
    assert evolved.core_anchor == char_def.core_anchor


# Case 17: Surface persona evolution blocks boundary violation
def test_case_17_evolution_blocks_boundary_violation(char_def):
    bad_pref = Preference(category="romance", item="romantic dating behavior", sentiment=PreferenceSentiment.LIKE)
    with pytest.raises(ValueError) as exc:
        SurfacePersonaEvolutionService.evolve_surface_persona(char_def, new_preferences=[bad_pref])
    assert "violates core boundary" in str(exc.value)


# Case 18: Default least privilege blocks ungranted permissions
@pytest.mark.asyncio
async def test_case_18_default_least_privilege():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        perm = PermissionService(session)
        assert await perm.is_permitted(Capability.NOTIFICATIONS) is False
        assert await perm.is_permitted(Capability.CAMERA) is False
    await engine.dispose()


# Case 19: File system permission is strictly non-grantable
@pytest.mark.asyncio
async def test_case_19_file_system_non_grantable():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        perm = PermissionService(session)
        with pytest.raises(ValueError):
            await perm.set_permission(Capability.FILE_SYSTEM, True)
    await engine.dispose()


# Case 20: Proactive urgency suppressed without permissions
def test_case_20_urgency_suppressed_without_permissions():
    now = datetime(2026, 9, 17, 6, 0, tzinfo=timezone.utc)
    c = ProactiveCandidate(id="c1", title="Finished score", importance=0.9, occurred_at=now)
    res = ProactiveUrgencyEngine.evaluate(c, now, notifications_permitted=False)
    assert res.should_trigger is False
    assert res.suppression_reason == "PERMISSIONS_DISABLED"


# Case 21: Proactive urgency suppressed during quiet hours
def test_case_21_urgency_suppressed_during_quiet_hours():
    # 23:30 in KL is 15:30 UTC
    night = datetime(2026, 9, 17, 15, 30, tzinfo=timezone.utc)
    c = ProactiveCandidate(id="c1", title="Finished score", importance=0.9, occurred_at=night)
    res = ProactiveUrgencyEngine.evaluate(c, night, notifications_permitted=True, timezone_name="Asia/Kuala_Lumpur")
    assert res.should_trigger is False
    assert res.suppression_reason == "QUIET_HOURS"


# Case 22: Absence > 24 hours generates non-clingy guidance
def test_case_22_absence_generates_anti_clingy_guidance():
    last = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
    presence = PresenceTracker.track_presence(last, now)
    assert "NEVER exhibit clinginess" in presence.absence_guidance


# Case 23: Focused activity sets realistic simulated delay
def test_case_23_focused_activity_sets_simulated_delay():
    now = datetime.now(timezone.utc)
    presence = PresenceTracker.track_presence(now, now, current_activity="piano_practice")
    assert presence.attention_level == "FOCUSED"
    assert presence.suggested_reply_delay_seconds > 0


# Case 24: Response Generator end-to-end generates clean envelope speech
@pytest.mark.asyncio
async def test_case_24_response_generator_end_to_end_clean(char_def, char_state, rel_state, emo_state):
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_response = AsyncMock(return_value=LLMResponse(
        content="<character_response>\n<character_speech>I was just working through a chord transition.</character_speech>\n</character_response>",
    ))

    context = CharacterResponseContext(
        user_input="What are you doing?",
        character=CharacterDefinitionContext.from_definition(char_def),
        character_state=CharacterStateContext.from_state(char_state),
        relationship=RelationshipContextBuilder.build(rel_state),
        emotion=CharacterEmotionContext.from_state(emo_state),
        memory=CharacterMemoryContext.from_memories(()),
        behavior=CharacterBehaviorContext.synthesize(
            CharacterStateContext.from_state(char_state),
            CharacterEmotionContext.from_state(emo_state),
        ),
        life=CharacterLifeContext(
            current_activity_summary="Resting",
            current_location_summary="Home",
            recent_experience_summary=(),
            life_guidance=("Currently resting.",),
        ),
    )

    generator = ResponseGenerator(provider=mock_provider)
    resp = await generator.generate_response(context)
    assert resp.content == "I was just working through a chord transition."
