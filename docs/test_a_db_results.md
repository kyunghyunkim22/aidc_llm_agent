# Test A — DB 실제 조회 결과

> 조회 기준일: 2026-05-12 | data_center_id=1
> LLM 응답 품질 평가 기준 자료 (질문 → 기대 응답 내용)

---

## get_device_info

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비 ID 54의 상세 정보 알려줘 | device_id=54, LV3-2-1, Electric Power / Switchboard, B3F > B3F 전기실#3 > A1 |
| 2 | 데이터센터 1번, 장비 번호 55의 스펙이랑 위치 알고 싶어 | device_id=55, LV3-2-3 UP, Electric Power / Switchboard, B3F > B3F 전기실#3 > A1 |
| 3 | 장비 56번이 어디 있고 어떤 타입인지 확인해줘 | device_id=56, LV3-2-3 DOWN, Electric Power / Switchboard, B3F > B3F 전기실#3 > A1 |
| 4 | 장비 ID 57 정보 조회해줘, 제조사랑 모델명도 보고 싶어 | device_id=57, LV1-A-1, Electric Power / Switchboard, B3F > B3F 전기실#2 > I1 (제조사/모델명 NULL) |
| 5 | 데이터센터 1에 있는 장비 ID 58 정보 가져와줘 | device_id=58, LV1-A-3, Electric Power / Switchboard, B3F > B3F 전기실#2 > I3 |

---

## get_alarm_info

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 알람 ID 5732176의 상세 내용 보여줘 | 계약전력 초과 - 5FE 엔씨소프트 7kW, device=5FE-08-09, Warning, 2025-10-17 13:18:51, 수집된 값(7.506kW) > 7.0kW |
| 2 | 알람 번호 5732177이 뭔지 자세히 알고 싶어 | 계약전력 초과 - 5FE 엔씨소프트 7kW, device=5FE-08-10, Warning, 2025-10-17 13:18:51, 수집된 값(7.533kW) > 7.0kW |
| 3 | 알람 ID 5732178 조회해줘 | 계약전력 초과 - 5FW NCC 6.6kW, device=5FW-19-10, Warning, 2025-10-17 13:19:08, 수집된 값(6.606kW) > 6.6kW |
| 4 | 알람 ID 5732179의 원인 메시지 확인해줘 | Meter Communication Alarm, device=6FW-TOB-18-A, **Fatal**, 2025-10-17 13:18:25, Alarm Threshold |
| 5 | 알람 ID 5797194 상세 정보 알려줘 | 고온냉동기 - Unit Warning Code AV 알람, device=CH-E-101-1, Warning, 2026-02-05 17:03:17, 오류코드 25 |

---

## get_active_alarms

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 지금 활성화된 알람 목록 보여줘 | 총 744건 (15건 조회) — 최신: CH-E-101-1 Warning 2026-02-05 |
| 2 | 현재 Critical 등급 알람만 뽑아줘 | **7건**: 냉각탑-인버터(2276), 냉방기-통합알람(CRAH-8F), 저온냉각탑 수조 저수위(B WING), 외 4건 |
| 3 | 지금 Warning 등급 알람 최대 10개 보여줘 | **734건** 중 15건 조회 — 주로 고온냉동기 Unit Warning Code AV |
| 4 | 현재 미처리 알람 전체 현황 알려줘 | 총 744건 (15건 조회) |
| 5 | 활성 알람 중 Fatal 등급인 것들 알려줘 | **2건**: Meter Communication Alarm (6FW-TOB-18-A, 6FW-TOB-18-B) |

> 활성 알람 전체 현황: Critical 7건 / Fatal 2건 / Minor 1건 / Warning 734건 = **총 744건**

---

## get_alarms_by_time

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 2026-02-04 00:00~2026-02-05 00:00 사이 알람 | **15건 조회** (총 100건+) — 냉각탑 인버터(Critical), 냉각탑 수조 고수위(Warning) 등 |
| 2 | 2026-02-04 00:00~12:00 Warning 알람 | **39건 중 15건 조회** — 고온냉각탑 수조 고수위, 저온냉각탑 수조 고수위 등 |
| 3 | 2026-02-05 00:00~2026-02-06 00:00 알람 | **4건** — 고온냉동기 Unit Warning Code AV |
| 4 | 2026-01-29 Warning 알람 | **15건 조회** (총 100건+) — 주로 계약전력 초과 Warning |
| 5 | 2026-02-04 09:00~18:00 알람 | **15건 조회** (총 100건+) — 냉각탑 인버터 Critical, 수조 고수위 Warning 등 |

---

## get_device_alarms

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비 ID 2208 최근 200일 알람 이력 | **1건**: 고온냉동기 Unit Warning Code AV, Warning, 2026-02-05 |
| 2 | 장비 2276번 최근 200일 알람 이력 | **1건**: 냉각탑 인버터 알람, Critical, 2026-02-04 |
| 3 | 장비 ID 2273 최근 200일 알람 내역 | **1건**: A 고온냉각탑 수조 고수위, Warning, 2026-02-04 |
| 4 | 장비 2274 최근 200일 알람 이력 | **1건**: 저온냉각탑 수조 고수위 계열 Warning, 2026-02-04 (장비 변경: 1499→2274) |
| 5 | 장비 ID 33077 최근 200일 알람 | **4건** — cur 테이블 33077 알람 (2026-01-29 ~ 2026-02-04) |

---

## get_device_alarms_by_time

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비명 CRAC-6F A-101-17, 2026-02-02 ~ 2026-02-04 알람 | **총 19건, 15건 조회** — Critical(CRAH 쿨존2 고온알람, 상시전원상태, 통합알람), Warning(CRAH 고온예비알람), Minor(온도/급기온도 변화량 감지) |
| 2 | 장비 ID 1499, 2026-01-01 ~ 2026-02-01 알람 이력 | **총 7건, 7건 조회** — Critical(CRAH 쿨존2 고온/상시전원/비상전원/메인전원/통합알람), Minor(온도 변화량 감지) |
| 3 | 장비 2208, 2026-01-01 ~ 2026-02-01 알람 | **총 12건, 15건 한도 내 조회** — Warning "고온냉동기 - Unit Warning Code AV 알람" (2026-01-21 ~ 2026-01-31) |
| 4 | 장비 ID 1499, 2026-02-03 ~ 2026-02-06, Warning 등급만 | **총 2건** — "CRAH 고온예비알람 - 6FE #17 28.5°C" (2026-02-05, 2026-02-03) |
| 5 | 장비 2276, 2026-02-01 ~ 2026-03-01 알람 최대 10건 | **총 2건** — Critical "냉각탑 - 인버터 알람" (2026-02-04 10:11:12 × 2건) |

> Q1은 2-step 호출: search_devices(device_nm="CRAC-6F A-101-17") → device_id=1499 획득 → get_device_alarms_by_time

---

## list_nearby_devices

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비 ID 15930 주변 장비 목록 | Electric Power/BMS 장비 다수 (954 1F ELEV-5, 23535~ B4F UPS실#2 계열) |
| 2 | 장비 15931 같은 구역 장비 전체 | Q1과 동일 (같은 zone) |
| 3 | 장비 15932 근처 장비 최대 10개 | Electric Power 장비들 (B3F 전기실(154), B4F UPS실#3 계열) |
| 4 | 장비 15930 동일 zone 장비 목록 | Q1과 동일 |
| 5 | 장비 15931 주변 장비들 확인 | Q2와 동일 |

> 실측(2026-05-13): 15930/15931 zone → Electric Power/BMS(B4F UPS실#2), 15932 zone → Electric Power(B3F 전기실)

---

## list_devices_by_type

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 카테고리 HVAC 장비 전체 목록 | **15건 조회** (총 50건+) — CRAC, 냉각탑, 냉동기 등 |
| 2 | 장비 유형이 Rack인 것들 | **15건 조회** (총 50건+) — IT/Rack (서버실 랙들) |
| 3 | 카테고리 IT 장비 목록 | **15건 조회** (총 50건+) — Rack 장비들 |
| 4 | 장비 타입 CRAC인 장비 최대 15개 | **15건 조회** (총 50건+) — CRAC-1F~9F 계열 |
| 5 | 카테고리 Electric Power, 타입 Switchboard | **15건 조회** (총 50건+) — LV, LP 계열 분전반들 |

---

## list_devices_by_ups

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1~5 | UPS-A01, UPS-MAIN-01, UPS-B-02, UPS-3F-01, UPS-RACK-A | **모두 0건** (connected_ups 데이터 없음) |

> tool 호출 성공 여부만 검증

---

## get_alarm_history

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비 ID 1499 최근 200일 이력 | **15건** (상위 15건 조회, his 총 29건) |
| 2 | 장비 2208 최근 200일 이력 | **15건** (상위 15건 조회, his 총 17건) |
| 3 | 장비 17546 최근 200일 이력 최대 10건 | **10건** (his 총 16건) |
| 4 | 장비 ID 1499 최근 200일 반복 알람 | Q1과 동일 |
| 5 | 장비 ID 2208 최근 200일 이력 | Q2와 동일 |

---

## get_active_alarm_summary

| Q | 질문 | DB 결과 (공통) |
|---|------|---------|
| 1~5 | 현재 활성 알람 요약 통계 | **Critical 7건(미확인 0) / Fatal 2건(미확인 0) / Minor 1건(미확인 0) / Warning 734건(미확인 205)** = 총 744건 |

---

## get_nearby_alarms

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비 15930 주변 활성 알람 | **1건**: CH-W-101-2 / 고온냉동기 Unit Warning Code AV / Warning |
| 2 | 장비 15931 같은 구역 활성 알람 | **1건**: 동일 (같은 zone) |
| 3 | 장비 15932 근처 활성 알람 | **7건**: CH-E 계열 고온냉동기 Unit Warning Code AV |
| 4 | 장비 15930 주변 알람 최대 20건 | Q1과 동일 1건 |
| 5 | 장비 15931 근처 동시 알람 | Q2와 동일 1건 |

---

## get_checkpoint_alarms

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | checkpoint "유효전력합" 알람 현황 | **15건** — 계약전력 초과 Warning (9FW 알리바바, 6FE 알리바바 등) |
| 2 | checkpoint "Unit Warning Code AV" 활성 알람 | **6건**: CH-E-101-1/3/4/5, CH-E-201-6, CH-W-101-2 / Warning |
| 3 | checkpoint "통합알람" 전 장비 알람 | **2건**: CRAH-8F A-201-12(Critical), CRAC-5F A-101-02(Critical) |
| 4 | checkpoint "upsAlarmGeneralWarning" 알람 | **2건**: UPS-B4-A#01, UPS-B4-A#02 / Critical |
| 5 | checkpoint "A 인버터 알람" 알람 최대 15건 | **1건**: A WING 고온 냉각탑-4-1 / Critical |

---

## search_devices

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 이름에 "CH-E" 들어가는 장비 | **14건** (전체 14건) — CH-EAST(B)-5/6, VTS_CH-East(B) 등 Switchboard 계열 |
| 2 | 위치 B3F + Switchboard | **15건 조회** (총 50건+) — LP-B2, LR-B2, LV 계열 분전반 다수 |
| 3 | 카테고리 HVAC + 타입 CRAC | **15건 조회** (총 50건+) — CRAC-1F~9F 계열 (위치 없는 가상장비 1건 포함) |
| 4 | 이름 LV3 + 카테고리 Electric Power | **15건 조회** (총 50건+) — LV3 계열 분전반 다수 |
| 5 | 위치 6F + 카테고리 IT | **15건 조회** (총 50건+) — 6FW/6FE 서버실 Rack 장비들 |
| 6 | 이름에 "HV2" 포함 | **15건 조회** (총 50건+) — HV2 SP1/SP2, HV2 A-M2 등 Switchboard(6F UPS실) |

---

## get_alarm_history_by_policy

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | "차단기#1" 200일 이력 | **15건** (상위 15건, his 총 347건) |
| 2 | "부하 상태#1" 200일 이력 | **15건** (상위 15건, his 총 316건) |
| 3 | "통신 오류(Push)" 200일 이력 | **15건** (상위 15건, his 총 279건) |
| 4 | "고온냉동기 - Unit Warning Code AV 알람" 200일 이력 최대 100건 | **15건** (상위 15건, his 총 161건) |
| 5 | "온도 변화량 감지 알람" 200일 이력 | **15건** (상위 15건, his 총 152건) |

---

## get_active_alarms_for_devices

| Q | 질문 | DB 결과 |
|---|------|---------|
| 1 | 장비 2208, 2276, 2273, 2274 활성 알람 | **4건**: CH-E-101-1(Warning), 냉각탑-4-1(Critical), 냉각탑-2-1/2-2(Warning) |
| 2 | 장비 2208, 2210, 2211 활성 알람 | **3건**: CH-E-101-1/3/4 모두 고온냉동기 Unit Warning Code AV / Warning |
| 3 | 장비 17546, 2208, 2276 활성 알람 | **3건**: CH-E-101-1(Warning), CH-E-201-6(Warning), 냉각탑-4-1(Critical) |
| 4 | 장비 33077, 33034, 2273, 2274, 2276 활성 알람 | **11건**: 냉각탑/냉동기 Warning/Critical 혼재 |
| 5 | 장비 ID [2210, 2211, 2274] 세 대 활성 알람 | **3건**: 고온냉동기 Unit Warning Code AV(2210/2211) + 저온냉각탑 Warning(2274) (장비 변경: 15930~15932→2210/2211/2274) |

---

## RCA 시나리오

> 복합 질문 — 여러 tool을 순차 호출해야 PASS. 예상 tool 호출 순서와 각 결과 명시.

| Q | 시나리오 요약 | 예상 tool 호출 순서 | 예상 결과 |
|---|-------------|-------------------|-----------|
| 1 | 장비 2276 Critical 알람 종합 분석 | get_device_info(2276) → get_alarm_info(5797064) → get_nearby_alarms(2276) → get_alarm_history(2276) | 장비: A WING 고온 냉각탑-4-1 / 알람: Critical 인버터 알람 / 주변알람: zone 내 0건 / 이력: **1건** (200일, 냉각탑-인버터 알람 2026-02-04) |
| 2 | 활성 알람 요약 후 Critical 장비 상세 분석 | get_active_alarm_summary → get_active_alarms(Critical) → get_device_info → get_alarm_info | 요약: Critical 7건 / Fatal 2건 / Warning 734건 / Critical 중 1개 선택하여 장비+알람 상세 조회 |
| 3 | "CH-E-101" 장비 최근 200일 알람 이력 + 주변 알람 | search_devices(CH-E-101) → get_alarm_history(첫 번째 장비 2208) → get_nearby_alarms | 첫 번째 장비: CH-E-101-1(2208) / 이력: **15건** (his 총 17건) / 주변알람: zone 내 결과 |

---

## 재발 패턴 분석

> 복합 질문 — 재발 패턴 파악을 위한 다중 tool 호출.

| Q | 시나리오 요약 | 예상 tool 호출 순서 | 예상 결과 |
|---|-------------|-------------------|-----------|
| 1 | 장비 1499 반복 알람 패턴 분석 | get_alarm_history(1499) → get_alarm_history_by_policy("온도 변화량 감지 알람") | 둘 다 **1건+** (200일, his 2025-10-17~2026-02-05 범위 커버) |
| 2 | 유효전력합 checkpoint + 장비 4대 알람 일괄 조회 | get_checkpoint_alarms("유효전력합") → get_active_alarms_for_devices([12690,12691,10308,10345]) → get_device_info x4 | checkpoint: 15건 (계약전력 초과 Warning) / 4대 알람: 현재 활성 알람 현황 / 장비 정보: 각 device_id 상세 |

---

## 0건 예상 케이스 요약

| tool | 이유 | 조치 |
|------|------|------|
| `list_devices_by_ups` | connected_ups 컬럼 데이터 없음 | 해결 불가 (데이터 없음) — tool 호출 성공 여부만 검증 |
| `get_device_alarms` Q4 (1499) | fm_fault_alarm_cur에 해당 장비 알람 없음 | 장비 변경: 1499 → 2274 |
| `get_active_alarms_for_devices` Q5 (15930~15932) | 해당 장비 cur 알람 없음 | 장비 변경: → 2210/2211/2274 |
