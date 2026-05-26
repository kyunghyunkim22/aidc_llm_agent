---
name: maria_mcp 테스트 구조 및 fixture 패턴
description: maria_mcp 모듈의 테스트 파일 위치, fixture 의존 관계, DB/미들웨어 테스트 분리 방법
type: project
---

## 테스트 파일 위치
- `tests/conftest.py` — 공통 fixture (session-scoped DB pool, sample_device, sample_alarm)
- `tests/test_maria_mcp_integration.py` — 실 DB 연결 통합 테스트 (10개 케이스)
- `tests/test_maria_mcp_middleware.py` — _ApiKeyMiddleware 단위 테스트 (8개 케이스, DB 불필요)
- `tests/test_maria_mcp_tools.py` — tools/queries 순수 단위 테스트 (86개 케이스, DB mock)

## fixture 의존 관계 (중요)
- `_pool`: DB pool 초기화. `autouse=False`. DB 연결 실패 시 `pytest.skip()`.
- `sample_device(_pool)`: _pool에 명시적 의존 → DB 없으면 skip.
- `sample_alarm(_pool)`: _pool에 명시적 의존 → DB 없으면 skip.
- 미들웨어 테스트는 어떤 DB fixture도 사용하지 않으므로 DB 없이 독립 실행 가능.

**Why:** 원래 `_pool`이 `autouse=True`였을 때 미들웨어 테스트까지 DB 연결을 시도해 전체 실패.
autouse 제거 후 명시적 의존으로 변경하여 분리 성공.

## DB 연결 환경
- 원격 MariaDB: `1.234.33.213:13306` (로컬 개발 환경에서 접근 불가 가능)
- 환경변수 `MCP_API_KEY`는 `.env`에 없으므로 테스트 실행 시 주입 필요:
  `MCP_API_KEY=test-key uv run pytest tests/ -v`

## timezone 처리 (test_get_alarms_by_time)
- DB 반환 `log_date`가 naive datetime일 수 있으므로 비교 전 `.replace(tzinfo=timezone.utc)` 처리.
- `datetime.now(tz=timezone.utc)`로 timezone-aware 기준 시간 사용.

## 단위 테스트 mock 패턴 (test_maria_mcp_tools.py)
- `patch("maria_mcp.tools.db.fetch_one", new=AsyncMock(return_value=...))` — fetch_one mock
- `patch("maria_mcp.tools.db.fetch_all", new=AsyncMock(return_value=...))` — fetch_all mock
- clamp 검증: `mock_fetch.call_args[0][2]` 로 params tuple 추출 후 해당 인덱스 확인
  - hours: params[2], days: params[2], limit: params[-1] (함수마다 파라미터 위치 다름)
- `get_active_alarms_for_devices` IN 플레이스홀더 수: `sql.count("%s") == len(device_ids) + 2`
  - 함수가 반환하는 SQL에만 %s가 있음 (data_center_id + N개 + limit)
- `list_devices_by_type`, `search_devices`, `get_active_alarms_for_devices` 조기 반환 시
  `mock_fetch.assert_not_called()`로 DB 호출 방지 검증
