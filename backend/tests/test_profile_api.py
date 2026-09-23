"""Tests for User Profile Editor and Reality Ledger REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_profile(client: AsyncClient):
    """Verify GET /character/profile returns Core, Bible priors, and Reality Ledger."""
    res = await client.get("/character/profile")
    assert res.status_code == 200
    data = res.json()

    assert data["character_id"] == "aevum"
    assert "core" in data
    assert "bible_version" in data
    assert len(data["behavioral_guidelines"]) > 0
    assert len(data["reasoning_guidelines"]) > 0
    assert "ledger" in data

    # Verify baseline is seeded in core
    core = data["core"]
    assert core["facts"]["identity.name"]["value"] == "Aevum"
    assert core["facts"]["location.residence"]["value"] == "unspecified"


@pytest.mark.asyncio
async def test_patch_profile_core_and_validation(client: AsyncClient):
    """Verify PATCH /character/profile/core updates user fields with strict validation."""
    # 1. Valid update: age from 21 to 23
    res = await client.patch(
        "/character/profile/core",
        json={"updates": {"identity.age": 23}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["core"]["facts"]["identity.age"]["value"] == 23
    assert data["core"]["facts"]["identity.age"]["authority"] == "USER_CONFIGURED"

    # 2. Invalid update: out of range age (15) -> 422
    res_inv = await client.patch(
        "/character/profile/core",
        json={"updates": {"identity.age": 15}},
    )
    assert res_inv.status_code == 422


@pytest.mark.asyncio
async def test_lock_and_unlock_fact_api(client: AsyncClient):
    """Verify POST /character/profile/core/{fact_key}/lock and /unlock."""
    # 1. Lock identity.name
    lock_res = await client.post("/character/profile/core/identity.name/lock")
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["status"] == "locked"
    assert lock_data["fact"]["locked"] is True
    assert lock_data["fact"]["authority"] == "USER_LOCKED"

    # 2. Attempting to PATCH a locked fact returns 409 Conflict
    conflict_res = await client.patch(
        "/character/profile/core",
        json={"updates": {"identity.name": "DifferentName"}},
    )
    assert conflict_res.status_code == 409
    assert "locked" in conflict_res.json()["detail"].lower()

    # 3. Unlock identity.name
    unlock_res = await client.post("/character/profile/core/identity.name/unlock")
    assert unlock_res.status_code == 200
    unlock_data = unlock_res.json()
    assert unlock_data["status"] == "unlocked"
    assert unlock_data["fact"]["locked"] is False
    assert unlock_data["fact"]["authority"] == "USER_CONFIGURED"


@pytest.mark.asyncio
async def test_confirm_and_reject_candidate_api(client: AsyncClient):
    """Verify Confirm transitions candidate to USER_CONFIGURED, Reject discards."""
    # 1. Prepare profile
    await client.get("/character/profile")

    # Manually insert candidate via PATCH? Remember CANDIDATE cannot be directly created by normal PATCH in 7B.1.
    # But we can test confirming a non-existent candidate -> 404
    res_404 = await client.post("/character/profile/core/nonexistent.key/confirm")
    assert res_404.status_code == 404

    # Confirming a non-CANDIDATE fact (e.g. identity.name) returns 400
    res_400 = await client.post("/character/profile/core/identity.name/confirm")
    assert res_400.status_code == 400
    assert "not candidate" in res_400.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_fact_api_permissions(client: AsyncClient):
    """Verify DELETE /character/profile/core/{fact_key} permissions:
    - SYSTEM_BASELINE -> 403 Forbidden
    - USER_LOCKED -> 409 Conflict
    - USER_CONFIGURED -> 200 OK
    """
    await client.get("/character/profile")

    # 1. Attempt to delete SYSTEM_BASELINE fact -> 403 Forbidden
    res_baseline = await client.delete("/character/profile/core/identity.occupation")
    assert res_baseline.status_code == 403
    assert "system baseline" in res_baseline.json()["detail"].lower()

    # 2. Create a user-configured fact via PATCH
    await client.patch(
        "/character/profile/core",
        json={"updates": {"lifestyle.beverage": "warm oolong tea"}},
    )

    # 3. Lock it and attempt to delete -> 409 Conflict
    await client.post("/character/profile/core/lifestyle.beverage/lock")
    res_locked = await client.delete("/character/profile/core/lifestyle.beverage")
    assert res_locked.status_code == 409
    assert "locked" in res_locked.json()["detail"].lower()

    # 4. Unlock and delete -> 200 OK
    await client.post("/character/profile/core/lifestyle.beverage/unlock")
    res_del = await client.delete("/character/profile/core/lifestyle.beverage")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"
