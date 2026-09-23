"""Tests for Reality Ledger multi-tier projections and statistics."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_service import CharacterCoreService
from app.reality.ledger_models import RealityLedgerProjection
from app.reality.ledger_service import RealityLedgerService
from app.reality.models import FactAuthority, FactSource, FactStatus, LedgerTier


@pytest.mark.asyncio
async def test_reality_ledger_three_tiers(test_session: AsyncSession):
    """Verify facts are cleanly partitioned into Green, Yellow, and Red tiers."""
    core_service = CharacterCoreService(test_session)
    await core_service.get_core("aevum")

    # 1. Baseline anchors are Red (SYSTEM_INTEGRITY)
    ledger_service = RealityLedgerService(test_session)
    ledger = await ledger_service.get_ledger("aevum")
    assert len(ledger.red_system_integrity) > 0
    assert any(item.key == "identity.occupation" for item in ledger.red_system_integrity)

    # 2. Add an Aevum-inferred candidate -> Yellow (AEVUM_EMERGENT)
    await core_service.set_fact(
        character_id="aevum",
        fact_key="education.university",
        value="Universiti Sains Malaysia",
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANDIDATE,
        confidence=0.85,
    )

    # 3. Add a user-configured fact -> Green (USER_EDITABLE)
    await core_service.set_fact(
        character_id="aevum",
        fact_key="lifestyle.favorite_drink",
        value="iced hojicha latte",
        source=FactSource.USER_CONFIGURED,
        authority=FactAuthority.USER_CONFIGURED,
        status=FactStatus.CANONICAL,
    )

    ledger_updated = await ledger_service.get_ledger("aevum")

    # Verify Green tier has user-configured fact
    assert any(item.key == "lifestyle.favorite_drink" for item in ledger_updated.green_user_editable)

    # Verify Yellow tier has candidate fact
    assert any(item.key == "education.university" for item in ledger_updated.yellow_aevum_emergent)

    # Verify Red tier preserves baseline anchors
    assert any(item.key == "identity.occupation" for item in ledger_updated.red_system_integrity)


@pytest.mark.asyncio
async def test_reality_ledger_statistics(test_session: AsyncSession):
    """Verify ledger summary metrics: counts and average confidence."""
    core_service = CharacterCoreService(test_session)
    await core_service.get_core("aevum")

    # Lock one fact
    await core_service.lock_fact("aevum", "identity.name")

    # Add a candidate
    await core_service.set_fact(
        character_id="aevum",
        fact_key="lifestyle.study_spot",
        value="central library second floor",
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANDIDATE,
        confidence=0.8,
    )

    ledger_service = RealityLedgerService(test_session)
    ledger = await ledger_service.get_ledger("aevum")

    assert ledger.locked_count >= 1
    assert ledger.candidate_count >= 1
    assert 0.0 <= ledger.average_confidence <= 1.0
    assert ledger.total_facts == (
        len(ledger.green_user_editable)
        + len(ledger.yellow_aevum_emergent)
        + len(ledger.red_system_integrity)
    )
