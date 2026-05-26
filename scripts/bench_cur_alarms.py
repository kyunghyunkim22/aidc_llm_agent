import asyncio, json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import asyncmy, httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")
# from run_test_questions import SYSTEM_PROMPT

LLM_BASE_URL   = os.environ["LLM_BASE_URL"]
LLM_MODEL      = os.environ["LLM_MODEL"]
LLM_API_KEY    = os.environ.get("LLM_API_KEY", "EMPTY")
TOKENIZE_URL   = LLM_BASE_URL.rstrip("/").removesuffix("/v1") + "/tokenize"
DATA_CENTER_ID = int(os.getenv("TEST_DATA_CENTER_ID", "1"))
LIMITS         = [int(x) for x in os.getenv("TEST_LIMITS", "50,100,150").split(",")]
MAX_MODEL_LEN  = int(os.getenv("MAX_MODEL_LEN", "32768"))

Q = """
SELECT id AS alarm_id, alarm_policy_display_name AS alarm_name,
    device_id, device_name, checkpoint_name,
    alarm_severity_name AS severity, confirm_state_name AS confirm_state,
    log_date, closed_date, message
FROM fm_fault_alarm_cur
WHERE data_center_id = %s AND closed_date IS NULL
ORDER BY log_date DESC LIMIT %s
"""

SYSTEM_PROMPT = """
[필수 행동 규칙]
1. 사용자 메시지를 받으면 인사말, 자기소개, 설명 없이 즉시 도구를 호출하라.
2. 도구 호출 결과를 받은 후에만 텍스트로 답변하라.
3. 파라미터가 불명확할 때 절대 되묻지 말고 아래 기본값으로 즉시 호출하라.
   - data_center_id=1
   - limit=15
   - 시간 범위 미지정 시 start_time=지금으로부터 24시간 전, end_time=지금
4. 사용자가 명시한 장비 타입명·카테고리명은 변환·추론 없이 그대로 파라미터로 전달하라.
   (예: 사용자가 "CRAC"이라 했으면 "CRAH"로 바꾸지 말 것)
5. 다중 조건 질문은 모든 조건을 빠짐없이 파라미터에 포함하라.
6. 특정 장비의 "주변 구역 알람" 또는 "같은 구역 알람"을 조회할 때는 반드시 get_nearby_alarms(device_id)를 사용하라.
   존재하지 않는 tool(예: list_nearby_alarms)을 호출하지 말 것.
7. 검색 결과가 다수(2개 이상)일 때 모든 항목을 반복 분석하지 말고, 첫 번째 항목 1개만 선택하여 상세 분석하라.

[역할]
DCIM 데이터센터 장비·알람 조회 에이전트. 도구 결과를 한국어로 간결하게 요약한다.
"""

USER_MSG  = "현재 알람/장비 목록을 조회해줘."
TOOL_CALL = json.dumps({"name": "get_active_alarms", "arguments": json.dumps({"data_center_id": DATA_CENTER_ID})})

def serialize(obj):
    def d(o):
        if isinstance(o, datetime): return o.isoformat()
        if isinstance(o, timedelta): return str(o)
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=d)

async def tok(client, text):
    r = await client.post(TOKENIZE_URL,
        json={"model": LLM_MODEL, "prompt": text},
        headers={"Authorization": f"Bearer {LLM_API_KEY}"})
    r.raise_for_status()
    return r.json()["count"]

async def run_case(conn, client, limit):
    async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
        await cur.execute(Q, (DATA_CENTER_ID, limit))
        rows = list(await cur.fetchall())

    result_json  = serialize(rows)
    result_bytes = len(result_json.encode("utf-8"))

    t_sys  = await tok(client, SYSTEM_PROMPT)
    t_user = await tok(client, USER_MSG)
    t_tc   = await tok(client, TOOL_CALL)
    t_tr   = await tok(client, result_json)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": USER_MSG},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "call_bench_01", "type": "function",
                         "function": {"name": "get_active_alarms",
                                      "arguments": json.dumps({"data_center_id": DATA_CENTER_ID})}}]},
        {"role": "tool", "tool_call_id": "call_bench_01", "content": result_json},
    ]

    print(f"[LIMIT={limit}] DB rows={len(rows)} tool_result={t_tr:,} tokens 전송 중...", flush=True)
    t0 = time.monotonic()
    try:
        resp = await client.post(f"{LLM_BASE_URL}/chat/completions",
            json={"model": LLM_MODEL, "messages": messages, "temperature": 0},
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            timeout=3600.0)
        elapsed = time.monotonic() - t0

        if resp.status_code != 200:
            print(f"[LIMIT={limit}] HTTP {resp.status_code}: {resp.text[:200]}", flush=True)
            return {"limit": limit, "rows": len(rows), "result_bytes": result_bytes,
                    "t_sys": t_sys, "t_user": t_user, "t_tc": t_tc, "t_tr": t_tr,
                    "prompt_tokens": 0, "completion_tokens": 0,
                    "finish": "ERR", "response_text": "",
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}", "elapsed": elapsed}

        data          = resp.json()
        usage         = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion    = usage.get("completion_tokens", 0)
        finish        = data["choices"][0].get("finish_reason", "?")
        response_text = (data["choices"][0].get("message") or {}).get("content") or ""
        print(f"[LIMIT={limit}] 완료 prompt={prompt_tokens:,} completion={completion:,} finish={finish} elapsed={elapsed:.1f}s", flush=True)

        return {"limit": limit, "rows": len(rows), "result_bytes": result_bytes,
                "t_sys": t_sys, "t_user": t_user, "t_tc": t_tc, "t_tr": t_tr,
                "prompt_tokens": prompt_tokens, "completion_tokens": completion,
                "finish": finish, "response_text": response_text, "error": "", "elapsed": elapsed}

    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"[LIMIT={limit}] ERR: {e}", flush=True)
        return {"limit": limit, "rows": len(rows), "result_bytes": result_bytes,
                "t_sys": t_sys, "t_user": t_user, "t_tc": t_tc, "t_tr": t_tr,
                "prompt_tokens": 0, "completion_tokens": 0,
                "finish": "ERR", "response_text": "", "error": str(e), "elapsed": elapsed}

def write_report(results):
    lines = [
        "# vLLM 컨텍스트 측정 — fm_fault_alarm_cur LIMIT 50/100/150",
        "",
        f"- 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- LLM: `{LLM_BASE_URL}` / `{LLM_MODEL}`",
        f"- max_model_len: {MAX_MODEL_LEN:,}",
        "",
        "---",
        "",
        "## 입력 구성 실제 내용",
        "",
        f"### 시스템 프롬프트 — {results[0]['t_sys']:,} tokens",
        "```",
        SYSTEM_PROMPT,
        "```",
        "",
        f"### 사용자 메시지 — {results[0]['t_user']:,} tokens",
        "```",
        USER_MSG,
        "```",
        "",
        f"### tool_call — {results[0]['t_tc']:,} tokens",
        "```json",
        TOOL_CALL,
        "```",
        "",
        "---",
        "",
        "## 토큰 사용량 상세",
        "",
        "| LIMIT | rows | result bytes | sys | user | tool_call | tool_result | 템플릿OH | prompt합계(vLLM) | completion | finish | ctx% | 소요시간 | 상태 |",
        "|------:|-----:|-------------:|----:|-----:|----------:|------------:|---------:|----------------:|-----------:|--------|-----:|--------:|------|",
    ]

    for r in results:
        if r["error"]:
            status = f"❌ {r['error'][:50]}"
            ctx = f"{(r['t_sys']+r['t_user']+r['t_tc']+r['t_tr'])/MAX_MODEL_LEN*100:.1f}%(est)"
            oh = "-"
            pt = "-"
            ct = "-"
        else:
            oh     = r["prompt_tokens"] - (r["t_sys"] + r["t_user"] + r["t_tc"] + r["t_tr"])
            status = "✅ OK" if r["finish"] == "stop" else f"⚠️ {r['finish']}"
            ctx    = f"{r['prompt_tokens']/MAX_MODEL_LEN*100:.1f}%"
            pt     = f"{r['prompt_tokens']:,}"
            ct     = f"{r['completion_tokens']:,}"
            oh     = f"{oh:,}"

        lines.append(
            f"| {r['limit']:,} | {r['rows']:,} | {r['result_bytes']:,} "
            f"| {r['t_sys']:,} | {r['t_user']:,} | {r['t_tc']:,} | {r['t_tr']:,} "
            f"| {oh} | {pt} | {ct} | {r['finish']} | {ctx} | {r['elapsed']:.1f}s | {status} |"
        )

    lines += ["", "---", "", "## LLM 응답 전문", ""]

    for r in results:
        lines.append(f"### LIMIT={r['limit']} / finish={r['finish']} / elapsed={r['elapsed']:.1f}s")
        if r["error"]:
            lines += [f"```", f"ERROR: {r['error']}", "```", ""]
        elif r["response_text"]:
            lines += ["```", r["response_text"], "```", ""]
        else:
            lines += ["_(응답 없음)_", ""]

    out = ROOT / "docs" / "test_results" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_bench_cur_50_100_150.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n리포트 저장: {out}", flush=True)

async def main():
    print(f"=== fm_fault_alarm_cur LIMIT={LIMITS} 측정 시작 (max={MAX_MODEL_LEN:,}) ===", flush=True)
    db_cfg = {"host": os.environ["MARIA_HOST"], "port": int(os.getenv("MARIA_PORT","3306")),
              "user": os.environ["MARIA_USER"], "password": os.environ["MARIA_PASSWORD"],
              "db": os.environ["MARIA_DB"]}

    results = []
    async with await asyncmy.connect(**db_cfg) as conn, httpx.AsyncClient() as http:
        for limit in LIMITS:
            r = await run_case(conn, http, limit)
            results.append(r)

    write_report(results)
    print("=== 완료 ===", flush=True)

asyncio.run(main())
