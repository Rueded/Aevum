"""Phase 19.4 Unit Tests — Epistemic Transformation & Epistemic Ladder Gatekeeper.

Verifies the 8 scenarios of the Anti-Skipping Matrix:
1. "我想学摄影" -> Open Thread (0 Preference) [PROSPECTIVE_INTENTION]
2. "买了相机" -> Action evidence (0 Preference; 0 Experience) [ACTION_RECORDED]
3. "第一次拍照" -> Experience evidence (0 Sustained Preference) [EXPERIENCE_ENCOUNTERED]
4. "持续拍摄且明确喜欢" -> Preference evidence (Never retroactively claiming "always liked it") [PREFERENCE_ELIGIBLE]
5. "尝试后明确讨厌" -> Negative experience evidence (Never increases preference; remains negative experience)
6. "没去日本" -> Thread Closure without action/experience (NON_ACTION_CLOSURE)
7. Illegal skip: Intention -> Preference directly (MUST raise IllegalEpistemicSkipError)
8. Illegal skip: Action -> Preference directly without experience (MUST raise IllegalEpistemicSkipError)
"""

from datetime import datetime, timezone
import pytest

from app.prospective.contracts import (
    EpistemicStanceKind,
    GravityTier,
    ProspectiveThread,
    ResonanceTier,
    SalienceCoordinates,
    ThreadDomainKind,
    ThreadEnduranceTier,
    ThreadLifecycleState,
    ThreadProvenanceKind,
    UncertaintyTier,
)
from app.prospective.transformation_models import (
    EpistemicStage,
    IllegalEpistemicSkipError,
    TransformationAuditRecord,
    TransformationEvidenceKind,
)
from app.prospective.transformation_engine import (
    EpistemicTransformationEngine,
    LEGAL_LADDER_STEPS,
)


@pytest.fixture
def sample_intention_thread() -> ProspectiveThread:
    """Creates a sample open prospective thread representing an intention."""
    now = datetime(2026, 10, 5, 10, 0, 0, tzinfo=timezone.utc)
    return ProspectiveThread(
        thread_id="th_camera_001",
        character_id="aevum",
        user_id="user_test",
        domain=ThreadDomainKind.SELF,
        title="学习胶片摄影",
        narrative_anchor="想要买台胶片相机学习摄影",
        lifecycle_state=ThreadLifecycleState.ACTIVE,
        salience=SalienceCoordinates(
            gravity=GravityTier.TRIVIAL,
            resonance=ResonanceTier.DEEP_CORE,
            uncertainty=UncertaintyTier.OPEN_EXPLORATION,
            endurance=ThreadEnduranceTier.DURABLE_ARC,
        ),
        provenance=ThreadProvenanceKind.LIFE_SIMULATION_EMERGENT,
        epistemic_stance=EpistemicStanceKind.INTENTION,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
    )


class TestPhase194EpistemicTransformation:
    """Test suite verifying the Epistemic Ladder Gatekeeper."""

    def test_scenario_1_open_thread_intention_zero_preference(
        self, sample_intention_thread: ProspectiveThread
    ):
        """Scenario 1: '我想学摄影' -> Open Thread.

        At PROSPECTIVE_INTENTION:
        - 0 Action
        - 0 Lived Experience
        - 0 Preference Eligibility
        """
        stage = EpistemicStage.PROSPECTIVE_INTENTION
        assert not EpistemicTransformationEngine.has_action_occurred(stage)
        assert not EpistemicTransformationEngine.has_lived_experience(stage)
        assert not EpistemicTransformationEngine.is_preference_eligible(stage)
        assert sample_intention_thread.epistemic_stance == EpistemicStanceKind.INTENTION

    def test_scenario_2_action_evidence_recorded(self):
        """Scenario 2: '买了相机' -> Action evidence.

        Intention -> Action Recorded:
        - Action occurred: True
        - Lived Experience: False (0 experience)
        - Preference Eligibility: False (0 preference)
        """
        now = datetime(2026, 10, 6, 14, 0, 0, tzinfo=timezone.utc)
        next_stage, audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_001",
            current_stage=EpistemicStage.PROSPECTIVE_INTENTION,
            evidence_kind=TransformationEvidenceKind.ACTION_ONLY,
            rationale="用户购置了相机，现实动作已落地，但尚未实际外出拍摄体验",
            timestamp=now,
        )

        assert next_stage == EpistemicStage.ACTION_RECORDED
        assert audit.from_stage == EpistemicStage.PROSPECTIVE_INTENTION
        assert audit.to_stage == EpistemicStage.ACTION_RECORDED
        assert audit.evidence_kind == TransformationEvidenceKind.ACTION_ONLY
        assert EpistemicTransformationEngine.has_action_occurred(next_stage)
        assert not EpistemicTransformationEngine.has_lived_experience(next_stage)
        assert not EpistemicTransformationEngine.is_preference_eligible(next_stage)

    def test_scenario_3_first_experience_evidence_encountered(self):
        """Scenario 3: '第一次拍照' -> Experience evidence.

        Action Recorded -> Experience Encountered:
        - Action occurred: True
        - Lived Experience: True
        - Preference Eligibility: False (0 Sustained Preference; single experience cannot form preference)
        """
        now = datetime(2026, 10, 7, 16, 30, 0, tzinfo=timezone.utc)
        next_stage, audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_001",
            current_stage=EpistemicStage.ACTION_RECORDED,
            evidence_kind=TransformationEvidenceKind.EXPERIENCE_POSITIVE,
            rationale="周末第一次去街头试拍，感受了取景构图与快门反馈",
            timestamp=now,
        )

        assert next_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
        assert audit.from_stage == EpistemicStage.ACTION_RECORDED
        assert audit.to_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
        assert EpistemicTransformationEngine.has_action_occurred(next_stage)
        assert EpistemicTransformationEngine.has_lived_experience(next_stage)
        assert not EpistemicTransformationEngine.is_preference_eligible(next_stage)

    def test_scenario_4_sustained_evidence_to_preference_eligibility(self):
        """Scenario 4: '持续拍摄且明确喜欢' -> Preference evidence.

        Experience Encountered -> Sustained Evidence -> Preference Eligible:
        - Traversed sequentially across calendar time
        - Never retroactively claims 'always liked it'
        """
        # Step 4a: Experience -> Sustained Evidence
        ts1 = datetime(2026, 10, 15, 11, 0, 0, tzinfo=timezone.utc)
        stage_sustained, audit1 = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_001",
            current_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
            evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
            rationale="多周持续拍摄，洗出多卷胶片，产生持续审美共振",
            timestamp=ts1,
        )
        assert stage_sustained == EpistemicStage.SUSTAINED_EVIDENCE
        assert not EpistemicTransformationEngine.is_preference_eligible(stage_sustained)

        # Step 4b: Sustained Evidence -> Preference Eligible
        ts2 = datetime(2026, 10, 22, 18, 0, 0, tzinfo=timezone.utc)
        stage_pref, audit2 = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_001",
            current_stage=stage_sustained,
            evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
            rationale="经长程多轮审美正向强化，符合 Phase 16 偏好形成准入标准",
            timestamp=ts2,
        )
        assert stage_pref == EpistemicStage.PREFERENCE_ELIGIBLE
        assert EpistemicTransformationEngine.is_preference_eligible(stage_pref)

    def test_scenario_5_negative_outcome_records_experience_without_preference(self):
        """Scenario 5: '尝试后明确讨厌' -> Negative experience evidence.

        Negative outcomes are first-class experiences:
        - Recorded at EXPERIENCE_ENCOUNTERED
        - Settles negative appraisal
        - CANNOT advance to SUSTAINED_EVIDENCE or PREFERENCE_ELIGIBLE
        """
        now = datetime(2026, 10, 8, 10, 0, 0, tzinfo=timezone.utc)
        # Record initial negative experience
        stage, audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_camera_001",
            current_stage=EpistemicStage.ACTION_RECORDED,
            evidence_kind=TransformationEvidenceKind.EXPERIENCE_NEGATIVE,
            rationale="试拍冲洗后觉得繁琐乏味，化学试剂气味刺鼻，产生明确排斥感",
            timestamp=now,
        )
        assert stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
        assert audit.evidence_kind == TransformationEvidenceKind.EXPERIENCE_NEGATIVE
        assert not EpistemicTransformationEngine.is_preference_eligible(stage)

        # Attempting to promote with negative outcome must be blocked
        with pytest.raises(IllegalEpistemicSkipError) as exc_info:
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_001",
                from_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                to_stage=EpistemicStage.SUSTAINED_EVIDENCE,
                evidence_kind=TransformationEvidenceKind.EXPERIENCE_NEGATIVE,
                rationale="试图将负面体验错误升华为偏好证据",
            )
        assert "Negative lived experience cannot advance" in str(exc_info.value)

    def test_scenario_6_non_action_closure_zero_fake_records(self):
        """Scenario 6: '没去日本' -> Thread Closure.

        Settles without action or experience:
        - from_stage: PROSPECTIVE_INTENTION
        - to_stage: PROSPECTIVE_INTENTION (settled)
        - 0 Action records, 0 Experience records manufactured
        """
        now = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
        stage, audit = EpistemicTransformationEngine.evaluate_transition(
            thread_id="th_japan_trip",
            current_stage=EpistemicStage.PROSPECTIVE_INTENTION,
            evidence_kind=TransformationEvidenceKind.NON_ACTION_CLOSURE,
            rationale="假期待在家里看书，去日本的旅行构想自然脱落失效",
            timestamp=now,
        )
        assert stage == EpistemicStage.PROSPECTIVE_INTENTION
        assert audit.from_stage == EpistemicStage.PROSPECTIVE_INTENTION
        assert audit.to_stage == EpistemicStage.PROSPECTIVE_INTENTION
        assert audit.evidence_kind == TransformationEvidenceKind.NON_ACTION_CLOSURE
        # Verifies 0 fake actions/experiences created
        assert not EpistemicTransformationEngine.has_action_occurred(stage)
        assert not EpistemicTransformationEngine.has_lived_experience(stage)
        assert not EpistemicTransformationEngine.is_preference_eligible(stage)

    def test_scenario_7_illegal_skip_intention_to_preference_directly(self):
        """Scenario 7: Illegal skip from Intention directly to Preference.

        MUST raise IllegalEpistemicSkipError.
        """
        with pytest.raises(IllegalEpistemicSkipError) as exc_info:
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_001",
                from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
                rationale="用户刚说了一句想学摄影，就直接标记为摄影爱好者",
            )
        assert "Intention cannot skip directly to Experience or Preference" in str(
            exc_info.value
        )

    def test_scenario_8_illegal_skip_action_to_preference_directly(self):
        """Scenario 8: Illegal skip from Action directly to Preference.

        MUST raise IllegalEpistemicSkipError. Action is NOT preference.
        """
        with pytest.raises(IllegalEpistemicSkipError) as exc_info:
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_001",
                from_stage=EpistemicStage.ACTION_RECORDED,
                to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
                rationale="用户买了台相机，未拍摄体验便直接认定喜欢摄影",
            )
        assert "Action cannot skip directly to Sustained Evidence or Preference" in str(
            exc_info.value
        )

    def test_illegal_skip_intention_to_experience_directly(self):
        """Intention cannot skip directly to Experience without concrete action."""
        with pytest.raises(IllegalEpistemicSkipError) as exc_info:
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_001",
                from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                to_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                evidence_kind=TransformationEvidenceKind.EXPERIENCE_POSITIVE,
                rationale="跳过现实动作直接断言体验发生",
            )
        assert "Intention cannot skip directly to Experience" in str(exc_info.value)

    def test_illegal_skip_single_experience_to_preference_directly(self):
        """Single lived experience cannot skip directly to Preference."""
        with pytest.raises(IllegalEpistemicSkipError) as exc_info:
            EpistemicTransformationEngine.advance_stage(
                thread_id="th_camera_001",
                from_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                evidence_kind=TransformationEvidenceKind.SUSTAINED_POSITIVE,
                rationale="单次体验跳过长期证据直达偏好",
            )
        assert "Single lived experience cannot skip directly to Preference" in str(
            exc_info.value
        )

    def test_audit_record_immutability_and_strictness(self):
        """TransformationAuditRecord is frozen and extra='forbid'."""
        record = TransformationAuditRecord(
            audit_id="audit_test_01",
            thread_id="th_test_01",
            from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
            to_stage=EpistemicStage.ACTION_RECORDED,
            evidence_kind=TransformationEvidenceKind.ACTION_ONLY,
            rationale="Test rationale",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):
            record.rationale = "Mutated rationale"  # type: ignore

        with pytest.raises(Exception):
            TransformationAuditRecord(
                audit_id="audit_test_02",
                thread_id="th_test_02",
                from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                to_stage=EpistemicStage.ACTION_RECORDED,
                evidence_kind=TransformationEvidenceKind.ACTION_ONLY,
                rationale="Test",
                timestamp=datetime.now(timezone.utc),
                unauthorized_score=0.95,  # type: ignore
            )
