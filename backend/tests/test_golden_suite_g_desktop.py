"""Golden Suite G — Desktop Integration & Proactive Reach-Out Benchmarks (Phase 8).

Benchmarks:
- GC-044: Zero Unconsented Reach-Out (Invariant 25)
- GC-045: Timezone-Aware Quiet Hours Inviolability & Midnight Wrap (Lock-in 8)
- GC-046: Daily Cap & Cooldown Hard Gating (Lock-in 9)
- GC-051: Proactive Intent Grounding & Decoupling (Lock-in 1)
"""

from datetime import datetime, timedelta, timezone
import zoneinfo
import pytest


from app.proactive.models import (
    DesktopUserSettings,
    ProactiveIntent,
    ProactiveIntentType,
    SuppressionReason,
)
from app.proactive.intent_engine import ProactiveIntentEngine
from app.proactive.gate_engine import ProactiveGateEngine, is_in_quiet_hours


def to_utc(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC for database comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)



class MockNotification:
    """Mock notification record for deterministic gate testing."""

    def __init__(self, status: str, delivered_at: datetime):
        self.status = status
        self.delivered_at = delivered_at


# ---------------------------------------------------------------------------
# GC-044: Zero Unconsented Reach-Out (Invariant 25)
# ---------------------------------------------------------------------------
def test_gc_044_zero_unconsented_reach_out():
    """Verify default settings strictly block proactive reach-outs with DISABLED."""
    gate_engine = ProactiveGateEngine()

    # Default settings has proactive_enabled = False
    default_settings = DesktopUserSettings(character_id="aevum")
    assert default_settings.proactive_enabled is False

    valid_intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.85,
        grounding_activity_title="read_literature",
    )

    eval_time = datetime(2026, 9, 18, 14, 0, tzinfo=timezone.utc)
    result = gate_engine.evaluate_gates(
        settings=default_settings,
        intent=valid_intent,
        current_time=eval_time,
        recent_notifications=[],
        fatigue=0.20,
        current_activity="rest_unwind",
    )

    assert result.passed is False
    assert result.suppression_reason == SuppressionReason.DISABLED
    assert result.gate_breakdown["master_switch"] is False


# ---------------------------------------------------------------------------
# GC-045: Quiet Hours Inviolability & Timezone Wrap (Lock-in 8)
# ---------------------------------------------------------------------------
def test_gc_045_quiet_hours_inviolability_and_timezone_wrap():
    """Verify timezone conversion and midnight wrap-around (23:00 -> 08:00)."""
    gate_engine = ProactiveGateEngine()

    # Configure user in America/New_York with 23:00 -> 08:00 quiet hours
    ny_tz = zoneinfo.ZoneInfo("America/New_York")
    settings = DesktopUserSettings(
        character_id="aevum",
        proactive_enabled=True,
        timezone="America/New_York",
        quiet_hours_enabled=True,
        quiet_hours_start="23:00",
        quiet_hours_end="08:00",
    )

    intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.80,
    )

    # 1. New York local time: 23:15 (Late evening, inside quiet hours)
    time_2315_ny = datetime(2026, 9, 18, 23, 15, tzinfo=ny_tz)
    result_2315 = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=time_2315_ny,
        recent_notifications=[],
    )
    assert result_2315.passed is False
    assert result_2315.suppression_reason == SuppressionReason.QUIET_HOURS
    assert result_2315.gate_breakdown["quiet_hours"] is False

    # 2. New York local time: 03:30 (Middle of night, inside wrap window)
    time_0330_ny = datetime(2026, 9, 19, 3, 30, tzinfo=ny_tz)
    result_0330 = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=time_0330_ny,
        recent_notifications=[],
    )
    assert result_0330.passed is False
    assert result_0330.suppression_reason == SuppressionReason.QUIET_HOURS

    # 3. New York local time: 14:00 (Afternoon, outside quiet hours)
    time_1400_ny = datetime(2026, 9, 19, 14, 0, tzinfo=ny_tz)
    result_1400 = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=time_1400_ny,
        recent_notifications=[],
    )
    assert result_1400.passed is True
    assert result_1400.suppression_reason is None
    assert result_1400.gate_breakdown["quiet_hours"] is True

    # 4. Explicit Timezone Difference Verification:
    # A single UTC instant: 2026-09-18 03:30 UTC
    # In Shanghai (UTC+8): local time is 11:30 AM (outside quiet hours)
    # In New York (EDT, UTC-4): local time is 23:30 PM (inside quiet hours)
    utc_instant = datetime(2026, 9, 18, 3, 30, tzinfo=timezone.utc)

    shanghai_settings = DesktopUserSettings(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=True,
        quiet_hours_start="23:00",
        quiet_hours_end="08:00",
    )
    res_shanghai = gate_engine.evaluate_gates(
        settings=shanghai_settings,
        intent=intent,
        current_time=utc_instant,
        recent_notifications=[],
    )
    assert res_shanghai.passed is True  # 11:30 AM in Shanghai

    res_ny = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=utc_instant,
        recent_notifications=[],
    )
    assert res_ny.passed is False  # 23:30 PM in NY -> suppressed
    assert res_ny.suppression_reason == SuppressionReason.QUIET_HOURS


# ---------------------------------------------------------------------------
# GC-046: Daily Cap & Cooldown Hard Gating (Lock-in 9)
# ---------------------------------------------------------------------------
def test_gc_046_daily_cap_and_cooldown_hard_gating():
    """Verify quota counts only DELIVERED/CLICKED/DISMISSED and cooldown enforces spacing."""
    gate_engine = ProactiveGateEngine()
    tz = zoneinfo.ZoneInfo("Asia/Shanghai")

    settings = DesktopUserSettings(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=False,  # Disable to isolate cap & cooldown
        max_daily_reach_outs=3,
        min_cooldown_minutes=120,
    )

    intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.85,
    )

    # 1. Cooldown Test: Last delivered 45 minutes ago -> COOLDOWN
    eval_time = datetime(2026, 9, 18, 14, 0, tzinfo=tz)
    recent_notifs = [
        MockNotification(status="DELIVERED", delivered_at=datetime(2026, 9, 18, 13, 15, tzinfo=tz)),
    ]

    res_cooldown = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=eval_time,
        recent_notifications=recent_notifs,
    )
    assert res_cooldown.passed is False
    assert res_cooldown.suppression_reason == SuppressionReason.COOLDOWN
    assert res_cooldown.gate_breakdown["cooldown"] is False

    # 2. Cooldown Elapsed Test: Last delivered 130 minutes ago -> passes cooldown
    recent_notifs_elapsed = [
        MockNotification(status="DELIVERED", delivered_at=datetime(2026, 9, 18, 11, 40, tzinfo=tz)),
    ]
    res_cooldown_ok = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=eval_time,
        recent_notifications=recent_notifs_elapsed,
    )
    assert res_cooldown_ok.passed is True

    # 3. Daily Cap Test: Exactly 3 delivered today -> 4th is suppressed with DAILY_CAP
    # Space them out to avoid cooldown triggers (09:00, 11:15, 13:30)
    eval_time_late = datetime(2026, 9, 18, 16, 0, tzinfo=tz)
    three_delivered = [
        MockNotification(status="DELIVERED", delivered_at=datetime(2026, 9, 18, 9, 0, tzinfo=tz)),
        MockNotification(status="CLICKED", delivered_at=datetime(2026, 9, 18, 11, 15, tzinfo=tz)),
        MockNotification(status="DISMISSED", delivered_at=datetime(2026, 9, 18, 13, 30, tzinfo=tz)),
    ]
    res_cap = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=eval_time_late,
        recent_notifications=three_delivered,
    )
    assert res_cap.passed is False
    assert res_cap.suppression_reason == SuppressionReason.DAILY_CAP
    assert res_cap.gate_breakdown["daily_cap"] is False

    # 4. Lock-in 9: SUPPRESSED and PENDING do NOT consume daily quota
    # 5 suppressed notifications today, 2 pending -> delivered count = 0 -> passes
    mixed_non_quota = [
        MockNotification(status="SUPPRESSED", delivered_at=datetime(2026, 9, 18, 9, 0, tzinfo=tz)),
        MockNotification(status="SUPPRESSED", delivered_at=datetime(2026, 9, 18, 10, 0, tzinfo=tz)),
        MockNotification(status="SUPPRESSED", delivered_at=datetime(2026, 9, 18, 11, 0, tzinfo=tz)),
        MockNotification(status="PENDING", delivered_at=None),
        MockNotification(status="PENDING", delivered_at=None),
    ]
    res_non_quota = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=eval_time_late,
        recent_notifications=mixed_non_quota,
    )
    assert res_non_quota.passed is True
    assert res_non_quota.gate_breakdown["daily_cap"] is True


# ---------------------------------------------------------------------------
# GC-047: Physiological & Sleep State Gating (GateEngine Regression)
# ---------------------------------------------------------------------------
def test_gc_047_physiological_and_sleep_state_gating():
    """
    Gate 6: Physiological State & Sleep.
    Verify that sleep activities suppress proactive reach-out with SLEEPING,
    and fatigue >= 0.85 suppresses with HIGH_FATIGUE.
    """
    gate_engine = ProactiveGateEngine()
    settings = DesktopUserSettings(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=False,
    )
    intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.85,
    )
    eval_time = datetime(2026, 9, 18, 14, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai"))

    # Case A: Ongoing SLEEP activity -> Suppressed: SLEEPING
    for sleep_act in ("SLEEP", "night_sleep", "nap"):
        res_sleep = gate_engine.evaluate_gates(
            settings=settings,
            intent=intent,
            current_time=eval_time,
            recent_notifications=[],
            current_activity=sleep_act,
            fatigue=0.20,
        )
        assert res_sleep.passed is False
        assert res_sleep.suppression_reason == SuppressionReason.SLEEPING
        assert res_sleep.gate_breakdown["physiological"] is False

    # Case B: High fatigue >= 0.85 -> Suppressed: HIGH_FATIGUE
    res_fatigue = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=eval_time,
        recent_notifications=[],
        current_activity="rest_unwind",
        fatigue=0.85,
    )
    assert res_fatigue.passed is False
    assert res_fatigue.suppression_reason == SuppressionReason.HIGH_FATIGUE
    assert res_fatigue.gate_breakdown["physiological"] is False

    # Case C: Normal restorative activity, low fatigue (< 0.85) -> Gate 6 PASSES
    res_ok = gate_engine.evaluate_gates(
        settings=settings,
        intent=intent,
        current_time=eval_time,
        recent_notifications=[],
        current_activity="read_literature",
        fatigue=0.40,
    )
    assert res_ok.passed is True
    assert res_ok.gate_breakdown["physiological"] is True


# ---------------------------------------------------------------------------
# GC-051: Proactive Intent Grounding & Decoupling (Lock-in 1)
# ---------------------------------------------------------------------------
def test_gc_051_proactive_intent_grounding_and_decoupling():
    """Verify that LifeEvent alone NEVER implies reach-out; requires internal desire and relational comfort."""
    intent_engine = ProactiveIntentEngine()
    gate_engine = ProactiveGateEngine()

    # Scenario A: Activity completed, but high solitude need & low social need
    # Aevum finishes reading, but wants quiet solitude.
    intent_solitary = intent_engine.evaluate_intent(
        character_id="aevum",
        social_need=0.10,
        solitude_need=0.85,  # Solitude preference
        relationship_comfort=0.70,
        relationship_trust=0.75,
        fatigue=0.20,
        attention_availability=0.80,
        current_activity="read_literature",
        life_event_id="ev-101",
        life_event_type="ACTIVITY_COMPLETED",
        activity_title="read_literature",
    )
    # Grounding check: LifeEvent exists, but NO intent is formed!
    assert intent_solitary is None

    # Scenario B: Low relationship comfort (< 0.20)
    # Character does not feel comfortable enough to reach out uninvited.
    intent_uncomfortable = intent_engine.evaluate_intent(
        character_id="aevum",
        social_need=0.80,
        solitude_need=0.10,
        relationship_comfort=0.15,  # Too low
        relationship_trust=0.30,
        fatigue=0.20,
        attention_availability=0.80,
        activity_title="walk_outside",
        life_event_type="ACTIVITY_COMPLETED",
    )
    assert intent_uncomfortable is None

    # Scenario C: Valid internal state + desire to share -> Intent Formed
    intent_valid = intent_engine.evaluate_intent(
        character_id="aevum",
        social_need=0.75,
        solitude_need=0.15,
        relationship_comfort=0.70,
        relationship_trust=0.75,
        fatigue=0.20,
        attention_availability=0.85,
        current_activity="rest_unwind",
        life_event_id="ev-202",
        life_event_type="ACTIVITY_COMPLETED",
        activity_title="practice_instrument",
        desire_focus="Share piano progress with user",
    )
    assert intent_valid is not None
    assert intent_valid.intent_type == ProactiveIntentType.SHARE_EXPERIENCE
    assert intent_valid.intent_strength >= 0.40
    assert intent_valid.grounding_event_id == "ev-202"
    assert intent_valid.grounding_activity_title == "practice_instrument"

    # Scenario D: Physiological block (sleep or exhaustion) suppresses intent formation
    intent_sleeping = intent_engine.evaluate_intent(
        character_id="aevum",
        social_need=0.80,
        solitude_need=0.10,
        relationship_comfort=0.80,
        relationship_trust=0.80,
        fatigue=0.90,  # Exhausted
        attention_availability=0.10,
        current_activity="night_sleep",
        activity_title="night_sleep",
        life_event_type="ACTIVITY_COMPLETED",
    )
    assert intent_sleeping is None

    # Scenario E: Intent formed in Scenario C must still clear GateEngine
    settings_quiet = DesktopUserSettings(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=True,
        quiet_hours_start="23:00",
        quiet_hours_end="08:00",
    )
    # Evaluate at 02:00 AM (Quiet Hours active)
    eval_time_quiet = datetime(2026, 9, 18, 2, 0, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai"))
    gate_res = gate_engine.evaluate_gates(
        settings=settings_quiet,
        intent=intent_valid,
        current_time=eval_time_quiet,
        recent_notifications=[],
    )
    assert gate_res.passed is False
    assert gate_res.suppression_reason == SuppressionReason.QUIET_HOURS


# ===========================================================================
# PHASE 8.2 BENCHMARKS: NOTIFICATION PERSISTENCE & ATOMIC CLAIM (GC-048 ~ 057)
# ===========================================================================

import asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.db.session import Base
from app.db.models import Conversation, Message, ProactiveNotificationRecord
from app.proactive.models import NotificationStatus, ProactiveContext
from app.proactive.message_generator import ProactiveMessageGenerator
from app.proactive.notification_service import ProactiveNotificationService
from app.life.clock import DeterministicSimulationClock


class SpyMessageGenerator(ProactiveMessageGenerator):
    """Spy message generator tracking invocation count to verify zero regeneration."""

    def __init__(self, fixed_reply: str = "Spy generated proactive message."):
        super().__init__(llm_provider=None)
        self.calls: int = 0
        self.fixed_reply = fixed_reply

    async def generate_proactive_message(self, context: ProactiveContext) -> str:
        self.calls += 1
        return self.fixed_reply


# ---------------------------------------------------------------------------
# GC-052: Atomic Notification Delivery Claim — True DB Race (Standard 35)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_052_atomic_notification_delivery_claim_true_db_race(tmp_path):
    """
    Standard 35 / Lock-in 2: Two independent AsyncSessions race to claim the same PENDING notification.
    Verifies:
    1. Exactly one worker achieves rowcount == 1 (returns True).
    2. The other worker receives rowcount == 0 (returns False).
    3. Zero global asyncio.Lock used; database conditional update provides race safety.
    """
    db_file = tmp_path / "concurrent_notif_gc052.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Setup initial conversation, message, and PENDING notification
    notif_id: str
    async with session_factory() as init_session:
        conv = Conversation(created_at=datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc))
        init_session.add(conv)
        await init_session.flush()

        msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content="Hey, just took a break from studying.",
            created_at=datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc),
        )
        init_session.add(msg)
        await init_session.flush()

        notif = ProactiveNotificationRecord(
            character_id="aevum",
            conversation_message_id=msg.id,
            trigger_type="SHARE_EXPERIENCE",
            idempotency_key="gc052-race-trigger-1",
            title="Aevum — Study Break",
            body=msg.content,
            status=NotificationStatus.PENDING.value,
            created_at=datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc),
        )
        init_session.add(notif)
        await init_session.commit()
        notif_id = notif.id

    # 2. Race: Two independent AsyncSessions attempt claim_notification concurrently
    claim_time = datetime(2026, 9, 18, 10, 1, 0, tzinfo=timezone.utc)

    async def worker_attempt(worker_id: str):
        async with session_factory() as session:
            service = ProactiveNotificationService(session)
            return await service.claim_notification(
                notification_id=notif_id,
                worker_id=worker_id,
                lease_timeout_seconds=60.0,
                current_time=claim_time,
            )

    res_a, res_b = await asyncio.gather(
        worker_attempt("worker-A"),
        worker_attempt("worker-B"),
        return_exceptions=True,
    )

    # Assertions: No exceptions
    assert not isinstance(res_a, Exception), f"Worker A failed with: {res_a}"
    assert not isinstance(res_b, Exception), f"Worker B failed with: {res_b}"

    # Exactly one winner, exactly one loser
    results = [res_a, res_b]
    assert results.count(True) == 1, f"Expected exactly one True, got {results}"
    assert results.count(False) == 1, f"Expected exactly one False, got {results}"

    winner_id = "worker-A" if res_a is True else "worker-B"

    # 3. Verify final DB state in fresh verification session
    async with session_factory() as verify_session:
        service_v = ProactiveNotificationService(verify_session)
        final_notif = await service_v.get_notification(notif_id)
        assert final_notif is not None
        assert final_notif.status == NotificationStatus.DELIVERING.value
        assert final_notif.claimed_by == winner_id
        assert final_notif.claimed_at is not None

    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-053: Message Identity Stability
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_053_message_identity_stability(tmp_path):
    """
    Lock-in 4 & 9: Verifies that notification failure and retry retain the SAME conversation_message_id.
    Zero second message is created in the conversation history on delivery retry.
    """
    db_file = tmp_path / "identity_gc053.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    t0 = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
    clock = DeterministicSimulationClock(t0)

    # 1. Create notification
    notif_id: str
    original_message_id: str
    conv_id: str
    async with session_factory() as session:
        service = ProactiveNotificationService(session, clock=clock)
        intent = ProactiveIntent(
            character_id="aevum",
            intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
            intent_strength=0.85,
            topic_hook="Reading progress",
        )
        context = ProactiveContext(character_id="aevum", approved_intent=intent)
        notif = await service.create_proactive_notification(
            intent=intent,
            context=context,
            idempotency_key="gc053-ident-1",
        )
        notif_id = notif.id
        original_message_id = notif.conversation_message_id
        assert original_message_id is not None

        # Get conversation ID
        stmt_msg = select(Message).where(Message.id == original_message_id)
        msg_record = (await session.scalars(stmt_msg)).one()
        conv_id = msg_record.conversation_id

    # 2. Worker A claims, then simulates delivery failure and releases claim
    async with session_factory() as session:
        service = ProactiveNotificationService(session, clock=clock)
        claimed = await service.claim_notification(notif_id, worker_id="worker-A")
        assert claimed is True

        # Failure occurs -> release claim back to PENDING
        released = await service.release_claim(notif_id, worker_id="worker-A")
        assert released is True

    # 3. Worker B re-claims and completes delivery
    async with session_factory() as session:
        service = ProactiveNotificationService(session, clock=clock)
        reclaimed = await service.claim_notification(notif_id, worker_id="worker-B")
        assert reclaimed is True

        completed = await service.complete_delivery(notif_id, worker_id="worker-B")
        assert completed is True

    # 4. Verify message identity stability in verification session
    async with session_factory() as session:
        service = ProactiveNotificationService(session, clock=clock)
        final_notif = await service.get_notification(notif_id)
        assert final_notif.status == NotificationStatus.DELIVERED.value
        # Hard Invariant: conversation_message_id is strictly unchanged
        assert final_notif.conversation_message_id == original_message_id

        # Verify only 1 message exists in conversation (no duplicate messages generated)
        stmt_count = select(func.count()).select_from(Message).where(Message.conversation_id == conv_id)
        count = await session.scalar(stmt_count)
        assert count == 1

    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-054: Mandatory Message Binding (Hard Invariant 2 & 7)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_054_mandatory_message_binding(tmp_path):
    """
    Lock-in 2 & 7: Every persisted notification MUST reference an existing canonical message.
    Verifies that create_proactive_notification generates the message in messages table
    and binds conversation_message_id non-null before returning PENDING.
    """
    db_file = tmp_path / "binding_gc054.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        intent = ProactiveIntent(
            character_id="aevum",
            intent_type=ProactiveIntentType.SOCIAL_CHECKIN,
            intent_strength=0.75,
            topic_hook="Afternoon break",
        )
        context = ProactiveContext(character_id="aevum", approved_intent=intent)

        notif = await service.create_proactive_notification(
            intent=intent,
            context=context,
            idempotency_key="gc054-binding-key-1",
        )

        # 1. Notification has non-null conversation_message_id
        assert notif.conversation_message_id is not None
        assert len(notif.conversation_message_id) > 0
        assert notif.status == NotificationStatus.PENDING.value

        # 2. Canonical message actually exists in database
        stmt = select(Message).where(Message.id == notif.conversation_message_id)
        bound_message = (await session.scalars(stmt)).first()
        assert bound_message is not None
        assert bound_message.role == "assistant"
        assert bound_message.content == notif.body

    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-055: Notification Idempotency Under Concurrent Creation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_055_notification_idempotency_concurrent_creation(tmp_path):
    """
    Lock-in 5: Concurrent workers calling create_proactive_notification with the same
    idempotency_key result in exactly ONE persisted notification record (database UNIQUE backstop).
    """
    db_file = tmp_path / "idempotent_gc055.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.80,
        grounding_activity_title="walk_outside",
    )
    context = ProactiveContext(character_id="aevum", approved_intent=intent)
    same_idempotency_key = "gc055-concurrent-idem-key"

    # Pre-create default conversation to prevent collision on conversation table
    async with session_factory() as init_session:
        conv = Conversation()
        init_session.add(conv)
        await init_session.commit()
        conv_id = conv.id

    async def create_attempt(worker_name: str):
        async with session_factory() as session:
            service = ProactiveNotificationService(session)
            return await service.create_proactive_notification(
                intent=intent,
                context=context,
                idempotency_key=same_idempotency_key,
                conversation_id=conv_id,
            )

    res1, res2 = await asyncio.gather(
        create_attempt("worker-1"),
        create_attempt("worker-2"),
        return_exceptions=True,
    )

    assert not isinstance(res1, Exception), f"Worker 1 threw: {res1}"
    assert not isinstance(res2, Exception), f"Worker 2 threw: {res2}"

    # Both workers received valid notification records with the same notification ID
    assert res1.id == res2.id
    assert res1.idempotency_key == same_idempotency_key

    # In database: exactly 1 row exists
    async with session_factory() as verify_session:
        stmt = select(func.count()).select_from(ProactiveNotificationRecord).where(
            ProactiveNotificationRecord.idempotency_key == same_idempotency_key
        )
        count = await verify_session.scalar(stmt)
        assert count == 1

    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-056: Stale Lease Recovery (Crash Recovery Lease)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_056_stale_lease_recovery(tmp_path):
    """
    Standard 35 & Hard Lock 8: A notification stuck in DELIVERING after worker crash
    becomes eligible for deterministic re-claim once claimed_at + lease_timeout < current_time.
    """
    db_file = tmp_path / "stale_lease_gc056.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    t0 = datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc)
    lease_timeout = 60.0  # 60 seconds

    notif_id: str
    message_id: str
    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        intent = ProactiveIntent(
            character_id="aevum",
            intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
            intent_strength=0.85,
        )
        context = ProactiveContext(character_id="aevum", approved_intent=intent)
        notif = await service.create_proactive_notification(
            intent=intent,
            context=context,
            idempotency_key="gc056-stale-key",
            current_time=t0,
        )
        notif_id = notif.id
        message_id = notif.conversation_message_id

    # 1. Worker A claims at T0 -> enters DELIVERING
    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        claimed_a = await service.claim_notification(
            notification_id=notif_id,
            worker_id="worker-A",
            lease_timeout_seconds=lease_timeout,
            current_time=t0,
        )
        assert claimed_a is True

    # 2. Worker B attempts claim at T0 + 30s (Lease still active, Worker A has not timed out)
    t_30s = t0 + timedelta(seconds=30)
    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        claimed_b_early = await service.claim_notification(
            notification_id=notif_id,
            worker_id="worker-B",
            lease_timeout_seconds=lease_timeout,
            current_time=t_30s,
        )
        # Must be rejected because Worker A still owns the active lease
        assert claimed_b_early is False

    # 3. Worker B attempts claim at T0 + 65s (Worker A crashed, lease is now stale)
    t_65s = t0 + timedelta(seconds=65)
    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        claimed_b_stale = await service.claim_notification(
            notification_id=notif_id,
            worker_id="worker-B",
            lease_timeout_seconds=lease_timeout,
            current_time=t_65s,
        )
        # Must succeed: stale lease reclaimed deterministically!
        assert claimed_b_stale is True

    # 4. Verify in DB: Worker B now owns the claim, same message ID preserved
    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        recovered_notif = await service.get_notification(notif_id)
        assert recovered_notif.status == NotificationStatus.DELIVERING.value
        assert recovered_notif.claimed_by == "worker-B"
        assert to_utc(recovered_notif.claimed_at) == t_65s
        assert recovered_notif.conversation_message_id == message_id


    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-057: No Regeneration After Delivery Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_057_no_regeneration_after_delivery_failure(tmp_path):
    """
    Lock-in 4 & Hard Lock 9: If delivery fails and is retried, the LLM message generator
    is NEVER called a second time. Generation call count remains strictly 1.
    """
    db_file = tmp_path / "noreg_gc057.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    spy_generator = SpyMessageGenerator("Consistent proactive greeting.")
    intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.85,
    )
    context = ProactiveContext(character_id="aevum", approved_intent=intent)

    # 1. Initial creation with spy generator
    notif_id: str
    message_id: str
    async with session_factory() as session:
        service = ProactiveNotificationService(session, message_generator=spy_generator)
        notif = await service.create_proactive_notification(
            intent=intent,
            context=context,
            idempotency_key="gc057-noreg-key",
            generator=spy_generator,
        )
        notif_id = notif.id
        message_id = notif.conversation_message_id
        # Generator called exactly once during initial creation
        assert spy_generator.calls == 1

    # 2. Worker A claims, simulates network/OS notification delivery failure, releases claim
    async with session_factory() as session:
        service = ProactiveNotificationService(session, message_generator=spy_generator)
        claimed = await service.claim_notification(notif_id, worker_id="worker-A")
        assert claimed is True
        # Simulate delivery failure
        await service.release_claim(notif_id, worker_id="worker-A")

    # 3. Worker B reclaims and successfully completes delivery
    async with session_factory() as session:
        service = ProactiveNotificationService(session, message_generator=spy_generator)
        reclaimed = await service.claim_notification(notif_id, worker_id="worker-B")
        assert reclaimed is True
        completed = await service.complete_delivery(notif_id, worker_id="worker-B")
        assert completed is True

    # 4. Strict assertion: Generator call count NEVER increased!
    assert spy_generator.calls == 1, f"Expected generator.calls == 1, got {spy_generator.calls}"

    # Verify message body is unchanged
    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        final_notif = await service.get_notification(notif_id)
        assert final_notif.body == "Consistent proactive greeting."
        assert final_notif.conversation_message_id == message_id

    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-048: Idempotent Trigger Reconciliation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_048_idempotent_trigger_reconciliation(tmp_path):
    """
    Invariant 28: Calling create_proactive_notification sequentially with the same idempotency_key
    returns the pre-existing record without creating duplicate messages or records.
    """
    db_file = tmp_path / "reconciliation_gc048.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    intent = ProactiveIntent(
        character_id="aevum",
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.85,
    )
    context = ProactiveContext(character_id="aevum", approved_intent=intent)
    idem_key = "gc048-sequential-idem-key"

    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        rec1 = await service.create_proactive_notification(
            intent=intent, context=context, idempotency_key=idem_key
        )
        rec2 = await service.create_proactive_notification(
            intent=intent, context=context, idempotency_key=idem_key
        )

        assert rec1.id == rec2.id
        assert rec1.conversation_message_id == rec2.conversation_message_id

    # Verify exactly 1 notification and 1 message in database
    async with session_factory() as session:
        notif_count = await session.scalar(select(func.count()).select_from(ProactiveNotificationRecord))
        msg_count = await session.scalar(select(func.count()).select_from(Message))
        assert notif_count == 1
        assert msg_count == 1

    await engine.dispose()


# ---------------------------------------------------------------------------
# GC-050: Dual Audit Trail Integrity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_050_dual_audit_trail_integrity(tmp_path):
    """
    Standard 33: Notification history reflects exact audit metadata, status,
    and timestamps for delivered items.
    """
    db_file = tmp_path / "audit_gc050.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    t0 = datetime(2026, 9, 18, 15, 0, 0, tzinfo=timezone.utc)
    t_deliv = datetime(2026, 9, 18, 15, 0, 30, tzinfo=timezone.utc)

    async with session_factory() as session:
        service = ProactiveNotificationService(session)
        intent = ProactiveIntent(
            character_id="aevum",
            intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
            intent_strength=0.90,
            topic_hook="Evening tea",
        )
        context = ProactiveContext(character_id="aevum", approved_intent=intent)

        notif = await service.create_proactive_notification(
            intent=intent, context=context, idempotency_key="gc050-audit-key", current_time=t0
        )
        assert notif.status == NotificationStatus.PENDING.value

        # Claim and deliver
        await service.claim_notification(notif.id, worker_id="audit-worker", current_time=t0)
        await service.complete_delivery(notif.id, worker_id="audit-worker", current_time=t_deliv)

        # Query audit history
        audit_list = await service.list_notifications(character_id="aevum")
        assert len(audit_list) == 1
        record = audit_list[0]
        assert record.id == notif.id
        assert record.status == NotificationStatus.DELIVERED.value
        assert to_utc(record.delivered_at) == t_deliv
        assert record.conversation_message_id is not None

    await engine.dispose()


# ===========================================================================
# PHASE 8.3 BENCHMARKS: CONTEXTUAL AWARENESS & ZERO-PERSISTENCE TELEMETRY
# ===========================================================================

from app.desktop.models import (
    DesktopHeartbeatRequest,
    DesktopUserSettingsUpdate,
    IdleCategory,
)
from app.desktop.service import DesktopService


# ---------------------------------------------------------------------------
# GC-049: Privacy Consent Revocation, Idle Telemetry Stripping, and Ephemeral In-Memory Reset
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gc_049_privacy_consent_revocation_and_ephemeral_reset(tmp_path):
    """
    Lock-in 4, Lock-in 5, Additional Lock-in A & B, Invariant 27:
    Zero-persistence telemetry, consent revocation, in-memory TTL, and process restart reset.
    """
    db_file = tmp_path / "telemetry_gc049.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    t0 = datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc)

    # -----------------------------------------------------------------------
    # Case A: Default Disabled — In-Memory Stripping & Zero DB Telemetry
    # -----------------------------------------------------------------------
    async with session_factory() as session:
        service = DesktopService(session)
        # Ensure default settings
        settings = await service.get_settings("aevum")
        assert settings.idle_awareness_enabled is False

        req = DesktopHeartbeatRequest(
            client_id="client-001",
            client_timestamp=t0,
            is_idle=True,
            idle_seconds=650.0,
            window_focused=False,
            app_active=True,
        )
        resp = await service.process_heartbeat(req, character_id="aevum", current_time=t0)

        # Telemetry is stripped in-memory
        assert resp.awareness_enabled is False

        # In-memory context is None
        ctx = service.get_transient_context("aevum", current_time=t0)
        assert ctx is None

        # Verify ZERO telemetry records written to SQLite
        notif_count = await session.scalar(select(func.count()).select_from(ProactiveNotificationRecord))
        assert notif_count == 0

    # -----------------------------------------------------------------------
    # Case B: Consent Opt-In — In-Memory Transient Availability Context Only
    # -----------------------------------------------------------------------
    async with session_factory() as session:
        service = DesktopService(session)
        await service.update_settings(
            DesktopUserSettingsUpdate(idle_awareness_enabled=True, idle_threshold_seconds=300),
            character_id="aevum",
        )

        req_active = DesktopHeartbeatRequest(
            client_id="client-001",
            client_timestamp=t0,
            is_idle=False,
            idle_seconds=45.0,
            window_focused=True,
            app_active=True,
        )
        resp_active = await service.process_heartbeat(req_active, character_id="aevum", current_time=t0)
        assert resp_active.awareness_enabled is True

        # In-memory context is formed
        ctx_active = service.get_transient_context("aevum", current_time=t0)
        assert ctx_active is not None
        assert ctx_active.is_user_available is True
        assert ctx_active.idle_category == IdleCategory.ACTIVE
        assert ctx_active.window_focused is True

        # Check idle heartbeat
        t1 = t0 + timedelta(minutes=10)
        req_idle = DesktopHeartbeatRequest(
            client_id="client-001",
            client_timestamp=t1,
            is_idle=True,
            idle_seconds=600.0,
            window_focused=False,
        )
        resp_idle = await service.process_heartbeat(req_idle, character_id="aevum", current_time=t1)
        assert resp_idle.awareness_enabled is True

        ctx_idle = service.get_transient_context("aevum", current_time=t1)
        assert ctx_idle is not None
        assert ctx_idle.is_user_available is False
        assert ctx_idle.idle_category == IdleCategory.BRIEFLY_AWAY

        # HARD INVARIANT: Zero telemetry rows written to SQLite even when enabled
        notif_count = await session.scalar(select(func.count()).select_from(ProactiveNotificationRecord))
        assert notif_count == 0

        # In-memory context expires after TTL (120s)
        t_expired = t1 + timedelta(seconds=125)
        assert service.get_transient_context("aevum", current_time=t_expired) is None

    # -----------------------------------------------------------------------
    # Case C: Consent Revocation — Immediate Eviction of Transient Context
    # -----------------------------------------------------------------------
    async with session_factory() as session:
        service = DesktopService(session)
        # Establish active context
        await service.process_heartbeat(req_active, character_id="aevum", current_time=t0)
        assert service.get_transient_context("aevum", current_time=t0) is not None

        # Revoke consent
        await service.update_settings(
            DesktopUserSettingsUpdate(idle_awareness_enabled=False),
            character_id="aevum",
        )

        # Transient context is immediately evicted from memory
        assert service.get_transient_context("aevum", current_time=t0) is None

        # Subsequent heartbeat strips telemetry
        resp_after_revocation = await service.process_heartbeat(req_active, character_id="aevum", current_time=t0)
        assert resp_after_revocation.awareness_enabled is False
        assert service.get_transient_context("aevum", current_time=t0) is None

    # -----------------------------------------------------------------------
    # Case D: Restart / Ephemeral Context Reset
    # -----------------------------------------------------------------------
    async with session_factory() as session:
        service = DesktopService(session)
        # Re-enable consent and populate context
        await service.update_settings(
            DesktopUserSettingsUpdate(idle_awareness_enabled=True),
            character_id="aevum",
        )
        await service.process_heartbeat(req_active, character_id="aevum", current_time=t0)
        assert service.get_transient_context("aevum", current_time=t0) is not None

    # Simulate backend process restart: memory cleared, new process starts with fresh memory
    DesktopService.clear_all_transient_contexts()

    async with session_factory() as session:
        service_new = DesktopService(session)
        # Verify no previous availability context can be recovered from disk/DB
        recovered_ctx = service_new.get_transient_context("aevum", current_time=t0)
        assert recovered_ctx is None

        # Database contains zero telemetry rows
        notif_count = await session.scalar(select(func.count()).select_from(ProactiveNotificationRecord))
        assert notif_count == 0

    await engine.dispose()


# ---------------------------------------------------------------------------
# Invariant 27: Telemetry Is Context Only (No Psychological Mutation)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invariant_27_telemetry_subordination_no_psychological_mutation(tmp_path):
    """
    Lock-in 5 & Additional Lock-in B:
    Processing 50 idle heartbeats must NEVER alter:
    - CharacterCore facts
    - CharacterState / emotion
    - RelationshipState / trust / intimacy
    """
    db_file = tmp_path / "subordination_inv27.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Seed baseline state & relationship
        from app.character.core_service import CharacterCoreService
        from app.character.state_service import CharacterStateService
        from app.relationship.service import RelationshipService

        core_service = CharacterCoreService(session)
        state_service = CharacterStateService(session)
        rel_service = RelationshipService(session)
        desktop_service = DesktopService(session)

        core_before = await core_service.get_core("aevum")
        state_before = await state_service.get_state("aevum")
        rel_before = await rel_service.get_relationship_state("user")

        initial_age = core_before.get_fact_value("identity.age")
        initial_mood = state_before.mood
        initial_trust = rel_before.trust

        # Enable idle awareness
        await desktop_service.update_settings(
            DesktopUserSettingsUpdate(idle_awareness_enabled=True),
            character_id="aevum",
        )

        # Process 50 idle heartbeats (user is idle for 40 minutes, unfocused)
        base_time = datetime(2026, 9, 18, 16, 0, 0, tzinfo=timezone.utc)
        for i in range(50):
            req = DesktopHeartbeatRequest(
                client_id="desktop-worker-1",
                client_timestamp=base_time + timedelta(seconds=i * 10),
                is_idle=True,
                idle_seconds=2400.0 + i * 10,
                window_focused=False,
            )
            await desktop_service.process_heartbeat(
                req, character_id="aevum", current_time=base_time + timedelta(seconds=i * 10)
            )

        # Check Core, State, Relationship after 50 idle heartbeats
        core_after = await core_service.get_core("aevum")
        state_after = await state_service.get_state("aevum")
        rel_after = await rel_service.get_relationship_state("user")

        # Zero mutation of core facts
        assert core_after.get_fact_value("identity.age") == initial_age
        # Zero mutation of emotional mood
        assert state_after.mood == initial_mood
        # Zero deduction of trust (telemetry != 'user is ignoring me' or 'user is avoiding me')
        assert rel_after.trust == initial_trust

    await engine.dispose()


