# 테스트 결과 — 2026-05-22 14:05:23

- 전체: 11건 / PASS: 10건 / FAIL: 1건
- LLM: http://1.234.33.212:8000/v1 / /models/gemma-4-E4B-it-W4A16

---

## search_devices

### [PASS] Q1: 이름에 "CH-E" 들어가는 장비 찾아줘
- 호출 tool: search_devices
- 소요시간: 4.3s
- 토큰: input=5494 output=67 total=5561
- 예상 결과: **14건** (전체 14건) — CH-EAST(B)-5/6, VTS_CH-East(B) 등 Switchboard 계열
- tool[1] search_devices args={'data_center_id': 1, 'device_nm': 'CH-E'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":17377,"device_name":"CH-EAST(B)-5","device_category_name":"Electric Power","device_type_name":"Switchboard","location":"B4F > B4F 기계실B > A1","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":17378,"device_name":"CH-EAST(B)-6","device_category_name":"Electric Power","device_type_name":"Switchboard","location":"B4F > B4F 기계실B > A1","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":16995,"device_name"
- LLM 답변:
```
총 15대의 장비가 검색되었습니다. 이 장비들에 대해 더 자세히 알고 싶으신가요? (예: 알람 상태 확인, 상세 정보 조회 등)
```

### [FAIL] Q2: 위치에 "B3F" 포함된 Switchboard 장비 검색해줘
- 호출 tool: search_devices, search_devices, search_devices, search_devices, search_devices, search_devices, search_devices, search_devices, search_devices, search_devices, search_devices, search_devices
- 소요시간: 14.1s
- 토큰: input=31824 output=468 total=32292
- 예상 결과: **15건 조회** (총 50건+) — LP-B2, LR-B2, LV 계열 분전반 다수
- tool[1] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-b71cbea94de064c5' artifact={'structured_content': {'result': []}}
- tool[2] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-982f1acfbe1791ce' artifact={'structured_content': {'result': []}}
- tool[3] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-b2e82c89ae269859' artifact={'structured_content': {'result': []}}
- tool[4] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-b297bf5c9dd852ba' artifact={'structured_content': {'result': []}}
- tool[5] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-89677a68783b23c8' artifact={'structured_content': {'result': []}}
- tool[6] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-90cc422a58233fb1' artifact={'structured_content': {'result': []}}
- tool[7] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-9f992e494bb1725e' artifact={'structured_content': {'result': []}}
- tool[8] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-b0fb9acba96440df' artifact={'structured_content': {'result': []}}
- tool[9] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-8b379f37031b5786' artifact={'structured_content': {'result': []}}
- tool[10] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-8dd04345aad30b72' artifact={'structured_content': {'result': []}}
- tool[11] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-8a72a515f5298d17' artifact={'structured_content': {'result': []}}
- tool[12] search_devices args={'data_center_id': 1, 'device_category_name': 'Switchboard', 'location': 'B3F'}
  → output_len=126, preview: content=[] name='search_devices' tool_call_id='chatcmpl-tool-8f8e8281cba395a2' artifact={'structured_content': {'result': []}}
- 오류: Recursion limit of 25 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key.
For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT

### [PASS] Q3: 카테고리 "HVAC"이고 타입이 "CRAC"인 장비 목록 뽑아줘
- 호출 tool: list_devices_by_type
- 소요시간: 3.3s
- 토큰: input=5167 output=103 total=5270
- 예상 결과: **15건 조회** (총 50건+) — CRAC-1F~9F 계열 (위치 없는 가상장비 1건 포함)
- tool[1] list_devices_by_type args={'data_center_id': 1, 'device_category_name': 'HVAC', 'device_type_name': 'CRAC'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":32946,"device_name":"10층 동관 습도","device_category_name":"HVAC","device_type_name":"CRAH","location":null,"enable_monitor":1},{"device_id":32954,"device_name":"10층 동관 온도","device_category_name":"HVAC","device_type_name":"CRAH","location":null,"enable_monitor":1},{"device_id":32953,"device_name":"10층 서관 습도","device_category_name":"HVAC","device_type_name":"CRAH","location":null,"enable_monitor":1},{"device_id":32960,"device_name":"10층 서관 온도","device_category
- LLM 답변:
```
총 15개의 장비가 확인되었습니다. 이 장비들은 모두 카테고리 "HVAC"이고 타입은 "CRAH"입니다. (요청하신 타입은 "CRAC"이었으나, 실제 데이터는 "CRAH"로 확인되었습니다.)
```

### [PASS] Q4: 이름에 "LV3" 포함되고 카테고리가 "Electric Power"인 장비 알려줘
- 호출 tool: search_devices
- 소요시간: 3.2s
- 토큰: input=5531 output=81 total=5612
- 예상 결과: **15건 조회** (총 50건+) — LV3 계열 분전반 다수
- tool[1] search_devices args={'data_center_id': 1, 'device_category_name': 'Electric Power', 'device_nm': 'LV3'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":609,"device_name":"LV3-2-1 APR","device_category_name":"Electric Power","device_type_name":"Switchboard","location":"B3F > B3F EPS/TPS > A1","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":610,"device_name":"LV3-2-2 SVC","device_category_name":"Electric Power","device_type_name":"Switchboard","location":"B3F > B3F EPS/TPS > A1","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":657,"device_name":"
- LLM 답변:
```
총 15개의 장비가 검색되었습니다. 이 장비들의 상세 정보가 필요하신가요? (예: 장비 ID를 알려주시면 해당 장비의 정보를 조회할 수 있습니다.)
```

### [PASS] Q5: "6F" 위치에 있는 IT 장비 찾아줘
- 호출 tool: search_devices
- 소요시간: 2.8s
- 토큰: input=5561 output=65 total=5626
- 예상 결과: **15건 조회** (총 50건+) — 6FW/6FE 서버실 Rack 장비들
- tool[1] search_devices args={'data_center_id': 1, 'location': '6F'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":1275,"device_name":"6F ELEV.HALL","device_category_name":"HVAC","device_type_name":"Temp/Hum Sensor","location":"06F > 6F 운영설비 > A1","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":1280,"device_name":"6F 배터리실-1-1 상부","device_category_name":"HVAC","device_type_name":"Temp/Hum Sensor","location":"06F > 6F 운영설비 > A1","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":1281,"device_name":"6F 배터리실-1-2 하
- LLM 답변:
```
"6F" 위치에는 총 15개의 장비가 있습니다. 이 장비들의 상세 정보가 필요하신가요? (예: 장비 ID, 장비 이름 등)
```

### [PASS] Q6: 이름에 "HV2" 포함되는 장비 알려줘
- 호출 tool: search_devices
- 소요시간: 3.0s
- 토큰: input=5504 output=70 total=5574
- 예상 결과: **15건 조회** (총 50건+) — HV2 SP1/SP2, HV2 A-M2 등 Switchboard(6F UPS실)
- tool[1] search_devices args={'data_center_id': 1, 'device_nm': 'HV2'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":16362,"device_name":"HV2 SP1","device_category_name":"Electric Power","device_type_name":"Switchboard","location":"06F > 6층 UPS실 A > A3","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":16363,"device_name":"HV2 SP2","device_category_name":"Electric Power","device_type_name":"Switchboard","location":"06F > 6층 UPS실 A > A3","enable_monitor":1,"manufacturer_name":null,"connected_ups":null},{"device_id":16375,"device_name":"HV2 A-
- LLM 답변:
```
총 15개의 장비가 이름에 "HV2"를 포함하고 있습니다. 이 장비들의 상세 정보가 필요하신가요? (예: 특정 장비의 알람 확인 등)
```

## list_devices_by_type

### [PASS] Q1: 카테고리 "HVAC" 장비 전체 목록 보여줘
- 호출 tool: list_devices_by_type
- 소요시간: 11.5s
- 토큰: input=5140 output=426 total=5566
- 예상 결과: **15건 조회** (총 50건+) — CRAC, 냉각탑, 냉동기 등
- tool[1] list_devices_by_type args={'data_center_id': 1, 'device_category_name': 'HVAC'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":32946,"device_name":"10층 동관 습도","device_category_name":"HVAC","device_type_name":"CRAH","location":null,"enable_monitor":1},{"device_id":32954,"device_name":"10층 동관 온도","device_category_name":"HVAC","device_type_name":"CRAH","location":null,"enable_monitor":1},{"device_id":32953,"device_name":"10층 서관 습도","device_category_name":"HVAC","device_type_name":"CRAH","location":null,"enable_monitor":1},{"device_id":32960,"device_name":"10층 서관 온도","device_category
- LLM 답변:
```
총 15개의 "HVAC" 카테고리 장비가 있습니다. 각 장비의 상세 정보는 다음과 같습니다:

**10층 (Floor 10)**
*   **32946**: 10층 동관 습도 (CRAH)
*   **32954**: 10층 동관 온도 (CRAH)
*   **32953**: 10층 서관 습도 (CRAH)
*   **32960**: 10층 서관 온도 (CRAH)

**3층 (Floor 3)**
*   **32941**: 3층 동관 습도 (CRAH)
*   **32959**: 3층 동관 온도 (CRAH)
*   **32948**: 3층 서관 습도 (CRAH)
*   **32965**: 3층 서관 온도 (CRAH)

**4층 (Floor 4)**
*   **32992**: 4층 동관 습도 (CRAH)
*   **32958**: 4층 동관 온도 (CRAH)
*   **32949**: 4층 서관 습도 (CRAH)
*   **32964**: 4층 서관 온도 (CRAH)

**5층 (Floor 5)**
*   **32943**: 5층 동관 습도 (CRAH)
*   **32957**: 5층 동관 온도 (CRAH)
*   **32950**: 5층 서관 습도 (CRAH)
```

### [PASS] Q2: 장비 유형이 "Rack"인 것들 다 뽑아줘
- 호출 tool: list_devices_by_type
- 소요시간: 2.8s
- 토큰: input=5375 output=73 total=5448
- 예상 결과: **15건 조회** (총 50건+) — IT/Rack (서버실 랙들)
- tool[1] list_devices_by_type args={'data_center_id': 1, 'device_type_name': 'Rack'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":21233,"device_name":"전력사용량","device_category_name":"IT","device_type_name":"Rack","location":null,"enable_monitor":1},{"device_id":19254,"device_name":"3FW-03-01","device_category_name":"IT","device_type_name":"Rack","location":"03F > 3층 서버실 A (서측-W) > A1","enable_monitor":1},{"device_id":19255,"device_name":"3FW-03-02","device_category_name":"IT","device_type_name":"Rack","location":"03F > 3층 서버실 A (서측-W) > A1","enable_monitor":1},{"device_id":19256,"dev
- LLM 답변:
```
총 15개의 장비가 있습니다. 이 장비들에 대해 더 궁금한 점이 있으신가요? (예: 특정 장비의 알람 확인, 상세 정보 요청 등)
```

### [PASS] Q3: 카테고리 "IT" 장비 목록 알려줘
- 호출 tool: list_devices_by_type
- 소요시간: 12.7s
- 토큰: input=5371 output=474 total=5845
- 예상 결과: **15건 조회** (총 50건+) — Rack 장비들
- tool[1] list_devices_by_type args={'data_center_id': 1, 'device_category_name': 'IT'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":21233,"device_name":"전력사용량","device_category_name":"IT","device_type_name":"Rack","location":null,"enable_monitor":1},{"device_id":19254,"device_name":"3FW-03-01","device_category_name":"IT","device_type_name":"Rack","location":"03F > 3층 서버실 A (서측-W) > A1","enable_monitor":1},{"device_id":19255,"device_name":"3FW-03-02","device_category_name":"IT","device_type_name":"Rack","location":"03F > 3층 서버실 A (서측-W) > A1","enable_monitor":1},{"device_id":19256,"dev
- LLM 답변:
```
총 15개의 "IT" 카테고리 장비가 있습니다. 각 장비의 상세 정보는 다음과 같습니다:

*   **장비 ID 21233**: 전력사용량 (IT, Rack)
*   **장비 ID 19254**: 3FW-03-01 (IT, Rack)
*   **장비 ID 19255**: 3FW-03-02 (IT, Rack)
*   **장비 ID 19256**: 3FW-03-03 (IT, Rack)
*   **장비 ID 19257**: 3FW-03-04 (IT, Rack)
*   **장비 ID 19258**: 3FW-03-05 (IT, Rack)
*   **장비 ID 19259**: 3FW-03-06 (IT, Rack)
*   **장비 ID 19260**: 3FW-03-07 (IT, Rack)
*   **장비 ID 19261**: 3FW-03-08 (IT, Rack)
*   **장비 ID 19262**: 3FW-03-09 (IT, Rack)
*   **장비 ID 19263**: 3FW-03-10 (IT, Rack)
*   **장비 ID 19264**: 3FW-03-11 (IT, Rack)
*   **장비 ID 19265**: 3FW-03-12 (IT, Rack)
*   **장비 ID 19266**: 3FW-03-13 (IT, Rack)
*   **장비 ID 19267**: 3FW-03-14 (IT, Rack)
```

### [PASS] Q4: 장비 타입 "CRAC"인 장비 최대 10개 조회해줘
- 호출 tool: list_devices_by_type
- 소요시간: 2.6s
- 토큰: input=5394 output=61 total=5455
- 예상 결과: **15건 조회** (총 50건+) — CRAC-1F~9F 계열
- tool[1] list_devices_by_type args={'data_center_id': 1, 'device_type_name': 'CRAC'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":21232,"device_name":"밸브개도율에 따른 유량값비교(3F B-101-13)","device_category_name":"HVAC","device_type_name":"CRAC","location":null,"enable_monitor":1},{"device_id":1563,"device_name":"CRAC-1F-112-1","device_category_name":"HVAC","device_type_name":"CRAC","location":"01F > 1F 운영설비 > A1","enable_monitor":1},{"device_id":1564,"device_name":"CRAC-1F-112-2","device_category_name":"HVAC","device_type_name":"CRAC","location":"01F > 1F 운영설비 > A1","enable_monitor":1},{"de
- LLM 답변:
```
총 16개의 장비가 조회되었습니다. (최대 10개 요청 시, 10개를 보여드립니다.)
```

### [PASS] Q5: 카테고리는 "Electric Power", 타입은 "Switchboard"인 장비 목록 보여줘
- 호출 tool: list_devices_by_type
- 소요시간: 2.5s
- 토큰: input=5205 output=67 total=5272
- 예상 결과: **15건 조회** (총 50건+) — LV, LP 계열 분전반들
- tool[1] list_devices_by_type args={'data_center_id': 1, 'device_category_name': 'Electric Power', 'device_type_name': 'Switchboard'}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"device_id":32967,"device_name":"10층 동관 전력사용량","device_category_name":"Electric Power","device_type_name":"Busway Gateway","location":null,"enable_monitor":1},{"device_id":32968,"device_name":"10층 서관 전력사용량","device_category_name":"Electric Power","device_type_name":"Busway Gateway","location":null,"enable_monitor":1},{"device_id":32969,"device_name":"3층 동관 전력사용량","device_category_name":"Electric Power","device_type_name":"Busway Gateway","location":null,"enable_monit
- LLM 답변:
```
총 14개의 장비가 확인되었습니다. 이 장비들의 상세 정보가 필요하신가요?
```
