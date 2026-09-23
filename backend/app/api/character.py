"""Character and companion domain API endpoints for Aevum Core.

Exposes read-only projections and user-consented management endpoints (e.g. forgetting memories)
for the desktop client. Adheres strictly to the architectural invariant:
Backend owns reality; frontend is purely a projection layer.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.engine_models import format_emotion_summary
from app.character.service import CharacterDefinitionService
from app.character.state_service import CharacterStateService
from app.db.session import get_db_session
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
) -> CharacterStateResponse:
    """Retrieve Aevum's current identity, baseline mood, energy, and situational condition."""
    char_def = await CharacterDefinitionService(db).get_character("aevum")
    if char_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character definition for 'aevum' not found.",
        )

    char_state = await CharacterStateService(db).get_state("aevum")
    emotion_state = await EmotionService(db).get_emotion_state("aevum")
    life_state = await LifeService(db).get_life_state("aevum")

    natural_mood_label = f"{char_state.mood.value.capitalize()} ({emotion_state.emotion_type.value.capitalize()})"

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


@router.get(
    "/life",
    response_model=LifeResponse,
    summary="Retrieve current life state, recent events, and active goals",
)
async def get_character_life(
    db: AsyncSession = Depends(get_db_session),
) -> LifeResponse:
    """Retrieve what Aevum has been doing, current location, and recent episodic events."""
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

