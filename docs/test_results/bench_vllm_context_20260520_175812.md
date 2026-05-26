# vLLM 컨텍스트 한계 측정 리포트

- 일시: 2026-05-20 18:08:38
- LLM: `http://1.234.33.212:8000/v1` / `/models/gemma-4-E4B-it-W4A16`
- max_model_len: 131,072
- 로그: `/tmp/bench_vllm_context.log`

---

## 입력 구성별 실제 내용 및 토큰 수 (vLLM /tokenize 실측)

### 시스템 프롬프트 — 332 tokens

```
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
```

### 사용자 메시지 — 15 tokens

```
현재 알람/장비 목록을 조회해서 요약해줘.
```

### tool_call (assistant → LLM이 생성한 함수 호출) — 26 tokens

```json
{"name": "get_active_alarms", "arguments": "{\"data_center_id\": 1}"}
```

### tool_result (DB 조회 결과 JSON) — 쿼리/LIMIT별 상이 (가장 큰 비중)

| 테이블 | LIMIT | rows | tool_result tokens | prompt 합계 | 채팅템플릿 오버헤드 | vLLM prompt_tokens |
|--------|------:|-----:|-------------------:|------------:|-------------------:|-------------------:|
| fm_fault_alarm_cur | 100 | 100 | 22,042 | 22,415 | +33 | 22,448 |
| fm_fault_alarm_his | 100 | 100 | 18,055 | 18,428 | +32 | 18,460 |
| im_device_inf | 100 | 100 | 7,817 | 8,190 | +30 | 8,220 |
| im_device_inf | 500 | 500 | 38,972 | 39,345 | +30 | 39,375 |
| im_device_inf | 1,000 | 1,000 | 77,920 | 78,293 | +30 | 78,323 |

> **고정 오버헤드 합계: 373 tokens** (시스템 프롬프트 332 + 사용자 메시지 15 + tool_call 26)
> **가변 부분: tool_result** — 전체 prompt의 98% 이상을 차지
> **채팅 템플릿 오버헤드**: 약 30~33 tokens (role 태그 등 Gemma 채팅 템플릿 포맷)

---

## 전체 측정 결과

| 테이블 | LIMIT | rows | result bytes | sys | user | tool_call | tool_result | prompt합계 | vLLM prompt | completion | finish | ctx% | 상태 |
|--------|------:|-----:|-------------:|----:|-----:|----------:|------------:|-----------:|------------:|-----------:|--------|-----:|------|
| fm_fault_alarm_cur | 100 | 100 | 51,753 | 332 | 15 | 26 | 22,042 | 22,415 | 22,448 | 616 | stop | 17.1% | ✅ |
| fm_fault_alarm_cur | 500 | 500 | 262,156 | 332 | 15 | 26 | ~111,000 | ~111,373 | - | - | - | ~85% | ❌ Timeout (>180s) |
| fm_fault_alarm_cur | 1,000 | 744 | 393,693 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| fm_fault_alarm_cur | 5,000 | 744 | 393,693 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| fm_fault_alarm_cur | 10,000 | 744 | 393,693 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| fm_fault_alarm_his | 100 | 100 | 39,527 | 332 | 15 | 26 | 18,055 | 18,428 | 18,460 | 831 | stop | 14.1% | ✅ |
| fm_fault_alarm_his | 500 | 500 | 226,583 | 332 | 15 | 26 | ~95,000 | ~95,373 | - | - | - | ~73% | ❌ Timeout (>180s) |
| fm_fault_alarm_his | 1,000 | 1,000 | 451,838 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| fm_fault_alarm_his | 5,000 | 2,653 | 1,271,497 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| fm_fault_alarm_his | 10,000 | 2,653 | 1,271,497 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| im_device_inf | 100 | 100 | 22,187 | 332 | 15 | 26 | 7,817 | 8,190 | 8,220 | 338 | stop | 6.3% | ✅ |
| im_device_inf | 500 | 500 | 109,532 | 332 | 15 | 26 | 38,972 | 39,345 | 39,375 | 467 | stop | 30.0% | ✅ |
| im_device_inf | 1,000 | 1,000 | 218,533 | 332 | 15 | 26 | 77,920 | 78,293 | 78,323 | 534 | stop | 59.8% | ✅ |
| im_device_inf | 5,000 | 5,000 | 1,178,626 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |
| im_device_inf | 10,000 | 10,000 | 2,411,854 | 332 | 15 | 26 | ~131,000+ | ~131,373+ | - | - | - | >100% | ❌ HTTP 400 |

---

## 결론: vLLM 처리 한계

| 테이블 | 정상 처리 최대 | 실패 시작 | 비고 |
|--------|-------------|---------|------|
| fm_fault_alarm_cur | **LIMIT 100** (22K tokens, 17.1%) | LIMIT 500 → Timeout | 알람 1건당 약 220 tokens |
| fm_fault_alarm_his | **LIMIT 100** (18K tokens, 14.1%) | LIMIT 500 → Timeout | 알람 1건당 약 181 tokens |
| im_device_inf | **LIMIT 1,000** (78K tokens, 59.8%) | LIMIT 5,000 → HTTP 400 | 장비 1건당 약 78 tokens |

- **HTTP 400 (컨텍스트 초과)**: vLLM 메시지 `"prompt contains at least 131,073 input tokens"` — 131,072 한도 정확히 초과
- **Timeout**: 컨텍스트는 초과하지 않으나 대용량 prompt 처리에 180초+ 소요
- **현재 `_LIMIT_MAX=15` 설정**: 알람 기준 최대 ~3,300 tokens → 전체 컨텍스트의 **2.5%** 수준으로 매우 안전

---

## LLM 응답 내용 (잘림 여부 확인)

### fm_fault_alarm_cur — LIMIT=100 / prompt=22,448 / completion=616 / finish=stop

```
총 100건의 알람 중, 현재 확인 및 조치가 필요한 알람은 다음과 같습니다.

**주요 알람 요약 (최신순):**

1.  **고온냉동기 알람 (가장 심각):**
    *   **알람명:** 고온냉동기 - Unit Warning Code AV 알람
    *   **발생 시각:** 2026-02-05 기준, 16:31부터 17:03 사이에 여러 대에서 발생.
    *   **상태:** 모든 관련 알람은 현재 **'확인'** 상태입니다.
    *   **장비:** CH-E-101-1, CH-E-201-6, CH-E-101-3, CH-E-101-4 (총 4대)
    *   **특이사항:** 해당 알람들은 고객명(DVD, China Telecom Global, SKT MEC 등)과 위치(B5F/기계실 B)가 명시되어 있습니다.

2.  **차단기 및 부하 관련 알람 (다수):**
    *   **발생 시각:** 2026년 2월 4일 기준, 09:40부터 09:43 사이에 집중적으로 다수 발생.
    *   **상태:** 대부분의 차단기 및 부하 관련 알람은 **'미확인'** 상태입니다.
    *   **내용:** 다양한 위치의 차단기(CB1) 및 부하 상태 알람이 기록되어 있습니다.

3.  **냉각탑 알람:**
    *   **알람명:** A 고온냉각탑 수조 고수위 (Alarm 값 1.0)
    *   **발생 시각:** 2026-02-04 10:17:26
    *   **상태:** **'확인'** 상태입니다.

**조치 필요 사항:**

*   **고온냉동기 알람 (가장 시급):** 4대의 고온냉동기에서 'Unit Warning Code AV'가 발생했으며, 이는 **'확인'** 상태입니다. 해당 알람의 원인(고객명, 위치)을 바탕으로 조치가 필요한지 확인해야 합니다.
*   **차단기/부하 알람:** 2월 4일 발생한 다수의 차단기 및 부하 관련 알람은 **'미확인'** 상태이므로, 해당 장비들의 정상 여부를 확인해야 합니다.

**요약하자면, 현재 시점 기준으로 가장 주목해야 할 것은 고온냉동기 4대의 'Unit Warning Code AV' 알람입니다.**
```

### fm_fault_alarm_cur — LIMIT=500 / finish=Timeout
_(응답 없음 — 180초 초과)_

### fm_fault_alarm_cur — LIMIT=1,000~10,000 / finish=HTTP 400
```
ERROR: This model's maximum context length is 131072 tokens.
       However, your prompt contains at least 131073 input tokens.
```

---

### fm_fault_alarm_his — LIMIT=100 / prompt=18,460 / completion=831 / finish=stop

```
최근 알람 기록을 요약해 드립니다. 주요 알람은 다음과 같습니다.

**주요 알람 유형별 요약:**

1.  **온도 관련 알람 (CRAC/냉방기):**
    *   **고온 알람:** 06층 서버실 A (서측-W)의 CRAC 장비에서 **고온예비알람**이 발생했습니다. (Alarm ID: 5797196, 발생 시각: 2026-02-05 17:05:41, 현재 온도 28.5℃).
    *   **온도 변화 알람:** 여러 시점에서 온도 변화량 감지 알람이 발생했습니다. (Alarm ID: 5797195, 5797193, 5797103 등)
    *   **냉방기 통합 알람:** 07층 및 08층 서버실의 여러 CRAC 장비에서 **통합알람** 및 **급기댐퍼 관련 알람**이 다수 발생했습니다. (Alarm ID: 579714x, 579710x)

2.  **장비별 주요 알람 및 조치 사항:**
    *   **고온냉동기 경고 (Warning):** 여러 대의 고온냉동기(CH-E-xxx, CH-W-xxx 등)에서 **Unit Warning Code AV 알람**이 발생했으며, 이는 고객명 및 위치에 따라 상이합니다.
    *   **발전기 가동 알람:** 여러 대의 발전기(B3F/B4F 위치)가 **Running 상태**로 가동 중이며, 이는 정상적인 운영 상태로 보입니다.

더 자세한 특정 알람에 대한 정보가 필요하시면 알람 ID 또는 발생 시각을 알려주세요.
```

### fm_fault_alarm_his — LIMIT=500 / finish=Timeout
_(응답 없음 — 180초 초과)_

### fm_fault_alarm_his — LIMIT=1,000~10,000 / finish=HTTP 400
```
ERROR: This model's maximum context length is 131072 tokens.
       However, your prompt contains at least 131073 input tokens.
```

---

### im_device_inf — LIMIT=100 / prompt=8,220 / completion=338 / finish=stop

```
총 50개의 장비가 조회되었습니다. 주요 장비 목록은 다음과 같습니다.

**화재 감지 센서 (Fire Detect Sensor)**:
*   10층 (10F) 및 3층 (3F)의 확산방지포 (총 10개)
*   4층 (4F)의 확산방지포 (총 4개)

**연료전지 가스미터 (Generic Sensor)**:
*   10K 관련 가스미터 (총 5개)

**HVAC 장비 (CRAH)**:
*   10층 (10F) 및 3층 (3F)의 동관 관련 습도/온도 센서 (총 8개)

**전력 관련 장비 (Busway Gateway / Switchboard)**:
*   10층, 3층, 4층, 5층의 전력사용량 모니터링 장비
*   6층 (6FW)의 다양한 스위치보드 장비 (총 30개)
```

### im_device_inf — LIMIT=500 / prompt=39,375 / completion=467 / finish=stop

```
총 15개 항목의 장비가 조회되었습니다. 주요 장비 목록은 다음과 같습니다:

**화재 감지 센서 (Fire Detect Sensor)**
*   **10층~8층:** 각 층별 전기실 확산방지포 다수

**주요 전력 및 환경 관련 장비 (Electric Power, HVAC, ETC)**
*   **전력 관련 (Switchboard, Busway Gateway):** 6층~8층 다양한 전력 장비
*   **HVAC (공조기):** 3층~8층 동관/서관 습도·온도·전력사용량 장비
*   **ETC (가스미터 등):** 연료전지 관련 가스미터
```

### im_device_inf — LIMIT=1,000 / prompt=78,323 / completion=534 / finish=stop

```
총 15개 항목의 장비가 조회되었습니다.

1.  **전기실/층별 장비:** 1층~8층 각 층별 전기실(전기실1~4)의 확산방지포,
    HVAC, 전력 관련 장비(CRAH, Busway Gateway, Switchboard) 확인.
2.  **전력 관련 장비:** 8FW-01~8FW-05 등 다양한 Switchboard 확인.

조회된 장비들은 화재 감지 센서, 공조 장비(CRAH), 전력 관련 장비(Switchboard, Busway Gateway)로
분류되며 1층~8층 전체 인프라를 구성합니다.
```

### im_device_inf — LIMIT=5,000~10,000 / finish=HTTP 400
```
ERROR: This model's maximum context length is 131072 tokens.
       However, your prompt contains at least 131073 input tokens.
```
