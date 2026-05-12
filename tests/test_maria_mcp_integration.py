"""maria_mcp 통합 테스트 — 실제 MariaDB에 연결해 5개 tool을 검증."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from maria_mcp import tools
from maria_mcp.models import AlarmDetail, AlarmSummary, DeviceInfo


pytestmark = pytest.mark.asyncio


async def test_get_device_info(sample_device: dict[str, int]) -> None:
    result = await tools.get_device_info(
        sample_device["data_center_id"], sample_device["device_id"]
    )
    assert result is not None
    assert isinstance(result, DeviceInfo)
    assert result.data_center_id == sample_device["data_center_id"]
    assert result.device_id == sample_device["device_id"]


async def test_get_device_info_not_found(_pool: Any) -> None:
    result = await tools.get_device_info(data_center_id=-1, device_id=-1)
    assert result is None


async def test_get_alarm_detail(sample_alarm: dict[str, Any]) -> None:
    result = await tools.get_alarm_detail(
        sample_alarm["data_center_id"], sample_alarm["id"]
    )
    assert result is not None
    assert isinstance(result, AlarmDetail)
    assert result.alarm_id == sample_alarm["id"]


async def test_get_alarm_detail_not_found(sample_alarm: dict[str, Any]) -> None:
    # sample_alarm 은 _pool 에 이미 의존하므로 추가 선언 불필요
    result = await tools.get_alarm_detail(
        sample_alarm["data_center_id"], alarm_id=-1
    )
    assert result is None


async def test_get_active_alarms(sample_alarm: dict[str, Any]) -> None:
    result = await tools.get_active_alarms(
        sample_alarm["data_center_id"], limit=5
    )
    assert isinstance(result, list)
    assert len(result) <= 5
    for a in result:
        assert isinstance(a, AlarmSummary)


async def test_get_active_alarms_limit_clamped(sample_alarm: dict[str, Any]) -> None:
    """limit 100 초과 시 100으로 클램프 — 에러 없이 동작 확인."""
    result = await tools.get_active_alarms(
        sample_alarm["data_center_id"], limit=999
    )
    assert isinstance(result, list)
    assert len(result) <= 100


async def test_get_active_alarms_severity_filter(sample_alarm: dict[str, Any]) -> None:
    """존재하지 않는 severity 필터 시 빈 리스트 반환 확인."""
    result = await tools.get_active_alarms(
        sample_alarm["data_center_id"],
        severity="__nonexistent_severity__",
        limit=10,
    )
    assert isinstance(result, list)
    assert result == [], "존재하지 않는 severity 필터는 빈 리스트를 반환해야 한다"


async def test_get_active_alarms_severity_filter_all_match(sample_alarm: dict[str, Any]) -> None:
    """severity=None(기본값)이면 필터 없이 전체 조회."""
    result_no_filter = await tools.get_active_alarms(
        sample_alarm["data_center_id"], severity=None, limit=20
    )
    assert isinstance(result_no_filter, list)
    # severity 필터 없는 결과는 severity 결과 합 이상이어야 함
    severities = {a.severity for a in result_no_filter if a.severity is not None}
    for sev in severities:
        result_filtered = await tools.get_active_alarms(
            sample_alarm["data_center_id"], severity=sev, limit=20
        )
        assert all(a.severity == sev for a in result_filtered), (
            f"severity={sev} 필터 결과에 다른 severity 값이 섞여서는 안 된다"
        )


async def test_get_alarms_by_time(sample_alarm: dict[str, Any]) -> None:
    from datetime import timezone

    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=30)
    result = await tools.get_alarms_by_time(
        sample_alarm["data_center_id"], start, end, limit=10
    )
    assert isinstance(result, list)
    assert len(result) <= 10
    for a in result:
        assert isinstance(a, AlarmSummary)
        if a.log_date is not None:
            # DB 반환값이 naive datetime 일 경우를 대비해 timezone-aware 로 통일
            log_date = a.log_date
            if log_date.tzinfo is None:
                log_date = log_date.replace(tzinfo=timezone.utc)
            assert start <= log_date < end


async def test_get_device_alarms(sample_alarm: dict[str, Any]) -> None:
    if sample_alarm["device_id"] is None:
        pytest.skip("샘플 알람의 device_id가 NULL")
    result = await tools.get_device_alarms(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        hours=720,  # 30일
        limit=10,
    )
    assert isinstance(result, list)
    assert len(result) <= 10
    for a in result:
        assert isinstance(a, AlarmSummary)
        assert a.device_id == sample_alarm["device_id"]
