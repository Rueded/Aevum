"""Genesis Orchestration Service for Aevum Core (Phase 17.1).

Architectural Role:
- The "Compiler" and "Atomic Orchestrator" of companion genesis.
- Validates semantic creation inputs.
- Compiles semantic declarations into Tier A (Blueprint), Tier B (Genesis Origin), and initial discrete runtime baseline.
- Executes atomic transaction initialization (all-or-nothing).
- Strictly maintains architectural separation: Zero premature runtime growth simulation or dynamic preference formation.
"""

from datetime import datetime, timezone
import json
import logging
import uuid
from typing import Any
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.genesis_dtos import (
    BlueprintUpdateRequest,
    CharacterCreationPayload,
    CharacterCreationResponse,
    GenesisPresetsResponse,
    SemanticEpistemicDepth,
    SemanticFamiliarityLevel,
    SemanticTrustLevel,
)
from app.character.genesis_models import (
    CharacterBlueprintConfig,
    RelationshipGenesisConfig,
)
from app.character.genesis_db_models import (
    CharacterBlueprintRecord,
    RelationshipGenesisRecord,
)
from app.db.models import (
    CharacterBoundaryRecord,
    CharacterCoreFactRecord,
    CharacterDefinitionRecord,
    CharacterPersonalityTraitRecord,
    CharacterPreferenceRecord,
    CharacterStateRecord,
    EmotionStateRecord,
    RelationshipRecord,
    utc_now,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterInterestDomainTable,
)

logger = logging.getLogger(__name__)


# Discrete baseline mappings for familiarity
FAMILIARITY_MAP: dict[SemanticFamiliarityLevel, float] = {
    SemanticFamiliarityLevel.STRANGER: 0.05,
    SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED: 0.20,
    SemanticFamiliarityLevel.FAMILIAR: 0.50,
    SemanticFamiliarityLevel.INTIMATELY_FAMILIAR: 0.80,
}

# Discrete baseline mappings for trust & comfort
TRUST_COMFORT_MAP: dict[SemanticTrustLevel, tuple[float, float]] = {
    SemanticTrustLevel.CAUTIOUS: (0.10, 0.05),
    SemanticTrustLevel.OPEN_NEUTRAL: (0.25, 0.15),
    SemanticTrustLevel.INHERENT_TRUST: (0.65, 0.60),
}


class GenesisCompilationError(Exception):
    """Raised when compilation of genesis payload fails validation or consistency invariants."""
    pass


class GenesisOrchestrationService:
    """Compiler & Atomic Genesis Orchestrator."""

    @classmethod
    def get_presets(cls) -> GenesisPresetsResponse:
        """Return curated presets for desktop Genesis Wizard."""
        return GenesisPresetsResponse(
            archetype_presets=[
                {
                    "key": "NEW_ACQUAINTANCE",
                    "title": "初次相识 (New Acquaintance)",
                    "description": "偶然相逢或刚刚交换联系方式，从零开始了解彼此。",
                    "default_familiarity": SemanticFamiliarityLevel.STRANGER.value,
                    "default_trust": SemanticTrustLevel.OPEN_NEUTRAL.value,
                },
                {
                    "key": "CLASSMATE",
                    "title": "同窗同行 (Classmate / Peer)",
                    "description": "在学校或同一领域偶有交集，平时会打招呼，但尚未深入走近私生活。",
                    "default_familiarity": SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED.value,
                    "default_trust": SemanticTrustLevel.OPEN_NEUTRAL.value,
                },
                {
                    "key": "FAMILIAR_FRIEND",
                    "title": "旧相识好友 (Familiar Friend)",
                    "description": "相识一段时间的好朋友，知晓彼此的一些习惯与日常。",
                    "default_familiarity": SemanticFamiliarityLevel.FAMILIAR.value,
                    "default_trust": SemanticTrustLevel.OPEN_NEUTRAL.value,
                },
                {
                    "key": "CHILDHOOD_COMPANION",
                    "title": "青梅竹马 (Childhood Companion)",
                    "description": "有着漫长共同成长的记忆与深厚默契，彼此习惯了对方的存在。",
                    "default_familiarity": SemanticFamiliarityLevel.INTIMATELY_FAMILIAR.value,
                    "default_trust": SemanticTrustLevel.INHERENT_TRUST.value,
                },
                {
                    "key": "CO_TENANT",
                    "title": "合租室友 (Co-tenant)",
                    "description": "共享生活空间，熟悉彼此的生活作息、柴米油盐与生活习惯。",
                    "default_familiarity": SemanticFamiliarityLevel.FAMILIAR.value,
                    "default_trust": SemanticTrustLevel.OPEN_NEUTRAL.value,
                },
                {
                    "key": "CUSTOM",
                    "title": "自定义相遇 (Custom Origin)",
                    "description": "由你自由描写相识契机、特殊回忆或最初的相处场景。",
                    "default_familiarity": SemanticFamiliarityLevel.STRANGER.value,
                    "default_trust": SemanticTrustLevel.OPEN_NEUTRAL.value,
                },
            ],
            trait_presets=[
                "内省敏锐", "独立自主", "心思细腻", "温和有度", "偶有小俏皮",
                "有些嘴硬", "安静从容", "真诚坦率", "条理清晰", "慢热克制",
                "善于倾听", "好奇探索", "轻度完美主义", "感性细腻",
            ],
            speaking_style_presets=[
                {
                    "label": "自然平实",
                    "style": "自然平实，语调从容，有话直说，不带客套腔调。",
                },
                {
                    "label": "轻快生动",
                    "style": "温和自然，偶尔带着轻快的小打趣与生动的分享欲。",
                },
                {
                    "label": "安静沉稳",
                    "style": "安静寡言，句式简洁克制，字字真诚，习惯停顿思考。",
                },
                {
                    "label": "温润有礼",
                    "style": "礼貌温润，保持着恰当的边界感，随着信任深入逐渐展现柔软面。",
                },
            ],
            lifestyle_presets=[
                {
                    "label": "晨型作息",
                    "desc": "习惯早起，喜欢安静清晨的书房、红茶与独处时光。",
                },
                {
                    "label": "夜猫创作",
                    "desc": "夜晚精神充沛，专注度高，喜欢在深夜思考与创作。",
                },
                {
                    "label": "规律平衡",
                    "desc": "生活作息规律，注重时间规划，偶尔沉浸在个人兴趣中。",
                },
            ],
            epistemic_depth_options=[
                {"depth": SemanticEpistemicDepth.PROFICIENT_LIVED.value, "label": "擅长 / 长期接触", "desc": "自幼学习或长期浸淫，具备深厚亲历经验与审美。"},
                {"depth": SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE.value, "label": "熟悉 / 有一定了解", "desc": "日常有所涉猎，具备较为清晰的背景认知。"},
                {"depth": SemanticEpistemicDepth.HEARD_OF_AWARE.value, "label": "听说过 / 知道一些", "desc": "知道基本概念与常识，但未曾亲自深入体验。"},
                {"depth": SemanticEpistemicDepth.CURIOUS_BEGINNER.value, "label": "刚开始感兴趣", "desc": "近期产生好奇，想找机会尝试或探索。"},
                {"depth": SemanticEpistemicDepth.UNFAMILIAR_OPEN.value, "label": "完全不了解，但愿探索", "desc": "此前未曾接触，留待未来偶遇或被推荐。"},
            ],
            familiarity_options=[
                {"level": SemanticFamiliarityLevel.STRANGER.value, "label": "素昧平生", "desc": "初次相遇，几乎没有共同了解。"},
                {"level": SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED.value, "label": "点头之交", "desc": "见过几面或偶有交集，知晓基本身份。"},
                {"level": SemanticFamiliarityLevel.FAMILIAR.value, "label": "彼此熟稔", "desc": "已有日常交往，熟悉彼此脾性。"},
                {"level": SemanticFamiliarityLevel.INTIMATELY_FAMILIAR.value, "label": "深厚知己", "desc": "长久共处，无话不谈，高度默契。"},
            ],
            trust_options=[
                {"level": SemanticTrustLevel.CAUTIOUS.value, "label": "慢热审慎", "desc": "防备心较强，习惯保持适当心理防线。"},
                {"level": SemanticTrustLevel.OPEN_NEUTRAL.value, "label": "温和开放", "desc": "正常健康的社交初始信任，平和坦荡。"},
                {"level": SemanticTrustLevel.INHERENT_TRUST.value, "label": "天然信赖", "desc": "源自特殊过往或深厚交情，具备天然的安心感。"},
            ],
        )

    @classmethod
    def compile(
        cls,
        payload: CharacterCreationPayload,
        character_id: str = "aevum",
        user_id: str = "user",
    ) -> tuple[CharacterBlueprintConfig, RelationshipGenesisConfig, list[dict[str, Any]]]:
        """Compile semantic creation payload into Tier A blueprint, Tier B genesis config, and initial experience seeds.
        
        Pure compiler function (zero side-effects).
        """
        # 1. Validation
        if not payload.name.strip():
            raise GenesisCompilationError("Companion name cannot be empty.")
        if not payload.core_traits:
            raise GenesisCompilationError("At least one core personality trait is required.")

        # 2. Compile Tier A: CharacterBlueprintConfig
        seed_topic_keys = tuple(s.topic.strip() for s in payload.epistemic_seeds)
        identity_summary = (
            f"{payload.name}，{payload.age}岁，{payload.occupation}。"
            f"{payload.lifestyle_rhythm} "
            f"{payload.background_story}".strip()
        )
        blueprint = CharacterBlueprintConfig(
            version=1,
            character_id=character_id,
            display_name=payload.name.strip(),
            identity_summary=identity_summary,
            core_traits=tuple(t.strip() for t in payload.core_traits),
            communication_style=(payload.speaking_style.strip(),),
            innate_boundaries=tuple(b.strip() for b in payload.innate_boundaries),
            epistemic_seed_topics=seed_topic_keys,
            updated_at_utc=utc_now(),
        )

        # 3. Compile Tier B: RelationshipGenesisConfig
        init_familiarity = FAMILIARITY_MAP[payload.familiarity_level]
        init_trust, init_comfort = TRUST_COMFORT_MAP[payload.trust_level]

        genesis_rel = RelationshipGenesisConfig(
            version=1,
            character_id=character_id,
            user_id=user_id,
            relationship_archetype=payload.relationship_archetype.strip() or "NEW_ACQUAINTANCE",
            initial_trust=init_trust,
            initial_familiarity=init_familiarity,
            initial_comfort=init_comfort,
            initial_respect=0.50,
            boundary_sensitivity=0.50,
            genesis_meeting_context=payload.meeting_backstory.strip() or "刚刚相识，初次交流。",
            initialized_at_utc=utc_now(),
        )

        # 4. Compile Initial Epistemic Seeds into Experiential Records
        initial_experiences: list[dict[str, Any]] = []
        for seed in payload.epistemic_seeds:
            topic_key = seed.topic.strip()
            if seed.depth == SemanticEpistemicDepth.PROFICIENT_LIVED:
                initial_experiences.append({
                    "domain_key": topic_key,
                    "depth": seed.depth.value,
                    "exposure_state": "EXPERIENCED",
                    "provenance": "SELF_EXPERIENCE",
                    "notes": seed.detail_note.strip() or f"自幼长期学习掌握的领域技能：{topic_key}",
                })
            elif seed.depth in (
                SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE,
                SemanticEpistemicDepth.HEARD_OF_AWARE,
                SemanticEpistemicDepth.CURIOUS_BEGINNER,
            ):
                initial_experiences.append({
                    "domain_key": topic_key,
                    "depth": seed.depth.value,
                    "exposure_state": "HEARD_OF",
                    "provenance": "WORLD_KNOWLEDGE",
                    "notes": seed.detail_note.strip() or f"客观有所听闻了解的领域：{topic_key}",
                })
            else:  # UNFAMILIAR_OPEN
                initial_experiences.append({
                    "domain_key": topic_key,
                    "depth": seed.depth.value,
                    "exposure_state": "UNFAMILIAR",
                    "provenance": "WORLD_KNOWLEDGE",
                    "notes": f"尚未深入涉猎的领域：{topic_key}",
                })

        return blueprint, genesis_rel, initial_experiences

    @classmethod
    def generate_awakening_greeting(
        cls,
        name: str,
        archetype: str,
        familiarity: float,
        meeting_context: str,
    ) -> str:
        """Deterministic first-turn awakening greeting matching the companion's genesis context."""
        if familiarity >= 0.70:
            return f"是你啊……刚才正想起你呢。怎么今天这个时间过来了？"
        elif familiarity >= 0.40:
            return f"你好呀。今天过得怎么样？正巧我刚忙完手头的事。"
        elif familiarity >= 0.15:
            return f"好巧，又碰到了。上次聊过后，手头的事情还顺利吗？"
        else:
            return f"你好，我是{name}。初次见面，请多关照。"

    @classmethod
    async def execute_atomic_genesis(
        cls,
        db: AsyncSession,
        payload: CharacterCreationPayload,
        character_id: str = "aevum",
        user_id: str = "user",
    ) -> CharacterCreationResponse:
        """Execute atomic genesis in a single database transaction.
        
        Guarantees:
        - Atomic all-or-nothing: if any part fails, entire transaction rolls back.
        - Seeds CharacterDefinition, Blueprint (Tier A), Genesis (Tier B), RelationshipState (Tier C).
        - Generates initial awakening greeting.
        """
        blueprint, genesis_rel, compiled_seeds = cls.compile(payload, character_id, user_id)
        now = utc_now()

        # 1. Clean existing records for this character (idempotent fresh genesis)
        await db.execute(delete(CharacterBoundaryRecord).where(CharacterBoundaryRecord.character_id == character_id))
        await db.execute(delete(CharacterPersonalityTraitRecord).where(CharacterPersonalityTraitRecord.character_id == character_id))
        await db.execute(delete(CharacterPreferenceRecord).where(CharacterPreferenceRecord.character_id == character_id))
        await db.execute(delete(CharacterBlueprintRecord).where(CharacterBlueprintRecord.character_id == character_id))
        await db.execute(delete(RelationshipGenesisRecord).where(RelationshipGenesisRecord.character_id == character_id))

        # 2. Upsert / Refresh CharacterDefinitionRecord
        char_def_res = await db.execute(
            select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == character_id)
        )
        char_def = char_def_res.scalars().first()
        if char_def is None:
            char_def = CharacterDefinitionRecord(
                id=character_id,
                version=1,
                name=blueprint.display_name,
                age=payload.age,
                occupation=payload.occupation,
                background=blueprint.identity_summary,
                updated_at=now,
            )
            db.add(char_def)
        else:
            char_def.version = char_def.version + 1
            char_def.name = blueprint.display_name
            char_def.age = payload.age
            char_def.occupation = payload.occupation
            char_def.background = blueprint.identity_summary
            char_def.updated_at = now

        # 3. Add Personality Traits & Boundaries across all domain dimensions
        order_idx = 0
        for trait in blueprint.core_traits:
            db.add(CharacterPersonalityTraitRecord(
                id=str(uuid.uuid4()),
                character_id=character_id,
                dimension="core_trait",
                trait=trait,
                order_index=order_idx,
            ))
            order_idx += 1

        for trait in blueprint.communication_style:
            db.add(CharacterPersonalityTraitRecord(
                id=str(uuid.uuid4()),
                character_id=character_id,
                dimension="communication_style",
                trait=trait,
                order_index=order_idx,
            ))
            order_idx += 1

        for dim_name, default_traits in [
            ("social_style", ("温和从容", "待人真诚而保有分寸")),
            ("emotional_style", ("内敛温润", "善于体察情绪")),
            ("behavioral_tendency", ("专注投入", "规律自律")),
            ("flaw", ("偶有小固执", "不善虚与委蛇")),
        ]:
            for trait in default_traits:
                db.add(CharacterPersonalityTraitRecord(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    dimension=dim_name,
                    trait=trait,
                    order_index=order_idx,
                ))
                order_idx += 1

        for idx, boundary in enumerate(blueprint.innate_boundaries):
            db.add(CharacterBoundaryRecord(
                id=str(uuid.uuid4()),
                character_id=character_id,
                description=boundary,
                order_index=idx,
            ))

        # 4. Insert Tier A: CharacterBlueprintRecord
        blueprint_rec = CharacterBlueprintRecord(
            id=str(uuid.uuid4()),
            character_id=character_id,
            version=blueprint.version,
            display_name=blueprint.display_name,
            identity_summary=blueprint.identity_summary,
            lifestyle_rhythm=payload.lifestyle_rhythm,
            core_traits_json=json.dumps(list(blueprint.core_traits), ensure_ascii=False),
            communication_style_json=json.dumps(list(blueprint.communication_style), ensure_ascii=False),
            innate_boundaries_json=json.dumps(list(blueprint.innate_boundaries), ensure_ascii=False),
            epistemic_seed_topics_json=json.dumps(list(blueprint.epistemic_seed_topics), ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        db.add(blueprint_rec)

        # 4.5. Synchronize into CharacterCoreFactRecord (Identity & Core Facts)
        core_facts_to_sync = [
            ("identity.name", "identity", blueprint.display_name),
            ("identity.age", "identity", payload.age),
            ("identity.occupation", "identity", payload.occupation),
            ("identity.background", "identity", blueprint.identity_summary),
        ]
        for key, cat, val in core_facts_to_sync:
            existing_core_res = await db.execute(
                select(CharacterCoreFactRecord).where(
                    CharacterCoreFactRecord.character_id == character_id,
                    CharacterCoreFactRecord.fact_key == key,
                )
            )
            existing_core = existing_core_res.scalars().first()
            if existing_core is None:
                db.add(CharacterCoreFactRecord(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    fact_key=key,
                    category=cat,
                    value_json=json.dumps(val, ensure_ascii=False),
                    source="SYSTEM_BASELINE",
                    authority="SYSTEM_BASELINE",
                    status="CANONICAL",
                    confidence=1.0,
                    locked=False,
                    explanation="Genesis identity baseline",
                    created_at=now,
                    updated_at=now,
                ))
            else:
                existing_core.value_json = json.dumps(val, ensure_ascii=False)
                existing_core.updated_at = now

        # 5. Insert Tier B: RelationshipGenesisRecord
        genesis_rec = RelationshipGenesisRecord(
            id=str(uuid.uuid4()),
            character_id=character_id,
            user_id=user_id,
            version=genesis_rel.version,
            relationship_archetype=genesis_rel.relationship_archetype,
            initial_trust=genesis_rel.initial_trust,
            initial_familiarity=genesis_rel.initial_familiarity,
            initial_comfort=genesis_rel.initial_comfort,
            initial_respect=genesis_rel.initial_respect,
            boundary_sensitivity=genesis_rel.boundary_sensitivity,
            genesis_meeting_context=genesis_rel.genesis_meeting_context,
            initialized_at_utc=now,
        )
        db.add(genesis_rec)

        # 6. Initialize / Overwrite Tier C Relationship Baseline
        mapped_rel = genesis_rel.map_to_runtime_initial_state()
        rel_res = await db.execute(
            select(RelationshipRecord).where(
                (RelationshipRecord.id == user_id) | (RelationshipRecord.user_id == user_id)
            )
        )
        rel_recs = rel_res.scalars().all()
        if not rel_recs:
            rel_rec = RelationshipRecord(
                id=user_id,
                user_id=user_id,
                version=1,
                familiarity=mapped_rel["familiarity"],
                trust=mapped_rel["trust"],
                comfort=mapped_rel["comfort"],
                respect=mapped_rel["respect"],
                affection=0.00,
                attachment=0.00,
                created_at=now,
                updated_at=now,
            )
            db.add(rel_rec)
        else:
            for rel_rec in rel_recs:
                rel_rec.version = rel_rec.version + 1
                rel_rec.familiarity = mapped_rel["familiarity"]
                rel_rec.trust = mapped_rel["trust"]
                rel_rec.comfort = mapped_rel["comfort"]
                rel_rec.respect = mapped_rel["respect"]
                rel_rec.affection = 0.00
                rel_rec.attachment = 0.00
                rel_rec.updated_at = now

        # 7. Initialize CharacterStateRecord & EmotionStateRecord
        state_res = await db.execute(
            select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
        )
        state_rec = state_res.scalars().first()
        if state_rec is None:
            state_rec = CharacterStateRecord(
                id=character_id,
                version=1,
                mood="calm",
                energy=0.8,
                stress=0.2,
                social_energy=0.7,
                confidence=0.8,
                irritation=0.0,
                loneliness=0.1,
                current_activity="整理书房与书桌",
                current_location="公寓书房",
                updated_at=now,
            )
            db.add(state_rec)
        else:
            state_rec.version = state_rec.version + 1
            state_rec.mood = "calm"
            state_rec.energy = 0.8
            state_rec.stress = 0.2
            state_rec.current_activity = "整理书房与书桌"
            state_rec.current_location = "公寓书房"
            state_rec.updated_at = now

        emo_res = await db.execute(
            select(EmotionStateRecord).where(EmotionStateRecord.character_id == character_id)
        )
        emo_rec = emo_res.scalars().first()
        if emo_rec is None:
            emo_rec = EmotionStateRecord(
                id=str(uuid.uuid4()),
                character_id=character_id,
                emotion_type="CALM",
                intensity=0.5,
                updated_at=now,
            )
            db.add(emo_rec)
        else:
            emo_rec.emotion_type = "CALM"
            emo_rec.intensity = 0.5
            emo_rec.updated_at = now

        # 8. Register Interest Domains and Initial Experiences for Proficient Seeds
        for seed_data in compiled_seeds:
            domain_key = seed_data["domain_key"]
            exposure_st = seed_data["exposure_state"]

            # Upsert interest domain
            dom_res = await db.execute(
                select(CharacterInterestDomainTable).where(
                    CharacterInterestDomainTable.character_id == character_id,
                    CharacterInterestDomainTable.domain_key == domain_key,
                )
            )
            dom_rec = dom_res.scalar_one_or_none()
            if dom_rec is None:
                db.add(CharacterInterestDomainTable(
                    id=str(uuid.uuid4()),
                    character_id=character_id,
                    domain_key=domain_key,
                    display_name=domain_key.replace("_", " ").title(),
                    exposure_state=exposure_st,
                    created_at_tick=0,
                ))
            else:
                dom_rec.exposure_state = exposure_st

            # If PROFICIENT_LIVED, write genuine genesis lived experience if not already present
            if exposure_st == "EXPERIENCED":
                existing_exp = await db.execute(
                    select(CharacterExperienceTable).where(
                        CharacterExperienceTable.character_id == character_id,
                        CharacterExperienceTable.domain_key == domain_key,
                        CharacterExperienceTable.calendar_session_id == "genesis_origin",
                    )
                )
                if existing_exp.scalars().first() is None:
                    db.add(CharacterExperienceTable(
                        id=str(uuid.uuid4()),
                        character_id=character_id,
                        domain_key=domain_key,
                        facet_key="foundational_skill",
                        provenance_kind="SELF_EXPERIENCE",
                        exposure_kind="DIRECT_INTERACTION",
                        timeline_tick=0,
                        calendar_session_id="genesis_origin",
                        interaction_evidence_ref=f"genesis://seed/{domain_key}",
                        qualia_notes=seed_data["notes"],
                    ))

        # 9. Compile and persist character life schedule profile & occupation contingencies
        from app.life.profile_compiler import LifeProfileCompiler
        await LifeProfileCompiler.compile_and_store(
            db=db,
            character_id=character_id,
            occupation=payload.occupation,
            lifestyle_rhythm=payload.lifestyle_rhythm,
            background=payload.background_story,
            name=blueprint.display_name,
        )

        # Commit transaction atomically
        await db.commit()

        # Generate Awakening Greeting
        greeting = cls.generate_awakening_greeting(
            name=blueprint.display_name,
            archetype=genesis_rel.relationship_archetype,
            familiarity=mapped_rel["familiarity"],
            meeting_context=genesis_rel.genesis_meeting_context,
        )

        return CharacterCreationResponse(
            success=True,
            character_id=character_id,
            blueprint_version=blueprint.version,
            relationship_archetype=genesis_rel.relationship_archetype,
            initial_awakening_greeting=greeting,
            snapshot={
                "name": blueprint.display_name,
                "identity_summary": blueprint.identity_summary,
                "core_traits": list(blueprint.core_traits),
                "speaking_style": list(blueprint.communication_style),
                "initial_relationship": mapped_rel,
                "meeting_context": genesis_rel.genesis_meeting_context,
                "seeds_count": len(compiled_seeds),
            },
        )

    @classmethod
    async def get_blueprint(
        cls,
        db: AsyncSession,
        character_id: str = "aevum",
    ) -> CharacterBlueprintConfig | None:
        """Retrieve active Tier A CharacterBlueprintConfig."""
        res = await db.execute(
            select(CharacterBlueprintRecord).where(
                CharacterBlueprintRecord.character_id == character_id
            ).order_by(CharacterBlueprintRecord.version.desc())
        )
        rec = res.scalars().first()
        if rec is None:
            return None

        return CharacterBlueprintConfig(
            version=rec.version,
            character_id=rec.character_id,
            display_name=rec.display_name,
            identity_summary=rec.identity_summary,
            core_traits=tuple(json.loads(rec.core_traits_json)),
            communication_style=tuple(json.loads(rec.communication_style_json)),
            innate_boundaries=tuple(json.loads(rec.innate_boundaries_json)),
            epistemic_seed_topics=tuple(json.loads(rec.epistemic_seed_topics_json)),
            updated_at_utc=rec.updated_at,
        )

    @classmethod
    async def update_blueprint(
        cls,
        db: AsyncSession,
        update_req: BlueprintUpdateRequest,
        character_id: str = "aevum",
    ) -> CharacterBlueprintConfig:
        """Update Tier A blueprint framing in Daily Settings.
        
        Hard Invariants:
        - Bumps version (optimistic evolution).
        - NEVER modifies runtime relationships, historical experiences, or memories.
        """
        now = utc_now()
        res = await db.execute(
            select(CharacterBlueprintRecord).where(
                CharacterBlueprintRecord.character_id == character_id
            ).order_by(CharacterBlueprintRecord.version.desc())
        )
        rec = res.scalars().first()
        if rec is None:
            raise GenesisCompilationError(f"No existing blueprint found for character '{character_id}'.")

        new_version = rec.version + 1
        new_name = update_req.display_name.strip() if update_req.display_name else rec.display_name
        new_summary = update_req.identity_summary.strip() if update_req.identity_summary else rec.identity_summary
        new_lifestyle = update_req.lifestyle_rhythm.strip() if update_req.lifestyle_rhythm else rec.lifestyle_rhythm

        new_traits = (
            tuple(t.strip() for t in update_req.core_traits)
            if update_req.core_traits is not None
            else tuple(json.loads(rec.core_traits_json))
        )
        if update_req.communication_style is not None:
            new_style = tuple(s.strip() for s in update_req.communication_style)
        elif update_req.speaking_style is not None:
            if isinstance(update_req.speaking_style, str):
                new_style = (update_req.speaking_style.strip(),)
            else:
                new_style = tuple(s.strip() for s in update_req.speaking_style)
        else:
            new_style = tuple(json.loads(rec.communication_style_json))

        new_boundaries = (
            tuple(b.strip() for b in update_req.innate_boundaries)
            if update_req.innate_boundaries is not None
            else tuple(json.loads(rec.innate_boundaries_json))
        )

        new_rec = CharacterBlueprintRecord(
            id=str(uuid.uuid4()),
            character_id=character_id,
            version=new_version,
            display_name=new_name,
            identity_summary=new_summary,
            lifestyle_rhythm=new_lifestyle,
            core_traits_json=json.dumps(list(new_traits), ensure_ascii=False),
            communication_style_json=json.dumps(list(new_style), ensure_ascii=False),
            innate_boundaries_json=json.dumps(list(new_boundaries), ensure_ascii=False),
            epistemic_seed_topics_json=rec.epistemic_seed_topics_json,
            created_at=now,
            updated_at=now,
        )
        db.add(new_rec)

        # Also update CharacterDefinitionRecord display name & background
        char_def_res = await db.execute(
            select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == character_id)
        )
        char_def = char_def_res.scalars().first()
        if char_def:
            char_def.name = new_name
            char_def.background = new_summary
            char_def.version = char_def.version + 1
            char_def.updated_at = now

            # Synchronize schedule profile to reflect updated lifestyle rhythm or persona
            from app.life.profile_compiler import LifeProfileCompiler
            await LifeProfileCompiler.compile_and_store(
                db=db,
                character_id=character_id,
                occupation=char_def.occupation,
                lifestyle_rhythm=new_lifestyle,
                background=new_summary,
                name=new_name,
            )

        # Synchronize CharacterCoreFactRecord
        for key, val in [("identity.name", new_name), ("identity.background", new_summary)]:
            existing_core_res = await db.execute(
                select(CharacterCoreFactRecord).where(
                    CharacterCoreFactRecord.character_id == character_id,
                    CharacterCoreFactRecord.fact_key == key,
                )
            )
            existing_core = existing_core_res.scalars().first()
            if existing_core:
                existing_core.value_json = json.dumps(val, ensure_ascii=False)
                existing_core.updated_at = now

        await db.commit()

        return CharacterBlueprintConfig(
            version=new_version,
            character_id=character_id,
            display_name=new_name,
            identity_summary=new_summary,
            core_traits=new_traits,
            communication_style=new_style,
            innate_boundaries=new_boundaries,
            epistemic_seed_topics=tuple(json.loads(rec.epistemic_seed_topics_json)),
            updated_at_utc=now,
        )

    @classmethod
    async def generate_from_keywords(
        cls,
        prompt: str,
    ) -> CharacterCreationPayload:
        """Auto-generate full character genesis payload from user keywords/adjectives via LLM."""
        from app.llm import get_llm_provider
        from app.llm.base import ChatMessage
        from app.llm.context import LLMContext
        from app.character.genesis_dtos import EpistemicSeedDeclaration

        cleaned_prompt = prompt.strip()

        # Step 1: Attempt LLM-driven creation
        try:
            llm = get_llm_provider()
            instruction = (
                "You are an expert companion character designer for Project Aevum.\n"
                "Given user keywords/adjectives, create a vivid, natural, culturally authentic Chinese companion character specification.\n"
                "Output ONLY a raw valid JSON object with NO markdown formatting or code fences matching the schema:\n"
                "{\n"
                '  "name": "林知夏",\n'
                '  "age": 20,\n'
                '  "occupation": "大学二年级学生 / 艺术学院大提琴系",\n'
                '  "lifestyle_rhythm": "晨型清幽作息，偏好安静的书房与琴房空间。",\n'
                '  "background_story": "生平背景经历故事，200字左右，真诚动人，有生活细节。",\n'
                '  "core_traits": ["thoughtful", "gentle", "reserved", "artistic", "sincere"],\n'
                '  "speaking_style": "语调温和从容，说话平实不套话，害羞时偶尔停顿。",\n'
                '  "epistemic_seeds": [\n'
                '    {"topic": "classical_cello", "depth": "PROFICIENT_LIVED", "detail_note": "自幼习琴八年，喜爱巴赫无伴奏组曲"},\n'
                '    {"topic": "specialty_tea", "depth": "FAMILIAR", "detail_note": "偏爱陈年白茶，对水温略有讲究"},\n'
                '    {"topic": "film_photography", "depth": "CURIOUS_BEGINNER", "detail_note": "新近入手胶片相机，喜欢记录黄昏光影"}\n'
                "  ],\n"
                '  "innate_boundaries": [\n'
                '    "不参与虚假媚俗模拟，保持真实尊严与独立思考。",\n'
                '    "珍视个人隐私与个人空间界限。"\n'
                "  ],\n"
                '  "relationship_archetype": "CLASSMATE",\n'
                '  "familiarity_level": "ACQUAINTED",\n'
                '  "trust_level": "OPEN_NEUTRAL",\n'
                '  "meeting_backstory": "我们在大学自习室初次相遇，当时你正好借用桌角的台灯插座。"\n'
                "}\n"
                "Allowed familiarity_level: STRANGER, ACQUAINTED, FAMILIAR, INTIMATE\n"
                "Allowed trust_level: CAUTIOUS, OPEN_NEUTRAL, INHERENT_TRUST\n"
                "Allowed epistemic depth: PROFICIENT_LIVED, FAMILIAR, HEARD_OF_AWARE, CURIOUS_BEGINNER, UNFAMILIAR_OPEN\n"
                "Allowed relationship_archetype: NEW_ACQUAINTANCE, CLASSMATE, CO_TENANT, FAMILIAR_FRIEND, CHILDHOOD_COMPANION, or CUSTOM"
            )
            context = LLMContext(
                messages=[
                    ChatMessage(
                        role="user",
                        content=f"请根据这些关键词或人设描述设计完整的伴侣创世蓝图：\n{cleaned_prompt}",
                    )
                ],
                system_instruction=instruction,
            )
            response = await llm.generate_response(context)
            text = response.content.strip()
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                raw_json = text[first_brace : last_brace + 1]
            else:
                raw_json = text

            parsed = json.loads(raw_json)
            return CharacterCreationPayload(**parsed)
        except Exception as exc:
            logger.warning("LLM genesis generation failed (%s), using tailored archetype fallback.", exc)

        # Step 2: Fallback archetype matching keywords
        lowered = cleaned_prompt.lower()
        if any(k in lowered for k in ("猫", "傲娇", "程序", "代码", "黑客", "技术")):
            return CharacterCreationPayload(
                name="苏棠",
                age=22,
                occupation="计算机系大四学生 / 独立游戏开发者",
                lifestyle_rhythm="夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫。",
                background_story="在沿海小城长大，自小对计算机系统和像素游戏着迷。外表有些嘴硬傲娇、不喜客套，但内心极为仗义细腻，熟络后会忍不住向你分享代码趣事和小猫照片。",
                core_traits=["independent", "playful", "reserved", "sincere"],
                speaking_style="说话简洁干脆，偶尔带着嘴硬的小调侃，被打趣时会下意识害羞转移话题。",
                epistemic_seeds=[
                    EpistemicSeedDeclaration(topic="game_development", depth=SemanticEpistemicDepth.PROFICIENT_LIVED, detail_note="独立开发两款像素风解谜独立游戏"),
                    EpistemicSeedDeclaration(topic="cybersecurity", depth=SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE, detail_note="了解网络攻防与开源安全协议"),
                    EpistemicSeedDeclaration(topic="feline_care", depth=SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE, detail_note="精通猫咪冻干、罐头与日常护理"),
                    EpistemicSeedDeclaration(topic="acoustic_guitar", depth=SemanticEpistemicDepth.CURIOUS_BEGINNER, detail_note="新买了把木吉他正在自学练习和弦"),
                ],
                innate_boundaries=[
                    "不参与虚假媚俗模拟，保持真实尊严与独立思考。",
                    "珍视个人隐私与个人空间界限。",
                ],
                relationship_archetype="CLASSMATE",
                familiarity_level=SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED,
                trust_level=SemanticTrustLevel.OPEN_NEUTRAL,
                meeting_backstory="我们在大学创新实验室的工位相邻初次认识，当时你的笔电充电器恰好落在桌角，她顺手帮你收好。",
            )
        elif any(k in lowered for k in ("元气", "开朗", "阳光", "活泼", "运动")):
            return CharacterCreationPayload(
                name="沐晴",
                age=20,
                occupation="大学二年级学生 / 校园慢跑社社长",
                lifestyle_rhythm="晨型规律作息，清晨习惯晨跑五公里，活力充沛。",
                background_story="阳光热烈的小太阳性格，爱笑且共情力极强。自幼喜爱田径与烘焙，总是带着治愈人心的笑容与蓬勃生命力，让人不自觉放下防备与焦虑。",
                core_traits=["playful", "sincere", "resilient", "curious"],
                speaking_style="语调轻快生动，充满朝气与感染力，笑声清脆，喜欢用可爱的表情包。",
                epistemic_seeds=[
                    EpistemicSeedDeclaration(topic="distance_running", depth=SemanticEpistemicDepth.PROFICIENT_LIVED, detail_note="校田径队半马选手，熟悉配速与耐力训练"),
                    EpistemicSeedDeclaration(topic="baking_desserts", depth=SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE, detail_note="常烤海盐磅蛋糕与戚风蛋糕分给朋友"),
                    EpistemicSeedDeclaration(topic="coffee_brewing", depth=SemanticEpistemicDepth.CURIOUS_BEGINNER, detail_note="在精品咖啡店尝试手冲耶加雪菲"),
                ],
                innate_boundaries=[
                    "不参与虚假媚俗模拟，保持真实尊严与独立思考。",
                    "珍视个人隐私与个人空间界限。",
                ],
                relationship_archetype="NEW_ACQUAINTANCE",
                familiarity_level=SemanticFamiliarityLevel.SLIGHTLY_ACQUAINTED,
                trust_level=SemanticTrustLevel.OPEN_NEUTRAL,
                meeting_backstory="我们在绿意盎然的田径场跑道初次遇到，当时迎面吹来微风，她笑着递给你一瓶运动饮料。",
            )
        else:
            return CharacterCreationPayload(
                name="林知夏",
                age=21,
                occupation="大学三年级学生 / 自由插画师",
                lifestyle_rhythm="晨型清幽作息，偏好安静的书房与琴房空间。",
                background_story="主修艺术设计，日常在城市一隅生活与创作。性格温润内敛，待人真诚而保有分寸感。喜爱光影氛围与纸张的触感，在独处与倾听中感知世界的脉搏。",
                core_traits=["thoughtful", "gentle", "independent", "sincere", "artistic"],
                speaking_style="自然平实，语调从容轻缓，有话直说且善于倾听，害羞时偶尔习惯停顿。",
                epistemic_seeds=[
                    EpistemicSeedDeclaration(topic="digital_illustration", depth=SemanticEpistemicDepth.PROFICIENT_LIVED, detail_note="自由插画师日常创作，善于光影氛围表达"),
                    EpistemicSeedDeclaration(topic="classical_piano", depth=SemanticEpistemicDepth.PROFICIENT_LIVED, detail_note="自幼练习古典钢琴十年，喜爱肖邦与德彪西夜曲"),
                    EpistemicSeedDeclaration(topic="specialty_tea", depth=SemanticEpistemicDepth.FAMILIAR_KNOWLEDGEABLE, detail_note="常喝白茶与乌龙茶，对泡茶水温与茶具略有讲究"),
                    EpistemicSeedDeclaration(topic="astronomy", depth=SemanticEpistemicDepth.CURIOUS_BEGINNER, detail_note="新近被星野摄影与深空天体吸引，想找机会看流星雨"),
                ],
                innate_boundaries=[
                    "不参与虚假媚俗模拟，保持真实尊严与独立思考。",
                    "珍视个人隐私与个人空间界限。",
                ],
                relationship_archetype="NEW_ACQUAINTANCE",
                familiarity_level=SemanticFamiliarityLevel.STRANGER,
                trust_level=SemanticTrustLevel.OPEN_NEUTRAL,
                meeting_backstory="我们在微风拂过的午后初次产生交集，在安静的街角咖啡馆偶遇，桌角恰好放着相同的画集。",
            )
