"""Unit and integration tests for Character Core, FactKeyRegistry, and Authority Matrix."""

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.character.core_service import (
    AevumCanonicalNotDirectlyEditableError,
    CandidateNotEditableError,
    CharacterCoreService,
    FactLockedError,
    SystemBaselineImmutableError,
)
from app.db.models import CharacterCoreFactRecord
from app.db.session import init_db
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.registry import FactKeyRegistry, InvalidFactValueError


@pytest.mark.unit
def test_fact_key_registry_validations():
    """Verify FactKeyRegistry enforces strict type and range constraints."""
    # Valid values
    assert FactKeyRegistry.validate("identity.name", "Aevum") == "Aevum"
    assert FactKeyRegistry.validate("identity.age", 21) == 21
    assert FactKeyRegistry.validate("identity.age", 100) == 100
    assert FactKeyRegistry.validate("education.year", 2) == 2
    assert FactKeyRegistry.validate("interests", ["piano", "gaming"]) == ["piano", "gaming"]

    # Invalid values
    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("identity.name", "")

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("identity.age", 15)

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("identity.age", 150)

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("identity.age", "twenty-one")

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("education.year", 0)

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("education.year", 10)

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("interests", [])

    with pytest.raises(InvalidFactValueError):
        FactKeyRegistry.validate("interests", [""])


@pytest.mark.unit
def test_core_fact_item_lock_invariant():
    """Verify locked == True iff authority == USER_LOCKED."""
    # Valid locked
    item1 = CoreFactItem(
        key="education.university",
        category="education",
        value="University of Malaya",
        source=FactSource.USER_CONFIGURED,
        authority=FactAuthority.USER_LOCKED,
        status=FactStatus.CANONICAL,
        locked=True,
    )
    assert item1.is_locked is True

    # Valid unlocked
    item2 = CoreFactItem(
        key="education.university",
        category="education",
        value="University of Malaya",
        source=FactSource.USER_CONFIGURED,
        authority=FactAuthority.USER_CONFIGURED,
        status=FactStatus.CANONICAL,
        locked=False,
    )
    assert item2.is_locked is False

    # Invariant violation: locked=True without USER_LOCKED
    with pytest.raises(ValueError, match="locked=True must have authority=USER_LOCKED"):
        CoreFactItem(
            key="education.university",
            category="education",
            value="University of Malaya",
            source=FactSource.USER_CONFIGURED,
            authority=FactAuthority.USER_CONFIGURED,
            status=FactStatus.CANONICAL,
            locked=True,
        )

    # Invariant violation: USER_LOCKED without locked=True
    with pytest.raises(ValueError, match="authority=USER_LOCKED must have locked=True"):
        CoreFactItem(
            key="education.university",
            category="education",
            value="University of Malaya",
            source=FactSource.USER_CONFIGURED,
            authority=FactAuthority.USER_LOCKED,
            status=FactStatus.CANONICAL,
            locked=False,
        )


@pytest.mark.asyncio
async def test_seed_default_core_purity(test_session: AsyncSession):
    """Verify seed_default_core seeds baseline anchors without unapproved biographical trivia."""
    service = CharacterCoreService(test_session)
    core = await service.get_core("aevum")

    # Foundational anchors exist
    assert core.has_fact("identity.name")
    assert core.get_value("identity.name") == "Aevum"
    assert core.get_value("identity.age") == 21
    assert core.get_value("identity.occupation") == "University Student"

    # STRICT INVARIANT: Location is unspecified (no city is canonical)
    assert core.get_value("location.residence") == "unspecified"
    assert not core.has_fact("location.city")

    # STRICT INVARIANT: No specific university or major seeded
    assert not core.has_fact("education.university")
    assert not core.has_fact("education.major")

    # Interests and dislikes projections
    assert "acoustic piano and guitar" in core.interests
    assert "crowded noisy social gatherings" in core.dislikes


@pytest.mark.asyncio
async def test_single_current_reality_replacement(test_session: AsyncSession):
    """Verify editing a SYSTEM_BASELINE fact replaces it with USER_CONFIGURED without dual reality."""
    service = CharacterCoreService(test_session)
    await service.get_core("aevum")

    # User updates age from 21 to 24
    updated_fact = await service.set_fact(
        character_id="aevum",
        fact_key="identity.age",
        value=24,
        source=FactSource.USER_CONFIGURED,
        authority=FactAuthority.USER_CONFIGURED,
    )

    assert updated_fact.value == 24
    assert updated_fact.authority == FactAuthority.USER_CONFIGURED
    assert updated_fact.source == FactSource.USER_CONFIGURED
    assert updated_fact.status == FactStatus.CANONICAL

    core = await service.get_core("aevum")
    assert core.get_value("identity.age") == 24


@pytest.mark.asyncio
async def test_candidate_confirm_and_reject(test_session: AsyncSession):
    """Verify Candidate lifecycle: Confirm promotes to USER_CONFIGURED; Reject cleanly discards."""
    service = CharacterCoreService(test_session)
    await service.get_core("aevum")

    # 1. Simulate Aevum cognitive system proposing a candidate university
    cand = await service.set_fact(
        character_id="aevum",
        fact_key="education.university",
        value="Universiti Sains Malaysia",
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANDIDATE,
        confidence=0.85,
    )
    assert cand.status == FactStatus.CANDIDATE
    assert cand.source == FactSource.AEVUM_INFERRED

    # 2. Confirm candidate: transitions to USER_CONFIGURED + CANONICAL, preserving source
    confirmed = await service.confirm_candidate_fact("aevum", "education.university")
    assert confirmed.status == FactStatus.CANONICAL
    assert confirmed.authority == FactAuthority.USER_CONFIGURED
    assert confirmed.source == FactSource.AEVUM_INFERRED
    assert confirmed.locked is False

    # 3. Simulate another candidate for transit preference
    await service.set_fact(
        character_id="aevum",
        fact_key="lifestyle.transit",
        value="campus shuttle bus",
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANDIDATE,
        confidence=0.75,
    )

    # 4. Reject candidate: cleanly discarded, not marked FALSIFIED
    rejected = await service.reject_candidate_fact("aevum", "lifestyle.transit")
    assert rejected is True

    core = await service.get_core("aevum")
    assert not core.has_fact("lifestyle.transit")


@pytest.mark.asyncio
async def test_lock_fact_and_forbidden_mutations(test_session: AsyncSession):
    """Verify locked facts strictly forbid updates and deletions."""
    service = CharacterCoreService(test_session)
    await service.get_core("aevum")

    # Lock identity.name
    locked_name = await service.lock_fact("aevum", "identity.name")
    assert locked_name.locked is True
    assert locked_name.authority == FactAuthority.USER_LOCKED

    # Attempt to modify locked fact -> FactLockedError
    with pytest.raises(FactLockedError):
        await service.set_fact(
            character_id="aevum",
            fact_key="identity.name",
            value="NewName",
            source=FactSource.USER_CONFIGURED,
            authority=FactAuthority.USER_CONFIGURED,
        )

    # Attempt to delete locked fact -> FactLockedError
    with pytest.raises(FactLockedError):
        await service.delete_fact("aevum", "identity.name")

    # Unlock fact
    unlocked_name = await service.unlock_fact("aevum", "identity.name")
    assert unlocked_name.locked is False
    assert unlocked_name.authority == FactAuthority.USER_CONFIGURED


@pytest.mark.asyncio
async def test_system_baseline_delete_forbidden(test_session: AsyncSession):
    """Verify foundational system baseline facts cannot be deleted."""
    service = CharacterCoreService(test_session)
    await service.get_core("aevum")

    with pytest.raises(SystemBaselineImmutableError):
        await service.delete_fact("aevum", "identity.occupation")
