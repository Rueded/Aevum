"""Phase 17.1 Golden Tests — Character Creation & Relationship Genesis API & Orchestration.

Tests Constitutional Locks:
- GC-419: No Continuous Psychological State Sliders
- GC-420: Genesis != Continuous Override (One-time Genesis Mapping)
- GC-421: Blueprint Non-Destructive Update (Tier A version bump only)
- GC-422: Epistemic Seed Declarations != Auto Heard-Of (Semantic Depth Mapping)
- GC-423: Relationship Archetypes as Presets, Not Closed Enums (Custom narrative context)
- GC-424: Genesis Wizard vs Daily Settings Strict Separation
- Atomic Transaction Guarantee: All-or-nothing genesis
"""

import json
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DbSession
from starlette.testclient import TestClient

from app.character.genesis_dtos import (
    BlueprintUpdateRequest,
    CharacterCreationPayload,
    EpistemicSeedDeclaration,
    SemanticEpistemicDepth,
    SemanticFamiliarityLevel,
    SemanticTrustLevel,
)
from app.character.genesis_service import (
    GenesisCompilationError,
    GenesisOrchestrationService,
)
from app.character.genesis_db_models import (
    CharacterBlueprintRecord,
    RelationshipGenesisRecord,
)
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
from app.main import app


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures & DB Setup (In-Memory Async Engine)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_payload() -> CharacterCreationPayload:
    return CharacterCreationPayload(
        name="林晚 (Lin Wan)",
        age=22,
        occupation="独立插画师与数字音乐人",
        lifestyle_rhythm="夜猫作息，喜欢在深夜放着环境音专注画画。",
        background_story="在海滨城市长大，习惯独处创作，有一间向阳的工作室和一台旧电钢琴。",
        core_traits=["内省敏锐", "独立自主", "心思细腻", "偶有小俏皮"],
        speaking_style="语调轻柔自然，偶尔带着一点安静的自嘲与分享欲。",
        epistemic_seeds=[
            EpistemicSeedDeclaration(
                topic="digital_illustration",
                depth=SemanticEpistemicDepth.PROFICIENT_LIVED,
                detail_note="自幼学习绘画，从事商业插画三年有余。",
            ),
            EpistemicSeedDeclaration(
                topic="indie_games",
                depth=SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE,
                detail_note="平时常玩小体量独立解谜游戏。",
            ),
            EpistemicSeedDeclaration(
                topic="synth_music",
                depth=SemanticEpistemicDepth.CURIOUS_BEGINNER,
                detail_note="最近想尝试模块合成器制作音效。",
            ),
            EpistemicSeedDeclaration(
                topic="rock_climbing",
                depth=SemanticEpistemicDepth.UNFAMILIAR_OPEN,
                detail_note="此前未曾接触。",
            ),
        ],
        innate_boundaries=[
            "不参与虚假媚俗模拟，保持真实尊严与独立思考。",
            "珍视个人隐私与个人空间界限。",
        ],
        relationship_archetype="CUSTOM",
        familiarity_level=SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED,
        trust_level=SemanticTrustLevel.OPEN_NEUTRAL,
        meeting_backstory="我们在大学艺术社团初遇，第一次见面时她正在帮朋友搬画架。后来因为常在同一间自习室遇到而慢慢熟悉。",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

def test_gc422_epistemic_seed_declarations_compilation(sample_payload: CharacterCreationPayload):
    """GC-422: Epistemic Seed Declarations compile to orthogonal 2D coordinates and initial experiences."""
    blueprint, genesis_rel, compiled_seeds = GenesisOrchestrationService.compile(
        sample_payload, character_id="aevum", user_id="user"
    )

    assert blueprint.display_name == "林晚 (Lin Wan)"
    assert "digital_illustration" in blueprint.epistemic_seed_topics
    assert "rock_climbing" in blueprint.epistemic_seed_topics

    # Check compiled seed categorizations
    proficient_seed = next(s for s in compiled_seeds if s["domain_key"] == "digital_illustration")
    assert proficient_seed["exposure_state"] == "EXPERIENCED"
    assert proficient_seed["provenance"] == "SELF_EXPERIENCE"
    assert "三年" in proficient_seed["notes"]

    curious_seed = next(s for s in compiled_seeds if s["domain_key"] == "synth_music")
    assert curious_seed["exposure_state"] == "HEARD_OF"
    assert curious_seed["provenance"] == "WORLD_KNOWLEDGE"

    unfamiliar_seed = next(s for s in compiled_seeds if s["domain_key"] == "rock_climbing")
    assert unfamiliar_seed["exposure_state"] == "UNFAMILIAR"


def test_gc419_no_continuous_psychological_sliders_and_discrete_mapping(sample_payload: CharacterCreationPayload):
    """GC-419: Psychological dimensions use discrete semantic levels, rejecting continuous sliders."""
    blueprint, genesis_rel, _ = GenesisOrchestrationService.compile(sample_payload)

    # Initial familiarity mapped discretely from SLIGHTLY_ACQUAINTED
    assert genesis_rel.initial_familiarity == 0.20
    # Initial trust mapped discretely from OPEN_NEUTRAL
    assert genesis_rel.initial_trust == 0.25
    assert genesis_rel.initial_comfort == 0.15
    assert genesis_rel.initial_respect == 0.50

    # Objective integer age is preserved
    assert sample_payload.age == 22


def test_gc423_custom_relationship_genesis_narrative(sample_payload: CharacterCreationPayload):
    """GC-423: Relationship Archetype supports CUSTOM with full narrative meeting backstory."""
    _, genesis_rel, _ = GenesisOrchestrationService.compile(sample_payload)

    assert genesis_rel.relationship_archetype == "CUSTOM"
    assert "艺术社团初遇" in genesis_rel.genesis_meeting_context
    assert "搬画架" in genesis_rel.genesis_meeting_context


@pytest.mark.asyncio
async def test_gc420_atomic_genesis_execution_database_consistency(sample_payload: CharacterCreationPayload):
    """GC-420: Atomic genesis initializes all tables in one coherent transaction."""
    import uuid
    from app.db.session import async_session_factory, init_db

    await init_db()
    cid = f"char_{uuid.uuid4().hex[:8]}"
    uid = f"user_{uuid.uuid4().hex[:8]}"

    async with async_session_factory() as db:
        res = await GenesisOrchestrationService.execute_atomic_genesis(
            db=db,
            payload=sample_payload,
            character_id=cid,
            user_id=uid,
        )

        assert res.success is True
        assert res.character_id == cid
        assert res.relationship_archetype == "CUSTOM"
        assert len(res.initial_awakening_greeting) > 0

        # Verify CharacterDefinitionRecord
        char_res = await db.execute(
            select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == cid)
        )
        char_rec = char_res.scalar_one_or_none()
        assert char_rec is not None
        assert char_rec.name == "林晚 (Lin Wan)"
        assert char_rec.age == 22

        # Verify CharacterBlueprintRecord (Tier A)
        bp_res = await db.execute(
            select(CharacterBlueprintRecord).where(CharacterBlueprintRecord.character_id == cid)
        )
        bp_rec = bp_res.scalar_one_or_none()
        assert bp_rec is not None
        assert bp_rec.version == 1
        traits = json.loads(bp_rec.core_traits_json)
        assert "内省敏锐" in traits

        # Verify RelationshipGenesisRecord (Tier B)
        rg_res = await db.execute(
            select(RelationshipGenesisRecord).where(RelationshipGenesisRecord.character_id == cid)
        )
        rg_rec = rg_res.scalar_one_or_none()
        assert rg_rec is not None
        assert rg_rec.initial_familiarity == 0.20
        assert rg_rec.initial_trust == 0.25
        assert "搬画架" in rg_rec.genesis_meeting_context

        # Verify RelationshipRecord (Tier C runtime baseline)
        rel_res = await db.execute(
            select(RelationshipRecord).where(RelationshipRecord.user_id == uid)
        )
        rel_rec = rel_res.scalar_one_or_none()
        assert rel_rec is not None
        assert rel_rec.familiarity == 0.20
        assert rel_rec.trust == 0.25
        assert rel_rec.comfort == 0.15
        assert rel_rec.respect == 0.50
        assert rel_rec.affection == 0.00
        assert rel_rec.attachment == 0.00

        # Verify CharacterExperienceTable has row only for PROFICIENT_LIVED seed
        exp_res = await db.execute(
            select(CharacterExperienceTable).where(CharacterExperienceTable.character_id == cid)
        )
        exp_rows = exp_res.scalars().all()
        assert len(exp_rows) == 1
        assert exp_rows[0].domain_key == "digital_illustration"
        assert exp_rows[0].provenance_kind == "SELF_EXPERIENCE"

        # Verify CharacterInterestDomainTable has rows for all declared seeds
        dom_res = await db.execute(
            select(CharacterInterestDomainTable).where(CharacterInterestDomainTable.character_id == cid)
        )
        dom_rows = dom_res.scalars().all()
        assert len(dom_rows) == 4


@pytest.mark.asyncio
async def test_gc420_genesis_does_not_override_evolved_runtime_state(sample_payload: CharacterCreationPayload):
    """GC-420: Genesis config does not act as continuous override over runtime evolved relationship."""
    from app.db.session import async_session_factory, init_db

    await init_db()

    async with async_session_factory() as db:
        await GenesisOrchestrationService.execute_atomic_genesis(
            db=db,
            payload=sample_payload,
            character_id="evolved_char",
            user_id="evolved_user",
        )

        # Simulate 6 months of evolved interaction in Tier C
        rel_res = await db.execute(
            select(RelationshipRecord).where(RelationshipRecord.user_id == "evolved_user")
        )
        rel_rec = rel_res.scalar_one()
        rel_rec.trust = 0.85
        rel_rec.familiarity = 0.90
        rel_rec.comfort = 0.88
        await db.commit()

        # Retrieve blueprint or origin config
        bp = await GenesisOrchestrationService.get_blueprint(db, character_id="evolved_char")
        assert bp is not None

        # Verify evolved relationship state was NOT overwritten by Tier A or Tier B
        rel_check = (await db.execute(
            select(RelationshipRecord).where(RelationshipRecord.user_id == "evolved_user")
        )).scalar_one()
        assert rel_check.trust == 0.85
        assert rel_check.familiarity == 0.90


@pytest.mark.asyncio
async def test_gc421_tier_a_blueprint_non_destructive_update(sample_payload: CharacterCreationPayload):
    """GC-421: Updating Tier A blueprint in Daily Settings increments version and never mutates experiences."""
    from app.db.session import async_session_factory, init_db

    await init_db()

    async with async_session_factory() as db:
        await GenesisOrchestrationService.execute_atomic_genesis(
            db=db,
            payload=sample_payload,
            character_id="mod_char",
            user_id="mod_user",
        )

        # Snapshot experience row count before edit
        exp_count_before = len((await db.execute(
            select(CharacterExperienceTable).where(CharacterExperienceTable.character_id == "mod_char")
        )).scalars().all())

        # Update Tier A in Daily Settings
        update_req = BlueprintUpdateRequest(
            display_name="晚晚 (Wanwan)",
            lifestyle_rhythm="晨型作息，最近改在清晨早起画画。",
            speaking_style=["语调温和，习惯在句末轻轻停顿思考。"],
        )
        new_bp = await GenesisOrchestrationService.update_blueprint(
            db=db,
            update_req=update_req,
            character_id="mod_char",
        )

        assert new_bp.version == 2
        assert new_bp.display_name == "晚晚 (Wanwan)"

        # Verify experiences are completely untouched
        exp_count_after = len((await db.execute(
            select(CharacterExperienceTable).where(CharacterExperienceTable.character_id == "mod_char")
        )).scalars().all())
        assert exp_count_after == exp_count_before


def test_genesis_presets():
    """Verify Genesis presets contain rich curated options for the Wizard UI."""
    presets = GenesisOrchestrationService.get_presets()
    assert len(presets.archetype_presets) >= 5
    assert len(presets.trait_presets) >= 10
    assert len(presets.speaking_style_presets) >= 3
    assert len(presets.epistemic_depth_options) == 5
    assert len(presets.familiarity_options) == 4
    assert len(presets.trust_options) == 3


def test_fastapi_genesis_endpoints_integration(sample_payload: CharacterCreationPayload):
    """Test REST API routes via FastAPI test client."""
    client = TestClient(app)

    # 1. GET /character/genesis/presets
    res = client.get("/character/genesis/presets")
    assert res.status_code == 200
    data = res.json()
    assert "archetype_presets" in data
    assert "epistemic_depth_options" in data

    # 2. POST /character/genesis
    create_res = client.post("/character/genesis", json=sample_payload.model_dump())
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["success"] is True
    assert created_data["blueprint_version"] == 1
    assert "initial_awakening_greeting" in created_data

    # 3. GET /character/blueprint
    bp_res = client.get("/character/blueprint")
    assert bp_res.status_code == 200
    bp_data = bp_res.json()
    assert bp_data["display_name"] == "林晚 (Lin Wan)"
    assert bp_data["version"] == 1

    # 4. PUT /character/blueprint
    update_res = client.put("/character/blueprint", json={
        "display_name": "晚晚",
        "lifestyle_rhythm": "改为早睡早起。",
    })
    assert update_res.status_code == 200
    up_data = update_res.json()
    assert up_data["version"] == 2
    assert up_data["display_name"] == "晚晚"


def test_validation_empty_name_rejected(sample_payload: CharacterCreationPayload):
    """Empty name in payload is rejected by validation."""
    payload_dict = sample_payload.model_dump()
    payload_dict["name"] = "   "
    client = TestClient(app)
    res = client.post("/character/genesis", json=payload_dict)
    assert res.status_code in (400, 422)


def test_validation_empty_traits_rejected(sample_payload: CharacterCreationPayload):
    """Empty traits in payload is rejected by validation."""
    payload_dict = sample_payload.model_dump()
    payload_dict["core_traits"] = []
    client = TestClient(app)
    res = client.post("/character/genesis", json=payload_dict)
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_atomic_genesis_rollback_on_database_error(sample_payload: CharacterCreationPayload):
    """Atomic transaction guarantee: Simulated error midway triggers clean rollback with zero partial state."""
    import uuid
    from app.db.session import async_session_factory, init_db

    await init_db()
    cid = f"fail_char_{uuid.uuid4().hex[:8]}"
    uid = f"fail_user_{uuid.uuid4().hex[:8]}"

    # Mock a failure by passing a mock session that fails during commit
    from unittest.mock import AsyncMock
    async with async_session_factory() as db:
        mock_commit = AsyncMock(side_effect=RuntimeError("Simulated DB connection drop during atomic commit"))
        db.commit = mock_commit

        with pytest.raises(RuntimeError, match="Simulated DB connection drop"):
            await GenesisOrchestrationService.execute_atomic_genesis(
                db=db,
                payload=sample_payload,
                character_id=cid,
                user_id=uid,
            )

    # In a clean separate session, verify zero partial records were committed for this character
    async with async_session_factory() as verify_db:
        bp_check = await verify_db.execute(
            select(CharacterBlueprintRecord).where(CharacterBlueprintRecord.character_id == cid)
        )
        assert bp_check.scalars().first() is None

        rg_check = await verify_db.execute(
            select(RelationshipGenesisRecord).where(RelationshipGenesisRecord.character_id == cid)
        )
        assert rg_check.scalars().first() is None


@pytest.mark.asyncio
async def test_blueprint_update_nonexistent_character_raises_error():
    """Updating a blueprint for an un-initialized character raises GenesisCompilationError."""
    from app.db.session import async_session_factory, init_db

    await init_db()
    async with async_session_factory() as db:
        with pytest.raises(GenesisCompilationError, match="No existing blueprint found"):
            await GenesisOrchestrationService.update_blueprint(
                db=db,
                update_req=BlueprintUpdateRequest(display_name="New"),
                character_id="nonexistent_char_xyz",
            )


def test_ai_generate_companion_genesis_endpoint():
    """Verify POST /character/genesis/ai-generate returns valid complete payload from keywords."""
    client = TestClient(app)
    res = client.post("/character/genesis/ai-generate", json={"prompt": "傲娇 程序员 独立游戏 猫咪"})
    assert res.status_code == 200
    data = res.json()
    assert "name" in data and len(data["name"]) > 0
    assert "age" in data and 14 <= data["age"] <= 100
    assert "occupation" in data
    assert "core_traits" in data and len(data["core_traits"]) > 0
    assert "epistemic_seeds" in data and len(data["epistemic_seeds"]) > 0
    assert "relationship_archetype" in data
    assert "familiarity_level" in data
    assert "trust_level" in data


