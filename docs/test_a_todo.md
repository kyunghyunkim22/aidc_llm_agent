# Test A 진행 현황

**목적**: 자연어 질문 → gemma4 LLM이 올바른 MCP tool + 파라미터를 선택하는지 검증  
**테스트 스크립트**: `/tmp/test_a.py` (병렬 실행, 동시 5건)  
**질문 목록**: `docs/test_questions.md`  
**총 질문 수**: 33건

---

## 진행 상태

| 단계 | 내용 | 상태 |
|------|------|------|
| A-1 | 실행 환경 검증 | ✅ 완료 |
| A-2 | 기본 5개 tool 검증 (#01~13) | 미완료 |
| A-3 | RCA 장비 조회 tool 검증 (#14~18) | 미완료 |
| A-4 | RCA 알람 조회 tool 검증 (#19~26) | 미완료 |
| A-5 | 검색·이력·일괄 tool 검증 (#27~33) | 미완료 |
| A-6 | 결과 분석 | 미완료 |

단건 실행 결과: 01번 PASS (get_device_info, 182초), 02번 PASS (get_device_info, 624초)

---

## 단계별 상세

### A-1. 실행 환경 검증
- gemma4 tool_call 단건 확인
- `data_center_id` 기본값 1 적용 여부 확인
- `tool_calls=None` 반환 이슈 해소 확인 (required에서 제거 + 시스템 프롬프트 강화로 수정 완료, 재검증 필요)

### A-2. 기본 5개 tool (#01~13)
| # | 질문 | 기대 tool | 상태 |
|---|------|-----------|------|
| 01 | 장비 ID 54의 상세 정보 알려줘 | get_device_info | ✓ PASS (182초) |
| 02 | 데이터센터 1번, 장비 번호 55의 스펙이랑 위치 알고 싶어 | get_device_info | ✓ PASS (624초) |
| 03 | 장비 56번이 어디 있고 어떤 타입인지 확인해줘 | get_device_info | 미실행 |
| 04 | 알람 ID 5732176의 상세 내용 보여줘 | get_alarm_detail | 미실행 |
| 05 | 알람 번호 5732179의 원인 메시지 확인해줘 | get_alarm_detail | 미실행 |
| 06 | 지금 활성화된 알람 목록 보여줘 | get_active_alarms | 미실행 |
| 07 | 현재 Critical 등급 알람만 뽑아줘 | get_active_alarms | 미실행 |
| 08 | 지금 Warning 등급 알람 최대 50개 보여줘 | get_active_alarms | 미실행 |
| 09 | 2026-02-04 00:00부터 2026-02-05 00:00 사이에 발생한 알람 목록 보여줘 | get_alarms_by_time | 미실행 |
| 10 | 2026-02-04 00:00 ~ 2026-02-04 12:00 사이 Warning 알람 알려줘 | get_alarms_by_time | 미실행 |
| 11 | 장비 ID 2208에서 발생한 최근 720시간 알람 이력 보여줘 | get_device_alarms | 미실행 |
| 12 | 장비 1499에서 최근 720시간 어떤 알람이 떴는지 봐줘 | get_device_alarms | 미실행 |

### A-3. RCA 장비 조회 tool (#13~18)
| # | 질문 | 기대 tool | 상태 |
|---|------|-----------|------|
| 13 | 장비 ID 15930 주변에 있는 장비들 목록 알려줘 | list_nearby_devices | 미실행 |
| 14 | 장비 15931번이랑 같은 구역에 있는 장비 전체 보여줘 | list_nearby_devices | 미실행 |
| 15 | 카테고리 HVAC 장비 전체 목록 보여줘 | list_devices_by_type | 미실행 |
| 16 | 장비 유형이 Rack인 것들 다 뽑아줘 | list_devices_by_type | 미실행 |
| 17 | 카테고리는 Electric Power, 타입은 Switchboard인 장비 목록 보여줘 | list_devices_by_type | 미실행 |
| 18 | UPS-A01에 연결된 장비 목록 알려줘 | list_devices_by_ups | 미실행 |

### A-4. RCA 알람 조회 tool (#19~26)
| # | 질문 | 기대 tool | 상태 |
|---|------|-----------|------|
| 19 | 장비 ID 1499의 최근 90일 알람 이력 보여줘 | get_alarm_history | 미실행 |
| 20 | 장비 2208번 최근 90일 완료 알람 다 보여줘 | get_alarm_history | 미실행 |
| 21 | 현재 활성 알람 요약 통계 보여줘 | get_active_alarm_summary | 미실행 |
| 22 | 현재 Critical / Warning / Fatal 각각 몇 건인지 보여줘 | get_active_alarm_summary | 미실행 |
| 23 | 장비 ID 15930 주변 장비들의 현재 알람 상태 알려줘 | get_nearby_alarms | 미실행 |
| 24 | 장비 15931번이랑 같은 구역에서 현재 활성 알람 있는 장비 있어? | get_nearby_alarms | 미실행 |
| 25 | 체크포인트 유효전력합 기준으로 알람 현황 보여줘 | get_checkpoint_alarms | 미실행 |
| 26 | checkpoint Unit Warning Code AV로 뜬 활성 알람 전체 뽑아줘 | get_checkpoint_alarms | 미실행 |

### A-5. 검색·이력·일괄 tool (#27~33)
| # | 질문 | 기대 tool | 상태 |
|---|------|-----------|------|
| 27 | 이름에 CH-E 들어가는 장비 찾아줘 | search_devices | 미실행 |
| 28 | 카테고리 HVAC이고 타입이 CRAC인 장비 목록 뽑아줘 | search_devices | 미실행 |
| 29 | 이름에 LV3 포함되고 카테고리가 Electric Power인 장비 알려줘 | search_devices | 미실행 |
| 30 | 차단기#1 알람이 최근 90일간 어떤 장비들에서 발생했는지 이력 보여줘 | get_alarm_history_by_policy | 미실행 |
| 31 | 알람 정책 부하 상태#1로 뜬 이력 90일치 다 뽑아줘 | get_alarm_history_by_policy | 미실행 |
| 32 | 장비 ID 2208, 2276, 2273, 2274 네 대의 현재 활성 알람 한 번에 보여줘 | get_active_alarms_for_devices | 미실행 |
| 33 | 장비 목록 2208, 2210, 2211에서 지금 뜨고 있는 알람 전부 뽑아줘 | get_active_alarms_for_devices | 미실행 |

---

## 이슈 및 사전 확인 사항

| 항목 | 내용 |
|------|------|
| 응답 속도 | gemma4 단건 ~180초. 병렬 5건으로 스크립트 수정 완료 (`/tmp/test_a.py`) |
| tool_calls=None | data_center_id required 제거 + 시스템 프롬프트 강화로 수정 완료, 재검증 필요 |
| 결과 0건 예상 케이스 | list_devices_by_ups(connected_ups 데이터 없음), get_alarm_history/get_alarm_history_by_policy(his 최신=2026-02-05, 오늘 기준 90일 초과) — tool 선택/파라미터만 검증 |

---

## 테스트 스크립트 실행 방법

```bash
# maria_mcp 서버 실행 (이미 실행 중이면 생략)
uv run maria-mcp &

# Test A 실행
PYTHONUNBUFFERED=1 uv run python /tmp/test_a.py
```
# test
