from datetime import datetime, timedelta, timezone
from typing import Any

from . import druid, queries
from .logging_setup import log_tool_call
from .models import CheckpointHistory, CheckpointPoint

# 닫힌 구간 [time - 10min, time] (양 끝 포함, 1분 rollup이므로 최대 11 slot)
_WINDOW = timedelta(minutes=10)


def _parse_time(time_str: str) -> datetime:
    """ISO 8601 문자열 → tz-aware datetime (UTC).

    'Z' suffix 도 허용. tz가 없으면 UTC 로 간주.
    """
    raw = time_str.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_iso(dt: datetime) -> str:
    """Druid TIME_PARSE 호환 ISO 8601 (UTC, 초 단위)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_point(row: dict[str, Any]) -> CheckpointPoint:
    raw_time = row.get("__time")
    # Druid 는 __time 을 epoch millis (int) 또는 ISO 문자열로 반환할 수 있다.
    if isinstance(raw_time, (int, float)):
        ts = datetime.fromtimestamp(raw_time / 1000.0, tz=timezone.utc)
    elif isinstance(raw_time, str):
        ts = _parse_time(raw_time)
    else:
        raise ValueError(f"unexpected __time type: {type(raw_time).__name__}")

    return CheckpointPoint(
        time=ts,
        last_value=row.get("last_value"),
        max_value=row.get("max_value"),
        min_value=row.get("min_value"),
        sum_value=row.get("sum_value"),
    )


async def get_checkpoint_history(
    data_center_id: str,
    device_id: str,
    checkpoint_id: str,
    time: str,
) -> CheckpointHistory:
    """한 체크포인트의 최근 10분 (닫힌 구간) 1분 단위 시계열."""
    end = _parse_time(time)
    start = end - _WINDOW

    with log_tool_call(
        "get_checkpoint_history",
        data_center_id=data_center_id,
        device_id=device_id,
        checkpoint_id=checkpoint_id,
        time=time,
    ) as meta:
        rows = await druid.sql_query(
            "select_checkpoint_history",
            queries.SELECT_CHECKPOINT_HISTORY,
            [data_center_id, device_id, checkpoint_id, _to_iso(start), _to_iso(end)],
        )
        points = [_row_to_point(r) for r in rows]
        meta["result_count"] = len(points)
        return CheckpointHistory(
            data_center_id=data_center_id,
            device_id=device_id,
            checkpoint_id=checkpoint_id,
            range_start=start,
            range_end=end,
            points=points,
        )
