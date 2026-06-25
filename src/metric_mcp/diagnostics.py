"""metric_mcp 진단 스크립트.

Druid 접속 확인 + datasource 존재 + 샘플 row + last_value unwrap 표현식 검증.

실행:
    uv run python -m metric_mcp.diagnostics
또는:
    uv run metric-mcp-diag
"""

from __future__ import annotations

import asyncio
from typing import Any

from . import druid
from .config import get_settings
from .logging_setup import configure_logging


def _kv(label: str, value: object) -> str:
    return f"  {label:<32} {value}"


# datasource 안에서 last_value (COMPLEX<serializablePairLongDouble>) 를 double 로
# 꺼내기 위한 후보 표현식. diagnostics 가 1개씩 시도해 성공한 첫 표현식을 안내한다.
_LAST_VALUE_UNWRAP_CANDIDATES = [
    "LATEST(last_value, 1024)",
    "ANY_VALUE(last_value)",
    "MAX(last_value)",
]


async def _select_one(sql: str, parameters: list[Any] | None = None) -> dict[str, Any] | None:
    rows = await druid.sql_query("diag", sql, parameters or [])
    return rows[0] if rows else None


async def _try_unwrap(expr: str) -> tuple[bool, str]:
    sql = (
        f"SELECT {expr} AS v FROM rollup_checkvalue_1min "
        "WHERE __time >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR "
        "GROUP BY __time LIMIT 1"
    )
    try:
        row = await _select_one(sql)
    except Exception as e:  # noqa: BLE001 — 진단 목적, 어떤 오류든 표시
        return False, f"FAIL ({type(e).__name__}: {e})"
    if row is None:
        return False, "EMPTY (최근 1시간 데이터 없음)"
    return True, f"OK value={row.get('v')}"


async def run() -> None:
    s = get_settings()
    print("=== metric_mcp 진단 ===")
    print(f"Druid: {s.druid_url}{s.druid_sql_path} (user={s.druid_user or '-'})")
    print()

    await druid.init_client()
    try:
        print("[접속 확인]")
        row = await _select_one("SELECT 1 AS ok")
        print(_kv("SELECT 1", row))
        print()

        print("[datasource 존재]")
        row = await _select_one(
            "SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_NAME = 'rollup_checkvalue_1min'"
        )
        exists = (row or {}).get("c", 0)
        print(_kv("rollup_checkvalue_1min", "OK" if exists else "NOT FOUND"))
        print()

        print("[최근 1시간 샘플 row]")
        row = await _select_one(
            "SELECT __time, data_center_id, device_id, checkpoint_id "
            "FROM rollup_checkvalue_1min "
            "WHERE __time >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR "
            "ORDER BY __time DESC LIMIT 1"
        )
        if row is None:
            print("  (최근 1시간 데이터 없음)")
        else:
            print(_kv("__time",          row.get("__time")))
            print(_kv("data_center_id",  row.get("data_center_id")))
            print(_kv("device_id",       row.get("device_id")))
            print(_kv("checkpoint_id",   row.get("checkpoint_id")))
        print()

        print("[last_value unwrap 표현식 검증]")
        winner: str | None = None
        for expr in _LAST_VALUE_UNWRAP_CANDIDATES:
            ok, msg = await _try_unwrap(expr)
            print(_kv(expr, msg))
            if ok and winner is None:
                winner = expr
        print()
        if winner:
            print(f"→ queries.SELECT_CHECKPOINT_HISTORY 에서 사용할 표현식: {winner}")
        else:
            print("→ 모든 후보 실패. queries.py 수정 필요.")
        print()

        print("OK — 진단 종료")
    finally:
        await druid.close_client()


def main() -> None:
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
