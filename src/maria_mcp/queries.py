SELECT_DEVICE_INFO = """
SELECT
    data_center_id,
    device_id,
    device_nm                   AS device_name,
    device_category_name,
    device_type_name,
    device_model_name,
    manufacturer_name,
    maintenance_provider_name,
    location,
    enable_monitor,
    device_desc
FROM im_device_inf
WHERE data_center_id = %s
  AND device_id      = %s
"""


_ALARM_SUMMARY_COLS = """
    id                          AS alarm_id,
    alarm_policy_display_name   AS alarm_name,
    device_id,
    device_name,
    checkpoint_name,
    alarm_severity_name         AS severity,
    confirm_state_name          AS confirm_state,
    log_date,
    closed_date,
    message
"""


_ALARM_DETAIL_COLS = """
    id                          AS alarm_id,
    alarm_policy_display_name   AS alarm_name,
    device_id,
    device_name,
    checkpoint_id,
    checkpoint_name,
    alarm_severity_name         AS severity,
    confirm_state_name          AS confirm_state,
    log_date,
    message,
    acknowledged_date,
    acknowledged_message,
    closed_date,
    closed_message
"""


SELECT_ALARM_DETAIL = f"""
SELECT
{_ALARM_DETAIL_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND id             = %s
"""


SELECT_ACTIVE_ALARMS = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND closed_date IS NULL
  AND (%s IS NULL OR alarm_severity_name = %s)
ORDER BY log_date DESC
LIMIT %s
"""


SELECT_ALARMS_BY_TIME = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND log_date >= %s
  AND log_date <  %s
  AND (%s IS NULL OR alarm_severity_name = %s)
ORDER BY log_date DESC
LIMIT %s
"""


SELECT_DEVICE_ALARMS = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND device_id      = %s
  AND log_date >= (NOW() - INTERVAL %s HOUR)
ORDER BY log_date DESC
LIMIT %s
"""


# ── RCA 확장 tool (§10.1) ─────────────────────────────────────────────────────

_DEVICE_SUMMARY_COLS = """
    device_id,
    device_nm           AS device_name,
    device_category_name,
    device_type_name,
    location,
    enable_monitor
"""

SELECT_NEARBY_DEVICES = f"""
SELECT
{_DEVICE_SUMMARY_COLS}
FROM im_device_inf
WHERE data_center_id = %s
  AND zone_id = (
      SELECT zone_id
      FROM im_device_inf
      WHERE data_center_id = %s
        AND device_id      = %s
  )
  AND device_id != %s
  AND use_yn = 'Y'
ORDER BY device_category_name ASC, device_nm ASC
LIMIT %s
"""

SELECT_DEVICES_BY_TYPE = f"""
SELECT
{_DEVICE_SUMMARY_COLS}
FROM im_device_inf
WHERE data_center_id = %s
  AND (
      (%s IS NOT NULL AND device_category_name = %s)
      OR
      (%s IS NOT NULL AND device_type_name = %s)
  )
  AND use_yn = 'Y'
ORDER BY location ASC, device_nm ASC
LIMIT %s
"""

SELECT_DEVICES_BY_UPS = f"""
SELECT
{_DEVICE_SUMMARY_COLS}
FROM im_device_inf
WHERE data_center_id = %s
  AND connected_ups  = %s
  AND use_yn         = 'Y'
ORDER BY location ASC, device_nm ASC
LIMIT %s
"""

SELECT_ALARM_HISTORY = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_his
WHERE data_center_id = %s
  AND device_id      = %s
  AND log_date >= (NOW() - INTERVAL %s DAY)
ORDER BY log_date DESC
LIMIT %s
"""

SELECT_ACTIVE_ALARM_SUMMARY = """
SELECT
    COUNT(*)                    AS total_active,
    alarm_severity_name         AS severity,
    SUM(
        CASE WHEN confirm_state_name = '미확인' THEN 1 ELSE 0 END
    )                           AS unacknowledged_count
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND closed_date IS NULL
GROUP BY alarm_severity_name
"""

SELECT_NEARBY_ALARMS = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND device_id != %s
  AND closed_date IS NULL
  AND device_id IN (
      SELECT device_id
      FROM im_device_inf
      WHERE data_center_id = %s
        AND zone_id = (
            SELECT zone_id
            FROM im_device_inf
            WHERE data_center_id = %s
              AND device_id      = %s
        )
        AND device_id != %s
        AND use_yn = 'Y'
  )
ORDER BY log_date DESC
LIMIT %s
"""

SELECT_CHECKPOINT_ALARMS = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id   = %s
  AND checkpoint_name  = %s
  AND closed_date IS NULL
ORDER BY log_date DESC
LIMIT %s
"""


# ── search_devices 동적 쿼리 빌더 ──────────────────────────────────────────────

_DEVICE_SEARCH_COLS = """
    device_id,
    device_nm           AS device_name,
    device_category_name,
    device_type_name,
    location,
    enable_monitor,
    manufacturer_name,
    connected_ups
"""


def build_search_devices_query(
    device_nm: str | None,
    device_type_name: str | None,
    device_category_name: str | None,
    location: str | None,
    floor_id: int | None,
    zone_id: int | None,
    connected_ups: str | None,
    manufacturer_name: str | None,
) -> tuple[str, tuple]:
    """None이 아닌 파라미터만 WHERE 절에 포함하는 동적 쿼리를 생성한다.

    data_center_id 와 limit 은 호출 측에서 params 앞뒤에 추가한다.
    반환: (sql_fragment_without_data_center_and_limit, params_tuple)
    """
    conditions: list[str] = ["data_center_id = %s", "use_yn = 'Y'"]
    params: list = []

    # LIKE 조건: 문자열 부분 일치
    like_fields: list[tuple[str, str | None]] = [
        ("device_nm", device_nm),
        ("device_type_name", device_type_name),
        ("device_category_name", device_category_name),
        ("location", location),
        ("connected_ups", connected_ups),
        ("manufacturer_name", manufacturer_name),
    ]
    for col, val in like_fields:
        if val is not None:
            conditions.append(f"{col} LIKE %s")
            params.append(f"%{val}%")

    # exact 조건: 정수 ID
    if floor_id is not None:
        conditions.append("floor_id = %s")
        params.append(floor_id)
    if zone_id is not None:
        conditions.append("zone_id = %s")
        params.append(zone_id)

    where_clause = "\n  AND ".join(conditions)
    sql = f"""
SELECT
{_DEVICE_SEARCH_COLS}
FROM im_device_inf
WHERE {where_clause}
ORDER BY location ASC, device_nm ASC
LIMIT %s
"""
    return sql, tuple(params)


# ── 신규 tool ─────────────────────────────────────────────────────────────────

SELECT_ALARM_HISTORY_BY_POLICY = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_his
WHERE data_center_id       = %s
  AND alarm_policy_name    = %s
  AND log_date >= (NOW() - INTERVAL %s DAY)
ORDER BY log_date DESC
LIMIT %s
"""


SELECT_DEVICE_ALARMS_BY_TIME = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND device_id      = %s
  AND log_date >= %s
  AND log_date <  %s
  AND (%s IS NULL OR alarm_severity_name = %s)
UNION ALL
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_his
WHERE data_center_id = %s
  AND device_id      = %s
  AND log_date >= %s
  AND log_date <  %s
  AND (%s IS NULL OR alarm_severity_name = %s)
ORDER BY log_date DESC
LIMIT %s
"""


def build_active_alarms_for_devices_query(device_ids: list[int]) -> tuple[str, tuple]:
    """device_ids 개수만큼 IN 플레이스홀더를 동적으로 생성한다.

    반환되는 params 에 data_center_id 와 limit 은 미포함.
    호출 측에서 (data_center_id, *id_params, limit) 형태로 조립해야 한다.
    """
    placeholders = ", ".join(["%s"] * len(device_ids))
    sql = f"""
SELECT
{_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND device_id IN ({placeholders})
  AND closed_date IS NULL
ORDER BY log_date DESC
LIMIT %s
"""
    return sql, tuple(device_ids)
