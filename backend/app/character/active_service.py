"""Active companion management service for Project Aevum.

Governed by AGENTS.md:
- Rule 11: The application owns persistent character state.
- Rule 19: Desktop UI is a projection; Core owns reality.
- Multi-Companion Invariant:
  1. Su Tang (aevum) must be preserved indefinitely with full history & memories.
  2. New companion personas are completely independent (0 memories, fresh relationship).
  3. Active companion selection is persisted in ApplicationStateRecord.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.state_models import CharacterMood, CharacterState
from app.db.models import (
    ApplicationStateRecord,
    CharacterBoundaryRecord,
    CharacterDefinitionRecord,
    CharacterPersonalityTraitRecord,
    CharacterPreferenceRecord,
    CharacterStateRecord,
    Conversation,
    EmotionStateRecord,
    LifeStateRecord,
    MemoryRecord,
    Message,
    RelationshipRecord,
    utc_now,
)

logger = logging.getLogger(__name__)


async def get_active_character_id(session: AsyncSession) -> str:
    """Retrieve currently active companion ID, defaulting to 'aevum'."""
    stmt = select(ApplicationStateRecord).where(ApplicationStateRecord.id == "canonical")
    app_state = (await session.scalars(stmt)).first()
    if not app_state:
        app_state = ApplicationStateRecord(
            id="canonical",
            active_character_id="aevum",
            version=1,
            updated_at=utc_now(),
        )
        session.add(app_state)
        await session.commit()
        return "aevum"
    return app_state.active_character_id or "aevum"


async def set_active_character_id(session: AsyncSession, character_id: str) -> str:
    """Switch currently active companion ID."""
    stmt = select(ApplicationStateRecord).where(ApplicationStateRecord.id == "canonical")
    app_state = (await session.scalars(stmt)).first()
    if not app_state:
        app_state = ApplicationStateRecord(
            id="canonical",
            active_character_id=character_id,
            version=1,
            updated_at=utc_now(),
        )
        session.add(app_state)
    else:
        app_state.active_character_id = character_id
        app_state.version += 1
        app_state.updated_at = utc_now()
    await session.commit()
    logger.info("Active companion switched to '%s'", character_id)
    return character_id


async def list_characters_overview(session: AsyncSession) -> dict[str, Any]:
    """List all available companion personas with memory and relationship metadata."""
    active_id = await get_active_character_id(session)

    # 1. Fetch character definitions
    stmt = select(CharacterDefinitionRecord).order_by(CharacterDefinitionRecord.updated_at.desc())
    char_records = (await session.scalars(stmt)).all()

    # 2. Gather memory counts
    mem_counts_stmt = select(MemoryRecord.character_id, func.count(MemoryRecord.id)).group_by(MemoryRecord.character_id)
    mem_counts_res = await session.execute(mem_counts_stmt)
    mem_counts = dict(mem_counts_res.fetchall())

    # 3. Gather message counts
    msg_counts_stmt = select(Conversation.character_id, func.count(Message.id)).join(
        Message, Conversation.id == Message.conversation_id
    ).group_by(Conversation.character_id)
    msg_counts_res = await session.execute(msg_counts_stmt)
    msg_counts = dict(msg_counts_res.fetchall())

    # 4. Gather relationships
    rel_stmt = select(RelationshipRecord)
    rel_res = (await session.scalars(rel_stmt)).all()
    rels = {r.id: r for r in rel_res}

    items = []
    seen_ids = set()
    # Ensure aevum comes first, followed by others
    sorted_recs = sorted(char_records, key=lambda r: (0 if r.id == "aevum" else 1, r.name))
    for r in sorted_recs:
        if r.id in seen_ids:
            continue
        # Filter out ephemeral automated test fixture records
        if r.id != "aevum" and r.id != active_id:
            if r.id.startswith("char_gc") or r.id.startswith("test_char_"):
                continue
            if r.id.startswith("char_") and len(r.id) == 13 and msg_counts.get(r.id, 0) == 0:
                continue
            if r.name in ("昔涟", "涟宝", "林晚 (Lin Wan)", "晚晚 (Wanwan)") and msg_counts.get(r.id, 0) == 0:
                continue

        seen_ids.add(r.id)

        rel = rels.get(r.id)
        if r.id == "aevum" and (rel is None or rel.affection == 0.0):
            rel = rels.get("user") or rel

        items.append({
            "id": r.id,
            "name": r.name,
            "occupation": r.occupation,
            "background": r.background[:100] + "..." if len(r.background or "") > 100 else (r.background or ""),
            "avatar": r.name[0] if r.name else "伴",
            "is_active": (r.id == active_id),
            "memory_count": mem_counts.get(r.id, 0),
            "message_count": msg_counts.get(r.id, 0),
            "affection": getattr(rel, "affection", 0.0) if rel else 0.0,
            "trust": getattr(rel, "trust", 0.2) if rel else 0.2,
        })

    # If no companion found in DB, return default aevum entry
    if not items:
        items = [{
            "id": "aevum",
            "name": "苏棠",
            "occupation": "计算机系大四学生 / 独立游戏开发者",
            "background": "计算机系大四学生兼独立游戏开发者",
            "avatar": "棠",
            "is_active": True,
            "memory_count": 0,
            "message_count": 0,
            "affection": 0.8,
            "trust": 0.8,
        }]

    return {
        "active_character_id": active_id,
        "characters": items,
    }


async def create_independent_companion(
    session: AsyncSession,
    name: str,
    occupation: str,
    background: str,
    personality_traits: list[str],
    speaking_style: str = "温和自然、真诚随和",
    custom_character_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a completely independent companion with 0 memories and clean stranger relationship."""
    char_id = custom_character_id or f"companion_{uuid.uuid4().hex[:6]}"
    now = utc_now()

    # 1. Definition
    char_def = CharacterDefinitionRecord(
        id=char_id,
        name=name,
        age=20,
        occupation=occupation,
        background=background,
        version=1,
        updated_at=now,
    )
    session.add(char_def)

    # 2. Traits
    for idx, trait in enumerate(personality_traits or ["真诚", "独立", "温和"]):
        session.add(CharacterPersonalityTraitRecord(
            id=str(uuid.uuid4()),
            character_id=char_id,
            dimension="core_trait",
            trait=trait,
            order_index=idx,
        ))

    # 3. State
    session.add(CharacterStateRecord(
        id=char_id,
        version=1,
        updated_at=now,
        mood="calm",
        energy=0.8,
        stress=0.1,
        social_energy=0.7,
        confidence=0.7,
        irritation=0.0,
        loneliness=0.1,
        current_activity="日常整理/休息中",
        current_location="生活空间",
    ))

    # 4. Life State
    session.add(LifeStateRecord(
        id=char_id,
        character_id=char_id,
        version=1,
        updated_at=now,
        current_activity="日常整理/休息中",
        current_location="生活空间",
        status="ACTIVE",
    ))

    # 5. Emotion State
    session.add(EmotionStateRecord(
        id=char_id,
        character_id=char_id,
        emotion_type="CALM",
        intensity=0.5,
        version=1,
        created_at=now,
        updated_at=now,
    ))

    # 6. Relationship (Fresh stranger baseline: affection 0.0, trust 0.20, familiarity 0.05)
    session.add(RelationshipRecord(
        id=char_id,
        user_id="user",
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=0.05,
        trust=0.20,
        comfort=0.10,
        affection=0.00,
        attachment=0.00,
        respect=0.50,
    ))

    # 7. Initial clean conversation with greeting
    conv = Conversation(
        id=str(uuid.uuid4()),
        character_id=char_id,
        created_at=now,
        updated_at=now,
    )
    session.add(conv)
    greeting_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        role="assistant",
        content=f"你好，我是{name}。初次见面，很高兴认识你。",
        created_at=now,
    )
    session.add(greeting_msg)

    # 8. Set as active companion
    await set_active_character_id(session, char_id)
    await session.commit()

    return {
        "character_id": char_id,
        "name": name,
        "occupation": occupation,
        "conversation_id": conv.id,
        "initial_message": greeting_msg.content,
    }
