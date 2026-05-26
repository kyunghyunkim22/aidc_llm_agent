---
name: "verify-mcp-answer"
description: "Use this skill when the user wants to verify a maria_mcp tool answer (or LLM's tool-calling result) against the real MariaDB. Trigger phrases (Korean/English): 'LLM 답변 검증', 'MCP tool 결과 비교', 'DB 실측 비교', 'tool 호출 결과 맞는지 확인', 'verify mcp answer', 'compare LLM answer with DB'. Runs the corresponding query in src/maria_mcp/queries.py directly via asyncmy (bypassing the MCP server) and prints an expected-vs-actual diff. Do NOT use for: writing new MCP tools (use maria-mcp-build), benchmark runs (use scripts/bench_*), or non-DB verification."
---

# verify-mcp-answer — LLM/MCP 응답을 실 DB로 검증

`maria_mcp` tool 호출 결과가 실제 MariaDB 상태와 일치하는지,
**MCP 서버를 거치지 않고** `queries.py` 의 SQL을 직접 실행해 비교한다.

## 0. 사용 전 필독

- `src/maria_mcp/queries.py` — 모든 SQL 원본
- `src/maria_mcp/tools.py` — tool명 ↔ SQL 매핑 + 파라미터 변환 규칙 (`_clamp`, severity 이중 바인딩 등)
- `src/maria_mcp/db.py` — `init_pool` / `cursor` / `fetch_all` / `fetch_one`
- `.env` — `MARIA_*` 접속정보 (환경변수로만 로드, 하드코딩 금지)

## 1. 입력 파싱

다음 3가지 형태를 모두 받는다.

**형태 A — 슬래시 인자**
```
/verify-mcp-answer 질문="..." llm답변="get_active_alarms(data_center_id=1, severity='Critical')" 결과="47건"
```

**형태 B — 자유 텍스트** (description 자연어 트리거)
> "이 LLM 답변 DB랑 비교해줘: {원문 붙여넣기}"

**형태 C — 파일 참조**
```
/verify-mcp-answer @docs/test_results/20260514_162946.md
```
→ 파일에서 `tool명(인자=값)` 패턴과 "결과:" 블록을 추출.

파싱 결과로 다음 3가지를 확정한다.
1. **tool명** (예: `get_active_alarms`)
2. **호출 인자** dict (예: `{data_center_id: 1, severity: "Critical", limit: 15}`)
3. **LLM이 주장한 결과** (건수/내용 — 가능한 만큼)

애매하면 추측하지 말고 한 줄 질문으로 확인. **단, CLAUDE.md "확인 질문 없이 바로 실행" 규칙을 우선**하여, 인자가 비어 있을 때만 물어본다.

## 2. 실측 실행

**원칙**: MCP 서버를 띄우지 않고, `tools.py` 의 async 함수를 그대로 import 해서 호출한다.
`tools.py` 함수가 `_clamp`, severity 이중 바인딩, dynamic SQL 빌더(`build_search_devices_query` 등)를 이미 처리하므로
SQL 직접 실행보다 안전하다 (호출 변환 로직까지 함께 검증됨).

### 실행 스크립트 템플릿

ad-hoc 스크립트를 만들지 말고, **`uv run python -c`** 로 1회성 실행한다.
복잡한 비교가 필요하면 `scripts/verify_mcp_answer.py` 를 만들어도 되지만,
**한 번 만들면 다음 호출에서도 재사용** 하도록 인자화한다.

```bash
uv run python -c "
import asyncio, json
from maria_mcp import db, tools

async def main():
    await db.init_pool()
    try:
        # ↓ 파싱 결과로 동적 치환
        result = await tools.get_active_alarms(data_center_id=1, severity='Critical', limit=15)
        print(json.dumps([r.model_dump(mode='json') for r in result], default=str, ensure_ascii=False, indent=2))
        print(f'__COUNT__={len(result)}')
    finally:
        await db.close_pool()

asyncio.run(main())
"
```

단건 조회(`get_device_info`, `get_alarm_info`) 는 `model_dump()` 한 dict 또는 `None` 처리.

## 3. 비교 & 출력 포맷

다음 구조로 결과를 한 번에 출력한다.

```markdown
## verify-mcp-answer 결과

**질문**: {원 질문}
**LLM 답변**: {요약}
**호출 추정**: `tool명(인자=값, ...)`

### 실측 vs LLM
| 항목 | LLM 주장 | DB 실측 | 일치 |
|------|---------|---------|------|
| 건수 | 47 | 51 | ❌ |
| 첫 alarm_id | 12345 | 12345 | ✅ |
| severity 분포 | Critical 30 / Major 17 | Critical 33 / Major 18 | ❌ |

### 판정
**MISMATCH** — 건수 차이 4건, severity 분포 불일치.
원인 추정: LLM 이 `limit=15` 의 잘림을 무시하고 전수 응답으로 해석한 듯.

### 실측 원본 (요약 5건)
- id=12345 severity=Critical log_date=2026-05-21 10:01 ...
- ...

### 비교 명령 재현
\`\`\`bash
uv run python -c "..."  # 위 스크립트 그대로
\`\`\`
```

판정은 반드시 **PASS / MISMATCH / PARTIAL** 셋 중 하나로 명시.

## 4. 결과 저장

- 기본 파일명: `docs/test_results/{YYYYMMDD_HHMMSS}_verify_{tool명}.md` (timestamp prefix 규칙 — CLAUDE.md 참고)
- 사용자가 별도 경로 지정 시 그대로 사용
- 동일 파일명 충돌 시 `_2`, `_3` suffix

저장 후 사용자에게는 파일 경로 한 줄 + 판정 한 줄만 회신.

## 5. tool ↔ queries 매핑 빠른 참조

| tool명 | SQL | 비고 |
|--------|-----|------|
| get_device_info | SELECT_DEVICE_INFO | 단건 |
| get_alarm_info | SELECT_ALARM_DETAIL | 단건 |
| get_active_alarms | SELECT_ACTIVE_ALARMS | severity 이중 바인딩 |
| get_alarms_by_time | SELECT_ALARMS_BY_TIME | severity 이중 바인딩 |
| get_device_alarms | SELECT_DEVICE_ALARMS | hours 기준 |
| list_nearby_devices | SELECT_NEARBY_DEVICES | zone_id 서브쿼리 |
| list_devices_by_type | SELECT_DEVICES_BY_TYPE | category OR type |
| list_devices_by_ups | SELECT_DEVICES_BY_UPS | |
| get_alarm_history | SELECT_ALARM_HISTORY | his 테이블 |
| get_active_alarm_summary | SELECT_ACTIVE_ALARM_SUMMARY | severity 집계 |
| get_nearby_alarms | SELECT_NEARBY_ALARMS | |
| get_checkpoint_alarms | SELECT_CHECKPOINT_ALARMS | |
| search_devices | build_search_devices_query (동적) | None 인자 제외 |
| get_alarm_history_by_policy | SELECT_ALARM_HISTORY_BY_POLICY | his 테이블 |
| get_active_alarms_for_devices | build_active_alarms_for_devices_query (동적) | IN 절 |
| get_device_alarms_by_time | SELECT_DEVICE_ALARMS_BY_TIME | cur+his UNION |

스펙 변경으로 tool/SQL이 추가/제거되면 이 표도 동기화.

## 6. 주의

- `_clamp(limit, 1, 15)` 가 적용되므로 LLM 이 `limit=100` 으로 호출했다고 주장해도 실측은 15에서 잘림 → MISMATCH가 아니라 정상 동작이다. 판정 시 명시.
- `data_center_id` 누락 시 절대 추측 금지 → 사용자에게 확인.
- DB 접속 실패 시 `.env` 의 `MARIA_*` 확인 안내 후 종료. 절대 모킹/우회 금지.
- 시간 비교 시 LLM 응답의 timezone 표기와 DB 의 `log_date` (naive datetime) 가 다를 수 있음 → 차이는 UTC/KST 변환 후 비교.
