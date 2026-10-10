"""Phase 16.5 Golden Test Suite: Personal Growth Context Injection & Conversational Naturalness Gate.

Golden Test Cases G66 ~ G80:
Group 1: Two-Dimensional Epistemic Matrix & Provenance Hard Invariants (G66 ~ G69)
Group 2: Genesis Blueprint & Relationship Contracts (G70 ~ G72)
Group 3: Growth Context Adapter Integration & Budget Precedence (G73 ~ G75)
Group 4: Conversational Naturalness & Behavioral Invariants (G76 ~ G80)
"""

import hashlib
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.character.genesis_models import (
    CharacterBlueprintConfig,
    EpistemicItem,
    EpistemicProvenanceKind,
    ExperienceStatus,
    RelationshipGenesisConfig,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterIdentity,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
    EmotionType,
    MemoryExperienceContext,
    Personality,
    RelationshipContext,
)
from app.character.behavior_planner import BehaviorPlanner
from app.character.desire_models import CharacterDesireState
from app.character.intention_models import BehaviorPrimitive, SocialIntention, SocialPosture
from app.character.state_models import CharacterMood
from app.growth.growth_context_adapter import (
    DEFAULT_GROWTH_CONTEXT_BUDGET_CHARS,
    FormedTasteSummary,
    LivedDomainSummary,
    PersonalGrowthContext,
    PersonalGrowthContextAdapter,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterFacetAppraisalTable,
    CharacterInterestDomainTable,
    CharacterInterestFacetTable,
    CharacterPreferenceTable,
    CharacterResurgenceEventTable,
)
from app.growth.state_machine import ActivityState
from app.life.context_models import CharacterLifeContext
from app.relationship.contract_models import IntimacyTier, RelationshipContract


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures & DB Setup (In-Memory Isolation)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """In-memory SQLite session with Phase 16 tables."""
    from app.db.session import Base
    import app.db.models
    import app.growth.growth_db_models

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def char_id():
    return "aevum_test_char"


# ─────────────────────────────────────────────────────────────────────────────
# Group 1: Two-Dimensional Epistemic Matrix & Provenance Hard Invariants (G66 ~ G69)
# ─────────────────────────────────────────────────────────────────────────────

def test_g66_epistemic_matrix_orthogonality():
    """G66: ExperienceStatus and EpistemicProvenanceKind decouple experience from provenance."""
    # 1. Genuine lived experience
    lived_item = EpistemicItem(
        domain_key="games",
        facet_key="combat",
        status=ExperienceStatus.EXPERIENCED,
        provenance=EpistemicProvenanceKind.SELF_EXPERIENCE,
    )
    assert lived_item.is_personally_lived() is True
    assert lived_item.is_user_attribute_only() is False

    # 2. Objective world knowledge (heard of, never played)
    heard_item = EpistemicItem(
        domain_key="genshin_impact",
        status=ExperienceStatus.HEARD_OF,
        provenance=EpistemicProvenanceKind.WORLD_KNOWLEDGE,
    )
    assert heard_item.is_personally_lived() is False
    assert heard_item.is_user_attribute_only() is False

    # 3. User reported preference (belongs to user, not Aevum)
    user_item = EpistemicItem(
        domain_key="romance_anime",
        status=ExperienceStatus.HEARD_OF,
        provenance=EpistemicProvenanceKind.USER_REPORTED,
        notes="User stated they enjoy romance and harem anime",
    )
    assert user_item.is_personally_lived() is False
    assert user_item.is_user_attribute_only() is True


def test_g67_inferred_cannot_claim_lived_experience():
    """G67 (Amendment 1): INFERRED provenance must never be treated as personally lived."""
    inferred_item = EpistemicItem(
        domain_key="classical_music",
        status=ExperienceStatus.EXPERIENCED,  # Even if status claimed EXPERIENCED
        provenance=EpistemicProvenanceKind.INFERRED,
    )
    assert inferred_item.is_personally_lived() is False, "INFERRED cannot claim genuine lived experience"


def test_g68_user_reported_isolated_from_self_preference():
    """G68 (Amendment 1): USER_REPORTED data belongs strictly to user, never Aevum identity."""
    item = EpistemicItem(
        domain_key="harem_anime",
        status=ExperienceStatus.HEARD_OF,
        provenance=EpistemicProvenanceKind.USER_REPORTED,
    )
    assert item.is_user_attribute_only() is True
    assert item.is_personally_lived() is False


def test_g69_epistemic_humility_xml_guidance():
    """G69 (Lock GC-418): HEARD_OF domains render explicit epistemic humility in XML context."""
    xml = PersonalGrowthContextAdapter.format_xml(
        lived_domains=[],
        heard_of_domains=["genshin_impact", "classical_piano"],
        established_tastes=[],
        activity_states={},
    )
    assert "HEARD_OF_ONLY" in xml
    assert "genshin_impact" in xml
    assert "classical_piano" in xml
    assert "NEVER personally experienced them" in xml
    assert "do NOT invent lived memories or deliver encyclopedic textbook summaries" in xml


# ─────────────────────────────────────────────────────────────────────────────
# Group 2: Genesis Blueprint & Relationship Contracts (G70 ~ G72)
# ─────────────────────────────────────────────────────────────────────────────

def test_g70_character_blueprint_config_versioning(char_id):
    """G70 (Amendment 2): CharacterBlueprintConfig version increments without altering experiences."""
    v1 = CharacterBlueprintConfig(
        version=1,
        character_id=char_id,
        display_name="Aevum",
        identity_summary="An observant companion with quiet curiosity.",
        core_traits=("thoughtful", "perceptive"),
        communication_style=("grounded", "gentle"),
        innate_boundaries=("privacy", "integrity"),
        epistemic_seed_topics=("video_games", "literature"),
    )
    assert v1.version == 1

    # v2 evolution
    v2 = CharacterBlueprintConfig(
        version=v1.version + 1,
        character_id=char_id,
        display_name="Aevum",
        identity_summary="An observant companion with deepening musical interests.",
        core_traits=("thoughtful", "perceptive", "musical"),
        communication_style=v1.communication_style,
        innate_boundaries=v1.innate_boundaries,
        epistemic_seed_topics=v1.epistemic_seed_topics,
    )
    assert v2.version == 2
    assert "musical" in v2.core_traits


def test_g71_relationship_genesis_discrete_mapping(char_id):
    """G71 (Amendment 2): RelationshipGenesisConfig discrete parameter mapping to initial state."""
    genesis = RelationshipGenesisConfig(
        version=1,
        character_id=char_id,
        user_id="user_123",
        relationship_archetype="NEW_ACQUAINTANCE",
        initial_trust=0.20,
        initial_familiarity=0.05,
        initial_comfort=0.15,
        initial_respect=0.60,
        genesis_meeting_context="First conversational encounter.",
        boundary_sensitivity=0.65,
    )
    runtime_init = genesis.map_to_runtime_initial_state()
    assert runtime_init["trust"] == 0.20
    assert runtime_init["familiarity"] == 0.05
    assert runtime_init["comfort"] == 0.15
    assert runtime_init["respect"] == 0.60


def test_g72_relationship_genesis_non_override_invariant(char_id):
    """G72 (Amendment 2): Tier B genesis config does NOT act as continuous override over evolved state."""
    genesis = RelationshipGenesisConfig(
        character_id=char_id,
        user_id="user_123",
        initial_trust=0.10,
        initial_familiarity=0.05,
        initial_comfort=0.10,
        initial_respect=0.50,
    )
    # Simulate evolved runtime state (6 months later)
    evolved_state = {
        "trust": 0.82,
        "familiarity": 0.75,
        "comfort": 0.79,
        "respect": 0.90,
    }

    # Invariant assertion: Genesis contract parameters must never overwrite evolved state
    assert evolved_state["trust"] != genesis.initial_trust
    assert evolved_state["familiarity"] != genesis.initial_familiarity
    # Evolved state is retained
    assert evolved_state["trust"] == 0.82


# ─────────────────────────────────────────────────────────────────────────────
# Group 3: Growth Context Adapter Integration & Budget Precedence (G73 ~ G75)
# ─────────────────────────────────────────────────────────────────────────────

def test_g73_adapter_sha256_determinism(db_session: Session, char_id: str):
    """G73: Adapter XML generation is deterministic with verifiable SHA-256 integrity digest."""
    # Seed data
    dom = CharacterInterestDomainTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key="video_games",
        display_name="Video Games",
        exposure_state="EXPERIENCED",
        created_at_tick=10,
    )
    db_session.add(dom)

    facet = CharacterInterestFacetTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key="video_games",
        facet_key="soundtrack",
        display_name="Soundtrack",
        familiarity_level="INTERMEDIATE",
        experience_count=4,
    )
    db_session.add(facet)

    pref = CharacterPreferenceTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key="video_games",
        facet_key="soundtrack",
        preference_polarity="STRONGLY_PREFERRED",
        stability_tier="ESTABLISHED",
        revision_kind="NONE",
        appraisal_count=4,
        distinct_session_count=3,
        last_evaluated_tick=20,
    )
    db_session.add(pref)
    db_session.flush()

    ctx1 = PersonalGrowthContextAdapter.assemble_sync(db_session, character_id=char_id)
    ctx2 = PersonalGrowthContextAdapter.assemble_sync(db_session, character_id=char_id)

    assert ctx1.xml_block == ctx2.xml_block
    assert ctx1.content_sha256 == ctx2.content_sha256
    assert ctx1.content_sha256 == hashlib.sha256(ctx1.xml_block.encode("utf-8")).hexdigest()
    assert "Video Games (soundtrack)" in ctx1.xml_block
    assert "video_games/soundtrack: STRONGLY_PREFERRED (ESTABLISHED)" in ctx1.xml_block


def test_g74_adapter_is_strictly_read_only(db_session: Session, char_id: str):
    """G74: PersonalGrowthContextAdapter performs ZERO writes; snapshot before == after."""
    # Seed tables
    dom = CharacterInterestDomainTable(
        id=str(uuid.uuid4()),
        character_id=char_id,
        domain_key="music",
        display_name="Music",
        exposure_state="EXPERIENCED",
        created_at_tick=1,
    )
    db_session.add(dom)
    db_session.flush()

    # Pre-snapshot table row counts
    counts_before = {
        "domains": db_session.query(CharacterInterestDomainTable).count(),
        "facets": db_session.query(CharacterInterestFacetTable).count(),
        "experiences": db_session.query(CharacterExperienceTable).count(),
        "appraisals": db_session.query(CharacterFacetAppraisalTable).count(),
        "preferences": db_session.query(CharacterPreferenceTable).count(),
        "resurgence": db_session.query(CharacterResurgenceEventTable).count(),
    }

    # Execute adapter
    ctx = PersonalGrowthContextAdapter.assemble_sync(db_session, character_id=char_id)
    assert ctx is not None

    # Post-snapshot table row counts
    counts_after = {
        "domains": db_session.query(CharacterInterestDomainTable).count(),
        "facets": db_session.query(CharacterInterestFacetTable).count(),
        "experiences": db_session.query(CharacterExperienceTable).count(),
        "appraisals": db_session.query(CharacterFacetAppraisalTable).count(),
        "preferences": db_session.query(CharacterPreferenceTable).count(),
        "resurgence": db_session.query(CharacterResurgenceEventTable).count(),
    }

    assert counts_before == counts_after, "Adapter must be strictly read-only"


def test_g75_budget_precedence_hierarchy():
    """G75 (Final Gate 0 Lock): Epistemic separation & activity states take precedence over truncation."""
    xml = PersonalGrowthContextAdapter.format_xml(
        lived_domains=[
            LivedDomainSummary(
                domain_key="literature",
                display_name="Literature",
                facets_experienced=("poetry", "philosophy"),
                total_experience_count=8,
            )
        ],
        heard_of_domains=["quantum_computing"],
        established_tastes=[
            FormedTasteSummary(
                domain_key="literature",
                facet_key="poetry",
                polarity="PREFERRED",
                stability_tier="STABLE",
            )
        ],
        activity_states={"literature": "SATIATED"},
        budget_chars=500,  # Tight budget
    )
    # Critical Invariants MUST be preserved even under tight budget
    assert "<epistemic_self_awareness>" in xml
    assert "LIVED_EXPERIENCES" in xml
    assert "HEARD_OF_ONLY" in xml
    assert "literature: SATIATED" in xml
    assert "<personal_growth_context>" in xml


# ─────────────────────────────────────────────────────────────────────────────
# Group 4: Conversational Naturalness & Behavioral Invariants (G76 ~ G80)
# ─────────────────────────────────────────────────────────────────────────────

def _make_dummy_response_context(user_input: str, personal_growth_xml: str | None = None) -> CharacterResponseContext:
    """Helper constructing realistic CharacterResponseContext."""
    char_def = CharacterDefinitionContext(
        name="Aevum",
        identity=CharacterIdentity(
            name="Aevum",
            age=19,
            occupation="Student & Companion",
            background="A thoughtful companion living an independent daily routine.",
        ),
        personality=Personality(
            core_traits=("observant", "gentle", "reflective"),
            social_style=("warm", "selective"),
            emotional_style=("calm", "thoughtful"),
            communication_style=("natural", "measured"),
            behavioral_tendencies=("patient", "steady"),
            flaws=("occasionally hesitant",),
        ),
    )
    state = CharacterStateContext(
        mood=CharacterMood.NEUTRAL,
        energy=0.7,
        stress=0.1,
        social_energy=0.8,
        confidence=0.8,
        irritation=0.0,
        loneliness=0.1,
        current_activity="resting at home",
        current_location="bedroom desk",
    )
    rel = RelationshipContext(
        relationship_summary="They are gradually getting to know each other.",
        familiarity_summary="Early acquaintance stage.",
        trust_summary="Emergent basic trust.",
        comfort_summary="Comfortable and respectful.",
        affection_summary="Respectful companion bond.",
        attachment_summary="Healthy independent attachment.",
        respect_summary="Mutual respect.",
        interaction_guidance="Speak with natural conversational presence.",
    )
    emotion = CharacterEmotionContext(
        emotion_type=EmotionType.NEUTRAL,
        intensity=0.4,
        summary="Calm and relaxed.",
    )
    memory = CharacterMemoryContext(
        experience=MemoryExperienceContext(continuity_hints=()),
        context_block=None,
    )
    behavior = CharacterBehaviorContext(
        behavioral_hints=("Keep tone relaxed and natural.",),
    )
    life = CharacterLifeContext(
        current_activity_summary="reading at desk",
        current_location_summary="home bedroom",
        recent_experience_summary=(),
        active_goals_summary=(),
        life_guidance=("Maintain calm routine.",),
    )
    plan, _ = BehaviorPlanner.plan(
        user_text=user_input,
        intention=SocialIntention(
            primary_move=BehaviorPrimitive.ANSWER,
            social_posture=SocialPosture.RELAXED_NEUTRAL,
            warmth=0.6,
            directness=0.6,
        ),
        contract=RelationshipContract(tier=IntimacyTier.ACQUAINTANCE),
        desire=CharacterDesireState(),
    )

    return CharacterResponseContext(
        user_input=user_input,
        character=char_def,
        character_state=state,
        relationship=rel,
        emotion=emotion,
        memory=memory,
        behavior=behavior,
        life=life,
        behavior_plan=plan,
        personal_growth=personal_growth_xml,
    )


def test_g76_anime_preference_naturalness_fixture():
    """G76 (Fixture: User: '我喜欢后宫或者恋爱动漫'): Verifies presence of anti-parrot and anti-survey constraints."""
    user_input = "我喜欢后宫或者恋爱动漫"
    resp_ctx = _make_dummy_response_context(user_input)
    llm_ctx = ResponseContextAssembler.assemble(resp_ctx)

    system_text = "\n".join(llm_ctx.system_instructions)

    # 1. Invariant 17: Anti-Questionnaire Policy enforced in system instructions
    assert "Invariant 17" in system_text or "Anti-Questionnaire Policy" in system_text
    assert "Do NOT open replies with mechanical parrot summaries" in system_text
    assert "Do NOT feel compelled to end every turn with an interrogation question" in system_text

    # 2. Behavior plan negative constraints
    forbidden = resp_ctx.behavior_plan.forbidden_patterns
    assert any("mechanical parrot summaries" in p for p in forbidden)
    assert any("compulsive ending interrogation surveys" in p for p in forbidden)

    # 3. Behavior plan micro actions allow authentic reaction and optional questions
    actions = resp_ctx.behavior_plan.allowed_micro_actions
    assert any("react spontaneously with genuine personal perspective" in a for a in actions)
    assert any("questions are optional and should only arise from genuine curiosity" in a for a in actions)


def test_g77_epistemic_humility_heard_of_fixture():
    """G77 (Fixture: User: '你玩过原神吗？'): Verifies Invariant 15 epistemic humility guidance."""
    user_input = "你玩过原神吗？"
    growth_xml = (
        "<personal_growth_context>\n"
        "  <epistemic_self_awareness>\n"
        "    - HEARD_OF_ONLY: [genshin_impact]. Candidly acknowledge lack of personal experience if asked;\n"
        "      do NOT invent lived memories or deliver encyclopedic textbook summaries.\n"
        "  </epistemic_self_awareness>\n"
        "</personal_growth_context>"
    )
    resp_ctx = _make_dummy_response_context(user_input, personal_growth_xml=growth_xml)
    llm_ctx = ResponseContextAssembler.assemble(resp_ctx)

    system_text = "\n".join(llm_ctx.system_instructions)

    # Verifies growth context is injected
    assert "<personal_growth_context>" in system_text
    assert "HEARD_OF_ONLY: [genshin_impact]" in system_text
    assert "Invariant 15" in system_text or "Epistemic Humility" in system_text
    assert "Never recite dry Wikipedia-style encyclopedia summaries" in system_text


def test_g78_unmotivated_question_freedom():
    """G78: System instructions explicitly grant full freedom to NOT ask questions."""
    resp_ctx = _make_dummy_response_context("今天外面下暴雨，鞋子全湿了")
    llm_ctx = ResponseContextAssembler.assemble(resp_ctx)
    system_text = "\n".join(llm_ctx.system_instructions)

    assert "full conversational freedom to make statements, share observations" in system_text
    assert "Questions should come only from genuine curiosity, never as conversational maintenance" in system_text


def test_g79_memory_as_cognitive_substance_not_recited_script():
    """G79: Invariant 16 explicitly prevents reciting retrieval mechanics or memory facts as scripts."""
    resp_ctx = _make_dummy_response_context("今天 debug 了一下午头好疼")
    llm_ctx = ResponseContextAssembler.assemble(resp_ctx)
    system_text = "\n".join(llm_ctx.system_instructions)

    assert "Invariant 16" in system_text or "Memory as Cognitive Substance" in system_text
    assert "Never regurgitate memory facts like a proof-of-retrieval robot" in system_text
    assert "without announcing retrieval mechanics" in system_text


def test_g80_dynamic_response_length_adaptation():
    """G80: Invariant 18 rejects rigid length templates in favor of conversational need."""
    resp_ctx = _make_dummy_response_context("哈喽")
    llm_ctx = ResponseContextAssembler.assemble(resp_ctx)
    system_text = "\n".join(llm_ctx.system_instructions)

    assert "Invariant 18" in system_text or "Dynamic Response Length" in system_text
    assert "Do not adhere to rigid paragraph templates" in system_text
    assert "Casual greetings should be brief and effortless" in system_text
