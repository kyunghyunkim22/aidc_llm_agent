---
name: maria_mcp spec 분석 결과
description: maria_mcp 모듈 (MariaDB MCP 서버) 전체 spec 분석, 5개 tool, 응답 모델, 의존성 및 TBD 항목 정리
type: reference
---

## maria_mcp 모듈 요약

**역할**: FastMCP 기반 HTTP+SSE 서버로 MariaDB 장비/알람 정보를 조회하는 MCP tool 노출 (읽기 전용)

**핵심 구현 대상**:
- **5개 MCP Tool**: get_device_info, get_alarm_detail, get_active_alarms, get_alarms_by_time, get_device_alarms
- **3개 Pydantic 모델**: DeviceInfo, AlarmDetail, AlarmSummary
- **7개 핵심 모듈**: db.py, tools.py, config.py, models.py, queries.py, logging_setup.py, server.py

**DB 테이블** (MariaDB):
- `im_device_inf` (PK: data_center_id, device_id)
- `fm_fault_alarm_cur` (UK: data_center_id, id)
- `fm_fault_alarm_his` (UK: data_center_id, id, log_date — log_date RANGE 파티션, 현재 미사용)

**의존성**:
- asyncmy (async MariaDB)
- fastmcp (MCP 서버 프레임워크)
- pydantic, pydantic-settings
- python-dotenv (선택)

**환경변수** (필수): MARIA_HOST, MARIA_USER, MARIA_PASSWORD, MARIA_DB

## 주요 TBD 항목

1. **llm_analysis_result 테이블 스키마** — 분석 결과 저장 테이블이 미정 (향후 저장 tool 추가 시 필요)
2. **Notification 관련 tool** — 사용자 조회 등 상세 spec 미정
3. **fm_fault_alarm_his 활용 tool** — 이력 테이블은 스키마에 도입됐으나 조회 tool 미구현. `cur` 보존 기간 초과 RCA 컨텍스트가 필요해지면 추가.

## 구현 순서 (위상 정렬)

1. models.py → config.py → queries.py → logging_setup.py → db.py → tools.py → server.py → __main__.py
2. 테스트, 진단 스크립트, 스크립트 엔트리 포인트 등록

## 로깅 규칙

- Tool 호출: `[maria_mcp] tool=<name> args=<...> elapsed_ms=<...> result_count=<...>`
- DB 쿼리: `[maria_mcp.db] sql=<요약> elapsed_ms=<...> rows=<...>`
