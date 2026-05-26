# verify-mcp-answer 결과 — get_active_alarms

- **실행일시**: 2026-05-22 13:48:09
- **검증 모드**: 실측 only (LLM 답변 비교 대상 없음)
- **호출**: `get_active_alarms(data_center_id=1, severity=None, limit=15)`
- **가정**: `data_center_id=1` (기존 테스트 관습값, 5회 사용 이력)

## 판정

**PASS (실측 정상 수행)** — 15건 반환, `_clamp(limit, 1, 15)` 상한값 동작.

## 실측 요약

| 항목 | 값 |
|------|---|
| 총 건수 | 15 (limit 상한 도달) |
| Critical | 1 |
| Warning | 14 |
| 미확인 | 8 |
| 확인 | 7 |
| 최신 log_date | 2026-02-05 17:03:17 |
| 최오래 log_date | 2026-02-04 09:47:19 |

> 모든 알람이 2026-02-04 ~ 2026-02-05 사이에 집중. 현재 시점(2026-05-22) 기준 약 3.5개월 전 알람들이 여전히 active(`closed_date IS NULL`) 상태로 남아있음. → DCIM 운영 측면에서 stale alarm 정리 누락 가능성. (검증 범위 외 — 참고용 관찰)

## 실측 원본 (15건 전체)

| # | alarm_id | severity | device_name | alarm_name | confirm_state | log_date |
|---|----------|----------|-------------|------------|---------------|----------|
| 1 | 5797194 | Warning | CH-E-101-1 | 고온냉동기 - Unit Warning Code AV 알람 | 확인 | 2026-02-05 17:03:17 |
| 2 | 5797192 | Warning | CH-E-201-6 | 고온냉동기 - Unit Warning Code AV 알람 | 확인 | 2026-02-05 16:44:12 |
| 3 | 5797191 | Warning | CH-E-101-3 | 고온냉동기 - Unit Warning Code AV 알람 | 확인 | 2026-02-05 16:42:17 |
| 4 | 5797190 | Warning | CH-E-101-4 | 고온냉동기 - Unit Warning Code AV 알람 | 확인 | 2026-02-05 16:31:00 |
| 5 | 5797065 | Warning | A WING 고온 냉각탑-2-1 | A 고온냉각탑 수조 고수위 | 확인 | 2026-02-04 10:17:26 |
| 6 | 5797066 | Warning | A WING 고온 냉각탑-2-2 | B 고온냉각탑 수조 고수위 | 확인 | 2026-02-04 10:17:26 |
| 7 | 5797064 | **Critical** | A WING 고온 냉각탑-4-1 | 냉각탑 - 인버터 알람 | 확인 | 2026-02-04 10:11:12 |
| 8 | 5797056 | Warning | 6FW-10-01-A | 차단기#1 | 미확인 | 2026-02-04 09:47:59 |
| 9 | 5797055 | Warning | 6FW-10-01-A | 부하 상태#1 | 미확인 | 2026-02-04 09:47:58 |
| 10 | 5797054 | Warning | 6FW-09-01-A | 차단기#1 | 확인 | 2026-02-04 09:47:50 |
| 11 | 5797053 | Warning | 6FW-09-02-A | 차단기#1 | 미확인 | 2026-02-04 09:47:42 |
| 12 | 5797052 | Warning | 6FW-09-03-A | 차단기#1 | 미확인 | 2026-02-04 09:47:31 |
| 13 | 5797051 | Warning | 6FW-10-02-A | 차단기#1 | 미확인 | 2026-02-04 09:47:23 |
| 14 | 5797050 | Warning | 6FW-10-02-A | 부하 상태#1 | 미확인 | 2026-02-04 09:47:23 |
| 15 | 5797048 | Warning | 6FW-10-01-B | 차단기#1 | 미확인 | 2026-02-04 09:47:19 |

## 비교 명령 재현

```bash
cd /Users/kyunghyun/workspace/aidc_llm_agent && uv run python -c "
import asyncio, json
from maria_mcp import db, tools

async def main():
    await db.init_pool()
    try:
        result = await tools.get_active_alarms(data_center_id=1, severity=None, limit=15)
        print(json.dumps([r.model_dump(mode='json') for r in result], default=str, ensure_ascii=False, indent=2))
        print(f'__COUNT__={len(result)}')
    finally:
        await db.close_pool()

asyncio.run(main())
"
```
