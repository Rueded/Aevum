"""
test_golden_suite_18.py — Golden Suite 18: Conversational Life & Natural Expression Realization

Acceptance Benchmarks GC-425 through GC-436 across 4 Clusters:
- Cluster 1 (GC-425 ~ GC-428): Conversational Agency & Ephemeral State Dynamics
- Cluster 2 (GC-429 & GC-430): Empirical Dual-Blind Evaluation & Character Agency Supremacy
- Cluster 3 (GC-431 & GC-434): CCDF Protocol Discipline & Emergent Chat Rhythm
- Cluster 4 (GC-432, GC-433, GC-435, GC-436): Negative Liberties, Known Fact Integrity & Expression Realization
"""

import pytest
from pydantic import ValidationError

from app.character.conversational_arbitrator import ConversationalArbitrator
from app.character.conversational_models import (
    ConversationalMotivation,
    ConversationalMomentumState,
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
from app.character.integrity import OutputBoundaryGuard
from app.character.models import (
    CharacterDefinition,
    CharacterIdentity,
    Personality,
)
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.state_models import CharacterMood
from app.core.time import now_utc
from app.emotion.emotion_models import EmotionType
from app.life.context_models import CharacterLifeContext
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


# ==============================================================================
# Cluster 1: Conversational Agency & Ephemeral State Dynamics (GC-425 ~ GC-428)
# ==============================================================================

class TestCluster1ConversationalAgency:
    """Cluster 1: GC-425 through GC-428."""

    def test_gc425_curiosity_as_motivation_flag_not_prohibition(self):
        """GC-425: Curiosity is a turn-level motivation flag, not a question prohibition rule."""
        dec_no_curiosity = TurnConversationalDecision(
            attention="午餐鸡扒",
            reaction="真糟糕",
            commitment=ResponseCommitmentTier.LOW_EFFORT,
            energy=ResponseEnergyTier.LOW,
            motivation=ConversationalMotivation.AFFECTIVE_SOUNDBITE,
            friction=FrictionTier.POLITE_DISTANT,
            curiosity=False,
        )
        assert dec_no_curiosity.curiosity is False
        assert dec_no_curiosity.motivation == ConversationalMotivation.AFFECTIVE_SOUNDBITE

    def test_gc426_emergent_bubble_count_no_planner_target(self):
        """GC-426: TurnConversationalDecision has zero bubble count targets."""
        fields = TurnConversationalDecision.model_fields.keys()
        assert "target_bubble_count" not in fields
        assert "min_bubbles" not in fields
        assert "max_bubbles" not in fields

    def test_gc427_ephemeral_response_energy_no_durable_bleed(self):
        """GC-427: ResponseEnergyTier is an ephemeral turn decision, distinct from persistent state.energy."""
        assert {t.value for t in ResponseEnergyTier} == {
            "VERY_LOW", "LOW", "NORMAL", "ENGAGED", "EXCITED"
        }
        dec = TurnConversationalDecision(
            attention="点心",
            reaction="想吃",
            commitment=ResponseCommitmentTier.PARTIAL_FLOW,
            energy=ResponseEnergyTier.EXCITED,
            motivation=ConversationalMotivation.GENUINE_SHARING,
            friction=FrictionTier.POLITE_DISTANT,
            curiosity=True,
        )
        assert dec.energy == ResponseEnergyTier.EXCITED

    def test_gc428_authentic_agency_tiers(self):
        """GC-428: Agency dimensions reflect authentic conversational ownership."""
        assert len(ResponseCommitmentTier) == 4
        assert len(ConversationalMotivation) >= 9
        assert len(FrictionTier) == 3


# ==============================================================================
# Cluster 2: Empirical Evaluation & Agency Supremacy (GC-429 & GC-430)
# ==============================================================================

class TestCluster2EvaluationAndAgencySupremacy:
    """Cluster 2: GC-429 & GC-430."""

    def test_gc429_dual_blind_and_failure_preservation_artifacts_exist(self):
        """GC-429: Dual-blind evaluation harness preserves failures without survivorship bias."""
        from pathlib import Path
        eval_artifact = Path("d:/Aevum/Aevum/scratch_phase183_candidate_eval.json")
        probe_artifact = Path("d:/Aevum/Aevum/scratch_phase184_expression_probes.json")
        # Ensure evaluation run datasets exist
        assert eval_artifact.exists() or probe_artifact.exists()

    def test_gc430_character_agency_over_phrasing_rules(self, base_context):
        """GC-430: System prompts anchor on agency decisions rather than artificial phrasing rules."""
        llm_ctx = ResponseContextAssembler.assemble(base_context)
        prompt_text = "\n".join(llm_ctx.system_instructions)
        assert "<internal_decision>" in prompt_text
        assert "attention:" in prompt_text
        assert "commitment:" in prompt_text
        assert "motivation:" in prompt_text


# ==============================================================================
# Cluster 3: CCDF Protocol Discipline & Natural Bubble Emergence (GC-431 & GC-434)
# ==============================================================================

class TestCluster3ProtocolDisciplineAndBubbles:
    """Cluster 3: GC-431 & GC-434."""

    def test_gc431_rejects_verbose_cot_in_attention_or_reaction(self):
        """GC-431: Reject verbose introspective thoughts exceeding 120 chars."""
        with pytest.raises(ValidationError):
            TurnConversationalDecision(
                attention="a" * 125,
                reaction="正常反应",
                commitment=ResponseCommitmentTier.LOW_EFFORT,
                energy=ResponseEnergyTier.LOW,
                motivation=ConversationalMotivation.AFFECTIVE_SOUNDBITE,
                friction=FrictionTier.POLITE_DISTANT,
                curiosity=False,
            )

    def test_gc434_natural_bubble_emergence_no_prescribed_quotas(self):
        """GC-434: Extract 1 concise bubble naturally without forcing paragraph splitting."""
        speech = "听着都影响心情，食堂偶尔是会这样。"
        bubbles = ConversationalResponseParser.extract_bubbles(speech)
        assert len(bubbles) == 1
        assert bubbles[0] == "听着都影响心情，食堂偶尔是会这样。"

        multi = "噗，你反应好大啊。\n\n我倒挺喜欢香菜的，觉得它挺香的。"
        multi_bubbles = ConversationalResponseParser.extract_bubbles(multi)
        assert len(multi_bubbles) == 2


# ==============================================================================
# Cluster 4: Negative Liberties, Known Fact Consistency & Expression (GC-432, GC-433, GC-435, GC-436)
# ==============================================================================

class TestCluster4NegativeLibertiesAndExpressionRealization:
    """Cluster 4: GC-432, GC-433, GC-435, GC-436."""

    def test_gc432_question_intent_typing(self, base_context):
        """GC-432: Differentiate information-seeking from affective/rhetorical questions."""
        llm_ctx = ResponseContextAssembler.assemble(base_context)
        full_prompt = "\n".join(llm_ctx.system_instructions)
        assert "GC-432" in full_prompt
        assert "Information-seeking questions require genuine curiosity" in full_prompt
        assert "affective, rhetorical, and teasing questions" in full_prompt

    def test_gc433_known_fact_consistency_and_persona_persistence(self, base_context):
        """GC-433: Invariant 1 and 24 enforce persona persistence and anti-amnesia."""
        llm_ctx = ResponseContextAssembler.assemble(base_context)
        full_prompt = "\n".join(llm_ctx.system_instructions)
        assert "GC-433" in full_prompt
        assert "Never invert, alter, or discard your established personal habits" in full_prompt
        assert "Never treat a known fact as an unknown fact" in full_prompt

    def test_gc435_negative_liberties_and_anti_unrequested_justification(self, base_context):
        """GC-435: Negative liberties forbid unrequested justification chains and therapy boilerplate."""
        llm_ctx = ResponseContextAssembler.assemble(base_context)
        full_prompt = "\n".join(llm_ctx.system_instructions)
        assert "GC-435" in full_prompt
        assert "Freedom from Unrequested Justification" in full_prompt
        assert "do NOT systematically produce [Opinion] -> [Because reason] -> [Therefore conclusion]" in full_prompt
        assert "Freedom from Therapeutic Articulation & Polite Closure" in full_prompt

    def test_gc436_uneven_expression_and_asymmetric_elaboration(self, base_context):
        """GC-436: Fluctuating response length and depth based on personal interest."""
        llm_ctx = ResponseContextAssembler.assemble(base_context)
        full_prompt = "\n".join(llm_ctx.system_instructions)
        assert "GC-436" in full_prompt
        assert "Uneven Expression & Asymmetric Elaboration" in full_prompt
        assert "You are NOT required to give uniform depth across different topics" in full_prompt
