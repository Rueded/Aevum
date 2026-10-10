"""Phase 19.1 — Prospective Contracts, Epistemic DTOs & Schema Isolation Unit Tests.

Verifies:
1. Enum completeness and membership locks.
2. SalienceCoordinates categorical dimensions, immutability, and zero-float enforcement.
3. ProspectiveThread valid instantiation across all domains and lifecycle states.
4. Bidirectional closure lifecycle validation (closed_at + closure_reason).
5. Anti-ticketing / Anti-task schema rejection via extra='forbid'.
6. Schema isolation (zero inheritance from MemoryRecord, Task, Reminder, LifeActivity).
7. Serialization & deserialization roundtrip determinism.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.prospective.contracts import (
    ClosureReasonKind,
    EpistemicStanceKind,
    GravityTier,
    ProspectiveThread,
    ResonanceTier,
    SalienceCoordinates,
    ThreadDomainKind,
    ThreadEnduranceTier,
    ThreadLifecycleState,
    ThreadProvenanceKind,
    UncertaintyTier,
)


def _make_sample_salience() -> SalienceCoordinates:
    return SalienceCoordinates(
        gravity=GravityTier.MODERATE,
        resonance=ResonanceTier.DEEP_CORE,
        uncertainty=UncertaintyTier.OPEN_EXPLORATION,
        endurance=ThreadEnduranceTier.SEASONAL,
    )


def test_enum_completeness_and_membership():
    """Verifies that all prospective enums contain exactly the mandated members."""
    # Lifecycle: 5 discrete states
    assert set(ThreadLifecycleState) == {
        ThreadLifecycleState.ACTIVE,
        ThreadLifecycleState.QUIET,
        ThreadLifecycleState.DORMANT,
        ThreadLifecycleState.CLOSED,
        ThreadLifecycleState.FORGOTTEN,
    }
    
    # Ownership Domain Triad: exactly 3
    assert set(ThreadDomainKind) == {
        ThreadDomainKind.SELF,
        ThreadDomainKind.USER,
        ThreadDomainKind.RELATIONAL,
    }

    # Closure Reasons: exactly 3
    assert set(ClosureReasonKind) == {
        ClosureReasonKind.REALIZED,
        ClosureReasonKind.ABANDONED,
        ClosureReasonKind.OBSOLETED,
    }

    # Provenance: exactly 3
    assert set(ThreadProvenanceKind) == {
        ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
        ThreadProvenanceKind.LIFE_SIMULATION_EMERGENT,
        ThreadProvenanceKind.SHARED_INTERACTION,
    }

    # Epistemic Stance: strictly INTENTION, EXPECTATION, PREDICTION.
    # GC-450: BELIEF is strictly forbidden.
    assert set(EpistemicStanceKind) == {
        EpistemicStanceKind.INTENTION,
        EpistemicStanceKind.EXPECTATION,
        EpistemicStanceKind.PREDICTION,
    }
    assert "BELIEF" not in [e.value for e in EpistemicStanceKind]


def test_salience_coordinates_immutability_and_extra_forbid():
    """Verifies SalienceCoordinates is immutable, pure categorical, and forbids extra fields."""
    coords = _make_sample_salience()
    assert coords.gravity == GravityTier.MODERATE
    assert coords.resonance == ResonanceTier.DEEP_CORE
    assert coords.uncertainty == UncertaintyTier.OPEN_EXPLORATION
    assert coords.endurance == ThreadEnduranceTier.SEASONAL

    # Frozen immutability
    with pytest.raises(ValidationError):
        coords.gravity = GravityTier.SIGNIFICANT  # type: ignore

    # Extra fields (such as pseudo-probabilistic float scores or thresholds) are rejected
    with pytest.raises(ValidationError):
        SalienceCoordinates(
            gravity=GravityTier.MODERATE,
            resonance=ResonanceTier.DEEP_CORE,
            uncertainty=UncertaintyTier.OPEN_EXPLORATION,
            endurance=ThreadEnduranceTier.SEASONAL,
            score=0.85,  # type: ignore
        )


def test_prospective_thread_instantiation_and_immutability():
    """Verifies valid thread creation across lifecycle states and frozen immutability."""
    now = datetime.now(timezone.utc)
    thread = ProspectiveThread(
        thread_id="thrd_001",
        character_id="aevum",
        user_id="user_123",
        domain=ThreadDomainKind.USER,
        title="胶片摄影探索",
        narrative_anchor="用户提到想试试胶片摄影，看中了某台二手老相机",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=ThreadLifecycleState.ACTIVE,
        salience=_make_sample_salience(),
        provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
    )

    assert thread.thread_id == "thrd_001"
    assert thread.domain == ThreadDomainKind.USER
    assert thread.lifecycle_state == ThreadLifecycleState.ACTIVE
    assert thread.closure_reason is None
    assert thread.closed_at is None

    # Frozen immutability check
    with pytest.raises(ValidationError):
        thread.lifecycle_state = ThreadLifecycleState.QUIET  # type: ignore


def test_closure_bidirectional_invariants():
    """Verifies bidirectional validation of closure_reason and closed_at."""
    now = datetime.now(timezone.utc)
    salience = _make_sample_salience()

    # 1. Valid CLOSED thread
    closed_thread = ProspectiveThread(
        thread_id="thrd_closed",
        character_id="aevum",
        user_id="user_123",
        domain=ThreadDomainKind.USER,
        title="胶片相机购入",
        narrative_anchor="用户提到想买胶片相机",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=ThreadLifecycleState.CLOSED,
        salience=salience,
        provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
        created_at=now,
        updated_at=now,
        closure_reason=ClosureReasonKind.REALIZED,
        closure_summary="用户在二手市场购入了富士胶片机，悬念落地",
        closed_at=now,
    )
    assert closed_thread.closure_reason == ClosureReasonKind.REALIZED
    assert closed_thread.closed_at is not None

    # 2. CLOSED thread missing closure_reason -> ERROR
    with pytest.raises(ValidationError, match="must specify 'closure_reason'"):
        ProspectiveThread(
            thread_id="thrd_err1",
            character_id="aevum",
            user_id="user_123",
            domain=ThreadDomainKind.USER,
            title="测试错误",
            narrative_anchor="锚点",
            epistemic_stance=EpistemicStanceKind.INTENTION,
            lifecycle_state=ThreadLifecycleState.CLOSED,
            salience=salience,
            provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
            created_at=now,
            updated_at=now,
            closure_reason=None,  # Missing
            closed_at=now,
        )

    # 3. CLOSED thread missing closed_at -> ERROR
    with pytest.raises(ValidationError, match="must specify 'closed_at'"):
        ProspectiveThread(
            thread_id="thrd_err2",
            character_id="aevum",
            user_id="user_123",
            domain=ThreadDomainKind.USER,
            title="测试错误",
            narrative_anchor="锚点",
            epistemic_stance=EpistemicStanceKind.INTENTION,
            lifecycle_state=ThreadLifecycleState.CLOSED,
            salience=salience,
            provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
            created_at=now,
            updated_at=now,
            closure_reason=ClosureReasonKind.REALIZED,
            closed_at=None,  # Missing
        )

    # 4. ACTIVE thread with premature closure_reason -> ERROR
    with pytest.raises(ValidationError, match="must NOT have 'closure_reason'"):
        ProspectiveThread(
            thread_id="thrd_err3",
            character_id="aevum",
            user_id="user_123",
            domain=ThreadDomainKind.USER,
            title="测试错误",
            narrative_anchor="锚点",
            epistemic_stance=EpistemicStanceKind.INTENTION,
            lifecycle_state=ThreadLifecycleState.ACTIVE,
            salience=salience,
            provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
            created_at=now,
            updated_at=now,
            closure_reason=ClosureReasonKind.REALIZED,  # Premature
            closed_at=None,
        )

    # 5. DORMANT thread with premature closed_at -> ERROR
    with pytest.raises(ValidationError, match="must NOT have 'closed_at'"):
        ProspectiveThread(
            thread_id="thrd_err4",
            character_id="aevum",
            user_id="user_123",
            domain=ThreadDomainKind.USER,
            title="测试错误",
            narrative_anchor="锚点",
            epistemic_stance=EpistemicStanceKind.INTENTION,
            lifecycle_state=ThreadLifecycleState.DORMANT,
            salience=salience,
            provenance=ThreadProvenanceKind.CONVERSATIONAL_SPONTANEOUS,
            created_at=now,
            updated_at=now,
            closure_reason=None,
            closed_at=now,  # Premature
        )


def test_anti_ticketing_and_extra_field_rejection():
    """Verifies that task, TODO, and reminder fields are strictly rejected."""
    now = datetime.now(timezone.utc)
    base_kwargs = dict(
        thread_id="thrd_anti_todo",
        character_id="aevum",
        user_id="user_123",
        domain=ThreadDomainKind.SELF,
        title="清理画桌与挑选水彩颜料",
        narrative_anchor="Aevum清理完画桌后想挑新颜料",
        epistemic_stance=EpistemicStanceKind.INTENTION,
        lifecycle_state=ThreadLifecycleState.ACTIVE,
        salience=_make_sample_salience(),
        provenance=ThreadProvenanceKind.LIFE_SIMULATION_EMERGENT,
        created_at=now,
        updated_at=now,
    )

    forbidden_fields = [
        {"due_date": "2026-10-10"},
        {"assigned_to": "aevum"},
        {"is_task": True},
        {"priority": 1},
        {"reminder_time": "2026-10-10T10:00:00Z"},
        {"todo_status": "PENDING"},
        {"is_completed": False},
        {"notification_queued": False},
    ]

    for forbidden in forbidden_fields:
        bad_kwargs = {**base_kwargs, **forbidden}
        with pytest.raises(ValidationError):
            ProspectiveThread(**bad_kwargs)


def test_schema_isolation_and_no_inheritance():
    """Verifies schema isolation: ProspectiveThread does NOT inherit from task/memory models."""
    mro_names = [cls.__name__ for cls in ProspectiveThread.__mro__]
    assert "BaseModel" in mro_names
    assert "MemoryRecord" not in mro_names
    assert "LifeActivity" not in mro_names
    assert "Task" not in mro_names
    assert "Reminder" not in mro_names
    assert "Goal" not in mro_names
    assert "Notification" not in mro_names


def test_serialization_and_deserialization_roundtrip():
    """Verifies JSON serialization and deserialization preserves all fields and typing."""
    now = datetime.now(timezone.utc)
    original = ProspectiveThread(
        thread_id="thrd_roundtrip",
        character_id="aevum",
        user_id="user_456",
        domain=ThreadDomainKind.RELATIONAL,
        title="下次一起聊聊那本画册",
        narrative_anchor="谈到一本装帧特别的书，约定下次继续探讨",
        epistemic_stance=EpistemicStanceKind.EXPECTATION,
        lifecycle_state=ThreadLifecycleState.QUIET,
        salience=_make_sample_salience(),
        provenance=ThreadProvenanceKind.SHARED_INTERACTION,
        created_at=now,
        updated_at=now,
        last_contextual_contact_at=now,
    )

    data_json = original.model_dump_json()
    reconstituted = ProspectiveThread.model_validate_json(data_json)

    assert reconstituted == original
    assert reconstituted.thread_id == original.thread_id
    assert reconstituted.domain == ThreadDomainKind.RELATIONAL
    assert reconstituted.lifecycle_state == ThreadLifecycleState.QUIET
    assert reconstituted.salience.gravity == GravityTier.MODERATE
