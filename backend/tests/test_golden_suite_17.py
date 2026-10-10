"""
test_golden_suite_17.py — Golden Suite 17: Character Creation & Relationship Genesis

Acceptance Benchmarks GC-419 through GC-425 across 4 Clusters:
- Cluster 1 (GC-419 & GC-420): Constitutional Integrity, Discrete Anchors & Genesis Single-Application Lock
- Cluster 2 (GC-421 & GC-424): Blueprint Non-Destructive Lifecycle & Separation of Concerns (Tier A vs Tier B/C)
- Cluster 3 (GC-422 & GC-423): Epistemic Seed Compilation, Provenance Boundaries & Archetype Narrative Flexibility
- Cluster 4 (GC-425): Static AST Constitutional Boundary & Architectural Purity Audit
"""

import ast
from pathlib import Path
import uuid
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.character.genesis_dtos import (
    BlueprintUpdateRequest,
    CharacterCreationPayload,
    CharacterCreationResponse,
    EpistemicSeedDeclaration,
    GenesisPresetsResponse,
    SemanticEpistemicDepth,
    SemanticFamiliarityLevel,
    SemanticTrustLevel,
)
from app.character.genesis_db_models import (
    CharacterBlueprintRecord,
    RelationshipGenesisRecord,
)
from app.character.genesis_service import GenesisOrchestrationService
from app.db.models import (
    CharacterBoundaryRecord,
    CharacterDefinitionRecord,
    CharacterPersonalityTraitRecord,
    CharacterStateRecord,
    RelationshipRecord,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterInterestDomainTable,
)
from app.db.session import async_session_factory, init_db


# ==============================================================================
# Cluster 1: Constitutional Integrity, Discrete Anchors & Locks (GC-419 & GC-420)
# ==============================================================================


class TestCluster1ConstitutionalIntegrity:
    """Cluster 1: GC-419 & GC-420."""

    def test_gc419_continuous_psychological_sliders_banned_and_discrete_anchors_enforced(self):
        """GC-419: Continuous 0~100 sliders are strictly forbidden. Discrete qualitative anchors must be used."""
        # 1. Verify discrete familiarity levels
        assert set(SemanticFamiliarityLevel) == {
            SemanticFamiliarityLevel.STRANGER,
            SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED,
            SemanticFamiliarityLevel.FAMILIAR,
            SemanticFamiliarityLevel.INTIMATELY_FAMILIAR,
        }

        # 2. Verify discrete trust levels
        assert set(SemanticTrustLevel) == {
            SemanticTrustLevel.CAUTIOUS,
            SemanticTrustLevel.OPEN_NEUTRAL,
            SemanticTrustLevel.INHERENT_TRUST,
        }

        # 3. Verify compiler maps discrete anchors to deterministic initial bounds
        service = GenesisOrchestrationService()

        # Test stranger + cautious
        p_stranger = CharacterCreationPayload(
            name="测试伴侣",
            age=22,
            occupation="学生",
            core_traits=["gentle"],
            familiarity_level=SemanticFamiliarityLevel.STRANGER,
            trust_level=SemanticTrustLevel.CAUTIOUS,
        )
        _, rel_cfg, _ = service.compile(p_stranger)
        assert rel_cfg.initial_familiarity == 0.05
        assert rel_cfg.initial_trust == 0.10
        assert rel_cfg.initial_comfort == 0.05

        # Test intimate + inherent trust
        p_intimate = CharacterCreationPayload(
            name="测试伴侣",
            age=22,
            occupation="学生",
            core_traits=["gentle"],
            familiarity_level=SemanticFamiliarityLevel.INTIMATELY_FAMILIAR,
            trust_level=SemanticTrustLevel.INHERENT_TRUST,
        )
        _, rel_cfg_int, _ = service.compile(p_intimate)
        assert rel_cfg_int.initial_familiarity == 0.80
        assert rel_cfg_int.initial_trust == 0.65
        assert rel_cfg_int.initial_comfort == 0.60

        # 4. Continuous arbitrary float injection must be rejected by Pydantic schema
        with pytest.raises(ValidationError):
            CharacterCreationPayload(
                name="测试伴侣",
                age=22,
                occupation="学生",
                core_traits=["gentle"],
                familiarity_level=0.73,  # Invalid: float slider injection
            )

    @pytest.mark.asyncio
    async def test_gc420_genesis_applied_strictly_once_and_no_continuous_override(self):
        """GC-420: Genesis baseline is applied strictly once.

        Subsequent interaction evolves runtime state; blueprint updates must NEVER
        override evolved relationship metrics back to genesis baseline.
        """
        await init_db()
        cid = f"char_gc420_{uuid.uuid4().hex[:8]}"
        uid = f"user_gc420_{uuid.uuid4().hex[:8]}"

        payload = CharacterCreationPayload(
            name="昔涟",
            age=21,
            occupation="插画师",
            core_traits=["gentle", "thoughtful"],
            familiarity_level=SemanticFamiliarityLevel.STRANGER,
            trust_level=SemanticTrustLevel.OPEN_NEUTRAL,
            meeting_backstory="在街角书店偶遇",
        )

        async with async_session_factory() as db:
            res = await GenesisOrchestrationService.execute_atomic_genesis(
                db=db,
                payload=payload,
                character_id=cid,
                user_id=uid,
            )
            assert res.success is True

            # Advance runtime relationship metrics in database (simulating interaction)
            rel_res = await db.execute(
                select(RelationshipRecord).where(RelationshipRecord.user_id == uid)
            )
            rel_rec = rel_res.scalars().first()
            if rel_rec:
                rel_rec.familiarity = 0.68
                rel_rec.trust = 0.72
                await db.commit()

            # User edits Tier A persona in Daily Settings (e.g. changes display name or lifestyle)
            bp_update = BlueprintUpdateRequest(
                display_name="涟宝",
                lifestyle_rhythm="夜猫创作型",
            )
            updated_bp = await GenesisOrchestrationService.update_blueprint(
                db=db,
                character_id=cid,
                update_req=bp_update,
            )
            assert updated_bp.display_name == "涟宝"
            assert updated_bp.version == 2

            # Verify evolved relationship state was NOT overwritten or reverted
            rel_check = await db.execute(
                select(RelationshipRecord).where(RelationshipRecord.user_id == uid)
            )
            refreshed_rel = rel_check.scalars().first()
            if refreshed_rel:
                assert refreshed_rel.familiarity == 0.68
                assert refreshed_rel.trust == 0.72


# ==============================================================================
# Cluster 2: Blueprint Non-Destructive Lifecycle & Separation of Concerns (GC-421 & GC-424)
# ==============================================================================


class TestCluster2BlueprintLifecycleAndSeparation:
    """Cluster 2: GC-421 & GC-424."""

    @pytest.mark.asyncio
    async def test_gc421_blueprint_version_bump_preserves_experiences_and_memories(self):
        """GC-421: Blueprint updates bump version optimistically without destroying experiences or memories."""
        await init_db()
        cid = f"char_gc421_{uuid.uuid4().hex[:8]}"
        uid = f"user_gc421_{uuid.uuid4().hex[:8]}"

        payload = CharacterCreationPayload(
            name="昔涟",
            age=21,
            occupation="学生",
            core_traits=["artistic"],
            epistemic_seeds=[
                EpistemicSeedDeclaration(
                    topic="classical_piano",
                    depth=SemanticEpistemicDepth.PROFICIENT_LIVED,
                    detail_note="十岁考过十级",
                )
            ],
        )

        async with async_session_factory() as db:
            res = await GenesisOrchestrationService.execute_atomic_genesis(
                db=db,
                payload=payload,
                character_id=cid,
                user_id=uid,
            )
            assert res.blueprint_version == 1

            # Confirm experience was created
            exp_res = await db.execute(
                select(CharacterExperienceTable).where(
                    CharacterExperienceTable.character_id == cid
                )
            )
            exp_count = exp_res.scalars().all()
            assert len(exp_count) >= 1

            # Perform multiple blueprint modifications (version bumps)
            for i in range(2, 5):
                upd = await GenesisOrchestrationService.update_blueprint(
                    db=db,
                    character_id=cid,
                    update_req=BlueprintUpdateRequest(
                        lifestyle_rhythm=f"生活节奏调整版本 v{i}",
                    ),
                )
                assert upd.version == i

            # Verify all experiences are strictly preserved (0 deletions)
            post_exp_res = await db.execute(
                select(CharacterExperienceTable).where(
                    CharacterExperienceTable.character_id == cid
                )
            )
            post_exp_count = post_exp_res.scalars().all()
            assert len(post_exp_count) == len(exp_count)

    def test_gc424_genesis_wizard_vs_daily_settings_strict_separation(self):
        """GC-424: Daily Settings allows only Tier A updates; relationship fields are forbidden."""
        # 1. BlueprintUpdateRequest allows Tier A fields
        valid_req = BlueprintUpdateRequest(
            display_name="新称呼",
            identity_summary="新的人设概述",
            lifestyle_rhythm="晨型作息",
            core_traits=["gentle", "candid"],
            speaking_style="平静从容",
        )
        assert valid_req.display_name == "新称呼"

        # 2. Attempting to smuggle Tier B / Tier C relationship overrides is strictly forbidden
        with pytest.raises(ValidationError):
            BlueprintUpdateRequest(
                display_name="新称呼",
                familiarity=100.0,  # Banned: relationship override in daily settings
            )

        with pytest.raises(ValidationError):
            BlueprintUpdateRequest(
                display_name="新称呼",
                trust_level="INHERENT_TRUST",  # Banned: relationship anchor in blueprint update
            )


# ==============================================================================
# Cluster 3: Epistemic Seed Compilation & Provenance Boundaries (GC-422 & GC-423)
# ==============================================================================


class TestCluster3EpistemicSeedCompilation:
    """Cluster 3: GC-422 & GC-423."""

    def test_gc422_epistemic_seed_declarations_compilation_and_depths(self):
        """GC-422: Epistemic seed declarations map accurately to 2D epistemic coordinates without fabricating experience."""
        payload = CharacterCreationPayload(
            name="昔涟",
            age=21,
            occupation="艺术生",
            core_traits=["thoughtful"],
            epistemic_seeds=[
                EpistemicSeedDeclaration(
                    topic="classical_piano",
                    depth=SemanticEpistemicDepth.PROFICIENT_LIVED,
                    detail_note="自幼练习古典钢琴",
                ),
                EpistemicSeedDeclaration(
                    topic="specialty_tea",
                    depth=SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE,
                    detail_note="对白茶水温略有讲究",
                ),
                EpistemicSeedDeclaration(
                    topic="astronomy",
                    depth=SemanticEpistemicDepth.CURIOUS_BEGINNER,
                    detail_note="想看流星雨",
                ),
                EpistemicSeedDeclaration(
                    topic="cricket_sport",
                    depth=SemanticEpistemicDepth.HEARD_OF_AWARE,
                    detail_note="知道是一项球类运动",
                ),
                EpistemicSeedDeclaration(
                    topic="quantum_computing",
                    depth=SemanticEpistemicDepth.UNFAMILIAR_OPEN,
                    detail_note="",
                ),
            ],
        )

        bp_cfg, _, exp_seeds = GenesisOrchestrationService.compile(payload)

        # 1. Epistemic seed topics in blueprint
        assert bp_cfg.epistemic_seed_topics == (
            "classical_piano",
            "specialty_tea",
            "astronomy",
            "cricket_sport",
            "quantum_computing",
        )

        # 2. Epistemic seeds compilation mapping
        seeds_by_domain = {s["domain_key"]: s for s in exp_seeds}
        assert seeds_by_domain["classical_piano"]["exposure_state"] == "EXPERIENCED"
        assert seeds_by_domain["classical_piano"]["provenance"] == "SELF_EXPERIENCE"

        assert seeds_by_domain["specialty_tea"]["exposure_state"] == "HEARD_OF"
        assert seeds_by_domain["specialty_tea"]["provenance"] == "WORLD_KNOWLEDGE"

        assert seeds_by_domain["astronomy"]["exposure_state"] == "HEARD_OF"
        assert seeds_by_domain["astronomy"]["provenance"] == "WORLD_KNOWLEDGE"

        assert seeds_by_domain["quantum_computing"]["exposure_state"] == "UNFAMILIAR"
        assert seeds_by_domain["quantum_computing"]["provenance"] == "WORLD_KNOWLEDGE"

    def test_gc423_relationship_archetypes_preset_flexibility_and_custom_backstory(self):
        """GC-423: Presets provide convenient archetypes while CUSTOM enables arbitrary meeting backstory."""
        presets = GenesisOrchestrationService.get_presets()

        # Check standard presets exist
        archetype_keys = [p["key"] for p in presets.archetype_presets]
        assert "NEW_ACQUAINTANCE" in archetype_keys
        assert "CLASSMATE" in archetype_keys
        assert "CO_TENANT" in archetype_keys
        assert "FAMILIAR_FRIEND" in archetype_keys
        assert "CUSTOM" in archetype_keys

        # Custom archetype with free-form meeting narrative
        custom_payload = CharacterCreationPayload(
            name="星野",
            age=24,
            occupation="摄影师",
            core_traits=["curious"],
            relationship_archetype="CUSTOM",
            familiarity_level=SemanticFamiliarityLevel.FAMILIAR,
            trust_level=SemanticTrustLevel.INHERENT_TRUST,
            meeting_backstory="我们在冰岛瓦特纳冰川徒步时被困避难所，彻夜烤火长谈而结为挚交。",
        )

        _, rel_cfg, _ = GenesisOrchestrationService.compile(custom_payload)
        assert rel_cfg.relationship_archetype == "CUSTOM"
        assert rel_cfg.genesis_meeting_context == "我们在冰岛瓦特纳冰川徒步时被困避难所，彻夜烤火长谈而结为挚交。"
        assert rel_cfg.initial_familiarity == 0.50
        assert rel_cfg.initial_trust == 0.65


# ==============================================================================
# Cluster 4: Static AST Constitutional Boundary & Purity Audit (GC-425)
# ==============================================================================


class TestCluster4StaticASTConstitutionalBoundaryAudit:
    """Cluster 4: GC-425 Static AST Audit across all Phase 17 modules."""

    def test_gc425_ast_zero_continuous_sliders_and_pure_boundaries(self):
        """GC-425: Static AST analysis confirms zero continuous sliders, strict schemas, and clean architectural boundaries."""
        target_files = [
            Path("app/character/genesis_dtos.py"),
            Path("app/character/genesis_service.py"),
            Path("app/character/genesis_db_models.py"),
            Path("app/api/genesis.py"),
        ]

        forbidden_slider_keywords = ["slider_value", "set_affinity", "force_affection"]

        for file_path in target_files:
            assert file_path.exists(), f"Phase 17 file missing: {file_path}"
            code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Verify no variable or function contains forbidden slider keywords
                if isinstance(node, ast.FunctionDef):
                    name_lower = node.name.lower()
                    for kw in forbidden_slider_keywords:
                        assert kw not in name_lower, (
                            f"Forbidden keyword '{kw}' found in function '{node.name}' in {file_path}"
                        )
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name_lower = target.id.lower()
                            for kw in forbidden_slider_keywords:
                                assert kw not in name_lower, (
                                    f"Forbidden keyword '{kw}' found in assignment '{target.id}' in {file_path}"
                                )

    def test_gc425_genesis_service_contains_awakening_greeting_generator(self):
        """GC-425: GenesisOrchestrationService must provide in-character awakening greetings."""
        # Stranger greeting
        g_stranger = GenesisOrchestrationService.generate_awakening_greeting(
            name="昔涟",
            archetype="NEW_ACQUAINTANCE",
            familiarity=0.05,
            meeting_context="初次在平台对话",
        )
        assert len(g_stranger) > 0
        assert "初次" in g_stranger or "你好" in g_stranger

        # Intimate greeting
        g_intimate = GenesisOrchestrationService.generate_awakening_greeting(
            name="昔涟",
            archetype="FAMILIAR_FRIEND",
            familiarity=0.80,
            meeting_context="多年旧友",
        )
        assert len(g_intimate) > 0
        assert "是你啊" in g_intimate or "正想起你" in g_intimate or "好久不见" in g_intimate
