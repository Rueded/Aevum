"""Character and companion domain API endpoints for Aevum Core.

Exposes read-only projections and user-consented management endpoints (e.g. forgetting memories)
for the desktop client. Adheres strictly to the architectural invariant:
Backend owns reality; frontend is purely a projection layer.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.character.engine_models import format_emotion_summary
from app.character.service import CharacterDefinitionService
from app.character.state_models import CharacterMood
from app.character.state_service import CharacterStateService
from app.db.session import get_db_session
from app.emotion.emotion_models import EmotionType
from app.emotion.service import EmotionService
from app.life.services import LifeService
from app.memory.service import MemoryService
from app.relationship.context_builder import (
    get_affection_summary,
    get_attachment_summary,
    get_comfort_summary,
    get_familiarity_summary,
    get_trust_summary,
    synthesize_relationship_summary,
)
from app.relationship.models import RelationshipStateUpdate
from app.relationship.service import RelationshipService
from app.character.desire_service import DesireEvaluationEngine
from app.relationship.contract_evaluator import RelationshipContractEvaluator
from app.character.social_intention_service import SocialIntentionService
from app.character.behavior_planner import BehaviorPlanner
from app.reality.history_service import RealityHistoryService

router = APIRouter(prefix="/character", tags=["Character"])


class EmotionProjection(BaseModel):
    type: str
    intensity: float
    summary: str


class CharacterStateResponse(BaseModel):
    name: str
    age: int
    occupation: str
    background: str
    mood: str
    natural_mood: str
    energy: float
    stress: float
    social_energy: float
    current_activity: str
    current_location: str
    emotion: EmotionProjection
    status: str = "online"


class CharacterStateUpdateRequest(BaseModel):
    mood: str | None = None
    emotion_type: str | None = None
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    energy: float | None = Field(default=None, ge=0.0, le=1.0)
    stress: float | None = Field(default=None, ge=0.0, le=1.0)
    social_energy: float | None = Field(default=None, ge=0.0, le=1.0)
    current_activity: str | None = None
    current_location: str | None = None


class RelationshipResponse(BaseModel):
    summary: str
    familiarity: float
    trust: float
    comfort: float
    affection: float
    attachment: float
    respect: float
    familiarity_label: str
    trust_label: str
    comfort_label: str
    affection_label: str
    attachment_label: str


class RelationshipUpdateRequest(BaseModel):
    familiarity: float | None = Field(default=None, ge=0.0, le=1.0)
    trust: float | None = Field(default=None, ge=0.0, le=1.0)
    comfort: float | None = Field(default=None, ge=0.0, le=1.0)
    respect: float | None = Field(default=None, ge=0.0, le=1.0)
    affection: float | None = Field(default=None, ge=0.0, le=1.0)
    attachment: float | None = Field(default=None, ge=0.0, le=1.0)


class LifeEventItem(BaseModel):
    id: str
    title: str
    description: str
    event_type: str
    occurred_at: str
    significance: float


class LifeGoalItem(BaseModel):
    id: str
    title: str
    description: str
    status: str
    progress: float | None = None


class LifeResponse(BaseModel):
    current_activity: str
    current_location: str
    status: str
    recent_events: list[LifeEventItem] = Field(default_factory=list)
    active_goals: list[LifeGoalItem] = Field(default_factory=list)


class MemoryItem(BaseModel):
    id: str
    category: str
    subject_entity: str
    content: str
    importance: float
    confidence: float
    emotional_weight: float
    created_at: str
    times_recalled: int


class MemoryDeleteResponse(BaseModel):
    status: str
    id: str


class BiographicalFactProjection(BaseModel):
    id: str
    domain: str
    attribute_key: str
    attribute_value: str
    era: str
    canonical_status: str
    recall_level: str
    provenance: str


class LifeEventProjection(BaseModel):
    id: str
    era: str
    domain: str
    headline: str
    summary: str
    canonical_status: str
    recall_level: str
    qualia_ids: list[str] = Field(default_factory=list)


class PersonalPreferenceProjection(BaseModel):
    id: str
    category: str
    object_name: str
    affinity: str
    era_acquired: str
    causal_state: str
    causal_relation_id: str | None = None


class QualiaAnchorProjection(BaseModel):
    id: str
    sensory_modality: str
    description: str
    emotional_coloring: str | None = None


class SocialContactProjection(BaseModel):
    id: str
    display_name: str
    relation_role: str
    era_first_met: str
    is_user: bool


class SharedHistoryEpisodeProjection(BaseModel):
    id: str
    episode_type: str
    title: str
    summary: str
    session_anchor: str
    key_learnings: list[str] = Field(default_factory=list)
    recall_level: str
    created_at_era: str


class LongitudinalMemoryResponse(BaseModel):
    facts: list[BiographicalFactProjection] = Field(default_factory=list)
    life_events: list[LifeEventProjection] = Field(default_factory=list)
    preferences: list[PersonalPreferenceProjection] = Field(default_factory=list)
    qualia: list[QualiaAnchorProjection] = Field(default_factory=list)
    contacts: list[SocialContactProjection] = Field(default_factory=list)
    shared_episodes: list[SharedHistoryEpisodeProjection] = Field(default_factory=list)
    relational_dynamics: dict[str, float] = Field(default_factory=dict)


class CharacterDebugResponse(BaseModel):
    character_id: str
    state_version: int
    relationship_version: int
    raw_state: dict[str, Any]
    raw_relationship: dict[str, float]
    raw_emotion: dict[str, Any]
    total_memories: int
    total_events: int
    decision_trace: dict[str, Any] | None = None
    reality_history: list[dict[str, Any]] | None = None


@router.get(
    "/state",
    response_model=CharacterStateResponse,
    summary="Retrieve current character definition and situational state",
)
async def get_character_state(
    db: AsyncSession = Depends(get_db_session),
    reconcile: bool = True,
) -> CharacterStateResponse:
    """Retrieve Aevum's current identity, baseline mood, energy, and situational condition."""
    char_def = await CharacterDefinitionService(db).get_character("aevum")
    if char_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character definition for 'aevum' not found.",
        )

    if reconcile:
        # Reconcile dynamic schedule with real-world time
        try:
            from app.life.schedule_engine import LifeScheduleEngine
            await LifeScheduleEngine.reconcile_schedule(db, "aevum")
        except Exception as sched_err:
            logger.warning("Dynamic schedule reconcile skipped: %s", sched_err)

    char_state = await CharacterStateService(db).get_state("aevum")
    emotion_state = await EmotionService(db).get_emotion_state("aevum")
    life_state = await LifeService(db).get_life_state("aevum")

    mood_zh = {
        "calm": "恬淡平稳",
        "good": "心情愉悦",
        "playful": "调皮想逗你",
        "focused": "专注认真",
        "tired": "微倦犯困",
        "annoyed": "傲娇小脾气",
        "reflective": "沉思感触",
    }.get(char_state.mood.value.lower(), char_state.mood.value)

    emo_zh = {
        "AMUSED": "逗趣开心",
        "TOUCHED": "心动微甜",
        "SHY": "害羞脸红",
        "CURIOUS": "好奇探究",
        "TIRED": "困意浓浓",
        "CALM": "平和自如",
        "GRUMPY": "气鼓鼓",
        "PROTECTIVE": "护短偏心",
        "SURPRISED": "惊讶好奇",
        "AFFECTIONATE": "亲昵依赖",
        "NEUTRAL": "平和自如",
    }.get(emotion_state.emotion_type.value.upper(), emotion_state.emotion_type.value)

    if mood_zh == emo_zh or emo_zh == "平和自如":
        natural_mood_label = mood_zh
    else:
        natural_mood_label = f"{mood_zh} · {emo_zh}"

    return CharacterStateResponse(
        name=char_def.identity.name,
        age=char_def.identity.age,
        occupation=char_def.identity.occupation,
        background=char_def.identity.background,
        mood=char_state.mood.value,
        natural_mood=natural_mood_label,
        energy=char_state.energy,
        stress=char_state.stress,
        social_energy=char_state.social_energy,
        current_activity=life_state.current_activity,
        current_location=life_state.current_location,
        emotion=EmotionProjection(
            type=emotion_state.emotion_type.value,
            intensity=emotion_state.intensity,
            summary=format_emotion_summary(emotion_state.emotion_type, emotion_state.intensity),
        ),
        status="online",
    )


@router.patch(
    "/state",
    response_model=CharacterStateResponse,
    summary="Update character situational/mood state directly (developer calibration)",
)
async def update_character_state(
    payload: CharacterStateUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CharacterStateResponse:
    """Update character mood and continuous state indicators for developer calibration."""
    state_service = CharacterStateService(db)
    current_state = await state_service.get_state("aevum")

    update_dict: dict[str, Any] = {}
    if payload.mood is not None:
        try:
            update_dict["mood"] = CharacterMood(payload.mood.lower())
        except ValueError:
            update_dict["mood"] = CharacterMood.CALM
    if payload.energy is not None:
        update_dict["energy"] = payload.energy
    if payload.stress is not None:
        update_dict["stress"] = payload.stress
    if payload.social_energy is not None:
        update_dict["social_energy"] = payload.social_energy
    if payload.current_activity is not None:
        update_dict["current_activity"] = payload.current_activity
    if payload.current_location is not None:
        update_dict["current_location"] = payload.current_location

    if update_dict:
        updated_state = current_state.model_copy(update=update_dict)
        await state_service.update_state(updated_state, character_id="aevum", commit=False)

        # Also sync LifeStateRecord if activity or location modified directly
        if payload.current_activity is not None or payload.current_location is not None:
            life_service = LifeService(db)
            curr_life = await life_service.get_life_state("aevum")
            await life_service.update_life_state(
                "aevum",
                current_activity=payload.current_activity or curr_life.current_activity,
                current_location=payload.current_location or curr_life.current_location,
                expected_version=curr_life.version,
            )

    if payload.emotion_type is not None:
        emotion_service = EmotionService(db)
        current_emo = await emotion_service.get_emotion_state("aevum")
        try:
            target_emo_type = EmotionType[payload.emotion_type.upper()]
        except KeyError:
            target_emo_type = EmotionType.CALM
        new_intensity = payload.intensity if payload.intensity is not None else current_emo.intensity
        updated_emo = current_emo.model_copy(update={"emotion_type": target_emo_type, "intensity": new_intensity})
        await emotion_service.update_emotion_state(updated_emo, character_id="aevum", commit=False)

    await db.commit()
    return await get_character_state(db, reconcile=False)


@router.get(
    "/relationship",
    response_model=RelationshipResponse,
    summary="Retrieve current relationship dynamic with the user",
)
async def get_character_relationship(
    db: AsyncSession = Depends(get_db_session),
) -> RelationshipResponse:
    """Retrieve multidimensional relational state and natural qualitative descriptors."""
    rel_service = RelationshipService(db)
    rel_state = await rel_service.get_relationship_state(relationship_id="user")

    return RelationshipResponse(
        summary=synthesize_relationship_summary(rel_state),
        familiarity=rel_state.familiarity,
        trust=rel_state.trust,
        comfort=rel_state.comfort,
        affection=rel_state.affection,
        attachment=rel_state.attachment,
        respect=rel_state.respect,
        familiarity_label=get_familiarity_summary(rel_state.familiarity),
        trust_label=get_trust_summary(rel_state.trust),
        comfort_label=get_comfort_summary(rel_state.comfort),
        affection_label=get_affection_summary(rel_state.affection),
        attachment_label=get_attachment_summary(rel_state.attachment),
    )


@router.patch(
    "/relationship",
    response_model=RelationshipResponse,
    summary="Update relationship state (developer inspection / sovereign calibration)",
)
async def update_character_relationship(
    payload: RelationshipUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RelationshipResponse:
    """Update relationship state metrics directly for developer debugging and testing."""
    rel_service = RelationshipService(db)
    current_rel = await rel_service.get_relationship_state(relationship_id="user")
    update_data = RelationshipStateUpdate(
        familiarity=payload.familiarity,
        trust=payload.trust,
        comfort=payload.comfort,
        respect=payload.respect,
        affection=payload.affection,
        attachment=payload.attachment,
    )
    new_state = await rel_service.apply_update(
        update_data=update_data,
        expected_version=current_rel.version,
        relationship_id="user",
    )
    return RelationshipResponse(
        summary=synthesize_relationship_summary(new_state),
        familiarity=new_state.familiarity,
        trust=new_state.trust,
        comfort=new_state.comfort,
        affection=new_state.affection,
        attachment=new_state.attachment,
        respect=new_state.respect,
        familiarity_label=get_familiarity_summary(new_state.familiarity),
        trust_label=get_trust_summary(new_state.trust),
        comfort_label=get_comfort_summary(new_state.comfort),
        affection_label=get_affection_summary(new_state.affection),
        attachment_label=get_attachment_summary(new_state.attachment),
    )


@router.get(
    "/life",
    response_model=LifeResponse,
    summary="Retrieve current life state, recent events, and active goals",
)
async def get_character_life(
    db: AsyncSession = Depends(get_db_session),
) -> LifeResponse:
    """Retrieve what Aevum has been doing, current location, and recent episodic events."""
    # Reconcile dynamic schedule with real-world time
    try:
        from app.life.schedule_engine import LifeScheduleEngine
        await LifeScheduleEngine.reconcile_schedule(db, "aevum")
    except Exception as sched_err:
        logger.warning("Dynamic schedule reconcile in get_life skipped: %s", sched_err)

    life_service = LifeService(db)
    life_state = await life_service.get_life_state("aevum")
    events = await life_service.list_events("aevum", limit=10)
    goals = await life_service.list_goals("aevum")

    return LifeResponse(
        current_activity=life_state.current_activity,
        current_location=life_state.current_location,
        status=life_state.status,
        recent_events=[
            LifeEventItem(
                id=e.id,
                title=e.title,
                description=e.description,
                event_type=e.event_type.value,
                occurred_at=e.occurred_at.isoformat(),
                significance=e.significance,
            )
            for e in events
        ],
        active_goals=[
            LifeGoalItem(
                id=g.id,
                title=g.title,
                description=g.description,
                status=g.status.value,
                progress=getattr(g, "progress", None),
            )
            for g in goals
        ],
    )


class SetSituationRequest(BaseModel):
    activity: str
    location: str
    duration_hours: float = 2.0
    status: str = "ACTIVE"


@router.post(
    "/life/situation",
    summary="Dynamically update companion's real-time situation, dating location, or activity",
)
async def set_character_situation(
    payload: SetSituationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Dynamically sets current date location or activity, persisting with an active override."""
    from datetime import datetime, timedelta, timezone
    from app.db.models import CharacterStateRecord, LifeStateRecord

    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(hours=max(0.5, payload.duration_hours))

    # 1. Update LifeStateRecord
    stmt_life = select(LifeStateRecord).where(LifeStateRecord.character_id == "aevum")
    life_rec = (await db.scalars(stmt_life)).first()
    if not life_rec:
        life_rec = LifeStateRecord(
            id="aevum",
            character_id="aevum",
            current_activity=payload.activity,
            current_location=payload.location,
            status=payload.status,
            active_contingency_id="dating_or_custom_activity",
            active_contingency_title=f"{payload.activity} @ {payload.location}",
            contingency_expires_at=expires_at,
            version=1,
        )
        db.add(life_rec)
    else:
        life_rec.current_activity = payload.activity
        life_rec.current_location = payload.location
        life_rec.status = payload.status
        life_rec.active_contingency_id = "dating_or_custom_activity"
        life_rec.active_contingency_title = f"{payload.activity} @ {payload.location}"
        life_rec.contingency_expires_at = expires_at
        life_rec.version += 1
        life_rec.updated_at = now_utc

    # 2. Sync to CharacterStateRecord
    stmt_char = select(CharacterStateRecord).where(CharacterStateRecord.id == "aevum")
    char_rec = (await db.scalars(stmt_char)).first()
    if char_rec:
        char_rec.current_activity = payload.activity
        char_rec.current_location = payload.location

    await db.commit()

    return {
        "status": "success",
        "current_activity": payload.activity,
        "current_location": payload.location,
        "expires_at": expires_at.isoformat(),
    }


@router.get(
    "/memories",
    response_model=list[MemoryItem],
    summary="List persistent memories with entity attribution",
)
async def list_character_memories(
    db: AsyncSession = Depends(get_db_session),
) -> list[MemoryItem]:
    """Retrieve list of long-term memories distinguishing User vs Character ownership."""
    mem_service = MemoryService(db)
    memories = await mem_service.list_memories(limit=100)

    return [
        MemoryItem(
            id=m.id,
            category=m.category.value,
            subject_entity=m.subject_entity.value,
            content=m.content,
            importance=m.importance,
            confidence=m.confidence,
            emotional_weight=m.emotional_weight,
            created_at=m.created_at.isoformat(),
            times_recalled=m.times_recalled,
        )
        for m in memories
    ]


@router.delete(
    "/memories/{memory_id}",
    response_model=MemoryDeleteResponse,
    summary="Delete / forget a long-term memory",
)
async def delete_character_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> MemoryDeleteResponse:
    """Explicitly delete a persistent memory record by ID."""
    mem_service = MemoryService(db)
    deleted = await mem_service.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found.",
        )
    return MemoryDeleteResponse(status="deleted", id=memory_id)


@router.get(
    "/longitudinal-memory",
    response_model=LongitudinalMemoryResponse,
    summary="Retrieve read-only projection of personal biography and longitudinal shared history",
)
async def get_longitudinal_memory(
    db: AsyncSession = Depends(get_db_session),
) -> LongitudinalMemoryResponse:
    """Retrieve read-only projection of personal biography, causal life graph, and shared history.
    
    Guarantees (Rule 19 & ADR-023):
    - Strictly READ-ONLY projection.
    - Zero mutation authority.
    - Preserves Lock F scope segregation and Lock D causal UNKNOWN bounds.
    """
    from app.biography.biography_registry import get_biography_service, get_shared_history_service
    
    bio_service = get_biography_service()
    shared_service = get_shared_history_service()
    rel_state = await RelationshipService(db).get_relationship_state("user")

    facts = [
        BiographicalFactProjection(
            id=f.fact_id,
            domain=f.domain.value,
            attribute_key=f.attribute_key,
            attribute_value=f.attribute_value,
            era=f.era.value,
            canonical_status=f.canonical_status.value,
            recall_level=f.recall_level.value,
            provenance=f.provenance,
        )
        for f in bio_service.get_all_facts()
    ]
    events = [
        LifeEventProjection(
            id=e.event_id,
            era=e.era.value,
            domain=e.domain.value,
            headline=e.headline,
            summary=e.summary,
            canonical_status=e.canonical_status.value,
            recall_level=e.recall_level.value,
            qualia_ids=list(e.qualia_ids),
        )
        for e in bio_service.get_all_events()
    ]
    preferences = [
        PersonalPreferenceProjection(
            id=p.preference_id,
            category=p.category,
            object_name=p.object_name,
            affinity=p.affinity.value,
            era_acquired=p.era_acquired.value,
            causal_state=p.causal_state.value,
            causal_relation_id=p.causal_relation_id,
        )
        for p in bio_service.get_all_preferences()
    ]
    qualia = [
        QualiaAnchorProjection(
            id=q.qualia_id,
            sensory_modality=q.sensory_modality,
            description=q.description,
            emotional_coloring=q.emotional_coloring,
        )
        for q in bio_service.get_all_qualia()
    ]
    contacts = [
        SocialContactProjection(
            id=c.contact_id,
            display_name=c.display_name,
            relation_role=c.relation_role,
            era_first_met=c.era_first_met.value,
            is_user=c.is_user,
        )
        for c in bio_service.get_all_contacts()
    ]
    shared_episodes = [
        SharedHistoryEpisodeProjection(
            id=ep.episode_id,
            episode_type=ep.episode_type.value,
            title=ep.title,
            summary=ep.summary,
            session_anchor=ep.session_anchor,
            key_learnings=list(ep.key_learnings),
            recall_level=ep.recall_level.value,
            created_at_era=ep.created_at_era.value,
        )
        for ep in shared_service.get_recent_episodes(limit=20)
    ]
    relational_dynamics = {
        "familiarity": rel_state.familiarity,
        "trust": rel_state.trust,
        "comfort": rel_state.comfort,
        "respect": rel_state.respect,
        "affection": rel_state.affection,
        "attachment": rel_state.attachment,
    }

    return LongitudinalMemoryResponse(
        facts=facts,
        life_events=events,
        preferences=preferences,
        qualia=qualia,
        contacts=contacts,
        shared_episodes=shared_episodes,
        relational_dynamics=relational_dynamics,
    )


@router.get(
    "/debug",
    response_model=CharacterDebugResponse,
    summary="Retrieve diagnostic state for optional developer debugging",
)
async def get_character_debug(
    db: AsyncSession = Depends(get_db_session),
) -> CharacterDebugResponse:
    """Retrieve sanitized runtime state for developer inspection.
    
    Guarantees:
    - Strictly ZERO private thoughts or chain-of-thought leaked.
    - Strictly ZERO system prompts leaked.
    - Strictly ZERO API keys or credentials exposed.
    """
    char_state = await CharacterStateService(db).get_state("aevum")
    rel_state = await RelationshipService(db).get_relationship_state("user")
    emotion_state = await EmotionService(db).get_emotion_state("aevum")
    mem_service = MemoryService(db)
    all_memories = await mem_service.list_memories(limit=500)
    life_service = LifeService(db)
    all_events = await life_service.list_events("aevum", limit=200)

    return CharacterDebugResponse(
        character_id="aevum",
        state_version=char_state.version,
        relationship_version=rel_state.version,
        raw_state={
            "mood": char_state.mood.value,
            "energy": char_state.energy,
            "stress": char_state.stress,
            "social_energy": char_state.social_energy,
            "confidence": char_state.confidence,
            "irritation": char_state.irritation,
            "loneliness": char_state.loneliness,
            "current_activity": char_state.current_activity,
            "current_location": char_state.current_location,
        },
        raw_relationship={
            "familiarity": rel_state.familiarity,
            "trust": rel_state.trust,
            "comfort": rel_state.comfort,
            "affection": rel_state.affection,
            "attachment": rel_state.attachment,
            "respect": rel_state.respect,
        },
        raw_emotion={
            "type": emotion_state.emotion_type.value,
            "intensity": emotion_state.intensity,
        },
        total_memories=len(all_memories),
        total_events=len(all_events),
        decision_trace=BehaviorPlanner.plan(
            "idle",
            intention=SocialIntentionService.evaluate(
                "idle",
                contract=RelationshipContractEvaluator.evaluate(
                    relationship=rel_state,
                    energy=char_state.energy,
                ),
                desire=DesireEvaluationEngine.evaluate(
                    current_activity=char_state.current_activity,
                    current_location=char_state.current_location,
                    energy=char_state.energy,
                    stress=char_state.stress,
                    social_energy=char_state.social_energy,
                    loneliness=char_state.loneliness,
                    mood=char_state.mood.value,
                ),
            ),
            contract=RelationshipContractEvaluator.evaluate(
                relationship=rel_state,
                energy=char_state.energy,
            ),
            desire=DesireEvaluationEngine.evaluate(
                current_activity=char_state.current_activity,
                current_location=char_state.current_location,
                energy=char_state.energy,
                stress=char_state.stress,
                social_energy=char_state.social_energy,
                loneliness=char_state.loneliness,
                mood=char_state.mood.value,
            ),
        )[1].model_dump(),
        reality_history=[
            r.model_dump()
            for r in (await RealityHistoryService(db).get_history("aevum"))
        ] if await RealityHistoryService(db).get_history("aevum") else None,
    )


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LIVE2D_STORAGE_DIR = _PROJECT_ROOT / "data" / "live2d_models"
_LIVE2D_REGISTRY_FILE = _PROJECT_ROOT / "data" / "live2d_directories.json"

ACTIVE_LIVE2D_DIRECTORIES: dict[str, Path] = {}


def _ensure_live2d_data_dirs() -> None:
    _LIVE2D_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    _LIVE2D_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_live2d_directories() -> dict[str, str]:
    if not _LIVE2D_REGISTRY_FILE.exists():
        return {}
    try:
        import json
        with open(_LIVE2D_REGISTRY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning("Failed to load live2d_directories.json: %s", e)
    return {}


def _save_live2d_directory(model_id: str, path_obj: Path) -> None:
    _ensure_live2d_data_dirs()
    import json
    current = _load_live2d_directories()
    current[model_id] = str(path_obj.resolve())
    current["current"] = str(path_obj.resolve())
    try:
        temp_file = _LIVE2D_REGISTRY_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        temp_file.replace(_LIVE2D_REGISTRY_FILE)
    except Exception as e:
        logger.warning("Failed to persist live2d_directories.json: %s", e)


def _get_live2d_dir(model_id: str) -> Path | None:
    # 1. Check in-memory active cache
    if model_id in ACTIVE_LIVE2D_DIRECTORIES:
        p = ACTIVE_LIVE2D_DIRECTORIES[model_id]
        if p.exists():
            return p
    if model_id == "current" and "current" in ACTIVE_LIVE2D_DIRECTORIES:
        p = ACTIVE_LIVE2D_DIRECTORIES["current"]
        if p.exists():
            return p

    # 2. Check persistent disk registry (recovering from backend restarts)
    registry = _load_live2d_directories()
    path_str = registry.get(model_id) or (registry.get("current") if model_id == "current" else None)
    if path_str:
        p = Path(path_str)
        if p.exists():
            ACTIVE_LIVE2D_DIRECTORIES[model_id] = p
            return p
    return None


def _find_live2d_model_file(root_dir: Path) -> Path | None:
    if not root_dir.exists():
        return None
    if root_dir.is_file():
        if root_dir.suffix.lower() == ".json":
            return root_dir
        return None

    # Priority 1: *.model3.json in root_dir
    for f in sorted(root_dir.glob("*.model3.json")):
        return f
    # Priority 2: *.model.json in root_dir
    for f in sorted(root_dir.glob("*.model.json")):
        return f
    # Priority 3: index.json in root_dir
    idx = root_dir / "index.json"
    if idx.exists() and idx.is_file():
        return idx
    # Priority 4: recursive *.model3.json
    for f in sorted(root_dir.rglob("*.model3.json")):
        return f
    # Priority 5: recursive *.model.json
    for f in sorted(root_dir.rglob("*.model.json")):
        return f
    # Priority 6: recursive index.json
    for f in sorted(root_dir.rglob("index.json")):
        return f
    return None


def _find_preview_icon(base_dir: Path) -> Path | None:
    candidate_names = [
        "icon.png", "icon.jpg", "icon.jpeg", "icon.webp",
        "avatar.png", "avatar.jpg", "avatar.jpeg", "avatar.webp",
        "preview.png", "preview.jpg", "preview.jpeg", "preview.webp",
        "character.png", "character.jpg", "character.jpeg", "character.webp",
        "sample.png", "sample.jpg", "sample.jpeg", "sample.webp",
    ]
    for name in candidate_names:
        c = base_dir / name
        if c.exists() and c.is_file():
            return c
    # Check parent dir if base_dir is nested (e.g. runtime/)
    if base_dir.parent.exists() and base_dir.parent != base_dir:
        for name in candidate_names:
            c = base_dir.parent / name
            if c.exists() and c.is_file():
                return c
    return None


class ResolveLocalModelRequest(BaseModel):
    file_path: str


class ResolveLocalModelResponse(BaseModel):
    success: bool
    name: str
    avatar_data_url: str | None = None
    model_json_path: str | None = None
    model_serve_url: str | None = None
    message: str


@router.get("/avatar/live2d-serve/{model_id}/{subpath:path}")
async def serve_live2d_model_file(model_id: str, subpath: str):
    """Serve Live2D model assets (.moc3, textures, physics) via standard HTTP for WebGL rendering."""
    import mimetypes
    import os
    from fastapi.responses import FileResponse

    base_dir = _get_live2d_dir(model_id)
    if not base_dir or not base_dir.exists():
        raise HTTPException(status_code=404, detail=f"Model directory for {model_id} not found")

    target_file = (base_dir / subpath).resolve()
    base_dir_resolved = base_dir.resolve()

    try:
        c_base = os.path.normcase(os.path.abspath(str(base_dir_resolved)))
        c_target = os.path.normcase(os.path.abspath(str(target_file)))
        if not (c_target == c_base or c_target.startswith(c_base + os.sep)):
            raise HTTPException(status_code=403, detail="Access denied")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail=f"File {subpath} not found in model {model_id}")

    if subpath.endswith(".model3.json"):
        try:
            import json
            from fastapi.responses import JSONResponse
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            filerefs = data.setdefault("FileReferences", {})
            if "Motions" not in filerefs:
                motions = {}
                for anim_dir in [base_dir / "animations", base_dir / "motions"]:
                    if anim_dir.exists() and anim_dir.is_dir():
                        for m in sorted(anim_dir.glob("*.motion3.json")):
                            clean_name = m.name.replace(".motion3.json", "")
                            grp = clean_name.split("_")[0]
                            entry = {"File": f"{anim_dir.name}/{m.name}"}
                            motions.setdefault(grp, []).append(entry)
                            if grp.lower() == "idle":
                                motions.setdefault("idle", []).append(entry)
                                motions.setdefault("Idle", []).append(entry)
                if motions:
                    filerefs["Motions"] = motions

            if "Expressions" not in filerefs:
                expressions = []
                exp_dir = base_dir / "expressions"
                if exp_dir.exists() and exp_dir.is_dir():
                    for exp in sorted(exp_dir.glob("*.exp3.json")):
                        clean_name = exp.name.replace(".exp3.json", "").lower()
                        expressions.append({
                            "Name": clean_name,
                            "File": f"expressions/{exp.name}"
                        })
                if expressions:
                    filerefs["Expressions"] = expressions

            groups = data.setdefault("Groups", [])
            group_names = {g.get("Name") for g in groups}
            if "EyeBlink" not in group_names:
                groups.append({
                    "Target": "Parameter",
                    "Name": "EyeBlink",
                    "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]
                })
            else:
                for g in groups:
                    if g.get("Name") == "EyeBlink" and not g.get("Ids"):
                        g["Ids"] = ["ParamEyeLOpen", "ParamEyeROpen"]

            if "LipSync" not in group_names:
                groups.append({
                    "Target": "Parameter",
                    "Name": "LipSync",
                    "Ids": ["ParamMouthOpen", "ParamMouthOpenY"]
                })
            else:
                for g in groups:
                    if g.get("Name") == "LipSync" and not g.get("Ids"):
                        g["Ids"] = ["ParamMouthOpen", "ParamMouthOpenY"]

            return JSONResponse(content=data)
        except Exception as e:
            logger.warning("Failed to enhance model3.json: %s", e)

    media_type, _ = mimetypes.guess_type(str(target_file))
    if subpath.endswith(".moc3") or subpath.endswith(".moc"):
        media_type = "application/octet-stream"
    elif subpath.endswith(".json"):
        media_type = "application/json"

    return FileResponse(target_file, media_type=media_type)


@router.post("/avatar/resolve-local-model", response_model=ResolveLocalModelResponse)
async def resolve_local_model(payload: ResolveLocalModelRequest) -> ResolveLocalModelResponse:
    """Resolve and extract an avatar/portrait from a user-specified local Live2D or image path."""
    raw_path = payload.file_path.strip().strip('"').strip("'")
    if not raw_path:
        raise HTTPException(status_code=400, detail="Empty path provided")

    path_obj = Path(raw_path)
    if not path_obj.exists():
        return ResolveLocalModelResponse(
            success=False,
            name="",
            message=f"路径在本地磁盘中不存在: {raw_path}",
        )

    # 1. If it's an image file directly
    if path_obj.is_file() and path_obj.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
        parent_dir = path_obj.parent
        dir_id = parent_dir.name
        ACTIVE_LIVE2D_DIRECTORIES[dir_id] = parent_dir
        ACTIVE_LIVE2D_DIRECTORIES["current"] = parent_dir
        _save_live2d_directory(dir_id, parent_dir)
        serve_img_url = f"http://127.0.0.1:8000/character/avatar/live2d-serve/{dir_id}/{path_obj.name}"
        return ResolveLocalModelResponse(
            success=True,
            name=path_obj.stem,
            avatar_data_url=serve_img_url,
            message="成功读取本地角色图片",
        )

    # 2. If it's a directory or .json file
    if path_obj.is_file() and path_obj.suffix.lower() == ".json":
        model_json_file = path_obj
    else:
        model_json_file = _find_live2d_model_file(path_obj)

    if not model_json_file or not model_json_file.exists():
        return ResolveLocalModelResponse(
            success=False,
            name=path_obj.name,
            message=f"在该目录及子目录中未找到 .model3.json 或 .model.json 配置文件: {raw_path}",
        )

    # Anchor base_dir to the parent directory of the model JSON file so relative paths resolve
    base_dir = model_json_file.parent
    model_name = path_obj.parent.name if path_obj.is_file() else path_obj.name
    model_id = model_name
    ACTIVE_LIVE2D_DIRECTORIES[model_id] = base_dir
    ACTIVE_LIVE2D_DIRECTORIES[base_dir.name] = base_dir
    ACTIVE_LIVE2D_DIRECTORIES["current"] = base_dir
    _save_live2d_directory(model_id, base_dir)
    if base_dir.name != model_id:
        _save_live2d_directory(base_dir.name, base_dir)

    serve_url = f"http://127.0.0.1:8000/character/avatar/live2d-serve/{model_id}/{model_json_file.name}"

    # Look for icon.jpg, icon.png, avatar.png, preview.png, etc. (NEVER raw texture sheets)
    icon_file = _find_preview_icon(base_dir)
    avatar_url = None
    if icon_file:
        try:
            rel = icon_file.relative_to(base_dir).as_posix()
            avatar_url = f"http://127.0.0.1:8000/character/avatar/live2d-serve/{model_id}/{rel}"
        except Exception:
            pass

    return ResolveLocalModelResponse(
        success=True,
        name=model_name,
        avatar_data_url=avatar_url,
        model_json_path=str(model_json_file),
        model_serve_url=serve_url,
        message=f"已成功加载 Live2D 模型 [{model_name}]" + (f" (包含预览图 {icon_file.name})" if icon_file else " (已激活 WebGL 骨骼渲染)"),
    )


@router.post("/avatar/upload-live2d-zip", response_model=ResolveLocalModelResponse)
async def upload_live2d_zip(file: UploadFile = File(...)) -> ResolveLocalModelResponse:
    """Extract an uploaded Live2D model zip archive and register it for streaming."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的 Live2D 模型压缩包")

    _ensure_live2d_data_dirs()
    import zipfile
    import io
    import re
    import shutil

    clean_stem = re.sub(r"[^\w\-_]", "_", Path(file.filename).stem) or "custom_model"
    extract_target = _LIVE2D_STORAGE_DIR / clean_stem
    if extract_target.exists():
        counter = 1
        while (_LIVE2D_STORAGE_DIR / f"{clean_stem}_{counter}").exists():
            counter += 1
        extract_target = _LIVE2D_STORAGE_DIR / f"{clean_stem}_{counter}"
        clean_stem = extract_target.name

    extract_target.mkdir(parents=True, exist_ok=True)

    try:
        contents = await file.read()
        with zipfile.ZipFile(io.BytesIO(contents)) as z:
            for member in z.infolist():
                member_path = Path(member.filename)
                # Prevent zip slip directory traversal attacks
                if member_path.is_absolute() or ".." in member_path.parts:
                    continue
                z.extract(member, extract_target)
    except Exception as e:
        logger.error("Failed to extract Live2D zip: %s", e)
        shutil.rmtree(extract_target, ignore_errors=True)
        return ResolveLocalModelResponse(
            success=False,
            name=clean_stem,
            message=f"解压模型压缩包失败: {e}",
        )

    # Discover model file
    model_json = _find_live2d_model_file(extract_target)
    if not model_json:
        return ResolveLocalModelResponse(
            success=False,
            name=clean_stem,
            message="压缩包内未找到 .model3.json 或 .model.json 配置文件，请确认压缩包内包含完整的 Live2D 模型数据",
        )

    base_dir = model_json.parent
    model_id = clean_stem
    ACTIVE_LIVE2D_DIRECTORIES[model_id] = base_dir
    ACTIVE_LIVE2D_DIRECTORIES["current"] = base_dir
    _save_live2d_directory(model_id, base_dir)

    serve_url = f"http://127.0.0.1:8000/character/avatar/live2d-serve/{model_id}/{model_json.name}"

    icon_file = _find_preview_icon(base_dir)
    avatar_url = None
    if icon_file:
        try:
            rel = icon_file.relative_to(base_dir).as_posix()
            avatar_url = f"http://127.0.0.1:8000/character/avatar/live2d-serve/{model_id}/{rel}"
        except Exception:
            pass

    return ResolveLocalModelResponse(
        success=True,
        name=clean_stem,
        avatar_data_url=avatar_url,
        model_json_path=str(model_json),
        model_serve_url=serve_url,
        message=f"已成功解压并加载 Live2D 模型 [{clean_stem}]！已启动 WebGL 骨骼渲染！",
    )


class AvailableModelItem(BaseModel):
    id: str
    name: str
    model_serve_url: str
    avatar_data_url: str | None = None
    is_current: bool = False


class SetActiveModelRequest(BaseModel):
    model_id: str


@router.get("/avatar/current-model")
async def get_current_model(request: Request) -> dict[str, Any]:
    """Retrieve the currently active persistent Live2D model configuration."""
    _ensure_live2d_data_dirs()
    registry = _load_live2d_directories()
    current_path_str = registry.get("current")

    active_dir = None
    if current_path_str and Path(current_path_str).exists():
        active_dir = Path(current_path_str)
    elif _LIVE2D_STORAGE_DIR.exists():
        # Auto-fallback: discover any existing model in data/live2d_models
        for sub in sorted(_LIVE2D_STORAGE_DIR.iterdir()):
            if sub.is_dir() and _find_live2d_model_file(sub):
                active_dir = sub
                break

    if not active_dir:
        return {"active": False, "name": "", "model_serve_url": "", "avatar_data_url": ""}

    model_file = _find_live2d_model_file(active_dir)
    if not model_file:
        return {"active": False, "name": "", "model_serve_url": "", "avatar_data_url": ""}

    base_dir = model_file.parent
    model_id = active_dir.name
    ACTIVE_LIVE2D_DIRECTORIES[model_id] = base_dir
    ACTIVE_LIVE2D_DIRECTORIES["current"] = base_dir
    _save_live2d_directory(model_id, base_dir)

    base_url = str(request.base_url).rstrip("/")
    serve_url = f"{base_url}/character/avatar/live2d-serve/{model_id}/{model_file.name}"
    icon_file = _find_preview_icon(base_dir)
    avatar_url = None
    if icon_file:
        try:
            rel = icon_file.relative_to(base_dir).as_posix()
            avatar_url = f"{base_url}/character/avatar/live2d-serve/{model_id}/{rel}"
        except Exception:
            pass

    return {
        "active": True,
        "name": model_id,
        "model_id": model_id,
        "model_serve_url": serve_url,
        "avatar_data_url": avatar_url,
    }


@router.get("/avatar/available-models", response_model=list[AvailableModelItem])
async def list_available_models(request: Request) -> list[AvailableModelItem]:
    """List all available local Live2D models on disk and in registry."""
    _ensure_live2d_data_dirs()
    registry = _load_live2d_directories()
    current_path_str = registry.get("current")
    current_canon = str(Path(current_path_str).resolve()) if current_path_str else ""
    base_url = str(request.base_url).rstrip("/")

    models: list[AvailableModelItem] = []
    seen_ids: set[str] = set()

    # 1. Scan storage directory data/live2d_models
    if _LIVE2D_STORAGE_DIR.exists():
        for sub in sorted(_LIVE2D_STORAGE_DIR.iterdir()):
            if not sub.is_dir():
                continue
            model_file = _find_live2d_model_file(sub)
            if not model_file:
                continue
            base_dir = model_file.parent
            model_id = sub.name
            seen_ids.add(model_id)
            ACTIVE_LIVE2D_DIRECTORIES[model_id] = base_dir

            serve_url = f"{base_url}/character/avatar/live2d-serve/{model_id}/{model_file.name}"
            icon_file = _find_preview_icon(base_dir)
            avatar_url = None
            if icon_file:
                try:
                    rel = icon_file.relative_to(base_dir).as_posix()
                    avatar_url = f"{base_url}/character/avatar/live2d-serve/{model_id}/{rel}"
                except Exception:
                    pass

            is_cur = current_canon == str(base_dir.resolve()) or current_canon == str(sub.resolve())
            models.append(
                AvailableModelItem(
                    id=model_id,
                    name=model_id,
                    model_serve_url=serve_url,
                    avatar_data_url=avatar_url,
                    is_current=is_cur,
                )
            )

    # 2. Check remaining registered directories
    for reg_id, reg_path in registry.items():
        if reg_id in ("current",) or reg_id in seen_ids:
            continue
        p = Path(reg_path)
        if not p.exists():
            continue
        model_file = _find_live2d_model_file(p)
        if not model_file:
            continue
        base_dir = model_file.parent
        ACTIVE_LIVE2D_DIRECTORIES[reg_id] = base_dir
        serve_url = f"{base_url}/character/avatar/live2d-serve/{reg_id}/{model_file.name}"
        icon_file = _find_preview_icon(base_dir)
        avatar_url = None
        if icon_file:
            try:
                rel = icon_file.relative_to(base_dir).as_posix()
                avatar_url = f"{base_url}/character/avatar/live2d-serve/{reg_id}/{rel}"
            except Exception:
                pass

        is_cur = current_canon == str(base_dir.resolve()) or current_canon == str(p.resolve())
        models.append(
            AvailableModelItem(
                id=reg_id,
                name=reg_id,
                model_serve_url=serve_url,
                avatar_data_url=avatar_url,
                is_current=is_cur,
            )
        )

    return models


@router.post("/avatar/set-active-model")
async def set_active_model(payload: SetActiveModelRequest, request: Request) -> dict[str, Any]:
    """Set the active Live2D model for the companion."""
    _ensure_live2d_data_dirs()
    target_id = payload.model_id.strip()
    target_dir = _get_live2d_dir(target_id)
    if not target_dir or not target_dir.exists():
        cand = _LIVE2D_STORAGE_DIR / target_id
        if cand.exists():
            target_dir = cand
        else:
            raise HTTPException(status_code=404, detail=f"Model '{target_id}' not found on server")

    model_file = _find_live2d_model_file(target_dir)
    if not model_file:
        raise HTTPException(status_code=400, detail=f"No model3.json found in '{target_id}'")

    base_dir = model_file.parent
    ACTIVE_LIVE2D_DIRECTORIES[target_id] = base_dir
    ACTIVE_LIVE2D_DIRECTORIES["current"] = base_dir
    _save_live2d_directory(target_id, base_dir)

    base_url = str(request.base_url).rstrip("/")
    serve_url = f"{base_url}/character/avatar/live2d-serve/{target_id}/{model_file.name}"
    icon_file = _find_preview_icon(base_dir)
    avatar_url = None
    if icon_file:
        try:
            rel = icon_file.relative_to(base_dir).as_posix()
            avatar_url = f"{base_url}/character/avatar/live2d-serve/{target_id}/{rel}"
        except Exception:
            pass

    return {
        "status": "success",
        "model_id": target_id,
        "model_serve_url": serve_url,
        "avatar_data_url": avatar_url,
    }



