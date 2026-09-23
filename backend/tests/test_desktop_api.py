from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Conversation, Message, ProactiveNotificationRecord
from app.desktop.service import DesktopService
from app.proactive.models import NotificationStatus, SuppressionReason
from app.proactive.notification_service import ProactiveNotificationService


@pytest.fixture(autouse=True)
def clean_transient_contexts():
    """Ensure in-memory transient context is cleanly cleared before each test."""
    DesktopService.clear_all_transient_contexts()
    yield
    DesktopService.clear_all_transient_contexts()


@pytest.mark.asyncio
async def test_desktop_settings_lifecycle(client: AsyncClient):
    """Test retrieving and updating desktop settings via API."""
    import uuid
    char_id = f"test_char_{uuid.uuid4().hex[:8]}"

    # 1. GET settings (returns defaults)
    resp = await client.get(f"/desktop/settings?character_id={char_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["character_id"] == char_id
    assert data["proactive_enabled"] is False
    assert data["idle_awareness_enabled"] is False
    assert data["timezone"] == "Asia/Shanghai"

    # 2. PATCH settings (enable proactive and idle awareness)
    patch_payload = {
        "proactive_enabled": True,
        "idle_awareness_enabled": True,
        "timezone": "Asia/Tokyo",
        "max_daily_reach_outs": 5,
    }
    patch_resp = await client.patch(f"/desktop/settings?character_id={char_id}", json=patch_payload)
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert patched_data["proactive_enabled"] is True
    assert patched_data["idle_awareness_enabled"] is True
    assert patched_data["timezone"] == "Asia/Tokyo"
    assert patched_data["max_daily_reach_outs"] == 5

    # 3. Invalid timezone is rejected
    bad_tz_resp = await client.patch(f"/desktop/settings?character_id={char_id}", json={"timezone": "Invalid/FakeZone"})
    assert bad_tz_resp.status_code == 422


@pytest.mark.asyncio
async def test_desktop_dnd_controls(client: AsyncClient):
    """Test activating and clearing DND via API."""
    import uuid
    char_id = f"test_char_{uuid.uuid4().hex[:8]}"

    # 1. Set DND for 60 minutes
    resp_set = await client.post(f"/desktop/settings/dnd?character_id={char_id}", json={"duration_minutes": 60})
    assert resp_set.status_code == 200
    assert resp_set.json()["dnd_until"] is not None

    # 2. Clear DND
    resp_clear = await client.post(f"/desktop/settings/dnd?character_id={char_id}", json={"clear": True})
    assert resp_clear.status_code == 200
    assert resp_clear.json()["dnd_until"] is None


@pytest.mark.asyncio
async def test_desktop_heartbeat_api_and_context(client: AsyncClient):
    """Test heartbeat endpoint and in-memory transient context via API."""
    import uuid
    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    t0 = datetime.now(timezone.utc).isoformat()

    # 1. Heartbeat when idle_awareness_enabled == False -> stripped
    hb_disabled = {
        "client_id": "desktop-client-1",
        "client_timestamp": t0,
        "is_idle": True,
        "idle_seconds": 600.0,
        "window_focused": False,
    }
    resp1 = await client.post(f"/desktop/heartbeat?character_id={char_id}", json=hb_disabled)
    assert resp1.status_code == 200
    assert resp1.json()["awareness_enabled"] is False

    # Context is null
    ctx_resp1 = await client.get(f"/desktop/context?character_id={char_id}")
    assert ctx_resp1.status_code == 200
    assert ctx_resp1.json() is None

    # 2. Enable idle awareness
    await client.patch(f"/desktop/settings?character_id={char_id}", json={"idle_awareness_enabled": True})

    # Send active heartbeat
    hb_active = {
        "client_id": "desktop-client-1",
        "client_timestamp": t0,
        "is_idle": False,
        "idle_seconds": 10.0,
        "window_focused": True,
    }
    resp2 = await client.post(f"/desktop/heartbeat?character_id={char_id}", json=hb_active)
    assert resp2.status_code == 200
    assert resp2.json()["awareness_enabled"] is True

    # Context is now ACTIVE in-memory
    ctx_resp2 = await client.get(f"/desktop/context?character_id={char_id}")
    assert ctx_resp2.status_code == 200
    ctx_data = ctx_resp2.json()
    assert ctx_data is not None
    assert ctx_data["is_user_available"] is True
    assert ctx_data["idle_category"] == "ACTIVE"
    assert ctx_data["window_focused"] is True

    # 3. Revoke consent -> context is immediately nullified
    await client.patch(f"/desktop/settings?character_id={char_id}", json={"idle_awareness_enabled": False})
    ctx_resp3 = await client.get(f"/desktop/context?character_id={char_id}")
    assert ctx_resp3.status_code == 200
    assert ctx_resp3.json() is None


# ==============================================================================
# Helper for seeding test notification records
# ==============================================================================


async def seed_notification(
    session: AsyncSession,
    *,
    character_id: str = "aevum",
    status: str = NotificationStatus.PENDING.value,
    created_at: Optional[datetime] = None,
    idempotency_key: Optional[str] = None,
    claimed_by: Optional[str] = None,
    claimed_at: Optional[datetime] = None,
    suppression_reason: Optional[str] = None,
    title: str = "Test Notification",
    body: str = "Hello from desktop notification test!",
) -> ProactiveNotificationRecord:
    """Helper to seed Conversation, Message, and ProactiveNotificationRecord directly."""
    import uuid
    from app.db.models import Conversation, Message, ProactiveNotificationRecord

    t = created_at or datetime.now(timezone.utc)
    conv = Conversation(created_at=t)
    session.add(conv)
    await session.flush()

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=body,
        created_at=t,
    )
    session.add(msg)
    await session.flush()

    record = ProactiveNotificationRecord(
        id=str(uuid.uuid4()),
        character_id=character_id,
        conversation_message_id=msg.id,
        trigger_type="TEST_REACHOUT",
        idempotency_key=idempotency_key or f"test-key-{uuid.uuid4().hex}",
        title=title,
        body=body,
        status=status,
        claimed_by=claimed_by,
        claimed_at=claimed_at,
        suppression_reason=suppression_reason,
        created_at=t,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


# ==============================================================================
# Step 3 REST Notification Endpoints & 24h Expiration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_desktop_notifications_pending_endpoint(client: AsyncClient, test_session: AsyncSession):
    """Test listing pending notifications eligible for delivery (<=24h) and stale suppression (>24h)."""
    import uuid
    from datetime import timedelta
    from app.proactive.models import NotificationStatus, SuppressionReason

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # 1. Eligible pending notification (age = 1h <= 24h)
    n_eligible = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
        created_at=now - timedelta(hours=1),
        title="Eligible Notification",
    )

    # 2. Stale pending notification (age = 25h > 24h)
    n_stale = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
        created_at=now - timedelta(hours=25),
        title="Stale Notification",
    )

    # 3. Notification for different character
    n_other = await seed_notification(
        test_session,
        character_id=f"other_{uuid.uuid4().hex[:8]}",
        status=NotificationStatus.PENDING.value,
        created_at=now - timedelta(hours=1),
        title="Other Character Notification",
    )

    # 4. Already delivered notification
    n_delivered = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.DELIVERED.value,
        created_at=now - timedelta(hours=2),
        title="Delivered Notification",
    )

    # Query GET /desktop/notifications/pending
    resp = await client.get(f"/desktop/notifications/pending?character_id={char_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == n_eligible.id
    assert data[0]["character_id"] == char_id
    assert data[0]["status"] == "PENDING"
    assert data[0]["title"] == "Eligible Notification"

    # Verify stale notification was proactively transitioned to SUPPRESSED (EXPIRED) in DB
    service = ProactiveNotificationService(test_session)
    stale_record = await service.get_notification(n_stale.id)
    assert stale_record is not None
    assert stale_record.status == NotificationStatus.SUPPRESSED.value
    assert stale_record.suppression_reason == SuppressionReason.EXPIRED.value


@pytest.mark.asyncio
async def test_desktop_notifications_get_by_id(client: AsyncClient, test_session: AsyncSession):
    """Test retrieving notification by ID with 404 and 403 character ownership verification."""
    import uuid
    from app.proactive.models import NotificationStatus

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    record = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
        title="Inspect Me",
    )

    # 1. Success without character_id param
    resp1 = await client.get(f"/desktop/notifications/{record.id}")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["id"] == record.id
    assert data1["character_id"] == char_id
    assert data1["title"] == "Inspect Me"
    assert data1["conversation_message_id"] == record.conversation_message_id

    # 2. Success with matching character_id param
    resp2 = await client.get(f"/desktop/notifications/{record.id}?character_id={char_id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == record.id

    # 3. 403 Forbidden with mismatched character_id param
    resp3 = await client.get(f"/desktop/notifications/{record.id}?character_id=wrong_char")
    assert resp3.status_code == 403
    assert "does not belong to character" in resp3.json()["detail"]

    # 4. 404 Not Found for non-existent notification ID
    resp4 = await client.get(f"/desktop/notifications/{uuid.uuid4()}")
    assert resp4.status_code == 404


@pytest.mark.asyncio
async def test_desktop_notifications_claim_lifecycle(client: AsyncClient, test_session: AsyncSession):
    """Test claiming delivery lease, conflict detection, 404, and 403."""
    import uuid
    from app.proactive.models import NotificationStatus

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    record = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
    )

    # 1. 403 Forbidden when character_id doesn't match
    claim_wrong_char = {
        "worker_id": "worker-1",
        "character_id": "different_char",
    }
    resp_403 = await client.post(f"/desktop/notifications/{record.id}/claim", json=claim_wrong_char)
    assert resp_403.status_code == 403

    # 2. 404 Not Found for unknown notification
    claim_payload = {
        "worker_id": "worker-1",
        "character_id": char_id,
    }
    resp_404 = await client.post(f"/desktop/notifications/{uuid.uuid4()}/claim", json=claim_payload)
    assert resp_404.status_code == 404

    # 3. 200 OK on valid claim
    resp_claim = await client.post(
        f"/desktop/notifications/{record.id}/claim",
        json={"worker_id": "worker-alpha", "character_id": char_id, "lease_timeout_seconds": 60.0},
    )
    assert resp_claim.status_code == 200
    claim_data = resp_claim.json()
    assert claim_data["claimed"] is True
    assert claim_data["status"] == "DELIVERING"
    assert claim_data["claimed_by"] == "worker-alpha"
    assert claim_data["claimed_at"] is not None

    # 4. 409 Conflict when second worker attempts to claim active lease
    resp_conflict = await client.post(
        f"/desktop/notifications/{record.id}/claim",
        json={"worker_id": "worker-beta", "character_id": char_id},
    )
    assert resp_conflict.status_code == 409
    assert "could not be claimed" in resp_conflict.json()["detail"]


@pytest.mark.asyncio
async def test_desktop_notifications_claim_24h_expiration_api(client: AsyncClient, test_session: AsyncSession):
    """Test that claiming an expired (>24h) notification transitions it to SUPPRESSED (EXPIRED) and returns 409."""
    import uuid
    from datetime import timedelta
    from app.proactive.models import NotificationStatus, SuppressionReason

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # 1. Notification aged 86,390s (< 24h) -> claim succeeds
    record_fresh = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
        created_at=now - timedelta(seconds=86390.0),
    )
    resp_fresh = await client.post(
        f"/desktop/notifications/{record_fresh.id}/claim",
        json={"worker_id": "worker-1", "character_id": char_id},
    )
    assert resp_fresh.status_code == 200
    assert resp_fresh.json()["claimed"] is True

    # 2. Notification aged 86,410s (> 24h) -> claim triggers 24h expiration
    record_stale = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
        created_at=now - timedelta(seconds=86410.0),
    )
    resp_stale = await client.post(
        f"/desktop/notifications/{record_stale.id}/claim",
        json={"worker_id": "worker-2", "character_id": char_id},
    )
    assert resp_stale.status_code == 409
    assert "expired (>24h)" in resp_stale.json()["detail"]

    # Verify DB state is SUPPRESSED / EXPIRED
    service = ProactiveNotificationService(test_session)
    updated = await service.get_notification(record_stale.id)
    assert updated is not None
    assert updated.status == NotificationStatus.SUPPRESSED.value
    assert updated.suppression_reason == SuppressionReason.EXPIRED.value


@pytest.mark.asyncio
async def test_desktop_notifications_24h_boundary_precision(test_session: AsyncSession):
    """
    Test exact 24-hour expiration boundary semantics with mathematical clock precision:
    - age < 86400.0s  -> eligible (claim succeeds)
    - age == 86400.0s -> eligible (inclusive upper bound, claim succeeds)
    - age > 86400.0s  -> expired (claim fails, SUPPRESSED / EXPIRED)
    """
    import uuid
    from datetime import timedelta
    from app.proactive.models import NotificationStatus, SuppressionReason

    service = ProactiveNotificationService(test_session)
    base_time = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Case A: age = 86,399.0s (< 86,400.0s) -> eligible
    notif_under = await seed_notification(
        test_session,
        created_at=base_time - timedelta(seconds=86399.0),
        status=NotificationStatus.PENDING.value,
    )
    claimed_under = await service.claim_notification(
        notification_id=notif_under.id,
        worker_id="worker-under",
        current_time=base_time,
    )
    assert claimed_under is True
    rec_under = await service.get_notification(notif_under.id)
    assert rec_under.status == NotificationStatus.DELIVERING.value

    # Case B: age = 86,400.0s (== 86,400.0s, inclusive boundary) -> eligible
    notif_exact = await seed_notification(
        test_session,
        created_at=base_time - timedelta(seconds=86400.0),
        status=NotificationStatus.PENDING.value,
    )
    claimed_exact = await service.claim_notification(
        notification_id=notif_exact.id,
        worker_id="worker-exact",
        current_time=base_time,
    )
    assert claimed_exact is True
    rec_exact = await service.get_notification(notif_exact.id)
    assert rec_exact.status == NotificationStatus.DELIVERING.value

    # Case C: age = 86,400.1s (> 86,400.0s) -> expired
    notif_over = await seed_notification(
        test_session,
        created_at=base_time - timedelta(seconds=86400.1),
        status=NotificationStatus.PENDING.value,
    )
    claimed_over = await service.claim_notification(
        notification_id=notif_over.id,
        worker_id="worker-over",
        current_time=base_time,
    )
    assert claimed_over is False
    rec_over = await service.get_notification(notif_over.id)
    assert rec_over.status == NotificationStatus.SUPPRESSED.value
    assert rec_over.suppression_reason == SuppressionReason.EXPIRED.value


@pytest.mark.asyncio
async def test_desktop_notifications_complete_endpoint(client: AsyncClient, test_session: AsyncSession):
    """Test completing notification delivery, worker verification, and idempotency."""
    import uuid
    from app.proactive.models import NotificationStatus

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    record = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
    )

    # Claim with worker-1
    await client.post(
        f"/desktop/notifications/{record.id}/claim",
        json={"worker_id": "worker-1", "character_id": char_id},
    )

    # 1. Complete with wrong worker -> 409 Conflict
    resp_wrong_worker = await client.post(
        f"/desktop/notifications/{record.id}/complete",
        json={"worker_id": "worker-impostor", "character_id": char_id},
    )
    assert resp_wrong_worker.status_code == 409

    # 2. Complete with wrong character_id -> 403 Forbidden
    resp_wrong_char = await client.post(
        f"/desktop/notifications/{record.id}/complete",
        json={"worker_id": "worker-1", "character_id": "alien_char"},
    )
    assert resp_wrong_char.status_code == 403

    # 3. Complete with valid worker -> 200 OK
    resp_ok = await client.post(
        f"/desktop/notifications/{record.id}/complete",
        json={"worker_id": "worker-1", "character_id": char_id},
    )
    assert resp_ok.status_code == 200
    data_ok = resp_ok.json()
    assert data_ok["completed"] is True
    assert data_ok["status"] == "DELIVERED"
    assert data_ok["delivered_at"] is not None

    # 4. Idempotency: Complete again on already DELIVERED notification -> 200 OK
    resp_idempotent = await client.post(
        f"/desktop/notifications/{record.id}/complete",
        json={"worker_id": "worker-1", "character_id": char_id},
    )
    assert resp_idempotent.status_code == 200
    assert resp_idempotent.json()["status"] == "DELIVERED"


@pytest.mark.asyncio
async def test_desktop_notifications_release_endpoint(client: AsyncClient, test_session: AsyncSession):
    """Test releasing delivery lease back to PENDING, worker verification, and idempotency."""
    import uuid
    from app.proactive.models import NotificationStatus

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    record = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
    )

    # Claim with worker-1
    await client.post(
        f"/desktop/notifications/{record.id}/claim",
        json={"worker_id": "worker-1", "character_id": char_id},
    )

    # 1. Release with wrong worker -> 409 Conflict
    resp_wrong_worker = await client.post(
        f"/desktop/notifications/{record.id}/release",
        json={"worker_id": "worker-wrong", "character_id": char_id},
    )
    assert resp_wrong_worker.status_code == 409

    # 2. Release with valid worker -> 200 OK
    resp_release = await client.post(
        f"/desktop/notifications/{record.id}/release",
        json={"worker_id": "worker-1", "character_id": char_id},
    )
    assert resp_release.status_code == 200
    assert resp_release.json()["status"] == "PENDING"
    assert resp_release.json()["released"] is True

    # Verify DB state has cleared claimed_by and claimed_at
    service = ProactiveNotificationService(test_session)
    released_rec = await service.get_notification(record.id)
    assert released_rec.status == NotificationStatus.PENDING.value
    assert released_rec.claimed_by is None
    assert released_rec.claimed_at is None

    # 3. Idempotency: Release again on already PENDING notification -> 200 OK
    resp_idempotent = await client.post(
        f"/desktop/notifications/{record.id}/release",
        json={"worker_id": "worker-1", "character_id": char_id},
    )
    assert resp_idempotent.status_code == 200
    assert resp_idempotent.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_desktop_notifications_interact_endpoint(client: AsyncClient, test_session: AsyncSession):
    """Test recording user interaction (CLICKED / DISMISSED), validation, and idempotency."""
    import uuid
    from app.proactive.models import NotificationStatus

    char_id = f"test_char_{uuid.uuid4().hex[:8]}"
    record = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
    )

    # 1. Interaction on PENDING notification -> 409 Conflict (invalid state)
    resp_bad_state = await client.post(
        f"/desktop/notifications/{record.id}/interact",
        json={"character_id": char_id, "action": "CLICKED"},
    )
    assert resp_bad_state.status_code == 409

    # Claim and complete to DELIVERED
    await client.post(
        f"/desktop/notifications/{record.id}/claim",
        json={"worker_id": "worker-1", "character_id": char_id},
    )
    await client.post(
        f"/desktop/notifications/{record.id}/complete",
        json={"worker_id": "worker-1", "character_id": char_id},
    )

    # 2. Invalid action -> 422 Unprocessable Entity
    resp_invalid_action = await client.post(
        f"/desktop/notifications/{record.id}/interact",
        json={"character_id": char_id, "action": "SNOOZE"},
    )
    assert resp_invalid_action.status_code == 422

    # 3. Valid CLICKED interaction -> 200 OK
    resp_clicked = await client.post(
        f"/desktop/notifications/{record.id}/interact",
        json={"character_id": char_id, "action": "CLICKED"},
    )
    assert resp_clicked.status_code == 200
    data_clicked = resp_clicked.json()
    assert data_clicked["interacted"] is True
    assert data_clicked["status"] == "CLICKED"
    assert data_clicked["conversation_message_id"] == record.conversation_message_id
    assert data_clicked["interacted_at"] is not None

    # 4. Idempotent CLICKED -> 200 OK
    resp_clicked_again = await client.post(
        f"/desktop/notifications/{record.id}/interact",
        json={"character_id": char_id, "action": "CLICKED"},
    )
    assert resp_clicked_again.status_code == 200
    assert resp_clicked_again.json()["status"] == "CLICKED"

    # 5. DISMISSED interaction on another delivered notification
    record2 = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.DELIVERED.value,
    )
    resp_dismissed = await client.post(
        f"/desktop/notifications/{record2.id}/interact",
        json={"character_id": char_id, "action": "DISMISSED"},
    )
    assert resp_dismissed.status_code == 200
    assert resp_dismissed.json()["status"] == "DISMISSED"

    # 6. Idempotent DISMISSED -> 200 OK
    resp_dismissed_again = await client.post(
        f"/desktop/notifications/{record2.id}/interact",
        json={"character_id": char_id, "action": "DISMISSED"},
    )
    assert resp_dismissed_again.status_code == 200
    assert resp_dismissed_again.json()["status"] == "DISMISSED"


@pytest.mark.asyncio
async def test_desktop_notifications_concurrent_claims(test_engine):
    """
    Test concurrent claim race condition under Standard 35 and Lock-in 2 & 8:
    Multiple workers attempt to claim the exact same pending notification concurrently.
    Exactly 1 worker succeeds (rowcount == 1); all other workers fail (rowcount == 0).
    """
    import asyncio
    from app.proactive.models import NotificationStatus

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # 1. Seed pending notification
    async with session_factory() as init_session:
        notif = await seed_notification(
            init_session,
            status=NotificationStatus.PENDING.value,
            title="Concurrent Race Target",
        )
        notif_id = notif.id

    # 2. Race: 5 concurrent workers attempting claim
    async def worker_attempt(worker_id: str) -> bool:
        async with session_factory() as worker_session:
            svc = ProactiveNotificationService(worker_session)
            return await svc.claim_notification(
                notification_id=notif_id,
                worker_id=worker_id,
                lease_timeout_seconds=30.0,
            )

    results = await asyncio.gather(*[worker_attempt(f"worker-{i}") for i in range(5)])

    # Exactly 1 winner
    assert results.count(True) == 1
    assert results.count(False) == 4

    # Verify winner holds the lease in database
    async with session_factory() as verify_session:
        svc = ProactiveNotificationService(verify_session)
        final_rec = await svc.get_notification(notif_id)
        assert final_rec.status == NotificationStatus.DELIVERING.value
        assert final_rec.claimed_by.startswith("worker-")


@pytest.mark.asyncio
async def test_step4_end_to_end_delivery_and_deterministic_activation(
    client: AsyncClient, test_session: AsyncSession
):
    """
    Step 4E End-to-End Integration Benchmark:
    1. Seed proactive notification with known message in SQLite.
    2. Frontend polling worker GET /desktop/notifications/pending discovers it.
    3. Frontend claims POST /desktop/notifications/{id}/claim.
    4. Frontend shows toast and completes POST /desktop/notifications/{id}/complete -> status is DELIVERED.
    5. Alt+Tab / Focus simulation: User focuses Aevum window without clicking toast.
       Verify notification remains DELIVERED, never marked CLICKED.
    6. User clicks Windows Toast -> Deep-link aevum://notification/{id} activates:
       - Frontend GET /desktop/notifications/{id} fetches payload, locating conversation_message_id.
       - Frontend calls POST /desktop/notifications/{id}/interact with action="CLICKED".
       - Status transitions to CLICKED with timestamp.
    7. Dual-worker decoupling verification:
       - Notification worker functions fully independently from heartbeat worker.
       - Notifications continue to poll and deliver regardless of idle_awareness_enabled setting.
    """
    import uuid
    from app.proactive.models import NotificationStatus

    char_id = f"char_step4_{uuid.uuid4().hex[:8]}"

    # Step 4.1: Seed proactive notification with linked conversation message
    record = await seed_notification(
        test_session,
        character_id=char_id,
        status=NotificationStatus.PENDING.value,
        title="Aevum Observation",
        body="I was just reflecting on our earlier conversation.",
    )
    notif_id = record.id
    target_msg_id = record.conversation_message_id
    assert target_msg_id is not None

    # Step 4.2: Frontend Notification Polling Worker queries pending
    pending_resp = await client.get(f"/desktop/notifications/pending?character_id={char_id}")
    assert pending_resp.status_code == 200
    pending_items = pending_resp.json()
    assert len(pending_items) >= 1
    found_item = next((item for item in pending_items if item["id"] == notif_id), None)
    assert found_item is not None
    assert found_item["status"] == "PENDING"

    # Step 4.3: Worker claims notification
    worker_id = f"desktop-worker-{uuid.uuid4().hex[:6]}"
    claim_resp = await client.post(
        f"/desktop/notifications/{notif_id}/claim",
        json={"worker_id": worker_id, "character_id": char_id},
    )
    assert claim_resp.status_code == 200
    assert claim_resp.json()["claimed"] is True

    # Step 4.4: Worker dispatches native WinRT toast and marks delivery complete
    complete_resp = await client.post(
        f"/desktop/notifications/{notif_id}/complete",
        json={"worker_id": worker_id, "character_id": char_id},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["completed"] is True
    assert complete_resp.json()["status"] == "DELIVERED"

    # Step 4.5: Alt+Tab / Focus Simulation:
    # User focuses the Aevum window manually (or presses Alt+Tab) WITHOUT clicking the Toast.
    # Frontend window focus handler DOES NOT invoke any interact endpoint.
    # Verify authoritative status in backend remains DELIVERED.
    check_resp = await client.get(f"/desktop/notifications/{notif_id}")
    assert check_resp.status_code == 200
    assert check_resp.json()["status"] == "DELIVERED"
    assert check_resp.json()["interacted_at"] is None

    # Step 4.6: Deep-link Activation Simulation:
    # User explicitly clicks the Windows Toast body (launch="aevum://notification/{id}").
    # Tauri captures deep-link and emits "notification-activated" event to React.
    # React handler looks up notification by ID:
    lookup_resp = await client.get(f"/desktop/notifications/{notif_id}")
    assert lookup_resp.status_code == 200
    lookup_data = lookup_resp.json()
    assert lookup_data["id"] == notif_id
    assert lookup_data["conversation_message_id"] == target_msg_id

    # React handler records interaction via POST /desktop/notifications/{id}/interact
    interact_resp = await client.post(
        f"/desktop/notifications/{notif_id}/interact",
        json={"character_id": char_id, "action": "CLICKED"},
    )
    assert interact_resp.status_code == 200
    interact_data = interact_resp.json()
    assert interact_data["interacted"] is True
    assert interact_data["status"] == "CLICKED"
    assert interact_data["interacted_at"] is not None

    # Step 4.7: Worker Decoupling Invariant Check:
    # Notification polling works even when idle_awareness_enabled is False.
    settings_resp = await client.get(f"/desktop/settings?character_id={char_id}")
    assert settings_resp.status_code == 200
    assert settings_resp.json()["idle_awareness_enabled"] is False

    # Send heartbeat while awareness is disabled -> zero telemetry persisted
    hb_resp = await client.post(
        f"/desktop/heartbeat?character_id={char_id}",
        json={
            "client_id": "test-hb-client",
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
            "is_idle": True,
            "idle_seconds": 900.0,
            "window_focused": False,
        },
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["awareness_enabled"] is False

    # Audit history reflects exact CLICKED status and delivered_at timestamp
    history_resp = await client.get(f"/desktop/notifications/history?character_id={char_id}&limit=10")
    assert history_resp.status_code == 200
    history_items = history_resp.json()
    hist_match = next((item for item in history_items if item["id"] == notif_id), None)
    assert hist_match is not None
    assert hist_match["status"] == "CLICKED"
    assert hist_match["interacted_at"] is not None

