import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryCategory, MemorySubjectEntity
from app.memory.service import MemoryService


@pytest.mark.asyncio
async def test_get_character_state(client: AsyncClient):
    """Verify GET /character/state returns 200 with full identity and situational state."""
    response = await client.get("/character/state")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Aevum"
    assert "mood" in data
    assert "natural_mood" in data
    assert "energy" in data
    assert 0.0 <= data["energy"] <= 1.0
    assert "current_activity" in data
    assert "current_location" in data
    assert "emotion" in data
    assert "type" in data["emotion"]
    assert "summary" in data["emotion"]
    assert data["status"] == "online"


@pytest.mark.asyncio
async def test_get_character_relationship(client: AsyncClient):
    """Verify GET /character/relationship returns 200 with multidimensional metrics and natural summaries."""
    response = await client.get("/character/relationship")
    assert response.status_code == 200

    data = response.json()
    assert "summary" in data
    assert len(data["summary"]) > 0
    assert "familiarity" in data
    assert "trust" in data
    assert "comfort" in data
    assert "affection" in data
    assert "attachment" in data
    assert "respect" in data
    assert "familiarity_label" in data
    assert "trust_label" in data
    assert "comfort_label" in data


@pytest.mark.asyncio
async def test_get_character_life(client: AsyncClient):
    """Verify GET /character/life returns 200 with life activities, events, and goals."""
    response = await client.get("/character/life")
    assert response.status_code == 200

    data = response.json()
    assert "current_activity" in data
    assert "current_location" in data
    assert "recent_events" in data
    assert "active_goals" in data
    assert isinstance(data["recent_events"], list)
    assert isinstance(data["active_goals"], list)


@pytest.mark.asyncio
async def test_memories_crud_api(client: AsyncClient, test_session: AsyncSession):
    """Verify GET /character/memories and DELETE /character/memories/{id}."""
    # 1. Seed a test memory with USER subject entity
    mem_service = MemoryService(test_session)
    mem = await mem_service.create_memory(
        category=MemoryCategory.PREFERENCE,
        content="Likes Earl Grey tea with lemon",
        importance=0.8,
        confidence=0.95,
        subject_entity=MemorySubjectEntity.USER,
    )

    # 2. Retrieve via API
    res = await client.get("/character/memories")
    assert res.status_code == 200
    memories = res.json()
    assert isinstance(memories, list)
    found = next((m for m in memories if m["id"] == mem.id), None)
    assert found is not None
    assert found["content"] == "Likes Earl Grey tea with lemon"
    assert found["subject_entity"] == "USER"
    assert found["category"] == "PREFERENCE"

    # 3. Delete memory via API
    del_res = await client.delete(f"/character/memories/{mem.id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"
    assert del_res.json()["id"] == mem.id

    # 4. Verify gone
    res_after = await client.get("/character/memories")
    memories_after = res_after.json()
    assert not any(m["id"] == mem.id for m in memories_after)

    # 5. Delete non-existent returns 404
    del_404 = await client.delete("/character/memories/non-existent-id")
    assert del_404.status_code == 404


@pytest.mark.asyncio
async def test_get_character_debug(client: AsyncClient):
    """Verify GET /character/debug returns runtime diagnostics without thought leakage."""
    response = await client.get("/character/debug")
    assert response.status_code == 200

    data = response.json()
    assert data["character_id"] == "aevum"
    assert "state_version" in data
    assert "relationship_version" in data
    assert "raw_state" in data
    assert "raw_relationship" in data
    assert "raw_emotion" in data
    assert "total_memories" in data
    assert "total_events" in data

    # Verify absence of private internals
    raw_text = response.text
    assert "thought_content" not in raw_text
    assert "system_prompt" not in raw_text
    assert "api_key" not in raw_text.lower()
