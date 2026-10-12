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


@pytest.mark.asyncio
async def test_patch_character_relationship(client: AsyncClient):
    """Verify PATCH /character/relationship updates metrics dynamically for dev calibration."""
    patch_payload = {
        "familiarity": 0.85,
        "trust": 0.90,
        "comfort": 0.80,
        "respect": 0.75,
    }
    response = await client.patch("/character/relationship", json=patch_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["familiarity"] == 0.85
    assert data["trust"] == 0.90
    assert data["comfort"] == 0.80
    assert data["respect"] == 0.75

    # Verify affection update
    patch_aff = {
        "affection": 0.95,
        "attachment": 0.90,
    }
    aff_res = await client.patch("/character/relationship", json=patch_aff)
    assert aff_res.status_code == 200
    assert aff_res.json()["affection"] == 0.95
    assert aff_res.json()["attachment"] == 0.90

    # Verify subsequent GET reflects updated state
    get_res = await client.get("/character/relationship")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["familiarity"] == 0.85
    assert get_data["affection"] == 0.95


@pytest.mark.asyncio
async def test_patch_character_state(client: AsyncClient):
    """Verify PATCH /character/state calibrates mood, emotion, and indicators for dev debugging."""
    state_payload = {
        "mood": "good",
        "emotion_type": "HAPPY",
        "intensity": 0.85,
        "energy": 0.90,
        "stress": 0.10,
    }
    response = await client.patch("/character/state", json=state_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["mood"] == "good"
    assert data["emotion"]["type"] == "HAPPY"
    assert "心情愉悦" in data["natural_mood"] or "Good" in data["natural_mood"]
    assert data["energy"] == 0.90
    assert data["stress"] == 0.10


@pytest.mark.asyncio
async def test_resolve_local_model_nonexistent(client: AsyncClient):
    """Verify POST /character/avatar/resolve-local-model handles nonexistent path safely."""
    res = await client.post(
        "/character/avatar/resolve-local-model",
        json={"file_path": "Z:\\nonexistent\\model.model3.json"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "不存在" in data["message"]


@pytest.mark.asyncio
async def test_resolve_local_model_with_temp_dir(client: AsyncClient, tmp_path):
    """Verify POST /character/avatar/resolve-local-model extracts icon and model info."""
    # Create fake live2d model dir
    model_dir = tmp_path / "test_char_vts"
    model_dir.mkdir()
    model_json = model_dir / "char.model3.json"
    model_json.write_text('{"Version": 3, "FileReferences": {"Textures": ["tex.png"]}}', encoding="utf-8")
    icon_file = model_dir / "icon.jpg"
    icon_file.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")

    res = await client.post(
        "/character/avatar/resolve-local-model",
        json={"file_path": str(model_json)},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["name"] == "test_char_vts"
    assert "live2d-serve/test_char_vts/icon.jpg" in data["avatar_data_url"]
    assert "live2d-serve/test_char_vts/char.model3.json" in data["model_serve_url"]

    # Also verify serving the model3.json via HTTP
    serve_res = await client.get("/character/avatar/live2d-serve/test_char_vts/char.model3.json")
    assert serve_res.status_code == 200
    serve_json = serve_res.json()
    assert serve_json["Version"] == 3
    # Verify auto-populated groups
    assert any(g.get("Name") == "EyeBlink" for g in serve_json["Groups"])
    assert any(g.get("Name") == "LipSync" for g in serve_json["Groups"])


@pytest.mark.asyncio
async def test_resolve_local_model_nested_and_no_texture_leak(client: AsyncClient, tmp_path):
    """Verify nested .model3.json discovery and that textures[0] is NEVER returned as avatar_data_url."""
    # Create nested folder: char_root/runtime/model.model3.json
    root_dir = tmp_path / "hiyori_bundle"
    runtime_dir = root_dir / "runtime"
    runtime_dir.mkdir(parents=True)
    model_json = runtime_dir / "hiyori.model3.json"
    model_json.write_text('{"Version": 3, "FileReferences": {"Textures": ["textures/texture_00.png"]}}', encoding="utf-8")
    tex_dir = runtime_dir / "textures"
    tex_dir.mkdir()
    (tex_dir / "texture_00.png").write_bytes(b"fake_texture_atlas_data")

    # Point to the root directory (not runtime dir)
    res = await client.post(
        "/character/avatar/resolve-local-model",
        json={"file_path": str(root_dir)},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["name"] == "hiyori_bundle"
    # CRITICAL: avatar_data_url must be None, NOT the disassembled texture atlas!
    assert data["avatar_data_url"] is None
    assert "hiyori.model3.json" in data["model_serve_url"]

    # Verify serving texture asset works relative to model JSON parent
    tex_res = await client.get("/character/avatar/live2d-serve/hiyori_bundle/textures/texture_00.png")
    assert tex_res.status_code == 200
    assert tex_res.content == b"fake_texture_atlas_data"

    # Test server restart recovery: wipe in-memory cache and verify still serves from persistent registry
    from app.api.character import ACTIVE_LIVE2D_DIRECTORIES
    ACTIVE_LIVE2D_DIRECTORIES.clear()

    recover_res = await client.get("/character/avatar/live2d-serve/hiyori_bundle/textures/texture_00.png")
    assert recover_res.status_code == 200
    assert recover_res.content == b"fake_texture_atlas_data"


@pytest.mark.asyncio
async def test_upload_live2d_zip(client: AsyncClient, tmp_path):
    """Verify POST /character/avatar/upload-live2d-zip extracts and serves model."""
    import io
    import zipfile

    # Build an in-memory zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("model_pack/character.model3.json", '{"Version": 3, "FileReferences": {}}')
        z.writestr("model_pack/icon.png", b"fake_icon_png")

    zip_bytes = zip_buffer.getvalue()

    files = {"file": ("my_live2d_waifu.zip", zip_bytes, "application/zip")}
    res = await client.post("/character/avatar/upload-live2d-zip", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "my_live2d_waifu" in data["name"]
    assert data["model_serve_url"] is not None
    assert "character.model3.json" in data["model_serve_url"]
    assert data["avatar_data_url"] is not None
    assert "icon.png" in data["avatar_data_url"]

    # Verify serving icon via HTTP
    serve_icon = await client.get(data["avatar_data_url"].replace("http://127.0.0.1:8000", ""))
    assert serve_icon.status_code == 200
    assert serve_icon.content == b"fake_icon_png"




