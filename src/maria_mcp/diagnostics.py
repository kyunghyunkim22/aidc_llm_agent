"""maria_mcp 진단 스크립트.

DB 접속 확인 + 테스트 fixture가 발견할 샘플 ID 미리 보기 + 주요 카운트.

실행:
    uv run python -m maria_mcp.diagnostics
또는:
    uv run maria-mcp-diag   (pyproject.toml [project.scripts] 등록 시)
"""

from __future__ import annotations

import asyncio

from . import db
from .config import get_settings
from .logging_setup import configure_logging


async def _scalar(sql: str) -> int:
    async with db.cursor() as cur:
        await cur.execute(sql)
        row = await cur.fetchone()
    if row is None:
        return 0
    return int(next(iter(row.values())))


async def _one(sql: str) -> dict[str, object] | None:
    async with db.cursor() as cur:
        await cur.execute(sql)
        return await cur.fetchone()


def _kv(label: str, value: object) -> str:
    return f"  {label:<28} {value}"


async def run() -> None:
    s = get_settings()
    print("=== maria_mcp 진단 ===")
    print(f"DB: {s.maria_host}:{s.maria_port}/{s.maria_db} (user={s.maria_user})")
    print()

    await db.init_pool()
    try:
        print("[테이블 행 수]")
        print(_kv("im_device_inf",          await _scalar("SELECT COUNT(*) c FROM im_device_inf")))
        print(_kv("  active (use_yn='Y')",  await _scalar("SELECT COUNT(*) c FROM im_device_inf WHERE use_yn='Y'")))
        print(_kv("fm_fault_alarm_cur",     await _scalar("SELECT COUNT(*) c FROM fm_fault_alarm_cur")))
        print(_kv("  active (closed=NULL)", await _scalar("SELECT COUNT(*) c FROM fm_fault_alarm_cur WHERE closed_date IS NULL")))
        print(_kv("  최근 24h",              await _scalar("SELECT COUNT(*) c FROM fm_fault_alarm_cur WHERE log_date >= NOW() - INTERVAL 24 HOUR")))
        print(_kv("fm_fault_alarm_his",     await _scalar("SELECT COUNT(*) c FROM fm_fault_alarm_his")))
        print()

        print("[샘플 device — sample_device fixture가 사용할 값]")
        device = await _one(
            "SELECT data_center_id, device_id, device_nm "
            "FROM im_device_inf WHERE use_yn='Y' "
            "ORDER BY data_center_id, device_id LIMIT 1"
        )
        if device is None:
            print("  (없음)")
        else:
            print(_kv("data_center_id", device["data_center_id"]))
            print(_kv("device_id",      device["device_id"]))
            print(_kv("device_nm",      device["device_nm"]))
        print()

        print("[샘플 alarm — sample_alarm fixture가 사용할 값]")
        alarm = await _one(
            "SELECT data_center_id, id, device_id, alarm_severity_name, log_date "
            "FROM fm_fault_alarm_cur WHERE id IS NOT NULL "
            "ORDER BY log_date DESC LIMIT 1"
        )
        if alarm is None:
            print("  (없음)")
        else:
            print(_kv("data_center_id",      alarm["data_center_id"]))
            print(_kv("id (alarm_id)",       alarm["id"]))
            print(_kv("device_id",           alarm["device_id"]))
            print(_kv("alarm_severity_name", alarm["alarm_severity_name"]))
            print(_kv("log_date",            alarm["log_date"]))
        print()

        print("OK — 접속/조회 정상")
    finally:
        await db.close_pool()


def main() -> None:
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
