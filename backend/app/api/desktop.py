"""Desktop Integration REST API (Phase 8.3).

Exposes settings, heartbeat telemetry, DND controls, and notification audit logs.
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

import uuid

from app.db.session import get_db_session
from app.desktop.models import (
    ClaimNotificationRequest,
    CompleteNotificationRequest,
    DesktopAvailabilityContext,
    DesktopHeartbeatRequest,
    DesktopHeartbeatResponse,
    DesktopUserSettingsUpdate,
    InteractNotificationRequest,
    NotificationItemResponse,
    ReleaseNotificationRequest,
    SetDNDRequest,
)
from app.desktop.service import DesktopService
from app.proactive.models import (
    NotificationStatus,
    ProactiveContext,
    ProactiveIntent,
    ProactiveIntentType,
    SuppressionReason,
)
from app.proactive.notification_service import ProactiveNotificationService

router = APIRouter(prefix="/desktop", tags=["Desktop Integration"])


@router.get("/settings", summary="Get desktop user settings and privacy configuration")
async def get_settings(
    character_id: str = "aevum",
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve user desktop integration settings."""
    service = DesktopService(session)
    record = await service.get_settings(character_id)
    return {
        "character_id": record.character_id,
        "proactive_enabled": record.proactive_enabled,
        "timezone": record.timezone,
        "quiet_hours_enabled": record.quiet_hours_enabled,
        "quiet_hours_start": record.quiet_hours_start,
        "quiet_hours_end": record.quiet_hours_end,
        "max_daily_reach_outs": record.max_daily_reach_outs,
        "min_cooldown_minutes": record.min_cooldown_minutes,
        "idle_awareness_enabled": record.idle_awareness_enabled,
        "idle_threshold_seconds": record.idle_threshold_seconds,
        "user_country": getattr(record, "user_country", "MY"),
        "sleep_realism_enabled": getattr(record, "sleep_realism_enabled", True),
        "dnd_until": record.dnd_until.isoformat() if record.dnd_until else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@router.patch("/settings", summary="Update desktop user settings and privacy configuration")
async def update_settings(
    updates: DesktopUserSettingsUpdate,
    character_id: str = "aevum",
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Update user desktop settings. Disabling idle awareness immediately clears telemetry."""
    service = DesktopService(session)
    record = await service.update_settings(updates, character_id=character_id)
    return {
        "status": "success",
        "character_id": record.character_id,
        "proactive_enabled": record.proactive_enabled,
        "timezone": record.timezone,
        "quiet_hours_enabled": record.quiet_hours_enabled,
        "quiet_hours_start": record.quiet_hours_start,
        "quiet_hours_end": record.quiet_hours_end,
        "max_daily_reach_outs": record.max_daily_reach_outs,
        "min_cooldown_minutes": record.min_cooldown_minutes,
        "idle_awareness_enabled": record.idle_awareness_enabled,
        "idle_threshold_seconds": record.idle_threshold_seconds,
        "user_country": getattr(record, "user_country", "MY"),
        "sleep_realism_enabled": getattr(record, "sleep_realism_enabled", True),
        "dnd_until": record.dnd_until.isoformat() if record.dnd_until else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }



@router.post("/settings/dnd", summary="Set or clear temporary Do-Not-Disturb")
async def set_dnd(
    payload: SetDNDRequest,
    character_id: str = "aevum",
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Activate or clear temporary DND suppressing reach-outs."""
    service = DesktopService(session)
    record = await service.set_dnd(
        duration_minutes=payload.duration_minutes,
        clear=payload.clear,
        character_id=character_id,
    )
    return {
        "status": "success",
        "dnd_until": record.dnd_until.isoformat() if record.dnd_until else None,
    }


@router.post(
    "/heartbeat",
    response_model=DesktopHeartbeatResponse,
    summary="Process periodic client heartbeat (consent-gated, zero-storage)",
)
async def process_heartbeat(
    request: DesktopHeartbeatRequest,
    character_id: str = "aevum",
    session: AsyncSession = Depends(get_db_session),
) -> DesktopHeartbeatResponse:
    """Process periodic desktop client heartbeat with strict privacy boundaries."""
    service = DesktopService(session)
    return await service.process_heartbeat(request, character_id=character_id)


@router.get(
    "/context",
    response_model=Optional[DesktopAvailabilityContext],
    summary="Get current transient in-memory desktop availability context",
)
async def get_transient_context(
    character_id: str = "aevum",
) -> Optional[DesktopAvailabilityContext]:
    """Retrieve current in-memory transient context (memory-only, null if expired or disabled)."""
    return DesktopService.get_transient_context(character_id=character_id)


@router.get("/notifications/history", summary="Query proactive notification audit history")
async def get_notification_history(
    character_id: str = "aevum",
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve dual audit trail of proactive candidates (DELIVERED and SUPPRESSED)."""
    service = DesktopService(session)
    records = await service.get_audit_history(character_id=character_id, limit=limit)
    return [
        {
            "id": r.id,
            "character_id": r.character_id,
            "conversation_message_id": r.conversation_message_id,
            "trigger_type": r.trigger_type,
            "idempotency_key": r.idempotency_key,
            "title": r.title,
            "body": r.body,
            "status": r.status,
            "claimed_by": r.claimed_by,
            "claimed_at": r.claimed_at.isoformat() if r.claimed_at else None,
            "suppression_reason": r.suppression_reason,
            "created_at": r.created_at.isoformat(),
            "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
            "interacted_at": r.interacted_at.isoformat() if r.interacted_at else None,
        }
        for r in records
    ]


@router.get(
    "/notifications/pending",
    response_model=list[NotificationItemResponse],
    summary="List pending notifications eligible for delivery (<=24h)",
)
async def list_pending_notifications(
    character_id: str = "aevum",
    session: AsyncSession = Depends(get_db_session),
) -> list[NotificationItemResponse]:
    """Retrieve all pending notifications for a character that have not expired (<=24h)."""
    service = ProactiveNotificationService(session)
    records = await service.list_pending_notifications(character_id=character_id)
    return [NotificationItemResponse.model_validate(r) for r in records]


@router.get(
    "/notifications/{notification_id}",
    response_model=NotificationItemResponse,
    summary="Get single notification record by ID",
)
async def get_notification_by_id(
    notification_id: str,
    character_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> NotificationItemResponse:
    """Retrieve a single proactive notification by ID with character ownership verification."""
    service = ProactiveNotificationService(session)
    record = await service.get_notification(notification_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    if character_id is not None and record.character_id != character_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Notification '{notification_id}' does not belong to character '{character_id}'.",
        )
    return NotificationItemResponse.model_validate(record)


@router.post(
    "/notifications/{notification_id}/claim",
    response_model=dict[str, Any],
    summary="Claim a pending notification lease for delivery",
)
async def claim_notification_lease(
    notification_id: str,
    payload: ClaimNotificationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Atomically claim delivery lease for a pending notification.

    24h Expiration Invariant:
    - If notification age > 24h, automatically transitions to SUPPRESSED (reason: EXPIRED)
      and returns 409 Conflict.
    """
    service = ProactiveNotificationService(session)
    record = await service.get_notification(notification_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    if record.character_id != payload.character_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Notification '{notification_id}' does not belong to character '{payload.character_id}'.",
        )

    # Attempt claim (handles 24h expiration check inside service atomically)
    claimed = await service.claim_notification(
        notification_id=notification_id,
        worker_id=payload.worker_id,
        lease_timeout_seconds=payload.lease_timeout_seconds,
    )

    if not claimed:
        refreshed = await service.get_notification(notification_id)
        if (
            refreshed
            and refreshed.status == NotificationStatus.SUPPRESSED.value
            and refreshed.suppression_reason == SuppressionReason.EXPIRED.value
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Notification has expired (>24h) and was suppressed.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Notification '{notification_id}' could not be claimed (already claimed, delivered, or suppressed).",
        )

    updated = await service.get_notification(notification_id)
    return {
        "status": "DELIVERING",
        "claimed": True,
        "notification_id": notification_id,
        "claimed_by": payload.worker_id,
        "claimed_at": updated.claimed_at.isoformat() if updated and updated.claimed_at else None,
    }


@router.post(
    "/notifications/{notification_id}/complete",
    response_model=dict[str, Any],
    summary="Mark delivering notification as successfully delivered",
)
async def complete_notification_delivery(
    notification_id: str,
    payload: CompleteNotificationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Complete delivery of a claimed notification.
    Idempotent: If already DELIVERED, returns success.
    """
    service = ProactiveNotificationService(session)
    record = await service.get_notification(notification_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    if record.character_id != payload.character_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Notification '{notification_id}' does not belong to character '{payload.character_id}'.",
        )

    # Idempotent success if already DELIVERED
    if record.status == NotificationStatus.DELIVERED.value:
        return {
            "status": "DELIVERED",
            "completed": True,
            "notification_id": notification_id,
            "delivered_at": record.delivered_at.isoformat() if record.delivered_at else None,
        }

    if record.status != NotificationStatus.DELIVERING.value or record.claimed_by != payload.worker_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete notification '{notification_id}': status is '{record.status}' (expected DELIVERING), claimed_by is '{record.claimed_by}' (expected '{payload.worker_id}').",
        )

    completed = await service.complete_delivery(
        notification_id=notification_id,
        worker_id=payload.worker_id,
    )
    if not completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Failed to complete notification delivery for '{notification_id}'.",
        )

    updated = await service.get_notification(notification_id)
    return {
        "status": "DELIVERED",
        "completed": True,
        "notification_id": notification_id,
        "delivered_at": updated.delivered_at.isoformat() if updated and updated.delivered_at else None,
    }


@router.post(
    "/notifications/{notification_id}/release",
    response_model=dict[str, Any],
    summary="Release delivering claim back to pending",
)
async def release_notification_claim(
    notification_id: str,
    payload: ReleaseNotificationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Release an active claim back to PENDING on recoverable dispatch failure.
    Idempotent: If already PENDING, returns success.
    """
    service = ProactiveNotificationService(session)
    record = await service.get_notification(notification_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    if record.character_id != payload.character_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Notification '{notification_id}' does not belong to character '{payload.character_id}'.",
        )

    # Idempotent if already PENDING
    if record.status == NotificationStatus.PENDING.value:
        return {
            "status": "PENDING",
            "released": True,
            "notification_id": notification_id,
        }

    if record.status != NotificationStatus.DELIVERING.value or record.claimed_by != payload.worker_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot release notification '{notification_id}': status is '{record.status}', claimed_by is '{record.claimed_by}'.",
        )

    released = await service.release_claim(
        notification_id=notification_id,
        worker_id=payload.worker_id,
    )
    if not released:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Failed to release notification claim for '{notification_id}'.",
        )

    return {
        "status": "PENDING",
        "released": True,
        "notification_id": notification_id,
    }


@router.post(
    "/notifications/{notification_id}/interact",
    response_model=dict[str, Any],
    summary="Record user interaction (CLICKED or DISMISSED)",
)
async def interact_with_notification(
    notification_id: str,
    payload: InteractNotificationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Record user click or dismissal of a delivered notification.
    Idempotent: Re-interacting with the same action returns success.
    """
    service = ProactiveNotificationService(session)
    record = await service.get_notification(notification_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    if record.character_id != payload.character_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Notification '{notification_id}' does not belong to character '{payload.character_id}'.",
        )

    action_norm = payload.action.strip().upper()
    if action_norm not in ("CLICKED", "DISMISSED"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid action '{payload.action}'. Must be 'CLICKED' or 'DISMISSED'.",
        )

    success, err = await service.interact_notification(
        notification_id=notification_id,
        action=action_norm,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err or "Failed to record notification interaction.",
        )

    updated = await service.get_notification(notification_id)
    return {
        "status": action_norm,
        "interacted": True,
        "notification_id": notification_id,
        "conversation_message_id": updated.conversation_message_id if updated else record.conversation_message_id,
        "interacted_at": updated.interacted_at.isoformat() if updated and updated.interacted_at else None,
    }


@router.post(
    "/proactive/trigger-test",
    response_model=dict[str, Any],
    summary="Trigger a test proactive reach-out notification",
)
async def trigger_proactive_test(
    character_id: str = "aevum",
    conversation_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Force-trigger a proactive reach-out notification for live interactive testing."""
    service = ProactiveNotificationService(session)
    intent = ProactiveIntent(
        character_id=character_id,
        intent_type=ProactiveIntentType.SHARE_EXPERIENCE,
        intent_strength=0.85,
        topic_hook="想知道你现在在忙些什么",
        grounding_activity_title="刚刚画完一幅插画草稿，伸了个懒腰",
    )
    context = ProactiveContext(
        approved_intent=intent,
        character_id=character_id,
        current_activity="画室休息中",
    )
    idempotency_key = f"manual-test-{uuid.uuid4()}"
    notif = await service.create_proactive_notification(
        intent=intent,
        context=context,
        idempotency_key=idempotency_key,
        conversation_id=conversation_id,
        title="晚晚发来了新消息",
    )
    await session.commit()
    return {
        "status": "success",
        "notification_id": notif.id,
        "title": notif.title,
        "body": notif.body,
        "conversation_message_id": notif.conversation_message_id,
    }

