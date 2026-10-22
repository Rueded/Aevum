"""Unit tests for ReplyLatencyPolicy (Phase 5 §8.6)."""

import pytest
from app.character.latency_policy import ReplyLatencyPolicy


def test_latency_disabled():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="期末考试",
        latency_enabled=False,
    )
    assert delay == 0.0


def test_latency_empty_activity():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity=None,
        latency_enabled=True,
    )
    assert delay == 0.0


def test_latency_academic_focus():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="大学英语上课中",
        latency_enabled=True,
        max_latency_minutes=15,
    )
    assert delay == 180.0


def test_latency_work_and_transit():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="公司开会讨论需求",
        latency_enabled=True,
        max_latency_minutes=15,
    )
    assert delay == 90.0

    delay_transit = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="地铁通勤赶路回家",
        latency_enabled=True,
        max_latency_minutes=15,
    )
    assert delay_transit == 90.0


def test_latency_dining():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="在食堂吃午餐",
        latency_enabled=True,
        max_latency_minutes=15,
    )
    assert delay == 45.0


def test_latency_status_busy_fallback():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="整理房间",
        current_status="BUSY",
        latency_enabled=True,
        max_latency_minutes=15,
    )
    assert delay == 60.0


def test_latency_clamped_by_user_ceiling():
    # 180s would exceed 2 minutes (120s)
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="期末考试",
        latency_enabled=True,
        max_latency_minutes=2,
    )
    assert delay == 120.0


def test_latency_free_time():
    delay = ReplyLatencyPolicy.calculate_delay_seconds(
        current_activity="在沙发上刷视频",
        current_status="ACTIVE",
        latency_enabled=True,
        max_latency_minutes=15,
    )
    assert delay == 0.0
