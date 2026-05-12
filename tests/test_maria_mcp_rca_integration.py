"""maria_mcp RCA 확장 tool 통합 테스트 — 실제 MariaDB에 연결해 7개 신규 tool 검증.

각 테스트는 conftest.py 의 _pool / sample_device / sample_alarm fixture 에 의존한다.
DB가 도달 불가능하거나 테이블이 비어 있으면 해당 테스트는 자동으로 skip 된다.
"""

from __future__ import annotations

from typing import Any

import pytest

from maria_mcp import db, tools
from maria_mcp.models import AlarmSummary, AlarmSummaryStats, DeviceSummary


pytestmark = pytest.mark.asyncio


# ── list_nearby_devices ───────────────────────────────────────────────────────

async def test_list_nearby_devices_returns_list(sample_device: dict[str, int]) -> None:
    """list_nearby_devices: 결과는 DeviceSummary 리스트여야 한다."""
    result = await tools.list_nearby_devices(
        sample_device["data_center_id"],
        sample_device["device_id"],
        limit=5,
    )
    assert isinstance(result, list)
    assert len(result) <= 5
    for item in result:
        assert isinstance(item, DeviceSummary)


async def test_list_nearby_devices_excludes_self(sample_device: dict[str, int]) -> None:
    """list_nearby_devices: 기준 장비 자신은 결과에 포함되지 않아야 한다."""
    result = await tools.list_nearby_devices(
        sample_device["data_center_id"],
        sample_device["device_id"],
        limit=50,
    )
    device_ids = [d.device_id for d in result]
    assert sample_device["device_id"] not in device_ids, (
        "기준 장비 자신(device_id)이 목록에 포함되어서는 안 된다"
    )


async def test_list_nearby_devices_limit_clamped(sample_device: dict[str, int]) -> None:
    """list_nearby_devices: limit 50 초과 시 50으로 클램프 — 에러 없이 동작."""
    result = await tools.list_nearby_devices(
        sample_device["data_center_id"],
        sample_device["device_id"],
        limit=999,
    )
    assert isinstance(result, list)
    assert len(result) <= 50


async def test_list_nearby_devices_nonexistent_device(_pool: Any) -> None:
    """list_nearby_devices: 존재하지 않는 device_id 는 빈 리스트 반환."""
    result = await tools.list_nearby_devices(
        data_center_id=-1,
        device_id=-1,
        limit=10,
    )
    assert result == []


# ── list_devices_by_type ──────────────────────────────────────────────────────

async def test_list_devices_by_type_both_none(_pool: Any) -> None:
    """list_devices_by_type: category / type 둘 다 None 이면 빈 리스트 반환 (에러 아님)."""
    result = await tools.list_devices_by_type(
        data_center_id=1,
        device_category_name=None,
        device_type_name=None,
    )
    assert result == [], "category / type 둘 다 None 이면 빈 리스트를 반환해야 한다"


async def test_list_devices_by_type_with_category(sample_device: dict[str, int]) -> None:
    """list_devices_by_type: 실제 카테고리명으로 조회 시 DeviceSummary 리스트 반환."""
    # 먼저 sample_device 의 category 를 조회해 필터에 사용
    async with db.cursor() as cur:
        await cur.execute(
            "SELECT device_category_name FROM im_device_inf "
            "WHERE data_center_id=%s AND device_id=%s LIMIT 1",
            (sample_device["data_center_id"], sample_device["device_id"]),
        )
        row = await cur.fetchone()

    if row is None or row.get("device_category_name") is None:
        pytest.skip("샘플 장비의 device_category_name 이 NULL")

    category = row["device_category_name"]
    result = await tools.list_devices_by_type(
        sample_device["data_center_id"],
        device_category_name=category,
        limit=10,
    )
    assert isinstance(result, list)
    assert len(result) <= 10
    for item in result:
        assert isinstance(item, DeviceSummary)
        assert item.device_category_name == category, (
            f"device_category_name 필터({category!r})와 다른 카테고리가 반환되었다: {item.device_category_name!r}"
        )


async def test_list_devices_by_type_nonexistent_returns_empty(_pool: Any) -> None:
    """list_devices_by_type: 존재하지 않는 카테고리명은 빈 리스트 반환."""
    result = await tools.list_devices_by_type(
        data_center_id=1,
        device_category_name="__nonexistent_category__",
    )
    assert result == []


async def test_list_devices_by_type_limit_clamped(_pool: Any) -> None:
    """list_devices_by_type: limit 100 초과 시 100으로 클램프 — 에러 없이 동작."""
    result = await tools.list_devices_by_type(
        data_center_id=1,
        device_category_name="UPS",
        limit=999,
    )
    assert isinstance(result, list)
    assert len(result) <= 100


# ── list_devices_by_ups ───────────────────────────────────────────────────────

async def test_list_devices_by_ups_returns_list(sample_device: dict[str, int]) -> None:
    """list_devices_by_ups: connected_ups 가 있는 장비를 찾아 조회 — DeviceSummary 리스트."""
    async with db.cursor() as cur:
        await cur.execute(
            "SELECT connected_ups FROM im_device_inf "
            "WHERE data_center_id=%s AND connected_ups IS NOT NULL AND use_yn='Y' "
            "LIMIT 1",
            (sample_device["data_center_id"],),
        )
        row = await cur.fetchone()

    if row is None:
        pytest.skip("connected_ups 가 설정된 장비 데이터 없음")

    ups_name: str = row["connected_ups"]
    result = await tools.list_devices_by_ups(
        sample_device["data_center_id"],
        ups_name=ups_name,
        limit=10,
    )
    assert isinstance(result, list)
    assert len(result) <= 10
    for item in result:
        assert isinstance(item, DeviceSummary)


async def test_list_devices_by_ups_nonexistent_ups(_pool: Any) -> None:
    """list_devices_by_ups: 존재하지 않는 UPS 이름은 빈 리스트 반환."""
    result = await tools.list_devices_by_ups(
        data_center_id=1,
        ups_name="__nonexistent_ups__",
    )
    assert result == []


# ── get_alarm_history ─────────────────────────────────────────────────────────

async def test_get_alarm_history_returns_list(sample_alarm: dict[str, Any]) -> None:
    """get_alarm_history: 결과는 AlarmSummary 리스트여야 한다."""
    if sample_alarm.get("device_id") is None:
        pytest.skip("샘플 알람의 device_id 가 NULL")

    result = await tools.get_alarm_history(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        days=90,
        limit=10,
    )
    assert isinstance(result, list)
    assert len(result) <= 10
    for item in result:
        assert isinstance(item, AlarmSummary)


async def test_get_alarm_history_days_clamped(sample_alarm: dict[str, Any]) -> None:
    """get_alarm_history: days 90 초과 시 90으로 클램프 — 에러 없이 동작."""
    if sample_alarm.get("device_id") is None:
        pytest.skip("샘플 알람의 device_id 가 NULL")

    result = await tools.get_alarm_history(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        days=999,
        limit=5,
    )
    assert isinstance(result, list)
    assert len(result) <= 5


async def test_get_alarm_history_nonexistent_device(_pool: Any) -> None:
    """get_alarm_history: 존재하지 않는 device_id 는 빈 리스트 반환."""
    result = await tools.get_alarm_history(
        data_center_id=-1,
        device_id=-1,
        days=30,
    )
    assert result == []


async def test_get_alarm_history_has_closed_date(sample_alarm: dict[str, Any]) -> None:
    """get_alarm_history: AlarmSummary 의 closed_date 필드가 None 이 아닌 경우 datetime 타입."""
    from datetime import datetime

    if sample_alarm.get("device_id") is None:
        pytest.skip("샘플 알람의 device_id 가 NULL")

    result = await tools.get_alarm_history(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        days=90,
        limit=20,
    )
    for item in result:
        if item.closed_date is not None:
            assert isinstance(item.closed_date, datetime), (
                "closed_date 는 datetime 타입이어야 한다"
            )


# ── get_active_alarm_summary ──────────────────────────────────────────────────

async def test_get_active_alarm_summary_returns_stats(sample_alarm: dict[str, Any]) -> None:
    """get_active_alarm_summary: AlarmSummaryStats 반환, total_active >= 0."""
    result = await tools.get_active_alarm_summary(sample_alarm["data_center_id"])
    assert isinstance(result, AlarmSummaryStats)
    assert result.total_active >= 0
    assert isinstance(result.by_severity, dict)
    assert result.unacknowledged >= 0


async def test_get_active_alarm_summary_totals_consistent(sample_alarm: dict[str, Any]) -> None:
    """get_active_alarm_summary: by_severity 합계 == total_active."""
    result = await tools.get_active_alarm_summary(sample_alarm["data_center_id"])
    severity_sum = sum(result.by_severity.values())
    assert severity_sum == result.total_active, (
        f"by_severity 합계({severity_sum})가 total_active({result.total_active})와 일치해야 한다"
    )


async def test_get_active_alarm_summary_unacknowledged_lte_total(
    sample_alarm: dict[str, Any],
) -> None:
    """get_active_alarm_summary: 미확인 건수 <= 전체 활성 건수."""
    result = await tools.get_active_alarm_summary(sample_alarm["data_center_id"])
    assert result.unacknowledged <= result.total_active, (
        "미확인 건수는 전체 활성 알람 수를 초과할 수 없다"
    )


async def test_get_active_alarm_summary_nonexistent_dc(_pool: Any) -> None:
    """get_active_alarm_summary: 존재하지 않는 DC 는 0 카운트 반환."""
    result = await tools.get_active_alarm_summary(data_center_id=-1)
    assert result.total_active == 0
    assert result.by_severity == {}
    assert result.unacknowledged == 0


# ── get_nearby_alarms ─────────────────────────────────────────────────────────

async def test_get_nearby_alarms_returns_list(sample_alarm: dict[str, Any]) -> None:
    """get_nearby_alarms: 결과는 AlarmSummary 리스트여야 한다."""
    if sample_alarm.get("device_id") is None:
        pytest.skip("샘플 알람의 device_id 가 NULL")

    result = await tools.get_nearby_alarms(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        limit=5,
    )
    assert isinstance(result, list)
    assert len(result) <= 5
    for item in result:
        assert isinstance(item, AlarmSummary)


async def test_get_nearby_alarms_excludes_self(sample_alarm: dict[str, Any]) -> None:
    """get_nearby_alarms: 기준 장비 자신의 알람은 결과에 포함되지 않아야 한다."""
    if sample_alarm.get("device_id") is None:
        pytest.skip("샘플 알람의 device_id 가 NULL")

    result = await tools.get_nearby_alarms(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        limit=50,
    )
    device_ids = [a.device_id for a in result if a.device_id is not None]
    assert sample_alarm["device_id"] not in device_ids, (
        "기준 장비 자신(device_id)의 알람이 목록에 포함되어서는 안 된다"
    )


async def test_get_nearby_alarms_limit_clamped(sample_alarm: dict[str, Any]) -> None:
    """get_nearby_alarms: limit 50 초과 시 50으로 클램프 — 에러 없이 동작."""
    if sample_alarm.get("device_id") is None:
        pytest.skip("샘플 알람의 device_id 가 NULL")

    result = await tools.get_nearby_alarms(
        sample_alarm["data_center_id"],
        sample_alarm["device_id"],
        limit=999,
    )
    assert isinstance(result, list)
    assert len(result) <= 50


async def test_get_nearby_alarms_nonexistent_device(_pool: Any) -> None:
    """get_nearby_alarms: 존재하지 않는 device_id 는 빈 리스트 반환."""
    result = await tools.get_nearby_alarms(data_center_id=-1, device_id=-1)
    assert result == []


# ── get_checkpoint_alarms ─────────────────────────────────────────────────────

async def test_get_checkpoint_alarms_returns_list(sample_alarm: dict[str, Any]) -> None:
    """get_checkpoint_alarms: 결과는 AlarmSummary 리스트여야 한다."""
    # sample_alarm 에서 checkpoint_name 을 조회
    async with db.cursor() as cur:
        await cur.execute(
            "SELECT checkpoint_name FROM fm_fault_alarm_cur "
            "WHERE data_center_id=%s AND checkpoint_name IS NOT NULL AND closed_date IS NULL "
            "LIMIT 1",
            (sample_alarm["data_center_id"],),
        )
        row = await cur.fetchone()

    if row is None:
        pytest.skip("활성 알람 중 checkpoint_name 이 설정된 데이터 없음")

    checkpoint_name: str = row["checkpoint_name"]
    result = await tools.get_checkpoint_alarms(
        sample_alarm["data_center_id"],
        checkpoint_name=checkpoint_name,
        limit=10,
    )
    assert isinstance(result, list)
    assert len(result) <= 10
    for item in result:
        assert isinstance(item, AlarmSummary)
        assert item.checkpoint_name == checkpoint_name, (
            f"checkpoint_name 필터({checkpoint_name!r})와 다른 값이 반환되었다: {item.checkpoint_name!r}"
        )


async def test_get_checkpoint_alarms_nonexistent_returns_empty(_pool: Any) -> None:
    """get_checkpoint_alarms: 존재하지 않는 checkpoint_name 은 빈 리스트 반환."""
    result = await tools.get_checkpoint_alarms(
        data_center_id=1,
        checkpoint_name="__nonexistent_checkpoint__",
    )
    assert result == []


async def test_get_checkpoint_alarms_limit_clamped(sample_alarm: dict[str, Any]) -> None:
    """get_checkpoint_alarms: limit 50 초과 시 50으로 클램프 — 에러 없이 동작."""
    result = await tools.get_checkpoint_alarms(
        sample_alarm["data_center_id"],
        checkpoint_name="temperature",
        limit=999,
    )
    assert isinstance(result, list)
    assert len(result) <= 50
