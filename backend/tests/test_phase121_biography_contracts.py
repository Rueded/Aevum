"""test_phase121_biography_contracts.py — Dedicated Unit Tests for Phase 12.1 Biography Contracts.

Governed by ADR-023:
1. Immutability, frozen status, and extra='forbid' across all biography models.
2. Canonical enums: HistoryScope, LifeEra, CanonicalStatus, RecallLevel, CausalKnowledgeState,
   CausalRelationType, BiographicalDomain, PreferenceAffinity.
3. Two orthogonal axes: CanonicalStatus (truth status) and RecallLevel (phenomenological clarity).
4. Lock 4 Relational Isolation: HistoryScope.AEVUM_PERSONAL strictly rejects user_present and session_anchor.
5. Lock 2 Causal Integrity: CausalKnowledgeState.UNKNOWN strictly forbids causal_relation_id; KNOWN requires it.
6. Anti-self-loop in CausalRelation: source_id != target_id.
7. Composite childhood memory node representation (Fact + Event + Qualia + RecallLevel).
8. Pure static AST boundary audit (0 DB, 0 LLM, 0 network, 0 mutation authority, 0 float confidence).
"""

from __future__ import annotations

import ast
import pathlib
import pytest
from pydantic import ValidationError

from app.biography.biography_models import (
    BiographicalAnchor,
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    CausalRelation,
    CausalRelationType,
    HistoryScope,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    PreferenceAffinity,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)


class TestBiographicalEnums:
    """Verifies all Phase 12 categorical enums per ADR-023."""

    def test_history_scope_members(self) -> None:
        """Verifies HistoryScope domain segregation (Lock 4)."""
        scopes = {s.value for s in HistoryScope}
        assert scopes == {"AEVUM_PERSONAL", "SHARED_WITH_USER"}
        assert len(HistoryScope) == 2

    def test_life_era_members_and_no_age_hardcoding(self) -> None:
        """Verifies LifeEra developmental stages without hardcoded ages or dynamic COLLEGE_CURRENT."""
        eras = {e.value for e in LifeEra}
        expected = {
            "EARLY_CHILDHOOD",
            "PRIMARY_SCHOOL",
            "SECONDARY_SCHOOL",
            "POST_SECONDARY",
            "UNIVERSITY",
            "ADULTHOOD",
            "OTHER",
            "UNKNOWN",
        }
        assert eras == expected
        assert "COLLEGE_CURRENT" not in eras
        assert len(LifeEra) == 8

    def test_canonical_status_members(self) -> None:
        """Verifies Axis 1: Truth / Reality Ledger status."""
        statuses = {s.value for s in CanonicalStatus}
        assert statuses == {"CANONICAL", "PROVISIONAL", "DISPUTED", "UNDEFINED"}
        assert len(CanonicalStatus) == 4

    def test_recall_level_members(self) -> None:
        """Verifies Axis 2: Phenomenological Recall clarity."""
        levels = {r.value for r in RecallLevel}
        assert levels == {"VIVID", "HAZY", "FRAGMENTARY", "UNDEFINED"}
        assert len(RecallLevel) == 4

    def test_causal_knowledge_state_members(self) -> None:
        """Verifies domain-level causal knowledge state (Lock 2)."""
        states = {s.value for s in CausalKnowledgeState}
        assert states == {"KNOWN", "UNKNOWN"}
        assert len(CausalKnowledgeState) == 2

    def test_causal_relation_type_members(self) -> None:
        """Verifies causal derivation relationship types."""
        types = {t.value for t in CausalRelationType}
        expected = {"ORIGINATED_FROM", "CATALYZED_BY", "CONDITIONED_BY", "MOTIVATED_BY"}
        assert types == expected
        assert len(CausalRelationType) == 4

    def test_biographical_domain_members(self) -> None:
        """Verifies all 6 biographical ontological domains."""
        domains = {d.value for d in BiographicalDomain}
        expected = {
            "ORIGIN_AND_IDENTITY",
            "EDUCATION_AND_GROWTH",
            "PASSION_AND_DISCIPLINE",
            "LIFESTYLE_AND_RHYTHM",
            "RELATIONAL_AND_SOCIAL",
            "SHARED_USER_JOURNEY",
        }
        assert domains == expected
        assert len(BiographicalDomain) == 6

    def test_preference_affinity_members(self) -> None:
        """Verifies preference affinity levels."""
        affinities = {a.value for a in PreferenceAffinity}
        assert affinities == {"FAVORITE", "ENJOYS", "NEUTRAL", "DISLIKES"}
        assert len(PreferenceAffinity) == 4


class TestOrthogonalAxesDecoupling:
    """Verifies that CanonicalStatus (truth) and RecallLevel (clarity) are orthogonal."""

    def test_canonical_fact_with_various_recall_levels(self) -> None:
        """A canonical fact can be vivid, hazy, or fragmentary."""
        # 1. Vivid canonical fact
        vivid_fact = BiographicalFact(
            fact_id="fact-birthplace",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            attribute_key="birth_place",
            attribute_value="Johor Bahru",
            era=LifeEra.EARLY_CHILDHOOD,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
        )
        assert vivid_fact.canonical_status == CanonicalStatus.CANONICAL
        assert vivid_fact.recall_level == RecallLevel.VIVID

        # 2. Hazy canonical fact (core outline known, details faded)
        hazy_fact = BiographicalFact(
            fact_id="fact-old-residence",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            attribute_key="primary_school_neighborhood",
            attribute_value="Muar town center near old bridge",
            era=LifeEra.PRIMARY_SCHOOL,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            provenance="family_record",
            valid_from_era=LifeEra.PRIMARY_SCHOOL,
        )
        assert hazy_fact.canonical_status == CanonicalStatus.CANONICAL
        assert hazy_fact.recall_level == RecallLevel.HAZY

        # 3. Fragmentary canonical fact (isolated snapshot)
        fragmentary_fact = BiographicalFact(
            fact_id="fact-early-memory",
            domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            attribute_key="earliest_music_exposure",
            attribute_value="Record player playing cello in rainy afternoon",
            era=LifeEra.EARLY_CHILDHOOD,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.FRAGMENTARY,
            provenance="episodic_anchor",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
        )
        assert fragmentary_fact.canonical_status == CanonicalStatus.CANONICAL
        assert fragmentary_fact.recall_level == RecallLevel.FRAGMENTARY

    def test_provisional_and_disputed_facts_with_vivid_recall(self) -> None:
        """Demonstrates that vivid recall does not imply canonical truth."""
        provisional_fact = BiographicalFact(
            fact_id="fact-candidate-hobby",
            domain=BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            attribute_key="baking_preference",
            attribute_value="Enjoys sourdough baking",
            era=LifeEra.UNIVERSITY,
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.VIVID,
            provenance="unverified_inference",
            valid_from_era=LifeEra.UNIVERSITY,
        )
        assert provisional_fact.canonical_status == CanonicalStatus.PROVISIONAL
        assert provisional_fact.recall_level == RecallLevel.VIVID

    def test_zero_float_confidence_in_model_schemas(self) -> None:
        """Resolution 5: Absolute zero float confidence fields in any biography model."""
        models = [
            BiographicalFact,
            LifeEventRecord,
            PersonalPreference,
            CausalRelation,
            QualiaAnchor,
            SocialContactRecord,
            BiographicalAnchor,
        ]
        for model_cls in models:
            for field_name, field_info in model_cls.model_fields.items():
                annotation = field_info.annotation
                annotation_str = str(annotation).lower()
                assert "float" not in annotation_str, (
                    f"Model {model_cls.__name__}.{field_name} must not use float fields"
                )


class TestHistoryScopeRelationalIsolation:
    """Verifies Lock 4: Relational Isolation between Aevum Personal Past and Shared User History."""

    def test_history_scope_is_domain_authority_independent_of_user_present(self) -> None:
        """Lock 4: HistoryScope defines domain identity; user_present is flexible provenance metadata."""
        # 1. Personal event with user_present=False
        solo_event = LifeEventRecord(
            event_id="evt-childhood-01",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.PRIMARY_SCHOOL,
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            headline="Won primary school math competition",
            summary="Participated in state-wide competition in Johor",
            user_present=False,
        )
        assert solo_event.scope == HistoryScope.AEVUM_PERSONAL
        assert solo_event.user_present is False

        # 2. Personal event with user_present=True (e.g. user was later realized to have been at the same library/event)
        coincidental_event = LifeEventRecord(
            event_id="evt-library-01",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.SECONDARY_SCHOOL,
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            headline="Studied systems programming in state library",
            summary="Spent weekend afternoons in the reference section",
            user_present=True,  # Provenance metadata does NOT change domain scope
            session_anchor="session-turn-42",  # Recording provenance does NOT mutate scope
        )
        assert coincidental_event.scope == HistoryScope.AEVUM_PERSONAL
        assert coincidental_event.user_present is True
        assert coincidental_event.session_anchor == "session-turn-42"

    def test_shared_history_episode_metadata_flexibility(self) -> None:
        """Shared history episodes represent co-experienced journey with flexible provenance."""
        # 1. Shared episode without session_anchor (canonicalized episode without raw turn reference)
        canonical_shared_episode = LifeEventRecord(
            event_id="evt-shared-01",
            scope=HistoryScope.SHARED_WITH_USER,
            era=LifeEra.UNIVERSITY,
            domain=BiographicalDomain.SHARED_USER_JOURNEY,
            headline="First architecture design discussion together",
            summary="Discussed the decoupling of mind and body in companion architecture",
            user_present=True,
            session_anchor=None,  # Absence of raw session does NOT invalidate shared history
        )
        assert canonical_shared_episode.scope == HistoryScope.SHARED_WITH_USER
        assert canonical_shared_episode.session_anchor is None

        # 2. Shared episode with session_anchor
        anchored_shared_episode = LifeEventRecord(
            event_id="evt-shared-02",
            scope=HistoryScope.SHARED_WITH_USER,
            era=LifeEra.UNIVERSITY,
            domain=BiographicalDomain.SHARED_USER_JOURNEY,
            headline="Celebrated project milestone",
            summary="Celebrated completing the Phase 12 architecture blueprint",
            user_present=True,
            session_anchor="sess-099",
        )
        assert anchored_shared_episode.scope == HistoryScope.SHARED_WITH_USER
        assert anchored_shared_episode.session_anchor == "sess-099"

    def test_shared_user_journey_domain_requires_shared_scope(self) -> None:
        """BiographicalDomain.SHARED_USER_JOURNEY is an explicit semantic conflict if marked AEVUM_PERSONAL."""
        with pytest.raises(ValidationError, match="Lock 4 Violation.*SHARED_USER_JOURNEY"):
            LifeEventRecord(
                event_id="evt-conflict-01",
                scope=HistoryScope.AEVUM_PERSONAL,  # CONFLICT with SHARED_USER_JOURNEY
                era=LifeEra.UNIVERSITY,
                domain=BiographicalDomain.SHARED_USER_JOURNEY,
                headline="Joint activity declared as personal",
                summary="Invalid semantic contradiction between domain and scope",
            )

    def test_social_contact_isolation(self) -> None:
        """User cannot be placed into personal social contacts; user contact must be SHARED_WITH_USER."""
        # User in personal past is forbidden
        with pytest.raises(ValidationError, match="Lock 4 Violation.*User"):
            SocialContactRecord(
                contact_id="user-as-contact",
                display_name="User",
                relation_role="friend",
                era_first_met=LifeEra.PRIMARY_SCHOOL,
                scope=HistoryScope.AEVUM_PERSONAL,
                is_user=True,
            )

        # Valid third-party personal contact
        mentor = SocialContactRecord(
            contact_id="contact-teacher-lee",
            display_name="Mr. Lee",
            relation_role="high_school_math_teacher",
            era_first_met=LifeEra.SECONDARY_SCHOOL,
            scope=HistoryScope.AEVUM_PERSONAL,
            is_user=False,
        )
        assert mentor.display_name == "Mr. Lee"
        assert mentor.is_user is False


class TestCausalKnowledgeStateAndRelations:
    """Verifies Lock 2: Epistemic Causal Integrity and domain-level UNKNOWN state."""

    def test_unknown_preference_strictly_forbids_causal_relation_id(self) -> None:
        """UNKNOWN causal_state cannot carry a causal_relation_id."""
        with pytest.raises(ValidationError, match="UNKNOWN causal_state cannot have causal_relation_id"):
            PersonalPreference(
                preference_id="pref-black-tea",
                category="beverage",
                object_name="black tea",
                affinity=PreferenceAffinity.FAVORITE,
                era_acquired=LifeEra.SECONDARY_SCHOOL,
                causal_state=CausalKnowledgeState.UNKNOWN,
                causal_relation_id="relation-001",  # VIOLATION
            )

    def test_known_preference_requires_causal_relation_id(self) -> None:
        """KNOWN causal_state must carry a non-empty causal_relation_id."""
        with pytest.raises(ValidationError, match="KNOWN causal_state requires non-empty causal_relation_id"):
            PersonalPreference(
                preference_id="pref-python",
                category="computing",
                object_name="Python",
                affinity=PreferenceAffinity.FAVORITE,
                era_acquired=LifeEra.SECONDARY_SCHOOL,
                causal_state=CausalKnowledgeState.KNOWN,
                causal_relation_id=None,  # VIOLATION
            )

    def test_valid_known_preference_with_causal_relation(self) -> None:
        """Valid known preference with causal link."""
        pref = PersonalPreference(
            preference_id="pref-systems-prog",
            category="computing",
            object_name="Rust & Systems Programming",
            affinity=PreferenceAffinity.FAVORITE,
            era_acquired=LifeEra.UNIVERSITY,
            causal_state=CausalKnowledgeState.KNOWN,
            causal_relation_id="causal-rel-spark",
        )
        assert pref.causal_state == CausalKnowledgeState.KNOWN
        assert pref.causal_relation_id == "causal-rel-spark"

    def test_causal_relation_anti_self_loop(self) -> None:
        """CausalRelation strictly forbids source_id == target_id."""
        with pytest.raises(ValidationError, match="Self-referential causal relation forbidden"):
            CausalRelation(
                relation_id="rel-loop",
                source_id="event-001",
                target_id="event-001",  # VIOLATION: Self loop
                relation_type=CausalRelationType.ORIGINATED_FROM,
                narrative_summary="Self cause",
            )

    def test_valid_causal_relation(self) -> None:
        """Valid causal derivation link."""
        rel = CausalRelation(
            relation_id="rel-spark",
            source_id="event-first-game-built",
            target_id="pref-systems-prog",
            relation_type=CausalRelationType.ORIGINATED_FROM,
            narrative_summary="Building text adventure in high school sparked interest in memory management",
        )
        assert rel.source_id == "event-first-game-built"
        assert rel.target_id == "pref-systems-prog"
        assert rel.relation_type == CausalRelationType.ORIGINATED_FROM


class TestCompositeChildhoodMemory:
    """Verifies Resolution 4: Structured Childhood Memory composition."""

    def test_structured_childhood_memory_assembly(self) -> None:
        """Childhood memory composite node: Fact + Event + Qualia + RecallLevel."""
        # 1. Background fact anchor
        residence = BiographicalFact(
            fact_id="fact-muar-childhood",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            attribute_key="childhood_residence",
            attribute_value="Muar town",
            era=LifeEra.EARLY_CHILDHOOD,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            provenance="seed_canon",
            valid_from_era=LifeEra.EARLY_CHILDHOOD,
            valid_to_era=LifeEra.PRIMARY_SCHOOL,
        )

        # 2. Qualia anchor
        tea_qualia = QualiaAnchor(
            qualia_id="qualia-tea-ritual",
            sensory_modality="multisensory",
            description="Smell of dried tea leaves, whistle of iron kettle, sound of rain on zinc roof",
            emotional_coloring="peaceful and nostalgic",
        )

        # 3. Episodic event anchor
        tea_event = LifeEventRecord(
            event_id="evt-grandfather-tea",
            scope=HistoryScope.AEVUM_PERSONAL,
            era=LifeEra.PRIMARY_SCHOOL,
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            headline="Grandfather's weekend tea ritual",
            summary="Sitting on the porch watching grandfather brew Oolong tea while listening to the radio",
            location_anchor="Muar old house",
            user_present=False,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            qualia_ids=[tea_qualia.qualia_id],
        )

        # 4. Composite anchor tying them together
        anchor = BiographicalAnchor(
            anchor_id="anchor-tea-childhood",
            domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
            core_fact=residence,
            key_event=tea_event,
            qualia=tea_qualia,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            notes="Childhood anchor of family tea culture",
        )

        assert anchor.core_fact.attribute_value == "Muar town"
        assert anchor.key_event.headline == "Grandfather's weekend tea ritual"
        assert anchor.qualia.sensory_modality == "multisensory"
        assert anchor.recall_level == RecallLevel.HAZY


class TestImmutabilityAndExtraForbid:
    """Verifies strict immutability (frozen=True) and rejection of extra kwargs (extra='forbid')."""

    def test_frozen_immutability_on_fact(self) -> None:
        fact = BiographicalFact(
            fact_id="fact-uni",
            domain=BiographicalDomain.EDUCATION_AND_GROWTH,
            attribute_key="current_university",
            attribute_value="Universiti Sains Malaysia",
            era=LifeEra.UNIVERSITY,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            provenance="seed_canon",
            valid_from_era=LifeEra.UNIVERSITY,
        )
        with pytest.raises(ValidationError):
            fact.attribute_value = "Another University"  # type: ignore[misc]

    def test_extra_forbid_on_preference(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            PersonalPreference(
                preference_id="pref-001",
                category="tea",
                object_name="Earl Grey",
                affinity=PreferenceAffinity.ENJOYS,
                era_acquired=LifeEra.SECONDARY_SCHOOL,
                bogus_field="illegal",  # VIOLATION: extra="forbid"
            )

    def test_personal_fact_subject_must_be_aevum(self) -> None:
        """Personal facts must have subject='aevum'."""
        with pytest.raises(ValidationError, match="BiographicalFact with AEVUM_PERSONAL scope must have subject='aevum'"):
            BiographicalFact(
                fact_id="fact-other",
                domain=BiographicalDomain.ORIGIN_AND_IDENTITY,
                subject="not_aevum",  # VIOLATION
                attribute_key="birth_place",
                attribute_value="Kuala Lumpur",
                era=LifeEra.EARLY_CHILDHOOD,
                canonical_status=CanonicalStatus.CANONICAL,
                recall_level=RecallLevel.VIVID,
                provenance="seed_canon",
                valid_from_era=LifeEra.EARLY_CHILDHOOD,
            )

    def test_anchor_domain_mismatch_rejection(self) -> None:
        """Anchor domain must match core_fact and key_event domains."""
        fact = BiographicalFact(
            fact_id="fact-code",
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE,
            attribute_key="spark_language",
            attribute_value="Python",
            era=LifeEra.SECONDARY_SCHOOL,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            provenance="seed_canon",
            valid_from_era=LifeEra.SECONDARY_SCHOOL,
        )
        # Domain mismatch with core_fact
        with pytest.raises(ValidationError, match="Anchor domain.*does not match core_fact domain"):
            BiographicalAnchor(
                anchor_id="anchor-mismatch-1",
                domain=BiographicalDomain.ORIGIN_AND_IDENTITY,  # MISMATCH
                core_fact=fact,
            )

    def test_all_causal_relation_types_instantiations(self) -> None:
        """Verifies clean creation across all 4 CausalRelationType values."""
        for rel_type in CausalRelationType:
            rel = CausalRelation(
                relation_id=f"rel-{rel_type.value.lower()}",
                source_id="src-001",
                target_id="tgt-002",
                relation_type=rel_type,
                narrative_summary=f"Causal link of type {rel_type.value}",
            )
            assert rel.relation_type == rel_type


class TestStaticASTConstitutionalBoundaryAudit:
    """Pure static AST boundary audit verifying zero DB, LLM, network, or mutation leaks."""

    def test_biography_models_ast_purity(self) -> None:
        models_path = pathlib.Path("app/biography/biography_models.py")
        assert models_path.exists(), f"File {models_path} must exist"

        source = models_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(models_path))

        forbidden_import_modules = [
            "sqlalchemy",
            "sqlite3",
            "database",
            "db",
            "llm",
            "google",
            "google.genai",
            "openai",
            "requests",
            "httpx",
            "urllib",
            "aiohttp",
        ]

        forbidden_name_tokens = [
            "promotionauthorizationtoken",
            "set_fact",
            "execute_query",
            "session.commit",
            "db_session",
            "cursor.execute",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_import_modules:
                        assert forbidden not in alias.name.lower(), (
                            f"Illegal import module '{alias.name}' in {models_path}"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for forbidden in forbidden_import_modules:
                    assert forbidden not in mod.lower(), (
                        f"Illegal from-import module '{mod}' in {models_path}"
                    )
            elif isinstance(node, ast.Name):
                for forbidden in forbidden_name_tokens:
                    assert forbidden not in node.id.lower(), (
                        f"Illegal token '{node.id}' in {models_path}"
                    )

        # Confirm zero float type annotations across all class definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                target_str = ast.unparse(node.annotation).lower()
                assert "float" not in target_str, (
                    f"Illegal float annotation '{target_str}' in {models_path}"
                )
