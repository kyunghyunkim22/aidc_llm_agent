# verify-mcp-answer 결과 — get_active_alarms (Critical)

- **실행일시**: 2026-05-22 13:52:07
- **질문**: 데이터센터 1의 Critical 활성 알람 알려줘
- **LLM 답변**: `get_active_alarms(data_center_id=1, severity='Critical')` → **47건**
- **호출 추정**: `get_active_alarms(data_center_id=1, severity='Critical', limit=15)`

## 판정

**MISMATCH** — LLM 주장 47건 vs DB 실측 **7건** (40건 과대 보고, 약 6.7배).

원인 추정: **환각(hallucination)**. 어떤 severity 조합으로도 47이 나오지 않으며,
정답 숫자 7 앞에 임의 자리(4)가 붙은 형태로 보임.
LLM이 tool 결과를 실제로 읽지 않았거나, 응답 생성 시 숫자를 임의 변형한 것으로 추정.

## 실측 vs LLM

| 항목 | LLM 주장 | DB 실측 | 일치 |
|------|---------|---------|------|
| Critical 건수 | 47 | 7 | ❌ |
| limit 도달 여부 | (불명) | 미도달 (7 < 15) | — |
| 전체 Critical (limit 무시) | — | 7 | (실측 = tool 결과) |

## 데이터센터 1 전체 severity 분포 (참고)

| severity | 건수 |
|----------|------|
| Warning | 734 |
| **Critical** | **7** |
| Fatal | 2 |
| Minor | 1 |
| **합계** | **744** |

→ LLM이 만약 전체 active(744)나 Warning(734)을 혼동했더라도 47과 일치하는 조합 없음 → 단순 환각.

## 실측 원본 — Critical 7건 전체

| # | alarm_id | device_name | alarm_name | confirm_state | log_date |
|---|----------|-------------|------------|---------------|----------|
| 1 | 5797064 | A WING 고온 냉각탑-4-1 | 냉각탑 - 인버터 알람 | 확인 | 2026-02-04 10:11:12 |
| 2 | 5795219 | CRAH-8F A-201-12 | 냉방기 - 통합알람 | 확인 | 2026-01-26 13:07:46 |
| 3 | 5794887 | B WING 저온 냉각탑-2 | 저온냉각탑 수조 저수위 | 확인 | 2026-01-21 17:31:13 |
| 4 | 5732251 | UPS-B4-A#01 | upsAlarmGeneralWarning | 확인 | 2025-10-17 13:55:34 |
| 5 | 5732249 | UPS-B4-A#02 | upsAlarmGeneralWarning | 확인 | 2025-10-17 13:35:21 |
| 6 | 5732221 | CRAC-5F A-101-02 | CRAH - 냉수밸브피드백센서알람 | 확인 | 2025-10-17 13:26:26 |
| 7 | 5732222 | CRAC-5F A-101-02 | 냉방기 - 통합알람 | 확인 | 2025-10-17 13:26:26 |

## 비교 명령 재현

```bash
# tool 경유
uv run python -c "
import asyncio, json
from maria_mcp import db, tools

async def main():
    await db.init_pool()
    try:
        result = await tools.get_active_alarms(data_center_id=1, severity='Critical', limit=15)
        print(json.dumps([r.model_dump(mode='json') for r in result], default=str, ensure_ascii=False, indent=2))
        print(f'__COUNT__={len(result)}')
    finally:
        await db.close_pool()

asyncio.run(main())
"

# 순수 SQL COUNT(*) — limit 영향 없는 진짜 총 개수
uv run python -c "
import asyncio
from maria_mcp import db

async def main():
    await db.init_pool()
    try:
        async with db.cursor() as cur:
            await cur.execute(
                'SELECT COUNT(*) AS total FROM fm_fault_alarm_cur '
                'WHERE data_center_id = %s AND alarm_severity_name = %s AND closed_date IS NULL',
                (1, 'Critical')
            )
            print(await cur.fetchone())
    finally:
        await db.close_pool()

asyncio.run(main())
"
```
