from datetime import datetime

from . import db, queries
from .logging_setup import log_tool_call
from .models import AlarmDetail, AlarmSummary, AlarmSummaryStats, DeviceInfo, DeviceSearchResult, DeviceSummary


_LIMIT_MAX = 15         # 토큰 절약: 모든 목록 조회 최대 15건
_HOURS_MAX = 3000       # ~125일
_DAYS_MAX = 365         # his 테이블 파티션 보존 기간
_ACTIVE_DEVICES_MAX = 50  # IN 절 device_id 최대 개수

# DB에 존재하는 유효 device_category_name 화이트리스트.
# device_category_name 슬롯에 이 외 값(예: 'Switchboard', 'CRAC')이 들어오면
# device_type_name 으로 잘못 매핑된 것으로 보고 자동 이동시킨다.
_VALID_CATEGORIES = frozenset({
    "HVAC", "IT", "Electric Power", "BMS",
})


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _normalize_category_type(
    device_category_name: str | None,
    device_type_name: str | None,
) -> tuple[str | None, str | None]:
    """LLM 이 device_category_name 슬롯에 타입명을 넣은 경우 type 슬롯으로 자동 이동."""
    if (
        device_category_name is not None
        and device_category_name not in _VALID_CATEGORIES
        and device_type_name is None
    ):
        return None, device_category_name
    return device_category_name, device_type_name


async def get_device_info(data_center_id: int, device_id: int) -> DeviceInfo | None:
    with log_tool_call("get_device_info", data_center_id=data_center_id, device_id=device_id) as meta:
        row = await db.fetch_one(
            "select_device_info",
            queries.SELECT_DEVICE_INFO,
            (data_center_id, device_id),
        )
        meta["result_count"] = 1 if row else 0
        return DeviceInfo(**row) if row else None


async def get_alarm_info(data_center_id: int, alarm_id: int) -> AlarmDetail | None:
    with log_tool_call("get_alarm_info", data_center_id=data_center_id, alarm_id=alarm_id) as meta:
        row = await db.fetch_one(
            "select_alarm_detail",
            queries.SELECT_ALARM_DETAIL,
            (data_center_id, alarm_id),
        )
        meta["result_count"] = 1 if row else 0
        return AlarmDetail(**row) if row else None


async def get_active_alarms(
    data_center_id: int,
    severity: str | None = None,
    limit: int = 15,
) -> list[AlarmSummary]:
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_active_alarms", data_center_id=data_center_id, severity=severity, limit=limit
    ) as meta:
        rows = await db.fetch_all(
            "select_active_alarms",
            queries.SELECT_ACTIVE_ALARMS,
            (data_center_id, severity, severity, limit),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_alarms_by_time(
    data_center_id: int,
    start_time: datetime,
    end_time: datetime,
    severity: str | None = None,
    limit: int = 15,
) -> list[AlarmSummary]:
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_alarms_by_time",
        data_center_id=data_center_id,
        start_time=start_time,
        end_time=end_time,
        severity=severity,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_alarms_by_time",
            queries.SELECT_ALARMS_BY_TIME,
            (data_center_id, start_time, end_time, severity, severity, limit),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_device_alarms(
    data_center_id: int,
    device_id: int,
    hours: int = 24,
    limit: int = 15,
) -> list[AlarmSummary]:
    hours = _clamp(hours, 1, _HOURS_MAX)
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_device_alarms",
        data_center_id=data_center_id,
        device_id=device_id,
        hours=hours,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_device_alarms",
            queries.SELECT_DEVICE_ALARMS,
            (data_center_id, device_id, hours, limit),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


# ── RCA 확장 tool (§10.1) ─────────────────────────────────────────────────────

async def list_nearby_devices(
    data_center_id: int,
    device_id: int,
    limit: int = 15,
) -> list[DeviceSummary]:
    """같은 구역 장비 목록 (알람 아님) — 기준 장비 자신 제외, zone_id 기준 내부 JOIN."""
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "list_nearby_devices",
        data_center_id=data_center_id,
        device_id=device_id,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_nearby_devices",
            queries.SELECT_NEARBY_DEVICES,
            (data_center_id, data_center_id, device_id, device_id, limit),
        )
        meta["result_count"] = len(rows)
        return [DeviceSummary(**r) for r in rows]


async def list_devices_by_type(
    data_center_id: int,
    device_category_name: str | None = None,
    device_type_name: str | None = None,
    limit: int = 15,
) -> list[DeviceSummary]:
    """동일 카테고리/유형 장비 목록 — 타입명 정확 매칭. category 또는 type 중 하나 이상 필수.
    둘 다 None이면 빈 리스트 반환 (에러 아님).
    부분 문자열·다중 조건 검색은 search_devices 사용.

    파라미터 분류:
    - device_category_name: 상위 분류만. 유효값: 'HVAC', 'IT', 'Electric Power', 'BMS' 등.
      → 'Switchboard', 'CRAC', 'CRAH', 'Rack' 같은 구체 타입명을 여기에 넣지 말 것.
    - device_type_name: 구체 타입명. 예) 'Switchboard', 'CRAC', 'CRAH', 'Rack'.
      → 'HVAC', 'IT', 'Electric Power' 같은 상위 분류명을 여기에 넣지 말 것.

    중요: 사용자가 말한 값을 변환 없이 그대로 전달하되, 위 분류에 따라 올바른 슬롯에 넣을 것.
    예) "카테고리 HVAC" → device_category_name='HVAC'
    예) "타입 Switchboard" → device_type_name='Switchboard'
    예) "CRAC"이라 하면 "CRAC", "CRAH"라 하면 "CRAH"로 전달 (변환 금지).
    사용자가 다중 조건(카테고리+타입)을 말하면 두 파라미터를 모두 채울 것.
    """
    limit = _clamp(limit, 1, _LIMIT_MAX)
    device_category_name, device_type_name = _normalize_category_type(
        device_category_name, device_type_name
    )
    with log_tool_call(
        "list_devices_by_type",
        data_center_id=data_center_id,
        device_category_name=device_category_name,
        device_type_name=device_type_name,
        limit=limit,
    ) as meta:
        if device_category_name is None and device_type_name is None:
            meta["result_count"] = 0
            return []
        rows = await db.fetch_all(
            "select_devices_by_type",
            queries.SELECT_DEVICES_BY_TYPE,
            (
                data_center_id,
                device_category_name, device_category_name,
                device_type_name, device_type_name,
                limit,
            ),
        )
        meta["result_count"] = len(rows)
        return [DeviceSummary(**r) for r in rows]


async def list_devices_by_ups(
    data_center_id: int,
    ups_name: str,
    limit: int = 15,
) -> list[DeviceSummary]:
    """특정 UPS에 연결된 장비 목록 — UPS 이름 정확 매칭, 전원 cascade 분석.
    UPS 이름 부분 문자열 검색은 search_devices(connected_ups=...) 사용.
    """
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "list_devices_by_ups",
        data_center_id=data_center_id,
        ups_name=ups_name,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_devices_by_ups",
            queries.SELECT_DEVICES_BY_UPS,
            (data_center_id, ups_name, limit),
        )
        meta["result_count"] = len(rows)
        return [DeviceSummary(**r) for r in rows]


async def get_alarm_history(
    data_center_id: int,
    device_id: int,
    days: int = 30,
    limit: int = 15,
) -> list[AlarmSummary]:
    """과거 N일 완료된 알람 이력 (his 테이블) — 재발 패턴 파악용. days 최대 365."""
    days = _clamp(days, 1, _DAYS_MAX)
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_alarm_history",
        data_center_id=data_center_id,
        device_id=device_id,
        days=days,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_alarm_history",
            queries.SELECT_ALARM_HISTORY,
            (data_center_id, device_id, days, limit),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_active_alarm_summary(data_center_id: int) -> AlarmSummaryStats:
    """심각도별 카운트 요약 (상세 목록 아님) — 분석 시작 전 전체 현황 파악용."""
    with log_tool_call("get_active_alarm_summary", data_center_id=data_center_id) as meta:
        rows = await db.fetch_all(
            "select_active_alarm_summary",
            queries.SELECT_ACTIVE_ALARM_SUMMARY,
            (data_center_id,),
        )
        meta["result_count"] = len(rows)

        total_active = 0
        by_severity: dict[str, int] = {}
        unacknowledged = 0

        for row in rows:
            count = int(row["total_active"])
            severity = row["severity"] or "Unknown"
            total_active += count
            by_severity[severity] = count
            unacknowledged += int(row["unacknowledged_count"] or 0)

        return AlarmSummaryStats(
            total_active=total_active,
            by_severity=by_severity,
            unacknowledged=unacknowledged,
        )


async def get_nearby_alarms(
    data_center_id: int,
    device_id: int,
    limit: int = 15,
) -> list[AlarmSummary]:
    """같은 구역 다른 장비 활성 알람 — 기준 장비 자신 알람 제외, zone_id 기준 내부 JOIN."""
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_nearby_alarms",
        data_center_id=data_center_id,
        device_id=device_id,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_nearby_alarms",
            queries.SELECT_NEARBY_ALARMS,
            (
                data_center_id, device_id,
                data_center_id,
                data_center_id, device_id, device_id,
                limit,
            ),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_checkpoint_alarms(
    data_center_id: int,
    checkpoint_name: str,
    limit: int = 15,
) -> list[AlarmSummary]:
    """동일 모니터링 항목 전 장비 활성 알람 — checkpoint_name 기준 공통 원인 탐지."""
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_checkpoint_alarms",
        data_center_id=data_center_id,
        checkpoint_name=checkpoint_name,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_checkpoint_alarms",
            queries.SELECT_CHECKPOINT_ALARMS,
            (data_center_id, checkpoint_name, limit),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_alarm_history_by_policy(
    data_center_id: int,
    alarm_policy_name: str,
    days: int = 30,
    limit: int = 15,
) -> list[AlarmSummary]:
    """과거 N일 특정 알람 정책의 완료된 이력 (his 테이블) — 알람 종류별 재발 패턴·영향 장비 파악.
    get_alarm_history(device_id 기준) 와 달리 alarm_policy_name 기준으로 전 장비 이력 조회.
    """
    days = _clamp(days, 1, _DAYS_MAX)
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_alarm_history_by_policy",
        data_center_id=data_center_id,
        alarm_policy_name=alarm_policy_name,
        days=days,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_alarm_history_by_policy",
            queries.SELECT_ALARM_HISTORY_BY_POLICY,
            (data_center_id, alarm_policy_name, days, limit),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_active_alarms_for_devices(
    data_center_id: int,
    device_ids: list[int],
    limit: int = 15,
) -> list[AlarmSummary]:
    """여러 장비의 활성 알람을 한 번에 조회 — list_nearby_devices 결과 후속 호출 N+1 방지.
    device_ids 가 비어 있으면 빈 리스트 반환. 50개 초과 시 앞 50개만 처리(조용히 잘라냄).
    """
    if not device_ids:
        return []
    device_ids = device_ids[:_ACTIVE_DEVICES_MAX]
    limit = _clamp(limit, 1, _LIMIT_MAX)
    sql, id_params = queries.build_active_alarms_for_devices_query(device_ids)
    params = (data_center_id, *id_params, limit)
    with log_tool_call(
        "get_active_alarms_for_devices",
        data_center_id=data_center_id,
        device_ids=device_ids,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all("get_active_alarms_for_devices", sql, params)
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def get_device_alarms_by_time(
    data_center_id: int,
    device_id: int,
    start_time: datetime,
    end_time: datetime,
    severity: str | None = None,
    limit: int = 15,
) -> list[AlarmSummary]:
    """특정 장비 + 절대 datetime 범위 알람 조회 (cur 활성 + his 이력 UNION).
    get_device_alarms(최근 N시간)와 달리 start_time/end_time으로 절대 기간을 지정한다.
    """
    limit = _clamp(limit, 1, _LIMIT_MAX)
    with log_tool_call(
        "get_device_alarms_by_time",
        data_center_id=data_center_id,
        device_id=device_id,
        start_time=start_time,
        end_time=end_time,
        severity=severity,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all(
            "select_device_alarms_by_time",
            queries.SELECT_DEVICE_ALARMS_BY_TIME,
            (
                data_center_id, device_id, start_time, end_time, severity, severity,
                data_center_id, device_id, start_time, end_time, severity, severity,
                limit,
            ),
        )
        meta["result_count"] = len(rows)
        return [AlarmSummary(**r) for r in rows]


async def search_devices(
    data_center_id: int,
    device_nm: str | None = None,
    device_type_name: str | None = None,
    device_category_name: str | None = None,
    location: str | None = None,
    floor_id: int | None = None,
    zone_id: int | None = None,
    connected_ups: str | None = None,
    manufacturer_name: str | None = None,
    limit: int = 15,
) -> list[DeviceSearchResult]:
    """device_id 불명 시, 다중 조건 부분 문자열 검색 — data_center_id 외 조건이 모두 None이면 빈 리스트 반환 (전체 조회 방지).

    파라미터 선택 기준:
    - device_category_name: 상위 분류만. 유효값: 'HVAC', 'IT', 'Electric Power', 'BMS' 등.
      → 'Switchboard', 'CRAC', 'CRAH', 'Rack' 같은 구체 타입명을 여기에 넣지 말 것.
    - device_type_name: 구체 타입명. 예) 'Switchboard', 'CRAC', 'CRAH', 'Rack'.
      → 'HVAC', 'IT', 'Electric Power' 같은 상위 분류명을 여기에 넣지 말 것.
    - device_nm: 장비 이름 부분 문자열. 예) 'LV3', 'CH-E'.
    - location: 층·구역·방 이름 텍스트 LIKE 검색. 예) '3층', 'A구역', '서버실', 'B3F'.
    - floor_id: DB 내부 정수 ID (층 번호가 아님). 정확한 floor_id 값을 알고 있을 때만 사용.
    - zone_id: DB 내부 정수 ID. 정확한 zone_id 값을 알고 있을 때만 사용.
    중요: 사용자가 말한 타입명·카테고리명은 위 기준에 따라 올바른 파라미터에 매핑한 뒤 변환 없이 그대로 전달할 것.
      예) "Switchboard 장비" → device_type_name='Switchboard' (device_category_name 아님)
      예) "HVAC 카테고리"   → device_category_name='HVAC'
    중요: 사용자가 위치+카테고리, 이름+카테고리 등 다중 조건을 말하면 해당 파라미터를 모두 채울 것. 조건을 임의로 생략하지 말 것.
    중요: 결과가 0건이면 다른 인자 슬롯으로 재시도하거나(예: category↔type) 빈 결과를 그대로 보고할 것. 동일 인자 재호출 금지.
    """
    optional_args = (
        device_nm, device_type_name, device_category_name, location,
        floor_id, zone_id, connected_ups, manufacturer_name,
    )
    if all(v is None for v in optional_args):
        return []

    device_category_name, device_type_name = _normalize_category_type(
        device_category_name, device_type_name
    )
    limit = _clamp(limit, 1, _LIMIT_MAX)
    sql, dynamic_params = queries.build_search_devices_query(
        device_nm=device_nm,
        device_type_name=device_type_name,
        device_category_name=device_category_name,
        location=location,
        floor_id=floor_id,
        zone_id=zone_id,
        connected_ups=connected_ups,
        manufacturer_name=manufacturer_name,
    )
    # data_center_id 는 WHERE 첫 번째 조건(%s)에, limit 은 LIMIT %s 에 대응
    params = (data_center_id, *dynamic_params, limit)

    with log_tool_call(
        "search_devices",
        data_center_id=data_center_id,
        device_nm=device_nm,
        device_type_name=device_type_name,
        device_category_name=device_category_name,
        location=location,
        floor_id=floor_id,
        zone_id=zone_id,
        connected_ups=connected_ups,
        manufacturer_name=manufacturer_name,
        limit=limit,
    ) as meta:
        rows = await db.fetch_all("search_devices", sql, params)
        meta["result_count"] = len(rows)
        return [DeviceSearchResult(**r) for r in rows]
