"""maria_mcp tools 단위 테스트.

실제 DB 접속 없이 db.fetch_one / db.fetch_all 을 AsyncMock으로 패치하여
각 tool 함수의 로직만 독립적으로 검증한다.

커버 범위:
- 기본 5개 tool: get_device_info, get_alarm_detail, get_active_alarms,
                 get_alarms_by_time, get_device_alarms
- RCA 확장 7개 tool: list_nearby_devices, list_devices_by_type, list_devices_by_ups,
                     get_alarm_history, get_active_alarm_summary,
                     get_nearby_alarms, get_checkpoint_alarms
- 신규 tool: get_alarm_history_by_policy, get_active_alarms_for_devices, search_devices
- queries 빌더 함수: build_search_devices_query, build_active_alarms_for_devices_query
- _clamp 로직 (limit/hours/days 최대값 초과)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from maria_mcp import tools
from maria_mcp.models import (
    AlarmDetail,
    AlarmSummary,
    AlarmSummaryStats,
    DeviceInfo,
    DeviceSearchResult,
    DeviceSummary,
)
from maria_mcp import queries


# ---------------------------------------------------------------------------
# 공통 픽스처 / 헬퍼
# ---------------------------------------------------------------------------

def _make_device_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "data_center_id": 1,
        "device_id": 10,
        "device_name": "SERVER-01",
        "device_category_name": "서버",
        "device_type_name": "랙 서버",
        "device_model_name": "PowerEdge R750",
        "manufacturer_name": "Dell",
        "maintenance_provider_name": "델 코리아",
        "location": "A동 3층 A-01",
        "enable_monitor": 1,
        "device_desc": "메인 애플리케이션 서버",
    }
    base.update(overrides)
    return base


def _make_device_summary_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "device_id": 10,
        "device_name": "SERVER-01",
        "device_category_name": "서버",
        "device_type_name": "랙 서버",
        "location": "A동 3층 A-01",
        "enable_monitor": 1,
    }
    base.update(overrides)
    return base


def _make_device_search_row(**overrides: Any) -> dict[str, Any]:
    base = _make_device_summary_row()
    base.update({
        "manufacturer_name": "Dell",
        "connected_ups": "UPS-A01",
    })
    base.update(overrides)
    return base


def _make_alarm_summary_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "alarm_id": 100,
        "alarm_name": "CPU 온도 경보",
        "device_id": 10,
        "device_name": "SERVER-01",
        "checkpoint_name": "CPU_TEMP",
        "severity": "Critical",
        "confirm_state": "미확인",
        "log_date": datetime(2026, 5, 12, 10, 0, 0),
        "closed_date": None,
        "message": "CPU 온도가 임계값을 초과했습니다.",
    }
    base.update(overrides)
    return base


def _make_alarm_detail_row(**overrides: Any) -> dict[str, Any]:
    base = _make_alarm_summary_row()
    base.update({
        "checkpoint_id": 5,
        "acknowledged_date": None,
        "acknowledged_message": None,
        "closed_message": None,
    })
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# get_device_info
# ---------------------------------------------------------------------------

class TestGetDeviceInfo:
    async def test_success(self) -> None:
        """정상 케이스: DeviceInfo 객체를 반환해야 한다."""
        row = _make_device_row()
        with patch("maria_mcp.tools.db.fetch_one", new=AsyncMock(return_value=row)):
            result = await tools.get_device_info(data_center_id=1, device_id=10)

        assert isinstance(result, DeviceInfo), "반환 타입은 DeviceInfo 여야 한다"
        assert result.data_center_id == 1
        assert result.device_id == 10
        assert result.device_name == "SERVER-01"

    async def test_empty_result_returns_none(self) -> None:
        """결과 없을 때: None을 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_one", new=AsyncMock(return_value=None)):
            result = await tools.get_device_info(data_center_id=1, device_id=9999)

        assert result is None, "DB에 행이 없으면 None을 반환해야 한다"

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 그대로 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_one",
            new=AsyncMock(side_effect=RuntimeError("DB pool not initialized")),
        ):
            with pytest.raises(RuntimeError, match="DB pool"):
                await tools.get_device_info(data_center_id=1, device_id=10)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_one",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_device_info(data_center_id=1, device_id=10)

    async def test_correct_params_passed(self) -> None:
        """파라미터 전달: fetch_one에 올바른 파라미터가 전달되어야 한다."""
        mock_fetch = AsyncMock(return_value=None)
        with patch("maria_mcp.tools.db.fetch_one", new=mock_fetch):
            await tools.get_device_info(data_center_id=2, device_id=55)

        call_args = mock_fetch.call_args
        # 세 번째 positional arg가 params tuple
        assert call_args[0][2] == (2, 55), "fetch_one에 (data_center_id, device_id)가 전달되어야 한다"


# ---------------------------------------------------------------------------
# get_alarm_detail
# ---------------------------------------------------------------------------

class TestGetAlarmDetail:
    async def test_success(self) -> None:
        """정상 케이스: AlarmDetail 객체를 반환해야 한다."""
        row = _make_alarm_detail_row()
        with patch("maria_mcp.tools.db.fetch_one", new=AsyncMock(return_value=row)):
            result = await tools.get_alarm_detail(data_center_id=1, alarm_id=100)

        assert isinstance(result, AlarmDetail), "반환 타입은 AlarmDetail 여야 한다"
        assert result.alarm_id == 100
        assert result.severity == "Critical"

    async def test_empty_result_returns_none(self) -> None:
        """결과 없을 때: None을 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_one", new=AsyncMock(return_value=None)):
            result = await tools.get_alarm_detail(data_center_id=1, alarm_id=9999)

        assert result is None

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_one",
            new=AsyncMock(side_effect=RuntimeError("connection lost")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_alarm_detail(data_center_id=1, alarm_id=100)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_one",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_alarm_detail(data_center_id=1, alarm_id=100)

    async def test_alarm_detail_has_extra_fields(self) -> None:
        """AlarmDetail은 AlarmSummary에 없는 checkpoint_id 등 추가 필드를 가져야 한다."""
        row = _make_alarm_detail_row(checkpoint_id=7, acknowledged_message="확인됨")
        with patch("maria_mcp.tools.db.fetch_one", new=AsyncMock(return_value=row)):
            result = await tools.get_alarm_detail(data_center_id=1, alarm_id=100)

        assert result is not None
        assert result.checkpoint_id == 7
        assert result.acknowledged_message == "확인됨"


# ---------------------------------------------------------------------------
# get_active_alarms
# ---------------------------------------------------------------------------

class TestGetActiveAlarms:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row(alarm_id=i) for i in range(3)]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_active_alarms(data_center_id=1)

        assert len(result) == 3
        assert all(isinstance(r, AlarmSummary) for r in result)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_active_alarms(data_center_id=1)

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_active_alarms(data_center_id=1)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_active_alarms(data_center_id=1)

    async def test_limit_clamped_to_max_100(self) -> None:
        """limit 최대값 초과: 100으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms(data_center_id=1, limit=9999)

        # fetch_all 호출 시 params 마지막 값이 limit
        call_args = mock_fetch.call_args
        params = call_args[0][2]
        assert params[-1] == 100, "limit은 최대 100으로 clamp되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms(data_center_id=1, limit=0)

        call_args = mock_fetch.call_args
        params = call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"

    async def test_severity_filter_passed(self) -> None:
        """severity 파라미터: fetch_all에 severity 값이 전달되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms(data_center_id=1, severity="Critical")

        call_args = mock_fetch.call_args
        params = call_args[0][2]
        # params: (data_center_id, severity, severity, limit)
        assert "Critical" in params, "severity 값이 파라미터에 포함되어야 한다"


# ---------------------------------------------------------------------------
# get_alarms_by_time
# ---------------------------------------------------------------------------

class TestGetAlarmsByTime:
    def _make_times(self) -> tuple[datetime, datetime]:
        start = datetime(2026, 5, 12, 0, 0, 0)
        end = datetime(2026, 5, 12, 12, 0, 0)
        return start, end

    async def test_success(self) -> None:
        """정상 케이스: 기간 내 AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row()]
        start, end = self._make_times()
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_alarms_by_time(
                data_center_id=1, start_time=start, end_time=end
            )

        assert len(result) == 1
        assert isinstance(result[0], AlarmSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        start, end = self._make_times()
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_alarms_by_time(
                data_center_id=1, start_time=start, end_time=end
            )

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        start, end = self._make_times()
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_alarms_by_time(
                    data_center_id=1, start_time=start, end_time=end
                )

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        start, end = self._make_times()
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_alarms_by_time(
                    data_center_id=1, start_time=start, end_time=end
                )

    async def test_limit_clamped_to_max_200(self) -> None:
        """limit 최대값 초과: 200(_ALARM_LIMIT_MAX)으로 clamp되어야 한다."""
        start, end = self._make_times()
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarms_by_time(
                data_center_id=1, start_time=start, end_time=end, limit=9999
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 200, "limit은 최대 200으로 clamp되어야 한다"

    async def test_start_end_time_passed_correctly(self) -> None:
        """시간 파라미터: start_time과 end_time이 fetch_all에 전달되어야 한다."""
        start, end = self._make_times()
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarms_by_time(
                data_center_id=1, start_time=start, end_time=end
            )

        params = mock_fetch.call_args[0][2]
        assert start in params, "start_time이 파라미터에 포함되어야 한다"
        assert end in params, "end_time이 파라미터에 포함되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        start, end = self._make_times()
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarms_by_time(
                data_center_id=1, start_time=start, end_time=end, limit=0
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# get_device_alarms
# ---------------------------------------------------------------------------

class TestGetDeviceAlarms:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row()]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_device_alarms(data_center_id=1, device_id=10)

        assert len(result) == 1
        assert isinstance(result[0], AlarmSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_device_alarms(data_center_id=1, device_id=10)

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_device_alarms(data_center_id=1, device_id=10)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_device_alarms(data_center_id=1, device_id=10)

    async def test_hours_clamped_to_max_720(self) -> None:
        """hours 최대값 초과: 720(_HOURS_MAX)으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_device_alarms(data_center_id=1, device_id=10, hours=9999)

        params = mock_fetch.call_args[0][2]
        # params: (data_center_id, device_id, hours, limit)
        assert params[2] == 720, "hours는 최대 720으로 clamp되어야 한다"

    async def test_hours_clamped_to_min_1(self) -> None:
        """hours 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_device_alarms(data_center_id=1, device_id=10, hours=0)

        params = mock_fetch.call_args[0][2]
        assert params[2] == 1, "hours는 최소 1로 clamp되어야 한다"

    async def test_limit_clamped_to_max_200(self) -> None:
        """limit 최대값 초과: 200으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_device_alarms(data_center_id=1, device_id=10, limit=9999)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 200, "limit은 최대 200으로 clamp되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_device_alarms(data_center_id=1, device_id=10, limit=0)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# list_nearby_devices
# ---------------------------------------------------------------------------

class TestListNearbyDevices:
    async def test_success(self) -> None:
        """정상 케이스: DeviceSummary 리스트를 반환해야 한다."""
        rows = [_make_device_summary_row(device_id=20), _make_device_summary_row(device_id=21)]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.list_nearby_devices(data_center_id=1, device_id=10)

        assert len(result) == 2
        assert all(isinstance(r, DeviceSummary) for r in result)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.list_nearby_devices(data_center_id=1, device_id=10)

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.list_nearby_devices(data_center_id=1, device_id=10)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.list_nearby_devices(data_center_id=1, device_id=10)

    async def test_limit_clamped_to_max_50(self) -> None:
        """limit 최대값 초과: 50으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_nearby_devices(data_center_id=1, device_id=10, limit=999)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 50, "limit은 최대 50으로 clamp되어야 한다"

    async def test_device_id_passed_correctly(self) -> None:
        """device_id: fetch_all 파라미터에 device_id가 포함되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_nearby_devices(data_center_id=1, device_id=42)

        params = mock_fetch.call_args[0][2]
        assert 42 in params, "device_id가 쿼리 파라미터에 포함되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_nearby_devices(data_center_id=1, device_id=10, limit=0)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# list_devices_by_type
# ---------------------------------------------------------------------------

class TestListDevicesByType:
    async def test_success_with_category(self) -> None:
        """정상 케이스(category만): DeviceSummary 리스트를 반환해야 한다."""
        rows = [_make_device_summary_row()]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.list_devices_by_type(
                data_center_id=1, device_category_name="서버"
            )

        assert len(result) == 1
        assert isinstance(result[0], DeviceSummary)

    async def test_success_with_type(self) -> None:
        """정상 케이스(type만): DeviceSummary 리스트를 반환해야 한다."""
        rows = [_make_device_summary_row()]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.list_devices_by_type(
                data_center_id=1, device_type_name="랙 서버"
            )

        assert len(result) == 1

    async def test_both_none_returns_empty_list(self) -> None:
        """category와 type 모두 None: DB 호출 없이 빈 리스트를 반환해야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            result = await tools.list_devices_by_type(data_center_id=1)

        assert result == [], "category와 type이 모두 None이면 빈 리스트를 반환해야 한다"
        mock_fetch.assert_not_called()

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.list_devices_by_type(
                data_center_id=1, device_category_name="존재하지않는카테고리"
            )

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.list_devices_by_type(
                    data_center_id=1, device_category_name="서버"
                )

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.list_devices_by_type(
                    data_center_id=1, device_category_name="서버"
                )

    async def test_limit_clamped_to_max_100(self) -> None:
        """limit 최대값 초과: 100으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_devices_by_type(
                data_center_id=1, device_category_name="서버", limit=9999
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 100, "limit은 최대 100으로 clamp되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_devices_by_type(
                data_center_id=1, device_category_name="서버", limit=0
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"

    async def test_both_category_and_type_specified(self) -> None:
        """category와 type 모두 지정: 두 조건 모두 파라미터에 포함되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_devices_by_type(
                data_center_id=1,
                device_category_name="서버",
                device_type_name="랙 서버",
            )

        mock_fetch.assert_called_once()
        params = mock_fetch.call_args[0][2]
        assert "서버" in params and "랙 서버" in params, "category와 type 모두 파라미터에 포함되어야 한다"


# ---------------------------------------------------------------------------
# list_devices_by_ups
# ---------------------------------------------------------------------------

class TestListDevicesByUps:
    async def test_success(self) -> None:
        """정상 케이스: DeviceSummary 리스트를 반환해야 한다."""
        rows = [_make_device_summary_row(device_id=30)]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.list_devices_by_ups(
                data_center_id=1, ups_name="UPS-A01"
            )

        assert len(result) == 1
        assert isinstance(result[0], DeviceSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.list_devices_by_ups(
                data_center_id=1, ups_name="존재하지않는UPS"
            )

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.list_devices_by_ups(data_center_id=1, ups_name="UPS-A01")

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.list_devices_by_ups(data_center_id=1, ups_name="UPS-A01")

    async def test_ups_name_passed_correctly(self) -> None:
        """ups_name: 정확한 UPS 이름이 파라미터에 포함되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_devices_by_ups(data_center_id=1, ups_name="UPS-MAIN")

        params = mock_fetch.call_args[0][2]
        assert "UPS-MAIN" in params, "ups_name이 쿼리 파라미터에 포함되어야 한다"

    async def test_limit_clamped_to_max_100(self) -> None:
        """limit 최대값 초과: 100으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_devices_by_ups(data_center_id=1, ups_name="UPS-A01", limit=9999)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 100, "limit은 최대 100으로 clamp되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.list_devices_by_ups(data_center_id=1, ups_name="UPS-A01", limit=0)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# get_alarm_history
# ---------------------------------------------------------------------------

class TestGetAlarmHistory:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row()]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_alarm_history(data_center_id=1, device_id=10)

        assert len(result) == 1
        assert isinstance(result[0], AlarmSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_alarm_history(data_center_id=1, device_id=10)

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_alarm_history(data_center_id=1, device_id=10)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_alarm_history(data_center_id=1, device_id=10)

    async def test_days_clamped_to_max_90(self) -> None:
        """days 최대값 초과: 90(_DAYS_MAX)으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history(data_center_id=1, device_id=10, days=999)

        params = mock_fetch.call_args[0][2]
        # params: (data_center_id, device_id, days, limit)
        assert params[2] == 90, "days는 최대 90으로 clamp되어야 한다"

    async def test_days_clamped_to_min_1(self) -> None:
        """days 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history(data_center_id=1, device_id=10, days=0)

        params = mock_fetch.call_args[0][2]
        assert params[2] == 1, "days는 최소 1로 clamp되어야 한다"

    async def test_limit_clamped_to_max_100(self) -> None:
        """limit 최대값 초과: 100으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history(data_center_id=1, device_id=10, limit=9999)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 100, "limit은 최대 100으로 clamp되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history(data_center_id=1, device_id=10, limit=0)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# get_active_alarm_summary
# ---------------------------------------------------------------------------

class TestGetActiveAlarmSummary:
    async def test_success_aggregates_correctly(self) -> None:
        """정상 케이스: 다중 severity 행을 집계해야 한다."""
        rows = [
            {"severity": "Critical", "total_active": 3, "unacknowledged_count": 2},
            {"severity": "Major", "total_active": 5, "unacknowledged_count": 3},
            {"severity": "Minor", "total_active": 10, "unacknowledged_count": 4},
        ]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_active_alarm_summary(data_center_id=1)

        assert isinstance(result, AlarmSummaryStats)
        assert result.total_active == 18, "total_active는 모든 severity 합산이어야 한다"
        assert result.unacknowledged == 9, "unacknowledged는 모든 unacknowledged_count 합산이어야 한다"
        assert result.by_severity["Critical"] == 3
        assert result.by_severity["Major"] == 5
        assert result.by_severity["Minor"] == 10

    async def test_empty_result_returns_zero_stats(self) -> None:
        """결과 없을 때: 모든 카운트가 0인 AlarmSummaryStats를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_active_alarm_summary(data_center_id=1)

        assert result.total_active == 0
        assert result.unacknowledged == 0
        assert result.by_severity == {}

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_active_alarm_summary(data_center_id=1)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_active_alarm_summary(data_center_id=1)

    async def test_null_severity_mapped_to_unknown(self) -> None:
        """severity가 None인 행: 'Unknown' 키로 집계되어야 한다."""
        rows = [
            {"severity": None, "total_active": 2, "unacknowledged_count": 1},
        ]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_active_alarm_summary(data_center_id=1)

        assert "Unknown" in result.by_severity, "severity=None 행은 'Unknown' 키로 집계되어야 한다"
        assert result.by_severity["Unknown"] == 2

    async def test_null_unacknowledged_count_treated_as_zero(self) -> None:
        """unacknowledged_count가 None인 행: 0으로 처리되어야 한다."""
        rows = [
            {"severity": "Info", "total_active": 1, "unacknowledged_count": None},
        ]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_active_alarm_summary(data_center_id=1)

        assert result.unacknowledged == 0, "unacknowledged_count=None은 0으로 처리되어야 한다"

    async def test_single_severity_row(self) -> None:
        """단일 severity 행: 집계 결과가 해당 행 값과 일치해야 한다."""
        rows = [
            {"severity": "Critical", "total_active": 7, "unacknowledged_count": 5},
        ]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_active_alarm_summary(data_center_id=1)

        assert result.total_active == 7
        assert result.unacknowledged == 5
        assert len(result.by_severity) == 1


# ---------------------------------------------------------------------------
# get_nearby_alarms
# ---------------------------------------------------------------------------

class TestGetNearbyAlarms:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row(device_id=20)]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_nearby_alarms(data_center_id=1, device_id=10)

        assert len(result) == 1
        assert isinstance(result[0], AlarmSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_nearby_alarms(data_center_id=1, device_id=10)

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_nearby_alarms(data_center_id=1, device_id=10)

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_nearby_alarms(data_center_id=1, device_id=10)

    async def test_limit_clamped_to_max_50(self) -> None:
        """limit 최대값 초과: 50으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_nearby_alarms(data_center_id=1, device_id=10, limit=999)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 50, "limit은 최대 50으로 clamp되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_nearby_alarms(data_center_id=1, device_id=10, limit=0)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# get_checkpoint_alarms
# ---------------------------------------------------------------------------

class TestGetCheckpointAlarms:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row(checkpoint_name="CPU_TEMP")]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_checkpoint_alarms(
                data_center_id=1, checkpoint_name="CPU_TEMP"
            )

        assert len(result) == 1
        assert isinstance(result[0], AlarmSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_checkpoint_alarms(
                data_center_id=1, checkpoint_name="NONEXISTENT"
            )

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_checkpoint_alarms(
                    data_center_id=1, checkpoint_name="CPU_TEMP"
                )

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_checkpoint_alarms(
                    data_center_id=1, checkpoint_name="CPU_TEMP"
                )

    async def test_limit_clamped_to_max_50(self) -> None:
        """limit 최대값 초과: 50으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_checkpoint_alarms(
                data_center_id=1, checkpoint_name="CPU_TEMP", limit=9999
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 50, "limit은 최대 50으로 clamp되어야 한다"

    async def test_checkpoint_name_passed_correctly(self) -> None:
        """checkpoint_name: 쿼리 파라미터에 올바른 이름이 전달되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_checkpoint_alarms(
                data_center_id=1, checkpoint_name="DISK_IO"
            )

        params = mock_fetch.call_args[0][2]
        assert "DISK_IO" in params, "checkpoint_name이 쿼리 파라미터에 포함되어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_checkpoint_alarms(
                data_center_id=1, checkpoint_name="CPU_TEMP", limit=0
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# get_alarm_history_by_policy
# ---------------------------------------------------------------------------

class TestGetAlarmHistoryByPolicy:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row()]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_alarm_history_by_policy(
                data_center_id=1, alarm_policy_name="CPU_OVERTEMP"
            )

        assert len(result) == 1
        assert isinstance(result[0], AlarmSummary)

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.get_alarm_history_by_policy(
                data_center_id=1, alarm_policy_name="NONEXISTENT"
            )

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_alarm_history_by_policy(
                    data_center_id=1, alarm_policy_name="CPU_OVERTEMP"
                )

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_alarm_history_by_policy(
                    data_center_id=1, alarm_policy_name="CPU_OVERTEMP"
                )

    async def test_days_clamped_to_max_90(self) -> None:
        """days 최대값 초과: 90으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history_by_policy(
                data_center_id=1, alarm_policy_name="CPU_OVERTEMP", days=999
            )

        params = mock_fetch.call_args[0][2]
        # params: (data_center_id, alarm_policy_name, days, limit)
        assert params[2] == 90, "days는 최대 90으로 clamp되어야 한다"

    async def test_limit_clamped_to_max_200(self) -> None:
        """limit 최대값 초과: 200(_HISTORY_POLICY_LIMIT_MAX)으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history_by_policy(
                data_center_id=1, alarm_policy_name="CPU_OVERTEMP", limit=9999
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 200, "limit은 최대 200으로 clamp되어야 한다"

    async def test_days_clamped_to_min_1(self) -> None:
        """days 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history_by_policy(
                data_center_id=1, alarm_policy_name="CPU_OVERTEMP", days=0
            )

        params = mock_fetch.call_args[0][2]
        assert params[2] == 1, "days는 최소 1로 clamp되어야 한다"

    async def test_policy_name_passed_correctly(self) -> None:
        """alarm_policy_name: 쿼리 파라미터에 올바른 이름이 전달되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_alarm_history_by_policy(
                data_center_id=1, alarm_policy_name="DISK_FAILURE"
            )

        params = mock_fetch.call_args[0][2]
        assert "DISK_FAILURE" in params, "alarm_policy_name이 쿼리 파라미터에 포함되어야 한다"


# ---------------------------------------------------------------------------
# get_active_alarms_for_devices
# ---------------------------------------------------------------------------

class TestGetActiveAlarmsForDevices:
    async def test_success(self) -> None:
        """정상 케이스: AlarmSummary 리스트를 반환해야 한다."""
        rows = [_make_alarm_summary_row(device_id=10), _make_alarm_summary_row(device_id=11)]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.get_active_alarms_for_devices(
                data_center_id=1, device_ids=[10, 11]
            )

        assert len(result) == 2
        assert all(isinstance(r, AlarmSummary) for r in result)

    async def test_empty_device_ids_returns_empty_list(self) -> None:
        """빈 device_ids: DB 호출 없이 빈 리스트를 반환해야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            result = await tools.get_active_alarms_for_devices(
                data_center_id=1, device_ids=[]
            )

        assert result == [], "device_ids가 비어있으면 빈 리스트를 반환해야 한다"
        mock_fetch.assert_not_called()

    async def test_device_ids_truncated_to_50(self) -> None:
        """50개 초과 device_ids: 처음 50개만 사용해야 한다."""
        device_ids = list(range(1, 101))  # 100개
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms_for_devices(
                data_center_id=1, device_ids=device_ids
            )

        # fetch_all에 전달된 SQL에서 IN 플레이스홀더 개수 확인
        call_args = mock_fetch.call_args
        sql: str = call_args[0][1]
        placeholder_count = sql.count("%s") - 2  # data_center_id, limit 제외
        assert placeholder_count == 50, "device_ids는 최대 50개로 잘려야 한다"

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.get_active_alarms_for_devices(
                    data_center_id=1, device_ids=[10, 11]
                )

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.get_active_alarms_for_devices(
                    data_center_id=1, device_ids=[10]
                )

    async def test_limit_clamped_to_max_200(self) -> None:
        """limit 최대값 초과: 200으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms_for_devices(
                data_center_id=1, device_ids=[10], limit=9999
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 200, "limit은 최대 200으로 clamp되어야 한다"

    async def test_params_structure_data_center_first_limit_last(self) -> None:
        """파라미터 구조: data_center_id가 첫 번째, limit이 마지막이어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms_for_devices(
                data_center_id=7, device_ids=[10, 20], limit=30
            )

        params = mock_fetch.call_args[0][2]
        assert params[0] == 7, "첫 번째 파라미터는 data_center_id여야 한다"
        assert params[-1] == 30, "마지막 파라미터는 limit이어야 한다"

    async def test_limit_clamped_to_min_1(self) -> None:
        """limit 최소값 미만: 1로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.get_active_alarms_for_devices(
                data_center_id=1, device_ids=[10], limit=0
            )

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 1, "limit은 최소 1로 clamp되어야 한다"


# ---------------------------------------------------------------------------
# search_devices
# ---------------------------------------------------------------------------

class TestSearchDevices:
    async def test_success_with_device_name(self) -> None:
        """정상 케이스(device_nm): DeviceSearchResult 리스트를 반환해야 한다."""
        rows = [_make_device_search_row()]
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=rows)):
            result = await tools.search_devices(data_center_id=1, device_nm="SERVER")

        assert len(result) == 1
        assert isinstance(result[0], DeviceSearchResult)

    async def test_all_conditions_none_returns_empty_list(self) -> None:
        """모든 조건 None: DB 호출 없이 빈 리스트를 반환해야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            result = await tools.search_devices(data_center_id=1)

        assert result == [], "모든 검색 조건이 None이면 빈 리스트를 반환해야 한다"
        mock_fetch.assert_not_called()

    async def test_empty_result(self) -> None:
        """결과 없을 때: 빈 리스트를 반환해야 한다."""
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[])):
            result = await tools.search_devices(data_center_id=1, device_nm="NONEXISTENT")

        assert result == []

    async def test_db_error_propagates(self) -> None:
        """DB 오류: 예외가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            with pytest.raises(RuntimeError):
                await tools.search_devices(data_center_id=1, device_nm="SERVER")

    async def test_timeout_propagates(self) -> None:
        """Timeout: asyncio.TimeoutError가 전파되어야 한다."""
        with patch(
            "maria_mcp.tools.db.fetch_all",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await tools.search_devices(data_center_id=1, device_nm="SERVER")

    async def test_limit_clamped_to_max_100(self) -> None:
        """limit 최대값 초과: 100(_SEARCH_LIMIT_MAX)으로 clamp되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.search_devices(data_center_id=1, device_nm="A", limit=9999)

        params = mock_fetch.call_args[0][2]
        assert params[-1] == 100, "limit은 최대 100으로 clamp되어야 한다"

    async def test_result_has_manufacturer_and_ups_fields(self) -> None:
        """DeviceSearchResult: manufacturer_name과 connected_ups 필드를 가져야 한다."""
        row = _make_device_search_row(manufacturer_name="HP", connected_ups="UPS-B02")
        with patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=[row])):
            result = await tools.search_devices(data_center_id=1, manufacturer_name="HP")

        assert result[0].manufacturer_name == "HP"
        assert result[0].connected_ups == "UPS-B02"

    async def test_floor_id_as_sole_condition_triggers_query(self) -> None:
        """floor_id만 지정: 조건 중 하나이므로 DB 쿼리가 실행되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.search_devices(data_center_id=1, floor_id=3)

        mock_fetch.assert_called_once(), "floor_id만 주어져도 DB 쿼리가 실행되어야 한다"

    async def test_multiple_conditions_combined(self) -> None:
        """다중 조건 동시 지정: 모든 조건이 쿼리 파라미터에 포함되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.search_devices(
                data_center_id=1, device_nm="web", location="3층"
            )

        mock_fetch.assert_called_once()
        params = mock_fetch.call_args[0][2]
        assert any("%web%" in str(p) for p in params), "device_nm 파라미터가 포함되어야 한다"
        assert any("%3층%" in str(p) for p in params), "location 파라미터가 포함되어야 한다"

    async def test_connected_ups_condition(self) -> None:
        """connected_ups만 지정: LIKE 조건으로 파라미터에 포함되어야 한다."""
        mock_fetch = AsyncMock(return_value=[])
        with patch("maria_mcp.tools.db.fetch_all", new=mock_fetch):
            await tools.search_devices(data_center_id=1, connected_ups="UPS-B")

        mock_fetch.assert_called_once()
        params = mock_fetch.call_args[0][2]
        assert any("%UPS-B%" in str(p) for p in params), "connected_ups 파라미터가 포함되어야 한다"


# ---------------------------------------------------------------------------
# queries.build_search_devices_query
# ---------------------------------------------------------------------------

class TestBuildSearchDevicesQuery:
    def test_single_condition_device_nm(self) -> None:
        """device_nm만 지정: LIKE 조건 1개가 포함된 SQL이 생성되어야 한다."""
        sql, params = queries.build_search_devices_query(
            device_nm="SERVER",
            device_type_name=None,
            device_category_name=None,
            location=None,
            floor_id=None,
            zone_id=None,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert "device_nm LIKE %s" in sql, "device_nm LIKE 조건이 SQL에 포함되어야 한다"
        assert "%SERVER%" in params, "파라미터에 %SERVER% 형식이 포함되어야 한다"

    def test_multiple_conditions_combined(self) -> None:
        """여러 조건 지정: 모든 조건이 AND로 결합되어야 한다."""
        sql, params = queries.build_search_devices_query(
            device_nm="SRV",
            device_type_name="랙 서버",
            device_category_name=None,
            location="3층",
            floor_id=None,
            zone_id=None,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert "device_nm LIKE %s" in sql
        assert "device_type_name LIKE %s" in sql
        assert "location LIKE %s" in sql
        assert len(params) == 3, "조건 3개에 대한 파라미터 3개여야 한다"

    def test_floor_id_exact_match(self) -> None:
        """floor_id: LIKE가 아닌 = 조건으로 생성되어야 한다."""
        sql, params = queries.build_search_devices_query(
            device_nm=None,
            device_type_name=None,
            device_category_name=None,
            location=None,
            floor_id=2,
            zone_id=None,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert "floor_id = %s" in sql, "floor_id는 LIKE가 아닌 = 조건이어야 한다"
        assert 2 in params

    def test_zone_id_exact_match(self) -> None:
        """zone_id: LIKE가 아닌 = 조건으로 생성되어야 한다."""
        sql, params = queries.build_search_devices_query(
            device_nm=None,
            device_type_name=None,
            device_category_name=None,
            location=None,
            floor_id=None,
            zone_id=5,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert "zone_id = %s" in sql, "zone_id는 LIKE가 아닌 = 조건이어야 한다"
        assert 5 in params

    def test_all_none_generates_base_conditions_only(self) -> None:
        """모든 파라미터 None: data_center_id와 use_yn 기본 조건만 포함되어야 한다."""
        sql, params = queries.build_search_devices_query(
            device_nm=None,
            device_type_name=None,
            device_category_name=None,
            location=None,
            floor_id=None,
            zone_id=None,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert "data_center_id = %s" in sql
        assert "use_yn = 'Y'" in sql
        assert len(params) == 0, "추가 조건 없으면 동적 파라미터는 비어 있어야 한다"

    def test_like_params_wrapped_with_percent(self) -> None:
        """LIKE 파라미터: %value% 형식으로 래핑되어야 한다."""
        _, params = queries.build_search_devices_query(
            device_nm=None,
            device_type_name=None,
            device_category_name=None,
            location="서버실",
            floor_id=None,
            zone_id=None,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert params[0] == "%서버실%", "location 파라미터는 %서버실% 형식이어야 한다"

    def test_returns_tuple_of_sql_and_params(self) -> None:
        """반환 타입: (str, tuple) 이어야 한다."""
        result = queries.build_search_devices_query(
            device_nm="X",
            device_type_name=None,
            device_category_name=None,
            location=None,
            floor_id=None,
            zone_id=None,
            connected_ups=None,
            manufacturer_name=None,
        )

        assert isinstance(result, tuple) and len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], tuple)

    def test_connected_ups_like_search(self) -> None:
        """connected_ups: LIKE 조건으로 생성되어야 한다."""
        sql, params = queries.build_search_devices_query(
            device_nm=None,
            device_type_name=None,
            device_category_name=None,
            location=None,
            floor_id=None,
            zone_id=None,
            connected_ups="UPS-A",
            manufacturer_name=None,
        )

        assert "connected_ups LIKE %s" in sql, "connected_ups LIKE 조건이 SQL에 포함되어야 한다"
        assert "%UPS-A%" in params, "파라미터에 %UPS-A% 형식이 포함되어야 한다"


# ---------------------------------------------------------------------------
# queries.build_active_alarms_for_devices_query
# ---------------------------------------------------------------------------

class TestBuildActiveAlarmsForDevicesQuery:
    def test_single_device_id_one_placeholder(self) -> None:
        """device_ids 1개: IN 절에 플레이스홀더 1개가 생성되어야 한다."""
        sql, params = queries.build_active_alarms_for_devices_query([10])

        assert "IN (%s)" in sql, "단일 device_id는 IN (%s) 형식이어야 한다"
        assert params == (10,)

    def test_multiple_device_ids_correct_placeholder_count(self) -> None:
        """device_ids 5개: IN 절에 플레이스홀더 5개가 생성되어야 한다."""
        device_ids = [10, 11, 12, 13, 14]
        sql, params = queries.build_active_alarms_for_devices_query(device_ids)

        expected_placeholders = ", ".join(["%s"] * 5)
        assert f"IN ({expected_placeholders})" in sql, "플레이스홀더 개수가 device_ids 개수와 일치해야 한다"
        assert params == (10, 11, 12, 13, 14)

    def test_params_match_device_ids_order(self) -> None:
        """파라미터 순서: device_ids 입력 순서대로 params에 담겨야 한다."""
        device_ids = [30, 10, 20]
        _, params = queries.build_active_alarms_for_devices_query(device_ids)

        assert params == (30, 10, 20), "파라미터는 입력된 device_ids 순서를 유지해야 한다"

    def test_returns_tuple_of_sql_and_params(self) -> None:
        """반환 타입: (str, tuple) 이어야 한다."""
        result = queries.build_active_alarms_for_devices_query([1, 2, 3])

        assert isinstance(result, tuple) and len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], tuple)

    def test_sql_contains_closed_date_is_null_filter(self) -> None:
        """SQL 구조: closed_date IS NULL 조건이 포함되어야 한다."""
        sql, _ = queries.build_active_alarms_for_devices_query([10])

        assert "closed_date IS NULL" in sql, "활성 알람 필터 조건이 SQL에 포함되어야 한다"

    def test_fifty_device_ids_correct_placeholder_count(self) -> None:
        """device_ids 50개 경계값: 플레이스홀더가 정확히 50개여야 한다."""
        device_ids = list(range(1, 51))
        sql, params = queries.build_active_alarms_for_devices_query(device_ids)

        assert len(params) == 50
        assert sql.count("%s") == 52  # data_center_id(1) + device_ids(50) + limit(1)
