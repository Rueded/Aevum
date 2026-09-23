"""Desktop integration package (Phase 8)."""

from app.desktop.models import (
    DesktopAvailabilityContext,
    DesktopHeartbeatRequest,
    DesktopHeartbeatResponse,
    DesktopUserSettingsUpdate,
    IdleCategory,
    SetDNDRequest,
)
from app.desktop.service import DesktopService

__all__ = [
    "DesktopAvailabilityContext",
    "DesktopHeartbeatRequest",
    "DesktopHeartbeatResponse",
    "DesktopService",
    "DesktopUserSettingsUpdate",
    "IdleCategory",
    "SetDNDRequest",
]
