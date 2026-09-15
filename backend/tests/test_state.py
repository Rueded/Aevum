"""Tests for Phase 1.5: Application State Foundation.

Validates provider-independent state models, SQLite persistence,
optimistic concurrency versioning, session boundaries, backend restarts,
and architectural separation from LLMs and Conversation models.
"""

from datetime import datetime, timezone
import importlib
import inspect
import sys
import pytest
import pydantic
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import ApplicationStateRecord
from app.db.session import Base
from app.state import (
    ApplicationState,
    ApplicationStateService,
    StateConflictError,
    get_application_state,
    update_application_state,
)


@pytest.mark.asyncio
async def test_initial_state_created_on_empty_db(test_session: AsyncSession):
    """1. State can be created when the database is empty."""
    service = ApplicationStateService(test_session)
    state = await service.get_state()

    assert state is not None
    assert state.id == "canonical"


@pytest.mark.asyncio
async def test_initial_version_is_deterministic(test_session: AsyncSession):
    """2. Initial version is deterministic (version == 1)."""
    service = ApplicationStateService(test_session)
    state = await service.get_state()

    assert state.version == 1


@pytest.mark.asyncio
async def test_initial_state_has_valid_utc_timestamp(test_session: AsyncSession):
    """3. State has a valid timezone-aware UTC timestamp."""
    service = ApplicationStateService(test_session)
    state = await service.get_state()

    assert isinstance(state.updated_at, datetime)
    assert state.updated_at.tzinfo is not None
    assert state.updated_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_repeated_reads_return_same_state(test_session: AsyncSession):
    """4. Repeated reads return the same persisted state."""
    service = ApplicationStateService(test_session)
    state1 = await service.get_state()
    state2 = await service.get_state()

    assert state1.id == state2.id
    assert state1.version == state2.version
    assert state1.updated_at == state2.updated_at


@pytest.mark.asyncio
async def test_state_survives_session_boundary(test_engine):
    """5. State survives a database session boundary."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session1:
        service1 = ApplicationStateService(session1)
        created = await service1.get_state()
        assert created.version == 1

    # Open a completely separate database session
    async with session_factory() as session2:
        service2 = ApplicationStateService(session2)
        loaded = await service2.get_state()
        assert loaded.id == created.id
        assert loaded.version == created.version
        assert loaded.updated_at == created.updated_at


@pytest.mark.asyncio
async def test_state_survives_service_reinstantiation(test_session: AsyncSession):
    """6. State survives service re-instantiation."""
    service_a = ApplicationStateService(test_session)
    created = await service_a.get_state()

    # Re-instantiate service on the same session
    service_b = ApplicationStateService(test_session)
    loaded = await service_b.get_state()

    assert loaded.id == created.id
    assert loaded.version == created.version
    assert loaded.updated_at == created.updated_at


@pytest.mark.asyncio
async def test_state_survives_backend_restart_simulation(tmp_path):
    """7. State survives backend restart simulation (new engine + session factory on disk)."""
    db_file = tmp_path / "restart_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # First engine/session instance: initialize db, create and update state
    engine1 = create_async_engine(db_url, echo=False)
    async with engine1.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory1 = async_sessionmaker(bind=engine1, class_=AsyncSession, expire_on_commit=False)
    async with session_factory1() as session1:
        service1 = ApplicationStateService(session1)
        state1 = await service1.get_state()
        assert state1.version == 1
        updated1 = await service1.update_state(expected_version=1)
        assert updated1.version == 2
        persisted_updated_at = updated1.updated_at

    # Simulate shutdown: dispose engine 1
    await engine1.dispose()

    # Second engine/session instance simulating a fresh backend process startup
    engine2 = create_async_engine(db_url, echo=False)
    session_factory2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)
    async with session_factory2() as session2:
        service2 = ApplicationStateService(session2)
        loaded = await service2.get_state()
        assert loaded.id == "canonical"
        assert loaded.version == 2
        assert loaded.updated_at == persisted_updated_at

    await engine2.dispose()


@pytest.mark.asyncio
async def test_state_can_be_updated(test_session: AsyncSession):
    """8. State can be updated via update_state."""
    service = ApplicationStateService(test_session)
    initial = await service.get_state()
    updated = await service.update_state()

    assert updated is not None
    assert updated.version > initial.version


@pytest.mark.asyncio
async def test_version_increments_correctly(test_session: AsyncSession):
    """9. Version increments sequentially and monotonically."""
    service = ApplicationStateService(test_session)
    state_v1 = await service.get_state()
    assert state_v1.version == 1

    state_v2 = await service.update_state()
    assert state_v2.version == 2

    state_v3 = await service.update_state()
    assert state_v3.version == 3


@pytest.mark.asyncio
async def test_updated_timestamp_changes_appropriately(test_session: AsyncSession):
    """10. Updated timestamp changes appropriately (monotonic non-decreasing)."""
    service = ApplicationStateService(test_session)
    initial = await service.get_state()
    updated = await service.update_state()

    # Avoid strict monotonic > to prevent flakiness due to clock/DB precision
    assert updated.updated_at >= initial.updated_at


@pytest.mark.asyncio
async def test_updated_state_persists(test_session: AsyncSession):
    """11. Updated state is persisted to the database record."""
    service = ApplicationStateService(test_session)
    await service.get_state()
    updated = await service.update_state()

    raw_record = await test_session.get(ApplicationStateRecord, "canonical")
    assert raw_record is not None
    assert raw_record.version == updated.version


@pytest.mark.asyncio
async def test_rereading_returns_updated_state(test_session: AsyncSession):
    """12. Re-reading returns the newly updated state."""
    service = ApplicationStateService(test_session)
    await service.get_state()
    updated = await service.update_state()
    reread = await service.get_state()

    assert reread.version == updated.version
    assert reread.updated_at == updated.updated_at


@pytest.mark.asyncio
async def test_correct_expected_version_succeeds(test_session: AsyncSession):
    """13. Correct expected version check succeeds."""
    service = ApplicationStateService(test_session)
    state = await service.get_state()
    assert state.version == 1

    updated = await service.update_state(expected_version=1)
    assert updated.version == 2


@pytest.mark.asyncio
async def test_stale_expected_version_is_rejected(test_session: AsyncSession):
    """14. Stale or incorrect expected version raises StateConflictError."""
    service = ApplicationStateService(test_session)
    await service.get_state()  # version is 1

    with pytest.raises(StateConflictError) as exc_info:
        await service.update_state(expected_version=99)

    assert exc_info.value.expected_version == 99
    assert exc_info.value.actual_version == 1


@pytest.mark.asyncio
async def test_rejected_update_does_not_modify_state(test_session: AsyncSession):
    """15. Rejected update leaves state and version unchanged."""
    service = ApplicationStateService(test_session)
    initial = await service.get_state()
    assert initial.version == 1

    with pytest.raises(StateConflictError):
        await service.update_state(expected_version=42)

    current = await service.get_state()
    assert current.version == 1
    assert current.updated_at == initial.updated_at


def test_state_serializes_correctly():
    """16. ApplicationState serializes cleanly to dict and JSON."""
    now = datetime.now(timezone.utc)
    state = ApplicationState(id="canonical", version=3, updated_at=now)

    data = state.model_dump()
    assert data["id"] == "canonical"
    assert data["version"] == 3
    assert data["updated_at"] == now

    json_str = state.model_dump_json()
    assert '"id":"canonical"' in json_str or '"id": "canonical"' in json_str
    assert '"version":3' in json_str or '"version": 3' in json_str


def test_serialized_state_can_be_reconstructed():
    """17. Serialized ApplicationState can be completely reconstructed."""
    now = datetime.now(timezone.utc)
    original = ApplicationState(id="canonical", version=5, updated_at=now)

    json_str = original.model_dump_json()
    restored = ApplicationState.model_validate_json(json_str)

    assert restored == original
    assert restored.id == original.id
    assert restored.version == original.version
    assert restored.updated_at == original.updated_at


def test_unsupported_or_invalid_values_rejected():
    """18. Non-serializable, speculative, or invalid values are rejected."""
    now = datetime.now(timezone.utc)

    # Negative version should be rejected (ge=1 constraint)
    with pytest.raises(pydantic.ValidationError):
        ApplicationState(id="canonical", version=-1, updated_at=now)

    # Invalid datetime format should be rejected
    with pytest.raises(pydantic.ValidationError):
        ApplicationState(id="canonical", version=1, updated_at="not-a-datetime")  # type: ignore

    # Speculative extra fields must be forbidden by extra="forbid"
    with pytest.raises(pydantic.ValidationError):
        ApplicationState(  # type: ignore
            id="canonical",
            version=1,
            updated_at=now,
            mood="happy",  # type: ignore
        )

    with pytest.raises(pydantic.ValidationError):
        ApplicationState(  # type: ignore
            id="canonical",
            version=1,
            updated_at=now,
            affection=100,  # type: ignore
        )


def test_state_model_does_not_import_gemini_sdk():
    """19. State model has no dependencies on Gemini or LLM SDKs."""
    import app.state.models as state_models_module

    source = inspect.getsource(state_models_module)
    assert "google" not in source.lower()
    assert "genai" not in source.lower()
    assert "gemini" not in source.lower()


def test_state_model_does_not_depend_on_conversation_models():
    """20. State model does not depend on Conversation or Message models."""
    import app.state.models as state_models_module

    source = inspect.getsource(state_models_module)
    assert "conversation" not in source.lower()
    assert "message" not in source.lower()


def test_state_model_contains_no_character_or_speculative_fields():
    """21. State model contains strictly foundational fields, no character/state engine fields."""
    allowed_fields = {"id", "version", "updated_at"}
    actual_fields = set(ApplicationState.model_fields.keys())

    assert actual_fields == allowed_fields, (
        f"Unexpected fields found in ApplicationState: {actual_fields - allowed_fields}"
    )


@pytest.mark.asyncio
async def test_convenience_functions(test_session: AsyncSession):
    """Verify get_application_state and update_application_state convenience functions."""
    state1 = await get_application_state(test_session)
    assert state1.version == 1

    state2 = await update_application_state(test_session, expected_version=1)
    assert state2.version == 2
