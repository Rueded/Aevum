"""Dynamic Reply Latency Policy for Project Aevum (Phase 5 §8.6).

Governed by AEVUM_HUMANLIKE_REFACTOR_BRIEF §8.6:
- Calculates realistic conversational reply delay based on character's current activity and physiological status.
- Gentle, natural defaults:
  * In class, exam, academic lecture: 3-8 minutes delay
  * Busy with work, meeting, commute, transport: 1-3 minutes delay
  * Eating, dining, cooking, quick chores: 30-90 seconds delay
  * Free, relaxing, slacking, chatting: 0-5 seconds delay
- Clamped by user-configured maximum delay (default 15 minutes).
- Disabled when reply_latency_enabled is False (instant reply).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ReplyLatencyPolicy:
    """Calculates realistic reply delays reflecting independent character life."""

    @classmethod
    def calculate_delay_seconds(
        cls,
        current_activity: Optional[str],
        current_status: Optional[str] = None,
        max_latency_minutes: int = 15,
        latency_enabled: bool = False,
    ) -> float:
        """Calculate recommended reply delay in seconds.
        
        Returns 0.0 if latency is disabled or activity permits instant replies.
        """
        if not latency_enabled or not current_activity:
            return 0.0

        act_lower = current_activity.lower()

        # 1. High-focus academic or professional engagement: 3-8 minutes
        if any(k in act_lower for k in ("上课", "class", "lecture", "考试", "exam", "合奏", "rehearsal")):
            delay = 180.0
        # 2. Busy with transit, meeting, work: 1-3 minutes
        elif any(k in act_lower for k in ("工作", "work", "开会", "meeting", "赶路", "通勤", "地铁", "巴士", "mrt", "lrt", "开车")):
            delay = 90.0
        # 3. Eating, dining, grooming: 30-90 seconds
        elif any(k in act_lower for k in ("吃饭", "用餐", "午市", "晚餐", "午餐", "早餐", "宵夜", "做饭", "洗澡", "收拾")):
            delay = 45.0
        # 4. Status-based fallback
        elif current_status == "BUSY":
            delay = 60.0
        else:
            delay = 0.0

        max_allowed_sec = float(max_latency_minutes * 60)
        final_delay = min(delay, max_allowed_sec)
        logger.debug(
            "ReplyLatencyPolicy: activity='%s', status='%s', calculated delay=%.1fs (max=%dm)",
            current_activity,
            current_status,
            final_delay,
            max_latency_minutes,
        )
        return final_delay
