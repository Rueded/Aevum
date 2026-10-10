"""Proactive Notification Service (Phase 8.2).

Governs the lifecycle of ProactiveNotificationRecord:
- Mandatory canonical conversation message binding (Lock-in 2 & 7)
- Atomic delivery claim with crash recovery lease (Standard 35 & Lock-in 2, 8)
- Stable message identity preventing re-generation on failure (Lock-in 4, 9)
- Zero global asyncio.Lock: concurrency safety via database conditional atomic updates.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import uuid

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, ProactiveNotificationRecord
from app.life.clock import RealTimeClock, SimulationClock
from app.proactive.message_generator import ProactiveMessageGenerator
from app.proactive.models import (
    NotificationStatus,
    ProactiveContext,
    ProactiveIntent,
    SuppressionReason,
)

logger = logging.getLogger(__name__)


class ProactiveNotificationService:
    """Service managing proactive reach-out notification creation, claim, and delivery."""

    DEFAULT_LEASE_TIMEOUT_SECONDS: float = 60.0
    MAX_NOTIFICATION_AGE_SECONDS: float = 86400.0  # 24 hours exact threshold

    def __init__(
        self,
        session: AsyncSession,
        clock: Optional[SimulationClock] = None,
        message_generator: Optional[ProactiveMessageGenerator] = None,
    ) -> None:
        self.session = session
        self.clock = clock or RealTimeClock()
        self.message_generator = message_generator or ProactiveMessageGenerator()

    async def get_or_create_default_conversation(self) -> Conversation:
        """Find the active conversation or create one if none exists."""
        stmt = select(Conversation).order_by(Conversation.updated_at.desc()).limit(1)
        conv = (await self.session.scalars(stmt)).first()
        if conv is None:
            conv = Conversation(
                id=str(uuid.uuid4()),
                created_at=self.clock.now(),
                updated_at=self.clock.now(),
            )
            self.session.add(conv)
            await self.session.flush()
        return conv

    async def get_notification(self, notification_id: str) -> Optional[ProactiveNotificationRecord]:
        """Fetch a notification record by primary key."""
        stmt = (
            select(ProactiveNotificationRecord)
            .where(ProactiveNotificationRecord.id == notification_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).first()

    async def get_notification_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[ProactiveNotificationRecord]:
        """Fetch a notification record by its unique idempotency key."""
        stmt = (
            select(ProactiveNotificationRecord)
            .where(ProactiveNotificationRecord.idempotency_key == idempotency_key)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).first()

    async def create_proactive_notification(
        self,
        intent: ProactiveIntent,
        context: ProactiveContext,
        idempotency_key: str,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
        generator: Optional[ProactiveMessageGenerator] = None,
        current_time: Optional[datetime] = None,
    ) -> ProactiveNotificationRecord:
        """
        Create and persist a canonical ConversationMessage and bound ProactiveNotificationRecord.

        Hard Invariants:
        - Lock-in 2 & 7: conversation_message_id is NOT NULL and references an existing canonical message.
        - Lock-in 11 & 12: LLM generation occurs before DB transaction; message and notification persist atomically.
        - Lock-in 5: Concurrent duplicate creation with the same idempotency_key yields exactly one record.
        """
        # 1. Idempotency pre-check
        existing = await self.get_notification_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        # 2. Generate proactive dialogue content bounded by ProactiveContext
        gen = generator or self.message_generator
        message_text = await gen.generate_proactive_message(context)

        # 3. Resolve target conversation
        target_conv_id: str
        if conversation_id is not None:
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv = (await self.session.scalars(conv_stmt)).first()
            if conv is None:
                raise ValueError(f"Conversation '{conversation_id}' not found.")
            target_conv_id = conv.id
        else:
            default_conv = await self.get_or_create_default_conversation()
            target_conv_id = default_conv.id

        now = current_time or self.clock.now()

        # 4. Short atomic database transaction
        message = Message(
            id=str(uuid.uuid4()),
            conversation_id=target_conv_id,
            role="assistant",
            content=message_text,
            created_at=now,
        )
        self.session.add(message)
        await self.session.flush()

        # Enforce Hard Invariant 2 & 7: mandatory message binding
        if not message.id:
            raise RuntimeError("Failed to generate canonical message identity.")

        notification = ProactiveNotificationRecord(
            id=str(uuid.uuid4()),
            character_id=intent.character_id,
            conversation_message_id=message.id,
            trigger_type=intent.intent_type.value,
            idempotency_key=idempotency_key,
            title=title or f"Aevum — {intent.topic_hook or 'New message'}",
            body=message_text,
            status=NotificationStatus.PENDING.value,
            claimed_by=None,
            claimed_at=None,
            suppression_reason=None,
            context_metadata=None,
            created_at=now,
        )
        self.session.add(notification)

        try:
            await self.session.commit()
            await self.session.refresh(notification)
            return notification
        except IntegrityError:
            # Concurrent race condition on unique idempotency_key: rollback and return winner
            await self.session.rollback()
            winner = await self.get_notification_by_idempotency_key(idempotency_key)
            if winner is not None:
                return winner
            raise

    async def claim_notification(
        self,
        notification_id: str,
        worker_id: str,
        lease_timeout_seconds: Optional[float] = None,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Atomically claim a PENDING notification or reclaim an expired DELIVERING lease.

        Phase 8.4 24h Expiration Invariant:
        - If notification age > 24 hours (86400.0s), PENDING transitions to SUPPRESSED with
          suppression_reason = "EXPIRED". Claim returns False.
        - Boundary rule:
          - age < 86400.0s  -> eligible
          - age == 86400.0s -> eligible (inclusive upper bound)
          - age > 86400.0s  -> SUPPRESSED / EXPIRED
        - Standard 35 & Lock-in 2, 6, 8:
          - Winner determined strictly by database rowcount == 1.
          - Stale lease recovery: claimed_at < (now - lease_timeout) enables safe re-claim.
          - Zero global asyncio.Lock.
        """
        now = current_time or self.clock.now()
        now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)

        # 1. 24h Expiration Check
        record = await self.get_notification(notification_id)
        if record is None:
            return False

        created_utc = (
            record.created_at
            if record.created_at.tzinfo is not None
            else record.created_at.replace(tzinfo=timezone.utc)
        )
        age_seconds = (now_utc - created_utc).total_seconds()

        if age_seconds > self.MAX_NOTIFICATION_AGE_SECONDS:
            if record.status == NotificationStatus.PENDING.value:
                logger.info(
                    "Notification %s expired (age=%.1fs > 86400s). Transitioning PENDING -> SUPPRESSED (EXPIRED).",
                    notification_id,
                    age_seconds,
                )
                suppress_stmt = (
                    update(ProactiveNotificationRecord)
                    .where(
                        ProactiveNotificationRecord.id == notification_id,
                        ProactiveNotificationRecord.status == NotificationStatus.PENDING.value,
                    )
                    .values(
                        status=NotificationStatus.SUPPRESSED.value,
                        suppression_reason=SuppressionReason.EXPIRED.value,
                    )
                    .execution_options(synchronize_session=False)
                )
                await self.session.execute(suppress_stmt)
                await self.session.commit()
            return False

        # 2. Atomic Lease Claim
        timeout = (
            lease_timeout_seconds
            if lease_timeout_seconds is not None
            else self.DEFAULT_LEASE_TIMEOUT_SECONDS
        )
        lease_cutoff = now_utc - timedelta(seconds=timeout)

        stmt = (
            update(ProactiveNotificationRecord)
            .where(
                ProactiveNotificationRecord.id == notification_id,
                or_(
                    ProactiveNotificationRecord.status == NotificationStatus.PENDING.value,
                    and_(
                        ProactiveNotificationRecord.status == NotificationStatus.DELIVERING.value,
                        ProactiveNotificationRecord.claimed_at < lease_cutoff,
                    ),
                ),
            )
            .values(
                status=NotificationStatus.DELIVERING.value,
                claimed_by=worker_id,
                claimed_at=now_utc,
            )
            .execution_options(synchronize_session=False)
        )

        res = await self.session.execute(stmt)
        if res.rowcount == 1:
            await self.session.commit()
            return True
        else:
            await self.session.rollback()
            return False

    async def complete_delivery(
        self,
        notification_id: str,
        worker_id: str,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Transition DELIVERING notification to DELIVERED.

        Lock-in 9: DELIVERED status consumes daily quota.
        """
        now = current_time or self.clock.now()
        now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        stmt = (
            update(ProactiveNotificationRecord)
            .where(
                ProactiveNotificationRecord.id == notification_id,
                ProactiveNotificationRecord.status == NotificationStatus.DELIVERING.value,
                ProactiveNotificationRecord.claimed_by == worker_id,
            )
            .values(
                status=NotificationStatus.DELIVERED.value,
                delivered_at=now_utc,
            )
            .execution_options(synchronize_session=False)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 1:
            await self.session.commit()
            return True
        else:
            await self.session.rollback()
            return False

    async def release_claim(
        self,
        notification_id: str,
        worker_id: str,
    ) -> bool:
        """
        Release a delivery claim back to PENDING on recoverable dispatch failure.

        Lock-in 4 & 11: Retains the same conversation_message_id; zero regeneration.
        """
        stmt = (
            update(ProactiveNotificationRecord)
            .where(
                ProactiveNotificationRecord.id == notification_id,
                ProactiveNotificationRecord.status == NotificationStatus.DELIVERING.value,
                ProactiveNotificationRecord.claimed_by == worker_id,
            )
            .values(
                status=NotificationStatus.PENDING.value,
                claimed_by=None,
                claimed_at=None,
            )
            .execution_options(synchronize_session=False)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 1:
            await self.session.commit()
            return True
        else:
            await self.session.rollback()
            return False

    async def interact_notification(
        self,
        notification_id: str,
        action: str,
        current_time: Optional[datetime] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Record user interaction (CLICKED or DISMISSED) with a notification.

        Returns (success, error_detail).
        Idempotent: Re-interacting with the same action returns (True, None).
        """
        now = current_time or self.clock.now()
        now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)

        record = await self.get_notification(notification_id)
        if record is None:
            return False, "Notification not found"

        action_norm = action.strip().upper()
        if action_norm not in (NotificationStatus.CLICKED.value, NotificationStatus.DISMISSED.value):
            return False, f"Invalid interaction action '{action}'. Must be CLICKED or DISMISSED."

        # Idempotent return
        if record.status == action_norm:
            return True, None

        if record.status not in (NotificationStatus.DELIVERED.value, NotificationStatus.DELIVERING.value):
            return False, f"Cannot interact with notification in status '{record.status}'"

        stmt = (
            update(ProactiveNotificationRecord)
            .where(
                ProactiveNotificationRecord.id == notification_id,
                or_(
                    ProactiveNotificationRecord.status == NotificationStatus.DELIVERED.value,
                    ProactiveNotificationRecord.status == NotificationStatus.DELIVERING.value,
                ),
            )
            .values(
                status=action_norm,
                interacted_at=now_utc,
            )
            .execution_options(synchronize_session=False)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 1:
            await self.session.commit()
            return True, None
        else:
            await self.session.rollback()
            return False, "Failed to update notification interaction state"

    async def list_pending_notifications(
        self, character_id: str = "aevum", current_time: Optional[datetime] = None
    ) -> list[ProactiveNotificationRecord]:
        """Retrieve all PENDING notifications for a character that are not expired (<=24h), ordered chronologically."""
        now = current_time or self.clock.now()
        now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        cutoff_24h = now_utc - timedelta(seconds=self.MAX_NOTIFICATION_AGE_SECONDS)

        # Proactively suppress any expired pending notifications (>24h) only if they exist
        try:
            has_expired_stmt = (
                select(func.count())
                .select_from(ProactiveNotificationRecord)
                .where(
                    ProactiveNotificationRecord.character_id == character_id,
                    ProactiveNotificationRecord.status == NotificationStatus.PENDING.value,
                    ProactiveNotificationRecord.created_at < cutoff_24h,
                )
            )
            expired_count = (await self.session.scalar(has_expired_stmt)) or 0
            if expired_count > 0:
                expired_stmt = (
                    update(ProactiveNotificationRecord)
                    .where(
                        ProactiveNotificationRecord.character_id == character_id,
                        ProactiveNotificationRecord.status == NotificationStatus.PENDING.value,
                        ProactiveNotificationRecord.created_at < cutoff_24h,
                    )
                    .values(
                        status=NotificationStatus.SUPPRESSED.value,
                        suppression_reason=SuppressionReason.EXPIRED.value,
                    )
                    .execution_options(synchronize_session=False)
                )
                await self.session.execute(expired_stmt)
                await self.session.commit()
        except Exception as exc:
            logger.warning("Failed to auto-suppress expired notifications during read poll: %s", exc)

        stmt = (
            select(ProactiveNotificationRecord)
            .where(
                ProactiveNotificationRecord.character_id == character_id,
                ProactiveNotificationRecord.status == NotificationStatus.PENDING.value,
                ProactiveNotificationRecord.created_at >= cutoff_24h,
            )
            .order_by(ProactiveNotificationRecord.created_at.asc())
            .execution_options(populate_existing=True)
        )
        return list((await self.session.scalars(stmt)).all())

    async def list_notifications(
        self, character_id: str = "aevum", limit: int = 50
    ) -> list[ProactiveNotificationRecord]:
        """Retrieve audit log of notifications ordered newest first."""
        stmt = (
            select(ProactiveNotificationRecord)
            .where(ProactiveNotificationRecord.character_id == character_id)
            .order_by(ProactiveNotificationRecord.created_at.desc())
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        return list((await self.session.scalars(stmt)).all())
