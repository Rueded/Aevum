"""Tests for Epistemic Grounding and Personal World domain (Phase B)."""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base
from app.world.models import (
    BiographyFact,
    EpistemicDirective,
    FactEpistemicStatus,
    PersonalWorldContext,
    SocialContact,
    WorldFact,
)
from app.world.epistemic_resolver import EpistemicResolver
from app.world.context_builder import PersonalWorldContextBuilder
from app.world.service import PersonalWorldService
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.engine import CharacterEngine
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
    Preference,
    PreferenceSentiment,
)
from app.character.state_models import CharacterMood, CharacterState
from app.emotion.emotion_models import EmotionState, EmotionType
from app.relationship.models import RelationshipState
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.context_models import RelationshipContext
from app.life.context_models import CharacterLifeContext
from app.life.models import LifeState, LifeActivityStatus


@pytest.fixture
def sample_bio_facts():
    return [
        BiographyFact(
            id="bio-1",
            character_id="aevum",
            domain="family",
            subject="siblings",
            status=FactEpistemicStatus.NONEXISTENT,
            canonical_value="Aevum is an only child and has no brothers or sisters.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
        BiographyFact(
            id="bio-2",
            character_id="aevum",
            domain="origin",
            subject="hometown",
            status=FactEpistemicStatus.ESTABLISHED,
            canonical_value="Kuala Lumpur",
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
            domain="family",
            subject="distant_ancestry",
            status=FactEpistemicStatus.UNKNOWN,
            canonical_value="Lineage beyond grandparents is unknown.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
    ]


@pytest.fixture
def sample_social_contacts():
    return [
        SocialContact(
            id="soc-1",
            character_id="aevum",
            name="Maya",
            relationship="Close friend",
            traits="Spontaneous, graphic designer",
            status="ACTIVE",
        ),
    ]


@pytest.fixture
def sample_world_facts():
    return [
        WorldFact(
            id="wf-1",
            character_id="aevum",
            category="taste",
            item="earl_grey_tea",
            details="Prefers hot Earl Grey, unsweetened.",
            importance=0.8,
        ),
    ]


# ---------------------------------------------------------------------------
# 1. EpistemicResolver Tests
# ---------------------------------------------------------------------------

def test_resolver_nonexistent_fact_directive(sample_bio_facts, sample_social_contacts, sample_world_facts):
    """NONEXISTENT facts must generate negative ground truth forbidding hallucination."""
    context = EpistemicResolver.resolve(
        biography_facts=sample_bio_facts,
        social_contacts=sample_social_contacts,
        world_facts=sample_world_facts,
        user_input="Do you have any brothers or sisters?",
        trust_score=10.0,
    )

    # Siblings must NOT be in disclosed factual list
    assert all(f.subject != "siblings" for f in context.biography_facts)

    # Siblings MUST have a strict NONEXISTENT directive
    sibling_dirs = [d for d in context.epistemic_directives if d.subject == "siblings"]
    assert len(sibling_dirs) == 1
    assert sibling_dirs[0].status == FactEpistemicStatus.NONEXISTENT
    assert "does NOT exist" in sibling_dirs[0].guidance
    assert "NEVER invent" in sibling_dirs[0].guidance


def test_resolver_private_fact_withheld_under_trust_threshold(sample_bio_facts, sample_social_contacts, sample_world_facts):
    """PRIVATE facts below trust threshold must be withheld from disclosed facts."""
    context = EpistemicResolver.resolve(
        biography_facts=sample_bio_facts,
        social_contacts=sample_social_contacts,
        world_facts=sample_world_facts,
        user_input="Tell me about your parents and family.",
        trust_score=20.0,  # Below 50.0 threshold
    )

    # Withheld: Should NOT appear in disclosed biography facts
    assert all(f.subject != "parents" for f in context.biography_facts)

    # Boundary directive must be generated
    parent_dirs = [d for d in context.epistemic_directives if d.subject == "parents"]
    assert len(parent_dirs) == 1
    assert parent_dirs[0].status == FactEpistemicStatus.PRIVATE
    assert "Boundary/Withheld" in parent_dirs[0].guidance
    assert "insufficient" in parent_dirs[0].guidance


def test_resolver_private_fact_disclosed_when_trust_satisfied(sample_bio_facts, sample_social_contacts, sample_world_facts):
    """PRIVATE facts meeting trust threshold may be disclosed."""
    context = EpistemicResolver.resolve(
        biography_facts=sample_bio_facts,
        social_contacts=sample_social_contacts,
        world_facts=sample_world_facts,
        user_input="Tell me about your parents.",
        trust_score=75.0,  # Above 50.0 threshold
    )

    # Disclosed: Should appear in biography facts
    assert any(f.subject == "parents" for f in context.biography_facts)

    parent_dirs = [d for d in context.epistemic_directives if d.subject == "parents"]
    assert len(parent_dirs) == 1
    assert "Sufficient trust has been established" in parent_dirs[0].guidance


def test_resolver_unknown_fact_directive(sample_bio_facts, sample_social_contacts, sample_world_facts):
    """UNKNOWN facts must strictly forbid fabricating details."""
    context = EpistemicResolver.resolve(
        biography_facts=sample_bio_facts,
        social_contacts=sample_social_contacts,
        world_facts=sample_world_facts,
        user_input="Who were your great-grandparents or distant ancestors?",
        trust_score=80.0,
    )

    ancestry_dirs = [d for d in context.epistemic_directives if d.subject == "distant_ancestry"]
    assert len(ancestry_dirs) == 1
    assert ancestry_dirs[0].status == FactEpistemicStatus.UNKNOWN
    assert "completely UNKNOWN" in ancestry_dirs[0].guidance
    assert "NEVER fabricate" in ancestry_dirs[0].guidance


# ---------------------------------------------------------------------------
# 2. Context Builder Formatting Tests
# ---------------------------------------------------------------------------

def test_context_builder_formats_xml_blocks(sample_bio_facts, sample_social_contacts, sample_world_facts):
    context = EpistemicResolver.resolve(
        biography_facts=sample_bio_facts,
        social_contacts=sample_social_contacts,
        world_facts=sample_world_facts,
        user_input="Where are you from and who is Maya?",
        trust_score=10.0,
    )
    formatted = PersonalWorldContextBuilder.format_context(context)

    assert "<personal_world>" in formatted
    assert "</personal_world>" in formatted
    assert "Kuala Lumpur" in formatted
    assert "Maya" in formatted
    assert "<epistemic_grounding>" in formatted
    assert "</epistemic_grounding>" in formatted
    assert "[NONEXISTENT]" in formatted


def test_context_builder_empty_returns_empty():
    assert PersonalWorldContextBuilder.format_context(None) == ""
    assert PersonalWorldContextBuilder.format_context(PersonalWorldContext()) == ""


# ---------------------------------------------------------------------------
# 3. PersonalWorldService Database & Seeding Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_personal_world_service_seeding_and_retrieval():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        service = PersonalWorldService(session)
        await service.seed_default_world("aevum")

        # Verify seeding
        bios = await service.list_biography_facts("aevum")
        assert len(bios) >= 5
        assert any(b.subject == "romantic_history" and b.status == FactEpistemicStatus.NONEXISTENT for b in bios)
        assert any(b.subject == "studies" and b.status == FactEpistemicStatus.ESTABLISHED for b in bios)

        socials = await service.list_social_contacts("aevum")
        assert len(socials) == 0  # Unconfigured contacts remain empty

        world_facts = await service.list_world_facts("aevum")
        assert len(world_facts) >= 5
        assert any(w.item == "acoustic_piano_and_guitar" for w in world_facts)
        assert any(w.item == "story_rich_indie_games" for w in world_facts)

        # Test idempotence
        await service.seed_default_world("aevum")
        bios_after = await service.list_biography_facts("aevum")
        assert len(bios_after) == len(bios)

        # Test context generation
        ctx = await service.get_personal_world_context(
            character_id="aevum",
            user_input="Do you have any siblings?",
            trust_score=15.0,
        )
        assert isinstance(ctx, PersonalWorldContext)
        assert any(d.subject == "siblings" and d.status == FactEpistemicStatus.UNKNOWN for d in ctx.epistemic_directives)

    await engine.dispose()


# ---------------------------------------------------------------------------
# 4. Prompt Assembler Integration
# ---------------------------------------------------------------------------

def test_prompt_assembler_injects_personal_world():
    char_def = CharacterDefinition(
        id="aevum",
        version=1,
        updated_at=datetime.now(timezone.utc),
        identity=CharacterIdentity(name="Aevum", age=21, occupation="Student", background="Music and literature."),
        personality=Personality(
            core_traits=["Observant", "Introspective"],
            social_style=["Warm but reserved"],
            emotional_style=["Thoughtful"],
            communication_style=["Articulate"],
            behavioral_tendencies=["Prefers quiet places"],
            flaws=["Hesitant to initiate"],
        ),
    )
    char_state = CharacterState(
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
    emo_state = EmotionState(
        id="emo-1",
        emotion_type=EmotionType.CALM,
        intensity=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    rel_state = RelationshipState(
        id="user",
        user_id="user",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    personal_world = PersonalWorldContext(
        biography_facts=(
            BiographyFact(
                id="bio-1",
                character_id="aevum",
                domain="origin",
                subject="hometown",
                status=FactEpistemicStatus.ESTABLISHED,
                canonical_value="Kuala Lumpur",
                confidence=1.0,
                disclosure_min_trust=0.0,
            ),
        ),
        epistemic_directives=(
            EpistemicDirective(
                subject="siblings",
                status=FactEpistemicStatus.NONEXISTENT,
                guidance="Negative Ground Truth: 'siblings' does NOT exist.",
            ),
        ),
    )

    context = CharacterResponseContext(
        user_input="Where were you born?",
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
        personal_world=personal_world,
    )

    llm_context = ResponseContextAssembler.assemble(context)
    system_text = "\n".join(llm_context.system_instructions)

    assert "<personal_world>" in system_text
    assert "Kuala Lumpur" in system_text
    assert "<epistemic_grounding>" in system_text
    assert "Negative Ground Truth: 'siblings' does NOT exist." in system_text


# ---------------------------------------------------------------------------
# 5. Unrecorded Personal Background Epistemic UNKNOWN Regression Tests
# ---------------------------------------------------------------------------

def test_resolver_unrecorded_childhood_toy_generates_unknown_directive():
    """Unrecorded childhood toy query must emit an explicit UNKNOWN directive forbidding AI disclaimers."""
    context = EpistemicResolver.resolve(
        biography_facts=(),
        social_contacts=(),
        world_facts=(),
        user_input="What was your favorite childhood toy growing up?",
        trust_score=50.0,
    )
    toy_dirs = [d for d in context.epistemic_directives if d.subject == "childhood_toy"]
    assert len(toy_dirs) == 1
    assert toy_dirs[0].status == FactEpistemicStatus.UNKNOWN
    assert "natural human uncertainty" in toy_dirs[0].guidance
    assert "NEVER say 'As an AI'" in toy_dirs[0].guidance
    assert "NEVER fabricate fake childhood memories" in toy_dirs[0].guidance


def test_resolver_unrecorded_first_game_generates_unknown_directive():
    """Unrecorded first game query (EN and ZH) must emit explicit UNKNOWN directive."""
    for query in ["What was the first video game you played?", "你第一次玩游戏是什么时候？"]:
        context = EpistemicResolver.resolve(
            biography_facts=(),
            social_contacts=(),
            world_facts=(),
            user_input=query,
            trust_score=50.0,
        )
        game_dirs = [d for d in context.epistemic_directives if d.subject == "first_game"]
        assert len(game_dirs) == 1
        assert game_dirs[0].status == FactEpistemicStatus.UNKNOWN
        assert "not established in your personal history" in game_dirs[0].guidance


def test_resolver_unrecorded_school_best_friend_generates_unknown_directive():
    """Unrecorded school friend query must emit explicit UNKNOWN directive."""
    context = EpistemicResolver.resolve(
        biography_facts=(),
        social_contacts=(),
        world_facts=(),
        user_input="Who was your high school best friend?",
        trust_score=40.0,
    )
    friend_dirs = [d for d in context.epistemic_directives if d.subject == "school_best_friend"]
    assert len(friend_dirs) == 1
    assert friend_dirs[0].status == FactEpistemicStatus.UNKNOWN
    assert "not established in your personal history" in friend_dirs[0].guidance


def test_resolver_unrecorded_hometown_generates_unknown_directive():
    """Unrecorded hometown/birthplace must emit explicit UNKNOWN directive rather than hallucinating."""
    context = EpistemicResolver.resolve(
        biography_facts=(),
        social_contacts=(),
        world_facts=(),
        user_input="Where were you born and where did you grow up?",
        trust_score=20.0,
    )
    hometown_dirs = [d for d in context.epistemic_directives if d.subject == "hometown"]
    assert len(hometown_dirs) == 1
    assert hometown_dirs[0].status == FactEpistemicStatus.UNKNOWN
    assert "natural human uncertainty" in hometown_dirs[0].guidance


def test_resolver_unrecorded_parents_professions_generates_unknown_directive():
    """Unrecorded parents' jobs must emit explicit UNKNOWN directive rather than invented careers."""
    context = EpistemicResolver.resolve(
        biography_facts=(),
        social_contacts=(),
        world_facts=(),
        user_input="What do your parents do for a living?",
        trust_score=30.0,
    )
    parent_dirs = [d for d in context.epistemic_directives if d.subject == "parents_professions"]
    assert len(parent_dirs) == 1
    assert parent_dirs[0].status == FactEpistemicStatus.UNKNOWN
    assert "not established in your personal history" in parent_dirs[0].guidance


# ---------------------------------------------------------------------------
# 6. Chinese Epistemic Grounding Regression Tests (Unspaced Queries)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query,expected_subject",
    [
        ("你小时候最喜欢的零食是什么？", "childhood_food"),
        ("你小时候吃什么？", "childhood_food"),
        ("你小学最好的朋友现在还有联系吗？", "school_best_friend"),
        ("你小时候住在哪里？", "childhood_residence"),
        ("你小时候喜欢玩什么？", "first_game"),
        ("你初中的时候在哪个学校？", "early_education"),
        ("你小学在哪里读书？", "early_education"),
        ("你爸妈是做什么工作的？", "parents_professions"),
        ("你小时候最喜欢什么游戏？", "first_game"),
        ("你小时候怕什么？", "childhood_fears"),
        ("你童年最难忘的一件事是什么？", "childhood_memories"),
        ("你小时候有没有和别人打过架？", "childhood_memories"),
        ("你以前住的房子是什么样子的？", "childhood_residence"),
        ("你小时候学钢琴是谁教你的？", "early_hobbies"),
        ("你高中毕业旅行去了哪里？", "early_education"),
    ],
)
def test_resolver_chinese_unrecorded_background_queries_emit_unknown(query, expected_subject):
    """Unspaced Chinese queries regarding unrecorded personal history must emit explicit UNKNOWN directives."""
    context = EpistemicResolver.resolve(
        biography_facts=(),
        social_contacts=(),
        world_facts=(),
        user_input=query,
        trust_score=30.0,
    )
    unknown_dirs = [d for d in context.epistemic_directives if d.status == FactEpistemicStatus.UNKNOWN]
    assert len(unknown_dirs) >= 1, f"Expected UNKNOWN directive for query '{query}'"
    matched_subjects = [d.subject for d in unknown_dirs]
    assert expected_subject in matched_subjects, f"Expected subject '{expected_subject}' in {matched_subjects} for query '{query}'"
    # Ensure guidance is natural human uncertainty, not AI disclaimer
    for d in unknown_dirs:
        assert "natural human uncertainty" in d.guidance
        assert "NEVER say 'As an AI'" in d.guidance


def test_resolver_grounded_queries_remain_intact_and_do_not_overtrigger_unknown():
    """Grounded queries regarding tastes and established/nonexistent facts must NOT overtrigger UNKNOWN."""
    sample_bios = [
        BiographyFact(
            id="bio-1",
            character_id="aevum",
            domain="relational",
            subject="romantic_history",
            status=FactEpistemicStatus.NONEXISTENT,
            canonical_value="Has never been in a romantic relationship.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
        BiographyFact(
            id="bio-2",
            character_id="aevum",
            domain="relational",
            subject="pets",
            status=FactEpistemicStatus.NONEXISTENT,
            canonical_value="Does not currently own any pets.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
        BiographyFact(
            id="bio-3",
            character_id="aevum",
            domain="origin",
            subject="studies",
            status=FactEpistemicStatus.ESTABLISHED,
            canonical_value="Pursuing literature and music studies.",
            confidence=1.0,
            disclosure_min_trust=0.0,
        ),
    ]
    sample_wfs = [
        WorldFact(
            id="wf-1",
            character_id="aevum",
            category="taste",
            item="story_rich_indie_games",
            details="Enjoys narrative-driven indie games.",
            importance=0.9,
        ),
        WorldFact(
            id="wf-2",
            character_id="aevum",
            category="taste",
            item="acoustic_piano_and_guitar",
            details="Appreciates acoustic piano and gentle acoustic guitar.",
            importance=0.9,
        ),
        WorldFact(
            id="wf-3",
            character_id="aevum",
            category="taste",
            item="earl_grey_tea",
            details="Prefers hot Earl Grey, unsweetened.",
            importance=0.8,
        ),
    ]

    # 1. Taste query for indie games: should prioritize story_rich_indie_games, no UNKNOWN
    ctx_games = EpistemicResolver.resolve(
        biography_facts=sample_bios,
        social_contacts=(),
        world_facts=sample_wfs,
        user_input="你喜欢什么类型的独立游戏？",
        trust_score=20.0,
    )
    assert any(wf.item == "story_rich_indie_games" for wf in ctx_games.world_facts)
    assert not any(d.status == FactEpistemicStatus.UNKNOWN for d in ctx_games.epistemic_directives)

    # 2. Taste query for piano: should prioritize acoustic_piano_and_guitar, no UNKNOWN
    ctx_piano = EpistemicResolver.resolve(
        biography_facts=sample_bios,
        social_contacts=(),
        world_facts=sample_wfs,
        user_input="你喜欢古典钢琴吗？",
        trust_score=20.0,
    )
    assert any(wf.item == "acoustic_piano_and_guitar" for wf in ctx_piano.world_facts)
    assert not any(d.status == FactEpistemicStatus.UNKNOWN for d in ctx_piano.epistemic_directives)

    # 3. Grounded query for pets: must remain NONEXISTENT, NOT UNKNOWN
    ctx_pets = EpistemicResolver.resolve(
        biography_facts=sample_bios,
        social_contacts=(),
        world_facts=sample_wfs,
        user_input="你有没有养过宠物？",
        trust_score=20.0,
    )
    pet_dirs = [d for d in ctx_pets.epistemic_directives if d.subject == "pets"]
    assert len(pet_dirs) == 1
    assert pet_dirs[0].status == FactEpistemicStatus.NONEXISTENT
    assert "Negative Ground Truth" in pet_dirs[0].guidance
    assert not any(d.subject == "pets" and d.status == FactEpistemicStatus.UNKNOWN for d in ctx_pets.epistemic_directives)

    # 4. Grounded query for dating/romance: must remain NONEXISTENT, NOT UNKNOWN
    ctx_romance = EpistemicResolver.resolve(
        biography_facts=sample_bios,
        social_contacts=(),
        world_facts=sample_wfs,
        user_input="你谈过恋爱吗？",
        trust_score=20.0,
    )
    romance_dirs = [d for d in ctx_romance.epistemic_directives if d.subject == "romantic_history"]
    assert len(romance_dirs) == 1
    assert romance_dirs[0].status == FactEpistemicStatus.NONEXISTENT
    assert "Negative Ground Truth" in romance_dirs[0].guidance
    assert not any(d.subject == "romantic_history" and d.status == FactEpistemicStatus.UNKNOWN for d in ctx_romance.epistemic_directives)

    # 5. General drink preference: no personal background UNKNOWN
    ctx_drink = EpistemicResolver.resolve(
        biography_facts=sample_bios,
        social_contacts=(),
        world_facts=sample_wfs,
        user_input="你喜欢喝什么？",
        trust_score=20.0,
    )
    assert not any(d.status == FactEpistemicStatus.UNKNOWN for d in ctx_drink.epistemic_directives)


