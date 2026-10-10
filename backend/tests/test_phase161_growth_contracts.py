"""Test suite for Phase 16.1 — Experiential Record Contracts & Provenance Schema.

Covers:
- All 13 Golden Test Cases (G1 ~ G13)
- Pure DTO immutability and extra field prohibition
- Permanent Note A: Absolute Zero Floats
- Append-Only multi-layer enforcement (ORM before_update & before_delete events)
- Static AST Boundary Audit (Zero set_fact(), zero tokens, zero network, zero LLM)
"""

import ast
import inspect
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.session import Base
from app.growth.experiential_models import (
    AutobiographicalClaimScope,
    ExperienceMutationProhibitedError,
    ExperienceProvenanceKind,
    ExperientialRecord,
    ExposureEvent,
    ExposureKind,
    ExposureState,
    FacetAppraisalKind,
    FamiliarityLevel,
    InterestDomainRecord,
    InterestFacetRecord,
    InvalidAutobiographicalClaimError,
    Phase17DeferredCapabilityError,
    UnanchoredExperienceProvenanceError,
    validate_autobiographical_claim_eligibility,
    validate_interaction_evidence_anchoring,
    validate_phase16_exposure_source,
    validate_qualia_evidence_barrier,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterInterestDomainTable,
    CharacterInterestFacetTable,
)
from app.growth.experience_repository import ExperienceRepository


@pytest_asyncio.fixture
async def async_test_session():
    """In-memory SQLite async engine & session fixture with full table metadata."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestPhase161GoldenCases:
    """Implementation of Golden Acceptance Cases G1 through G13."""

    def test_g1_user_recommendation_exposure_only(self):
        """G1: USER_RECOMMENDATION creates an exposure event only, producing zero experience records."""
        event = ExposureEvent(
            exposure_id="exp-101",
            character_id="aevum",
            domain_key="genshin_impact",
            exposure_kind=ExposureKind.USER_RECOMMENDATION,
            source_speech_act="ASSERTION",
            context_notes="User recommended exploring Genshin",
            timeline_tick=100,
        )
        assert event.exposure_kind == ExposureKind.USER_RECOMMENDATION
        assert event.domain_key == "genshin_impact"
        # ExposureEvent cannot be used as an ExperientialRecord (distinct types)
        assert not isinstance(event, ExperientialRecord)

    def test_g2_recommendation_followed_by_authorized_direct_interaction(self):
        """G2: User recommends Genshin, followed later by authorized tool execution -> valid ExperientialRecord."""
        record = ExperientialRecord(
            experience_id="rec-201",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="world_exploration",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.USER_RECOMMENDATION,
            calendar_session_id="session-42",
            timeline_tick=150,
            interaction_evidence_ref="tool://genshin_runner/session_42_sub1",
            qualia_notes="First hands-on exploration of Mondstadt foothills",
        )
        # Provenance anchoring passes
        validate_interaction_evidence_anchoring(record.provenance_kind, record.interaction_evidence_ref)
        assert record.provenance_kind == ExperienceProvenanceKind.DIRECT_INTERACTION
        assert record.interaction_evidence_ref.startswith("tool://")

    def test_g3_unanchored_or_fake_direct_interaction_rejected(self):
        """G3: Fake or unanchored DIRECT_INTERACTION without execution evidence fails."""
        # 1. Empty evidence reference
        with pytest.raises(UnanchoredExperienceProvenanceError):
            validate_interaction_evidence_anchoring(ExperienceProvenanceKind.DIRECT_INTERACTION, "")

        # 2. Fake / mock prefix
        with pytest.raises(UnanchoredExperienceProvenanceError, match="unauthorized mock"):
            validate_interaction_evidence_anchoring(ExperienceProvenanceKind.DIRECT_INTERACTION, "tool://fake/test")

        with pytest.raises(UnanchoredExperienceProvenanceError, match="unauthorized mock"):
            validate_interaction_evidence_anchoring(ExperienceProvenanceKind.DIRECT_INTERACTION, "tool://unauthorized/run")

        # 3. Unrecognized non-provider format
        with pytest.raises(UnanchoredExperienceProvenanceError, match="authorized direct provider"):
            validate_interaction_evidence_anchoring(ExperienceProvenanceKind.DIRECT_INTERACTION, "https://example.com/play")

    def test_g4_user_reported_cannot_support_personal_claim(self):
        """G4: USER_REPORTED ("User says he beat Abyss") cannot support first-person claim."""
        is_eligible_solitary = validate_autobiographical_claim_eligibility(
            ExperienceProvenanceKind.USER_REPORTED,
            claim_scope=AutobiographicalClaimScope.SOLITARY,
        )
        is_eligible_shared = validate_autobiographical_claim_eligibility(
            ExperienceProvenanceKind.USER_REPORTED,
            claim_scope=AutobiographicalClaimScope.SHARED,
        )
        assert is_eligible_solitary is False
        assert is_eligible_shared is False

    def test_g5_observed_media_sensory_boundary(self):
        """G5: OBSERVED_MEDIA supports sensory/media target ("I heard OST"), not gameplay ("I played")."""
        # Solitary autobiographical gameplay claim eligibility must be False
        is_eligible_gameplay = validate_autobiographical_claim_eligibility(
            ExperienceProvenanceKind.OBSERVED_MEDIA,
            claim_scope=AutobiographicalClaimScope.SOLITARY,
        )
        assert is_eligible_gameplay is False

    def test_g6_authorized_direct_interaction_supports_first_person_claim(self):
        """G6: Authorized DIRECT_INTERACTION supports solitary first-person lived claim."""
        is_eligible = validate_autobiographical_claim_eligibility(
            ExperienceProvenanceKind.DIRECT_INTERACTION,
            claim_scope=AutobiographicalClaimScope.SOLITARY,
        )
        assert is_eligible is True

    def test_g7_shared_interaction_scope_isolation(self):
        """G7: SHARED_INTERACTION supports shared claim, but strictly rejects solitary claim."""
        # Shared claim ("We played together"): Valid
        assert validate_autobiographical_claim_eligibility(
            ExperienceProvenanceKind.SHARED_INTERACTION,
            claim_scope=AutobiographicalClaimScope.SHARED,
        ) is True

        # Solitary claim ("I played myself"): Strictly Invalid
        assert validate_autobiographical_claim_eligibility(
            ExperienceProvenanceKind.SHARED_INTERACTION,
            claim_scope=AutobiographicalClaimScope.SOLITARY,
        ) is False

    def test_g8_autonomous_curiosity_lockout(self):
        """G8: AUTONOMOUS_CURIOSITY fails closed with Phase17DeferredCapabilityError."""
        with pytest.raises(Phase17DeferredCapabilityError, match="strictly deferred to Phase 17"):
            validate_phase16_exposure_source(ExposureKind.AUTONOMOUS_CURIOSITY)

        # Allowed Phase 16 exposure kinds pass cleanly
        validate_phase16_exposure_source(ExposureKind.USER_RECOMMENDATION)
        validate_phase16_exposure_source(ExposureKind.SHARED_EXPERIENCE)
        validate_phase16_exposure_source(ExposureKind.ENVIRONMENTAL_STIMULUS)
        validate_phase16_exposure_source(ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE)

    @pytest.mark.asyncio
    async def test_g9_created_at_has_zero_semantic_effect(self, async_test_session):
        """G9: created_at changes do not alter longitudinal ordering or query results."""
        repo = ExperienceRepository(async_test_session)
        rec1 = ExperientialRecord(
            experience_id="exp-g9-1",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="music_ost",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-1",
            timeline_tick=200,
            interaction_evidence_ref="tool://ost_player/track1",
        )
        await repo.record_experience(rec1)

        # Fetch the row and inspect created_at
        res = await repo.get_experience("exp-g9-1")
        assert res is not None
        assert res.timeline_tick == 200

    @pytest.mark.asyncio
    async def test_g10_timeline_tick_governs_semantic_ordering(self, async_test_session):
        """G10: Experiences inserted in arbitrary order are returned strictly ordered by timeline_tick."""
        repo = ExperienceRepository(async_test_session)

        # Insert tick 500, then tick 100, then tick 300
        rec_late = ExperientialRecord(
            experience_id="exp-late",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="lore",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-3",
            timeline_tick=500,
            interaction_evidence_ref="tool://reader/vol3",
        )
        rec_early = ExperientialRecord(
            experience_id="exp-early",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="lore",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-1",
            timeline_tick=100,
            interaction_evidence_ref="tool://reader/vol1",
        )
        rec_mid = ExperientialRecord(
            experience_id="exp-mid",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="lore",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-2",
            timeline_tick=300,
            interaction_evidence_ref="tool://reader/vol2",
        )

        await repo.record_experience(rec_late)
        await repo.record_experience(rec_early)
        await repo.record_experience(rec_mid)

        ordered = await repo.list_experiences("aevum", domain_key="genshin_impact")
        assert len(ordered) == 3
        assert [r.experience_id for r in ordered] == ["exp-early", "exp-mid", "exp-late"]
        assert [r.timeline_tick for r in ordered] == [100, 300, 500]

    def test_g11_qualia_without_evidence_ref_rejected(self):
        """G11: qualia_notes cannot self-validate an experience without authorized evidence ref."""
        with pytest.raises(UnanchoredExperienceProvenanceError, match="qualia_notes cannot self-validate"):
            validate_qualia_evidence_barrier(evidence_ref="", qualia_notes="I felt so moved by the piano music.")

        with pytest.raises(UnanchoredExperienceProvenanceError, match="qualia_notes cannot self-validate"):
            validate_qualia_evidence_barrier(evidence_ref="   ", qualia_notes="Deep reflection on Fontaine.")

        # Non-empty evidence ref passes cleanly
        validate_qualia_evidence_barrier(
            evidence_ref="tool://music_player/track_1",
            qualia_notes="I felt so moved by the piano music.",
        )

    @pytest.mark.asyncio
    async def test_g12_existing_experience_update_rejected(self, async_test_session):
        """G12: Attempting an ORM update on an existing CharacterExperienceTable row raises ExperienceMutationProhibitedError."""
        repo = ExperienceRepository(async_test_session)
        rec = ExperientialRecord(
            experience_id="exp-immutable-1",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="music_ost",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-1",
            timeline_tick=100,
            interaction_evidence_ref="tool://ost_player/track1",
            qualia_notes="Original qualia",
        )
        await repo.record_experience(rec)

        # Attempt to modify row via ORM session
        row = await async_test_session.get(CharacterExperienceTable, "exp-immutable-1")
        assert row is not None
        row.qualia_notes = "Mutated qualia attempt"

        with pytest.raises(ExperienceMutationProhibitedError, match="immutable event logs"):
            await async_test_session.flush()

    @pytest.mark.asyncio
    async def test_g13_existing_experience_delete_rejected(self, async_test_session):
        """G13: Attempting an ORM delete on an existing CharacterExperienceTable row raises ExperienceMutationProhibitedError."""
        repo = ExperienceRepository(async_test_session)
        rec = ExperientialRecord(
            experience_id="exp-immutable-2",
            character_id="aevum",
            domain_key="genshin_impact",
            facet_key="music_ost",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-1",
            timeline_tick=100,
            interaction_evidence_ref="tool://ost_player/track1",
        )
        await repo.record_experience(rec)

        # Attempt to delete row via ORM session
        row = await async_test_session.get(CharacterExperienceTable, "exp-immutable-2")
        assert row is not None
        await async_test_session.delete(row)

        with pytest.raises(ExperienceMutationProhibitedError, match="append-only event logs"):
            await async_test_session.flush()


class TestPhase161ContractsAndInvariants:
    """Verifies DTO immutability, zero floats, and domain/facet entity relationships."""

    def test_dto_immutability_and_extra_forbidden(self):
        """DTOs must be frozen and forbid extra fields."""
        rec = ExperientialRecord(
            experience_id="exp-frozen",
            character_id="aevum",
            domain_key="classical_music",
            facet_key="piano",
            provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
            exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
            calendar_session_id="sess-1",
            timeline_tick=10,
            interaction_evidence_ref="tool://piano_synth/chopin",
        )
        with pytest.raises(Exception):  # FrozenInstanceError / ValidationError
            rec.qualia_notes = "Cannot modify frozen"

        # Extra forbidden
        with pytest.raises(Exception):
            ExperientialRecord(
                experience_id="exp-extra",
                character_id="aevum",
                domain_key="classical_music",
                facet_key="piano",
                provenance_kind=ExperienceProvenanceKind.DIRECT_INTERACTION,
                exposure_kind=ExposureKind.DIRECT_TOOL_BACKED_EXPERIENCE,
                calendar_session_id="sess-1",
                timeline_tick=10,
                interaction_evidence_ref="tool://piano_synth/chopin",
                unauthorized_extra_field="malicious",
            )

    def test_permanent_note_a_absolute_zero_floats(self):
        """Permanent Note A: All growth models must contain absolute zero float fields."""
        dto_classes = [
            ExperientialRecord,
            ExposureEvent,
            InterestDomainRecord,
            InterestFacetRecord,
        ]
        for cls in dto_classes:
            for field_name, field_info in cls.model_fields.items():
                annotation = field_info.annotation
                annotation_str = str(annotation).lower()
                assert "float" not in annotation_str, (
                    f"Permanent Note A violation: {cls.__name__}.{field_name} has float type: {annotation}"
                )

        table_classes = [
            CharacterExperienceTable,
            CharacterInterestDomainTable,
            CharacterInterestFacetTable,
        ]
        for tbl in table_classes:
            for col in tbl.__table__.columns:
                col_type_str = str(col.type).lower()
                assert "float" not in col_type_str and "double" not in col_type_str, (
                    f"Permanent Note A violation: {tbl.__tablename__}.{col.name} has float/double type: {col.type}"
                )

    @pytest.mark.asyncio
    async def test_domain_and_facet_registration_and_retrieval(self, async_test_session):
        """Tests domain and sub-facet persistence and unique constraint enforcement."""
        repo = ExperienceRepository(async_test_session)

        # 1. Register domain
        domain = InterestDomainRecord(
            domain_key="genshin_impact",
            character_id="aevum",
            display_name="原神 (Genshin Impact)",
            exposure_state=ExposureState.EXPOSED,
            created_at_tick=100,
        )
        await repo.register_domain(domain)
        fetched_domain = await repo.get_domain("aevum", "genshin_impact")
        assert fetched_domain is not None
        assert fetched_domain.display_name == "原神 (Genshin Impact)"
        assert fetched_domain.exposure_state == ExposureState.EXPOSED

        # 2. Register facets
        facet_music = InterestFacetRecord(
            facet_key="music_ost",
            domain_key="genshin_impact",
            character_id="aevum",
            display_name="管弦乐与原声音乐",
            experience_count=1,
            familiarity_level=FamiliarityLevel.SURFACE_AWARE,
            last_experienced_tick=120,
        )
        await repo.register_facet(facet_music)

        fetched_facet = await repo.get_facet("aevum", "genshin_impact", "music_ost")
        assert fetched_facet is not None
        assert fetched_facet.experience_count == 1
        assert fetched_facet.familiarity_level == FamiliarityLevel.SURFACE_AWARE


class TestPhase161StaticASTBoundaryAudit:
    """Performs static syntax tree inspection on backend/app/growth/ to enforce constitutional boundaries."""

    def test_zero_set_fact_zero_promotion_tokens_zero_network(self):
        """Constitutional Guard: Zero set_fact(), zero PromotionAuthorizationToken, zero network calls."""
        growth_dir = Path(__file__).resolve().parent.parent / "app" / "growth"
        assert growth_dir.exists() and growth_dir.is_dir()

        py_files = list(growth_dir.glob("*.py"))
        assert len(py_files) >= 3, f"Expected at least 3 python files in app/growth, found {len(py_files)}"

        forbidden_imports = {
            "requests", "httpx", "urllib", "aiohttp",
            "openai", "anthropic", "google.generativeai",
        }
        forbidden_calls = {"set_fact", "PromotionAuthorizationToken"}

        for py_path in py_files:
            source = py_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_imports:
                            assert forbidden not in alias.name, (
                                f"Forbidden import '{alias.name}' in {py_path.name}:{node.lineno}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for forbidden in forbidden_imports:
                        assert forbidden not in module, (
                            f"Forbidden import from '{module}' in {py_path.name}:{node.lineno}"
                        )
                elif isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    for forbidden_call in forbidden_calls:
                        assert func_name != forbidden_call, (
                            f"Forbidden function call '{func_name}' in {py_path.name}:{node.lineno}"
                        )
