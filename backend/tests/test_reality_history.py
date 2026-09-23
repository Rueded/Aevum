"""Unit tests for Reality History and Version Revisions (Phase 7B.3.6).

Verifies append-only history tracking, supersession lineage, and active version lookups.
"""

import pytest
from app.reality.history_service import RealityHistoryService


@pytest.mark.asyncio
async def test_reality_history_versioning_and_supersession() -> None:
    service = RealityHistoryService()

    # Step 1: Record initial residence
    rev1 = await service.record_revision(
        character_id="aevum",
        fact_key="location.residence",
        value="Penang",
        effective_from="2023-09-01",
    )
    assert rev1.fact_key == "location.residence"
    assert rev1.value == "Penang"
    assert rev1.supersedes_id is None
    assert rev1.superseded_by is None
    assert rev1.is_current is True

    # Step 2: Record move to KL
    rev2 = await service.record_revision(
        character_id="aevum",
        fact_key="location.residence",
        value="Kuala Lumpur",
        effective_from="2024-07-01",
    )
    assert rev2.value == "Kuala Lumpur"
    assert rev2.supersedes_id == rev1.id
    assert rev2.superseded_by is None
    assert rev2.is_current is True

    # Step 3: Query history
    history = await service.get_history("aevum", "location.residence")
    assert len(history) == 2
    assert history[0].value == "Penang"
    assert history[0].superseded_by == rev2.id
    assert history[0].is_current is False
    assert history[1].value == "Kuala Lumpur"
    assert history[1].is_current is True

    # Step 4: Active revision query
    active = await service.get_active_revision("aevum", "location.residence")
    assert active is not None
    assert active.value == "Kuala Lumpur"
    assert active.id == rev2.id

    # Step 5: Point-in-time temporal query (effective_from / effective_until)
    # In December 2023, Aevum resided in Penang
    past_rev = await service.get_revision_at_time("aevum", "location.residence", "2023-12-15")
    assert past_rev is not None
    assert past_rev.value == "Penang"
    assert past_rev.id == rev1.id

    # In August 2024, Aevum resided in Kuala Lumpur
    current_rev = await service.get_revision_at_time("aevum", "location.residence", "2024-08-01")
    assert current_rev is not None
    assert current_rev.value == "Kuala Lumpur"
    assert current_rev.id == rev2.id
