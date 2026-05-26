"""vLLM tool result 크기별 컨텍스트 한계 측정 스크립트.

[측정 항목]
- 구성별 토큰 분해: system_prompt / user_msg / tool_call / tool_result / 합계
- vLLM 실제 보고 input_tokens (prompt_tokens)
- finish_reason 및 응답 텍스트 (잘림 위치 확인)
- HTTP 400 발생 시점 (vLLM 요청 거부 한계)

실행:
    uv run python scripts/bench_vllm_context.py &
    tail -f /tmp/bench_vllm_context.log
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import asyncmy
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(ROOT / ".env")

from run_test_questions import SYSTEM_PROMPT  # noqa: E402

# ── 설정 ──────────────────────────────────────────────────────────────────────

MAX_MODEL_LEN  = 131_072
LIMITS         = [100, 500, 1000, 5000, 10000]
DATA_CENTER_ID = int(os.getenv("TEST_DATA_CENTER_ID", "1"))
LLM_BASE_URL   = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_MODEL      = os.environ.get("LLM_MODEL",    "google/gemma-4-e4b-it")
LLM_API_KEY    = os.environ.get("LLM_API_KEY",  "EMPTY")

LOG_FILE    = Path("/tmp/bench_vllm_context.log")
REPORT_FILE = ROOT / "docs" / "test_results" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_bench_vllm_context.md"

# ── 로거 설정 ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("bench")

# ── 쿼리 ──────────────────────────────────────────────────────────────────────

Q_ACTIVE_ALARMS = """
SELECT id AS alarm_id, alarm_policy_display_name AS alarm_name,
    device_id, device_name, checkpoint_name,
    alarm_severity_name AS severity, confirm_state_name AS confirm_state,
    log_date, closed_date, message
FROM fm_fault_alarm_cur
WHERE data_center_id = %s AND closed_date IS NULL
ORDER BY log_date DESC LIMIT %s
"""

Q_ALARM_HISTORY = """
SELECT id AS alarm_id, alarm_policy_display_name AS alarm_name,
    device_id, device_name, checkpoint_name,
    alarm_severity_name AS severity, confirm_state_name AS confirm_state,
    log_date, closed_date, message
FROM fm_fault_alarm_his
WHERE data_center_id = %s
ORDER BY log_date DESC LIMIT %s
"""

Q_DEVICES = """
SELECT device_id, device_nm AS device_name, device_category_name,
    device_type_name, location, enable_monitor, manufacturer_name, connected_ups
FROM im_device_inf
WHERE data_center_id = %s AND use_yn = 'Y'
ORDER BY location ASC, device_nm ASC LIMIT %s
"""

QUERY_CASES: list[tuple[str, str, str]] = [
    ("fm_fault_alarm_cur", "get_active_alarms", Q_ACTIVE_ALARMS),
    ("fm_fault_alarm_his", "get_alarm_history", Q_ALARM_HISTORY),
    ("im_device_inf",      "search_devices",    Q_DEVICES),
]

USER_MSG = "현재 알람/장비 목록을 조회해서 요약해줘."

# ── 직렬화 / 토큰 추정 ─────────────────────────────────────────────────────────

def _serialize(obj) -> str:
    def _default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, timedelta):
            return str(o)
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=_default)


def _est(text: str) -> int:
    """chars / 4 근사 토큰 추정."""
    return len(text) // 4


# ── vLLM 호출 ─────────────────────────────────────────────────────────────────

def _build_messages(tool_name: str, tool_result_json: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": USER_MSG},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_bench_01",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps({"data_center_id": DATA_CENTER_ID}),
                },
            }],
        },
        {
            "role": "tool",
            "tool_call_id": "call_bench_01",
            "content": tool_result_json,
        },
    ]


async def call_vllm(client: httpx.AsyncClient, tool_name: str, tool_result_json: str) -> dict:
    messages = _build_messages(tool_name, tool_result_json)
    resp = await client.post(
        f"{LLM_BASE_URL}/chat/completions",
        json={"model": LLM_MODEL, "messages": messages, "temperature": 0},
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        timeout=180.0,
    )
    resp.raise_for_status()
    return resp.json()


# ── 결과 레코드 ────────────────────────────────────────────────────────────────

class CaseResult:
    def __init__(self, table: str, tool: str, limit: int, actual_rows: int, result_json: str):
        self.table       = table
        self.tool        = tool
        self.limit       = limit
        self.actual_rows = actual_rows
        self.result_bytes = len(result_json.encode("utf-8"))

        # 구성별 추정 토큰
        self.tok_system      = _est(SYSTEM_PROMPT)
        self.tok_user        = _est(USER_MSG)
        self.tok_tool_call   = _est(json.dumps({"name": tool, "arguments": json.dumps({"data_center_id": DATA_CENTER_ID})}))
        self.tok_tool_result = _est(result_json)
        self.tok_est_total   = self.tok_system + self.tok_user + self.tok_tool_call + self.tok_tool_result

        # vLLM 실제 보고값
        self.prompt_tokens   = 0
        self.completion_tokens = 0
        self.finish_reason   = ""
        self.response_text   = ""
        self.error           = ""
        self.elapsed         = 0.0


# ── 측정 ──────────────────────────────────────────────────────────────────────

async def run_case(
    conn: asyncmy.Connection,
    client: httpx.AsyncClient,
    table: str, tool: str, sql: str, limit: int,
) -> CaseResult:
    async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
        await cur.execute(sql, (DATA_CENTER_ID, limit))
        rows = list(await cur.fetchall())

    result_json = _serialize(rows)
    r = CaseResult(table, tool, limit, len(rows), result_json)

    log.info(
        "[%s] LIMIT=%d rows=%d result_bytes=%d est_tokens=%d",
        table, limit, len(rows), r.result_bytes, r.tok_est_total,
    )

    t0 = time.monotonic()
    try:
        resp = await call_vllm(client, tool, result_json)
        r.elapsed           = time.monotonic() - t0
        usage               = resp.get("usage", {})
        r.prompt_tokens     = usage.get("prompt_tokens", 0)
        r.completion_tokens = usage.get("completion_tokens", 0)
        choice              = resp["choices"][0]
        r.finish_reason     = choice.get("finish_reason", "?")
        r.response_text     = (choice.get("message") or {}).get("content") or ""

        log.info(
            "[%s] LIMIT=%d prompt_tokens=%d completion_tokens=%d finish=%s elapsed=%.1fs",
            table, limit, r.prompt_tokens, r.completion_tokens, r.finish_reason, r.elapsed,
        )
        if r.finish_reason == "length":
            log.warning("[%s] LIMIT=%d finish=length → 응답 잘림 (max_tokens=512 도달)", table, limit)
        log.info("[%s] LIMIT=%d response_preview=%s", table, limit, r.response_text[:200].replace("\n", " "))

    except httpx.HTTPStatusError as e:
        r.elapsed = time.monotonic() - t0
        r.error   = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        log.error("[%s] LIMIT=%d %s", table, limit, r.error)
    except Exception as e:
        r.elapsed = time.monotonic() - t0
        r.error   = str(e)
        log.error("[%s] LIMIT=%d ERR: %s", table, limit, r.error)

    return r


# ── 리포트 작성 ────────────────────────────────────────────────────────────────

def write_report(results: list[CaseResult]) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# vLLM 컨텍스트 한계 측정 리포트",
        f"",
        f"- 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- LLM: `{LLM_BASE_URL}` / `{LLM_MODEL}`",
        f"- max_model_len: {MAX_MODEL_LEN:,}",
        f"- 로그: `{LOG_FILE}`",
        f"",
        "---",
        "",
        "## 토큰 구성 (추정)",
        "",
        f"| 항목 | 추정 tokens |",
        f"|------|------------|",
        f"| 시스템 프롬프트 | {_est(SYSTEM_PROMPT):,} |",
        f"| 사용자 메시지 | {_est(USER_MSG):,} |",
        f"| tool_call (assistant) | ~10 |",
        f"| **tool_result (가변)** | **쿼리별 상이** |",
        "",
        "---",
        "",
        "## 측정 결과",
        "",
        "| 테이블 | LIMIT | rows | result bytes | est tokens | prompt_tokens(vLLM) | completion | finish | ctx% | 상태 |",
        "|--------|------:|-----:|-------------:|-----------:|--------------------:|-----------:|--------|-----:|------|",
    ]

    for r in results:
        if r.error:
            status = f"❌ {r.error[:60]}"
            ctx_pct = f"{r.tok_est_total/MAX_MODEL_LEN*100:.1f}% (est)"
        else:
            over = " 🚨OVER" if r.prompt_tokens > MAX_MODEL_LEN else ""
            status = "✅ OK" if r.finish_reason == "stop" else f"⚠️ {r.finish_reason}"
            ctx_pct = f"{r.prompt_tokens/MAX_MODEL_LEN*100:.1f}%{over}"

        lines.append(
            f"| {r.table} | {r.limit:,} | {r.actual_rows:,} | {r.result_bytes:,} "
            f"| {r.tok_est_total:,} | {r.prompt_tokens:,} | {r.completion_tokens:,} "
            f"| {r.finish_reason or 'ERR'} | {ctx_pct} | {status} |"
        )

    lines += ["", "---", "", "## 응답 내용 (잘림 여부 확인)", ""]

    prev_table = None
    for r in results:
        if r.table != prev_table:
            lines.append(f"### {r.table}")
            prev_table = r.table

        lines.append(f"#### LIMIT={r.limit:,} / finish={r.finish_reason or 'ERR'}")
        if r.error:
            lines.append(f"```\nERROR: {r.error}\n```")
        elif r.response_text:
            lines.append(f"```\n{r.response_text}\n```")
        else:
            lines.append("_(응답 없음)_")
        lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    log.info("리포트 저장: %s", REPORT_FILE)


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    log.info("=== 측정 시작: max_model_len=%d ===", MAX_MODEL_LEN)
    log.info("LLM: %s / %s", LLM_BASE_URL, LLM_MODEL)
    log.info("LIMITS: %s", LIMITS)

    db_cfg = {
        "host":     os.environ["MARIA_HOST"],
        "port":     int(os.getenv("MARIA_PORT", "3306")),
        "user":     os.environ["MARIA_USER"],
        "password": os.environ["MARIA_PASSWORD"],
        "db":       os.environ["MARIA_DB"],
    }

    results: list[CaseResult] = []

    async with await asyncmy.connect(**db_cfg) as conn, httpx.AsyncClient() as http:
        total = len(QUERY_CASES) * len(LIMITS)
        idx = 0
        for table, tool, sql in QUERY_CASES:
            for limit in LIMITS:
                idx += 1
                log.info("--- (%d/%d) %s LIMIT=%d ---", idx, total, table, limit)
                r = await run_case(conn, http, table, tool, sql, limit)
                results.append(r)

    write_report(results)
    log.info("=== 측정 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
