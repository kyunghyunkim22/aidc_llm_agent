# 알람 도구 테스트 종합 결과 — 2026-05-22

11개 알람 관련 MCP tool · 55 케이스 · Gemma4-E4B-W4A16 (vLLM, http://1.234.33.212:8000/v1)

## 1. 종합 요약

| 항목 | 값 |
|------|-----|
| 대상 tool | 11개 (`get_alarm_detail`, `get_active_alarms`, `get_alarms_by_time`, `get_device_alarms`, `get_device_alarms_by_time`, `get_alarm_history`, `get_active_alarm_summary`, `get_nearby_alarms`, `get_checkpoint_alarms`, `get_alarm_history_by_policy`, `get_active_alarms_for_devices`) |
| 총 케이스 | 55 (각 tool 5건) |
| 초기 batch (16:30) | **45/55 PASS** — FAIL 10건 (3 패턴) |
| 패치 후 누적 | **54/55 PASS (98.2%)** — 잔여 1건은 모델 한계 |
| 잔여 FAIL | get_device_alarms Q5 환각 (rule 9-A 추가 시도 후 무효 → 9-A 원복) |

## 2. tool별 최종 상태

| tool | 케이스 | 초기 | 최종 | 비고 |
|------|--------|------|------|------|
| get_alarm_detail | 5 | 1/5 | **5/5** | rule 3-A로 회복 (data_center_id 누락 4건) |
| get_active_alarms | 5 | 5/5 | 5/5 | — |
| get_alarms_by_time | 5 | 5/5 | 5/5 | — |
| get_device_alarms | 5 | 0/5 | **4/5** | rule 3-B로 4건 회복, Q5 환각만 잔존 |
| get_device_alarms_by_time | 5 | 5/5 | 5/5 | — |
| get_alarm_history | 5 | 5/5 | 5/5 | — |
| get_active_alarm_summary | 5 | 5/5 | 5/5 | — |
| get_nearby_alarms | 5 | 5/5 | 5/5 | — |
| get_checkpoint_alarms | 5 | 5/5 | 5/5 | — |
| get_alarm_history_by_policy | 5 | 5/5 | 5/5 | — |
| get_active_alarms_for_devices | 5 | 4/5 | **5/5** | rule 6-A로 Q2 recursion 회복 |
| **합계** | **55** | **45** | **54** | **+9 회복, 1 잔존** |

## 3. SYSTEM_PROMPT 패치 이력 (scripts/run_test_questions.py)

| Rule | 추가 이유 | 적용 대상 패턴 | 결과 |
|------|-----------|----------------|------|
| **3-A** | get_alarm_detail 4 FAIL — alarm_id만 명시된 단건 조회에서 `data_center_id` 누락 | 모든 tool 호출 시 `data_center_id=1` 필수 포함 | ✅ 4/4 회복 |
| **3-B** | get_device_alarms 4 FAIL — "최근 N시간" 표현을 `get_device_alarms_by_time(start_time='2500 hours ago')` 문자열 인자로 잘못 매핑 | hours/days 인자 받는 tool 우선 사용 | ✅ 4/4 회복 |
| **6-A** | get_active_alarms_for_devices Q2 — `data_center_id=2208`(device_id 값을 잘못된 슬롯에 넣음) → 동일 호출 12회 반복 → LangGraph recursion limit | data_center_id ≠ device_id 명시, device_ids 리스트 매핑 강조 | ✅ 1/1 회복 |
| ~~9-A~~ | get_device_alarms Q5 — 빈 결과 시 가짜 `alarm_id=1001`, `"Power Supply Failure"` 생성 | `structured_content.result == []` 명시 검사 | ❌ 효과 없음 → **원복** (모델 한계로 분류) |

## 4. 잔여 모델 한계 (수정 금지)

### get_device_alarms Q5 — 빈 결과 환각

- **질문**: "장비 ID 33077의 최근 알람 최대 10건 가져와줘, 2500시간 기준으로"
- **tool 호출**: `get_device_alarms(data_center_id=1, device_id=33077, hours=2500, limit=10)` ✅ (호출 자체는 정상)
- **DB 실측**: `[]` (cur 테이블에 33077 알람 없음)
- **LLM 답변**: `alarm_id=1001`, `severity=Critical`, `checkpoint_name="Power Supply Failure"`, `occur_time="2024-05-15T10:00:00Z"` — 학습데이터로 추정되는 가짜 값 생성

**조치**: rule 9-A 추가 시도 → 무효 → 원복. `docs/테스트_검증_가이드.md` §"Gemma4-E4B (W4A16) 모델 한계" 표에 기록. **동일 패턴 재발 시 프롬프트/코드 보강 금지**. 모델 교체 시점 재평가.

## 5. 케이스별 최종 결과

### get_alarm_detail (5/5)
- ✅ Q1: 알람 ID 5732176의 상세 내용 보여줘
- ✅ Q2: 알람 번호 5732177이 뭔지 자세히 알고 싶어
- ✅ Q3: 알람 ID 5732178 조회해줘, 언제 발생했고 심각도가 어떻게 되는지
- ✅ Q4: 알람 ID 5732179의 원인 메시지 확인해줘
- ✅ Q5: 데이터센터 1에서 발생한 알람 ID 5797194 상세 정보 알려줘

> 초기 batch에서 Q1~Q4 FAIL (data_center_id 누락) → rule 3-A 적용 후 5/5 (재테스트 17:04). Q5는 처음부터 PASS.

### get_active_alarms (5/5)
- ✅ Q1: 지금 활성화된 알람 목록 보여줘 → `get_active_alarms(data_center_id=1)`
- ✅ Q2: 현재 Critical 등급 알람만 뽑아줘 → `severity='Critical'`
- ✅ Q3: 지금 Warning 등급 알람 최대 10개 보여줘 → `severity='Warning', limit=10`
- ✅ Q4: 현재 미처리 알람 전체 현황 알려줘 → `get_active_alarm_summary` 자동 선택
- ✅ Q5: 활성 알람 중 Fatal 등급인 것들 알려줘 → `severity='Fatal'`

### get_alarms_by_time (5/5)
- ✅ Q1: 2026-02-04 00:00부터 2026-02-05 00:00 사이에 발생한 알람
- ✅ Q2: 2026-02-04 00:00 ~ 2026-02-04 12:00 사이 Warning 알람
- ✅ Q3: 2026-02-05 00:00부터 2026-02-06 00:00까지 발생한 알람
- ✅ Q4: 2026-01-29 전체 하루 동안 발생한 Warning 알람
- ✅ Q5: 2026-02-04 09:00 이후 2026-02-04 18:00 이전 알람 시간순

### get_device_alarms (4/5)
- ✅ Q1: 장비 ID 2208에서 발생한 최근 2500시간 알람 이력 → `hours=2500`
- ✅ Q2: 장비 2276번의 최근 2500시간 알람 이력 → `hours=2500`
- ✅ Q3: 장비 ID 2273 최근 2500시간 알람 내역 → `hours=2500`
- ✅ Q4: 장비 2274에서 최근 2500시간 어떤 알람이 떴는지 → `hours=2500`
- ❌ **Q5 (환각, 모델 한계)**: 장비 ID 33077의 최근 알람 최대 10건, 2500시간 기준 — DB `[]` → LLM이 `alarm_id=1001/"Power Supply Failure"` 가공

> 초기 batch는 Q1~Q4가 모두 `get_device_alarms_by_time(start_time='2500 hours ago')` 형태로 잘못 호출되어 FAIL. rule 3-B 적용 후 4/5 PASS (재테스트 17:04).

### get_device_alarms_by_time (5/5)
- ✅ Q1: 장비명 CRAC-6F A-101-17 2026-02-02~02-04 (search_devices → device_id=1499 변환 후 호출)
- ✅ Q2: 장비 1499의 2026-01-01~02-01 이력
- ✅ Q3: 장비 2208번 2026-01-01~02-01 알람
- ✅ Q4: 장비 1499 2026-02-03~02-06 Warning만
- ✅ Q5: 장비 2276번 2026-02-01~03-01 최대 10건

### get_alarm_history (5/5)
- ✅ Q1: 장비 1499 최근 200일 이력
- ✅ Q2: 장비 2208번 최근 200일 완료 알람
- ✅ Q3: 장비 17546 지난 200일 최대 10건
- ✅ Q4: 장비 1499 200일간 반복 패턴
- ✅ Q5: 장비 2208 200일 이력

### get_active_alarm_summary (5/5)
- ✅ Q1: 현재 활성 알람 요약 통계
- ✅ Q2: 데이터센터 전체 상황 심각도별
- ✅ Q3: 미확인(unacknowledged) 알람 포함 현황
- ✅ Q4: Critical/Warning/Fatal 각각 건수
- ✅ Q5: 분석 시작 전 전체 현황

### get_nearby_alarms (5/5)
- ✅ Q1: 장비 15930 주변 알람 상태
- ✅ Q2: 장비 15931 같은 구역 활성 알람
- ✅ Q3: 장비 15932 근처 알람
- ✅ Q4: 장비 15930 주변 알람 최대 15건
- ✅ Q5: 장비 15931 근처 동시 알람

### get_checkpoint_alarms (5/5)
- ✅ Q1: "유효전력합" 체크포인트
- ✅ Q2: "Unit Warning Code AV" 활성 알람
- ✅ Q3: "통합알람" 체크포인트 전 장비
- ✅ Q4: "upsAlarmGeneralWarning" 장비 수
- ✅ Q5: "A 인버터 알람" 최대 15건

### get_alarm_history_by_policy (5/5)
- ✅ Q1: "차단기#1" 200일 이력
- ✅ Q2: "부하 상태#1" 정책 200일
- ✅ Q3: "통신 오류(Push)" 반복 패턴 200일
- ✅ Q4: "고온냉동기 - Unit Warning Code AV 알람" 정책 200일 최대 15건
- ✅ Q5: "온도 변화량 감지 알람" 200일

### get_active_alarms_for_devices (5/5)
- ✅ Q1: 장비 [2208, 2276, 2273, 2274] 4건
- ✅ Q2: 장비 [2208, 2210, 2211] 3건 — *이전 recursion fail, rule 6-A로 회복*
- ✅ Q3: 장비 [17546, 2208, 2276] 3건
- ✅ Q4: 장비 [33077, 33034, 2273, 2274, 2276] 10건 (limit 적용)
- ✅ Q5: 장비 [2210, 2211, 2274] 3건

## 6. 검증 환경

| 항목 | 값 |
|------|-----|
| LLM | Gemma4-E4B W4A16 quantized |
| vLLM endpoint | `http://1.234.33.212:8000/v1` (직접 접속, 터널 불필요) |
| MCP server | `uv run maria-mcp` (localhost:8001) |
| MariaDB | im_device_inf · fm_fault_alarm_cur · fm_fault_alarm_his |
| 데이터 기준 시점 | 최신 알람 2026-02-05 (cur 744건) |
| 실행 스크립트 | `scripts/run_test_questions.py -s <tool> -t <timeout> -o <out>` |
| SYSTEM_PROMPT | scripts/run_test_questions.py:52~ (rule 3-A, 3-B, 6-A 포함, 9-A 원복됨) |

## 7. 소스 결과 파일

| 파일 | 내용 |
|------|------|
| `20260522_163033_alarm_tools.md` / `.log` | 초기 11개 tool 전체 batch (45/55) |
| `20260522_165819_alarm_detail_retest.md` / `.log` | rule 3-A 검증 — get_alarm_detail 5/5 |
| `20260522_170326_device_alarms_retest.md` / `.log` | rule 3-B 검증 — get_device_alarms + get_device_alarms_by_time 9/10 |
| `20260522_171256_for_devices_retest.md` / `.log` | rule 6-A 검증 — get_active_alarms_for_devices 5/5 |
| `verify_get_active_alarms_20260522_135207.md` | LLM "47 Critical" 주장 → DB 실측 7건 (별도 검증, 본 batch 외) |
