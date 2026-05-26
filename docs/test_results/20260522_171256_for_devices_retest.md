# 테스트 결과 — 2026-05-22 17:13:34

- 전체: 5건 / PASS: 5건 / FAIL: 0건
- LLM: http://1.234.33.212:8000/v1 / /models/gemma-4-E4B-it-W4A16

---

## get_active_alarms_for_devices

### [PASS] Q1: 장비 ID 2208, 2276, 2273, 2274 네 대의 현재 활성 알람 한 번에 보여줘
- 호출 tool: get_active_alarms_for_devices
- 소요시간: 8.8s
- 토큰: input=6652 output=256 total=6908
- 예상 결과: **4건**: CH-E-101-1(Warning), 냉각탑-4-1(Critical), 냉각탑-2-1/2-2(Warning)
- tool[1] get_active_alarms_for_devices args={'data_center_id': 1, 'device_ids': [2208, 2276, 2273, 2274]}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"alarm_id":5797194,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":2208,"device_name":"CH-E-101-1","checkpoint_name":"Unit Warning Code AV","severity":"Warning","confirm_state":"확인","log_date":"2026-02-05T17:03:17","closed_date":null,"message":"고온냉동기에서 오류(25 )이/가 발생하였습니다.\\n- 고객명 : DVD\\n- 위치 : B5F/기계실 B (동측-E)\\n"},{"alarm_id":5797065,"alarm_name":"A 고온냉각탑 수조 고수위","device_id":2273,"device_name":"A WING 고온 냉각탑-2-1","checkpoint_name":"A 수조 고수위","severity":"
- LLM 답변:
```
총 4건의 활성 알람이 있습니다. 첫 번째 알람의 상세 정보는 다음과 같습니다.

**알람 상세 정보 (Alarm ID: 5797194)**
*   **알람 이름:** 고온냉동기 - Unit Warning Code AV 알람
*   **장치 ID:** 2208
*   **장치 이름:** CH-E-101-1
*   **체크포인트 이름:** Unit Warning Code AV
*   **심각도:** Warning
*   **확인 상태:** 확인
*   **로그 날짜:** 2026-02-05T17:03:17
*   **메시지:** 고온냉동기에서 오류(25 )이/가 발생하였습니다.
    *   고객명 : DVD
    *   위치 : B5F/기계실 B (동측-E)
```

### [PASS] Q2: 장비 목록 [2208, 2210, 2211]에서 지금 뜨고 있는 알람 전부 뽑아줘
- 호출 tool: get_active_alarms_for_devices
- 소요시간: 6.7s
- 토큰: input=6591 output=245 total=6836
- 예상 결과: **3건**: CH-E-101-1/3/4 모두 고온냉동기 Unit Warning Code AV / Warning
- tool[1] get_active_alarms_for_devices args={'data_center_id': 1, 'device_ids': [2208, 2210, 2211]}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"alarm_id":5797194,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":2208,"device_name":"CH-E-101-1","checkpoint_name":"Unit Warning Code AV","severity":"Warning","confirm_state":"확인","log_date":"2026-02-05T17:03:17","closed_date":null,"message":"고온냉동기에서 오류(25 )이/가 발생하였습니다.\\n- 고객명 : DVD\\n- 위치 : B5F/기계실 B (동측-E)\\n"},{"alarm_id":5797191,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":2210,"device_name":"CH-E-101-3","checkpoint_name":"Unit Warning
- LLM 답변:
```
총 3건의 알람이 있습니다. 첫 번째 알람의 상세 정보는 다음과 같습니다.

**알람 상세 정보 (Alarm ID: 5797194)**
*   **알람 이름:** 고온냉동기 - Unit Warning Code AV 알람
*   **장치 ID:** 2208
*   **장치 이름:** CH-E-101-1
*   **체크포인트 이름:** Unit Warning Code AV
*   **심각도:** Warning
*   **확인 상태:** 확인
*   **발생 시간:** 2026-02-05T17:03:17
*   **메시지:** 고온냉동기에서 오류(25 )이/가 발생하였습니다.
    - 고객명 : DVD
    - 위치 : B5F/기계실 B (동측-E)
```

### [PASS] Q3: 장비 ID [17546, 2208, 2276]인데, 얘네 중에 지금 알람 있는 거 있어?
- 호출 tool: get_active_alarms_for_devices
- 소요시간: 6.7s
- 토큰: input=6527 output=247 total=6774
- 예상 결과: **3건**: CH-E-101-1(Warning), CH-E-201-6(Warning), 냉각탑-4-1(Critical)
- tool[1] get_active_alarms_for_devices args={'data_center_id': 1, 'device_ids': [17546, 2208, 2276]}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"alarm_id":5797194,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":2208,"device_name":"CH-E-101-1","checkpoint_name":"Unit Warning Code AV","severity":"Warning","confirm_state":"확인","log_date":"2026-02-05T17:03:17","closed_date":null,"message":"고온냉동기에서 오류(25 )이/가 발생하였습니다.\\n- 고객명 : DVD\\n- 위치 : B5F/기계실 B (동측-E)\\n"},{"alarm_id":5797192,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":17546,"device_name":"CH-E-201-6","checkpoint_name":"Unit Warnin
- LLM 답변:
```
총 3건의 알람이 있습니다. 첫 번째 알람의 상세 정보는 다음과 같습니다.

**알람 상세 정보 (Alarm ID: 5797194)**
*   **알람 이름:** 고온냉동기 - Unit Warning Code AV 알람
*   **장치 ID:** 2208
*   **장치 이름:** CH-E-101-1
*   **체크포인트 이름:** Unit Warning Code AV
*   **심각도:** Warning
*   **확인 상태:** 확인
*   **발생 시각:** 2026-02-05T17:03:17
*   **메시지:** 고온냉동기에서 오류(25 )이/가 발생하였습니다.
    - 고객명 : DVD
    - 위치 : B5F/기계실 B (동측-E)
```

### [PASS] Q4: 장비 ID [33077, 33034, 2273, 2274, 2276] 다섯 대 활성 알람 최대 10건 조회해줘
- 호출 tool: get_active_alarms_for_devices
- 소요시간: 8.1s
- 토큰: input=8209 output=243 total=8452
- 예상 결과: **11건**: 냉각탑/냉동기 Warning/Critical 혼재
- tool[1] get_active_alarms_for_devices args={'data_center_id': 1, 'device_ids': [33077, 33034, 2273, 2274, 2276]}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"alarm_id":5797065,"alarm_name":"A 고온냉각탑 수조 고수위","device_id":2273,"device_name":"A WING 고온 냉각탑-2-1","checkpoint_name":"A 수조 고수위","severity":"Warning","confirm_state":"확인","log_date":"2026-02-04T10:17:26","closed_date":null,"message":"The value (Alarm) is equal to 1.0 \\n- 고객명 : DVD\\n"},{"alarm_id":5797066,"alarm_name":"B 고온냉각탑 수조 고수위","device_id":2274,"device_name":"A WING 고온 냉각탑-2-2","checkpoint_name":"B 수조 고수위","severity":"Warning","confirm_state":"확인","log_date":
- LLM 답변:
```
총 10건의 활성 알람이 있습니다. 첫 번째 알람의 상세 정보는 다음과 같습니다:

**알람 정보:**
*   **알람 ID:** 5797065
*   **알람 이름:** A 고온냉각탑 수조 고수위
*   **장치 ID:** 2273
*   **장치 이름:** A WING 고온 냉각탑-2-1
*   **체크포인트 이름:** A 수조 고수위
*   **심각도:** Warning
*   **확인 상태:** 확인
*   **로그 날짜:** 2026-02-04T10:17:26
*   **메시지:** The value (Alarm) is equal to 1.0 \n- 고객명 : DVD
```

### [PASS] Q5: 장비 ID [2210, 2211, 2274] 세 대 활성 알람 한꺼번에 확인해줘
- 호출 tool: get_active_alarms_for_devices
- 소요시간: 7.2s
- 토큰: input=6575 output=264 total=6839
- 예상 결과: **3건**: 고온냉동기 Unit Warning Code AV(2210/2211) + 저온냉각탑 Warning(2274) (장비 변경: 15930~15932→2210/2211/2274)
- tool[1] get_active_alarms_for_devices args={'data_center_id': 1, 'device_ids': [2210, 2211, 2274]}
  → output_len=N/A, preview: [{'type': 'text', 'text': '[{"alarm_id":5797191,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":2210,"device_name":"CH-E-101-3","checkpoint_name":"Unit Warning Code AV","severity":"Warning","confirm_state":"확인","log_date":"2026-02-05T16:42:17","closed_date":null,"message":"고온냉동기에서 오류(25 )이/가 발생하였습니다.\\n- 고객명 : DVD,China Telecom Global(알리바바) [KR191],SKT MEC(AWS) [SKT MEC]\\n- 위치 : B5F/기계실 B (동측-E)\\n"},{"alarm_id":5797190,"alarm_name":"고온냉동기 - Unit Warning Code AV 알람","device_id":2211,
- LLM 답변:
```
총 3건의 활성 알람이 있습니다. 첫 번째 알람의 상세 정보는 다음과 같습니다.

**알람 상세 정보 (Alarm ID: 5797191)**

*   **알람 이름:** 고온냉동기 - Unit Warning Code AV 알람
*   **장비 ID:** 2210
*   **장비 이름:** CH-E-101-3
*   **심각도:** Warning
*   **체크포인트:** Unit Warning Code AV
*   **발생 시간:** 2026-02-05T16:42:17
*   **메시지:** 고온냉동기에서 오류(25 )이/가 발생하였습니다.
    - 고객명 : DVD,China Telecom Global(알리바바) [KR191],SKT MEC(AWS) [SKT MEC]
    - 위치 : B5F/기계실 B (동측-E)
```
