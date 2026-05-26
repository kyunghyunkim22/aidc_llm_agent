"""MCP tool 응답 크기 측정 스크립트.

[측정 항목]
1. 고정 오버헤드: tool 스키마 16개 (OpenAI function-calling 포맷)
   - 시스템 프롬프트는 현재 maria_mcp 에 미정의 → 0 tokens
2. 가변 부분: DB 쿼리 결과 JSON (LIMIT 변경하며 측정)
3. 잔여 컨텍스트: max_model_len(131072) - 오버헤드 - tool result

실행:
    uv run python scripts/bench_mcp_response_size.py

추정 token: chars / 4  (tiktoken 미설치 환경 대비 근사값)
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import asyncmy
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPTS_DIR))

MAX_MODEL_LEN = 131072
LIMITS = [100, 500, 1000, 5000, 10000]
DATA_CENTER_ID = int(os.getenv("TEST_DATA_CENTER_ID", "1"))

# ── 쿼리 정의 ──────────────────────────────────────────────────────────────────

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

Q_DEVICES = f"""
SELECT {_DEVICE_SEARCH_COLS}
FROM im_device_inf
WHERE data_center_id = %s
  AND use_yn = 'Y'
ORDER BY location ASC, device_nm ASC
LIMIT %s
"""

Q_ACTIVE_ALARMS = f"""
SELECT {_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_cur
WHERE data_center_id = %s
  AND closed_date IS NULL
ORDER BY log_date DESC
LIMIT %s
"""

Q_ALARM_HISTORY = f"""
SELECT {_ALARM_SUMMARY_COLS}
FROM fm_fault_alarm_his
WHERE data_center_id = %s
ORDER BY log_date DESC
LIMIT %s
"""

QUERIES: list[tuple[str, str, list]] = [
    ("im_device_inf    ", Q_DEVICES,        [DATA_CENTER_ID]),
    ("fm_fault_alarm_cur", Q_ACTIVE_ALARMS,  [DATA_CENTER_ID]),
    ("fm_fault_alarm_his", Q_ALARM_HISTORY,  [DATA_CENTER_ID]),
]


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _serialize(obj) -> str:
    def _default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, timedelta):
            return str(o)
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=_default)


def _tokens(text: str) -> int:
    return len(text) // 4


# ── 1단계: tool 스키마 오버헤드 측정 ────────────────────────────────────────────

async def measure_overhead() -> int:
    """FastMCP mcp 객체에서 tool 스키마를 읽고, run_test_questions 의 SYSTEM_PROMPT 를 합산."""
    from maria_mcp.server import mcp
    from run_test_questions import SYSTEM_PROMPT

    raw_tools = await mcp.list_tools()

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.parameters,
            },
        }
        for t in raw_tools
    ]

    schema_json = _serialize(openai_tools)
    schema_bytes = len(schema_json.encode("utf-8"))
    schema_tokens = _tokens(schema_json)

    prompt_bytes = len(SYSTEM_PROMPT.encode("utf-8"))
    prompt_tokens = _tokens(SYSTEM_PROMPT)

    total_overhead = schema_tokens + prompt_tokens

    print("=" * 65)
    print("1. 고정 오버헤드")
    print("=" * 65)
    print(f"  시스템 프롬프트  : {prompt_bytes:>10,} bytes / {prompt_tokens:>6,} tokens")
    print(f"  tool 스키마({len(raw_tools):>2}개): {schema_bytes:>10,} bytes / {schema_tokens:>6,} tokens")
    print(f"  합계             :              / {total_overhead:>6,} tokens")
    print(f"  남은 컨텍스트    :              / {MAX_MODEL_LEN - total_overhead:>6,} tokens "
          f"({(MAX_MODEL_LEN - total_overhead) / MAX_MODEL_LEN * 100:.1f}%)")
    print()

    return total_overhead


# ── 2단계: DB 쿼리 결과 크기 측정 ───────────────────────────────────────────────

async def measure_query_results(conn: asyncmy.Connection, overhead_tokens: int) -> None:
    available = MAX_MODEL_LEN - overhead_tokens

    print("=" * 65)
    print("2. 가변 부분 (DB 쿼리 결과 JSON)")
    print(f"   사용 가능 컨텍스트: {available:,} tokens (max {MAX_MODEL_LEN:,} - overhead {overhead_tokens:,})")
    print("=" * 65)

    col = f"{'테이블':<22} {'LIMIT':>7} {'rows':>7} {'bytes':>12} {'~tokens':>9}  {'가용대비':>8}  비고"
    print(col)
    print("-" * len(col))

    for label, sql, base_params in QUERIES:
        for limit in LIMITS:
            params = tuple(base_params) + (limit,)
            async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
                await cur.execute(sql, params)
                rows = list(await cur.fetchall())

            serialized = _serialize(rows)
            byte_count = len(serialized.encode("utf-8"))
            token_est = _tokens(serialized)
            ratio = token_est / available * 100
            note = "*** OVER ***" if token_est > available else ""

            print(
                f"{label:<22} {limit:>7,} {len(rows):>7,} {byte_count:>12,}"
                f" {token_est:>9,}  {ratio:>7.1f}%  {note}"
            )
        print()


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print(f"\n=== MCP 응답 크기 측정 (data_center_id={DATA_CENTER_ID}, max_model_len={MAX_MODEL_LEN:,}) ===\n")

    overhead_tokens = await measure_overhead()

    cfg = {
        "host":     os.environ["MARIA_HOST"],
        "port":     int(os.getenv("MARIA_PORT", "3306")),
        "user":     os.environ["MARIA_USER"],
        "password": os.environ["MARIA_PASSWORD"],
        "db":       os.environ["MARIA_DB"],
    }
    async with await asyncmy.connect(**cfg) as conn:
        await measure_query_results(conn, overhead_tokens)

    print("완료.")


if __name__ == "__main__":
    asyncio.run(main())
