---
name: "maria-mcp-build"
description: "Use this skill when (re)building, extending, or refactoring the maria_mcp module — the MariaDB-backed MCP server that exposes DCIM device/alarm data to LangGraph agents. Trigger when adding new tools to maria_mcp, implementing the deferred llm_analysis_result write path, or fixing/regression-checking maria_mcp. Do NOT use for scaffolding new MCP servers (use new-mcp-server-scaffold instead) or non-MCP modules."
---

# maria_mcp 구축 플레이북

`maria_mcp` 는 LangGraph 에이전트가 DCIM 운영 MariaDB 의 장비/장애 알람을
조회할 수 있도록 MCP tool 을 노출하는 read-only MCP 서버다.

## 0. 작업 시작 전 필독

- `CLAUDE.md` — 시스템 흐름, 코딩 규칙, 모듈별 상태
- `docs/spec/maria_mcp_spec.md` — tool 명세 (파라미터/응답 컬럼/SQL 대상/정렬)
- `docs/spec/mcp_common_spec.md` — 포트/환경변수/디렉토리/로깅 공통 규약
- `docs/schema/mariadb_schema.sql` — 실제 DDL (`im_device_inf`, `fm_fault_alarm_cur`, `fm_fault_alarm_his`)

부분 읽기 금지. 위 4개는 전체를 읽는다.

> 공통 scaffold 패턴(lazy Settings, lifespan, _ApiKeyMiddleware, logging, conftest 구조)은
> `new-mcp-server-scaffold` 스킬에 정리되어 있다. 이 파일은 maria_mcp 고유 내용만 다룬다.

## 1. 핵심 원칙

- **read-only 1차 범위 유지**. `llm_analysis_result` 저장 / Notification 관련은 별도 작업으로 분리.
- **응답 컬럼은 핵심만**. sLLM 컨텍스트 절약. spec 의 응답 표를 임의 확장하지 않는다.
- **페이징 없음**. `limit` 으로 결과 수 제한, 디폴트 정렬 1개만.
- **`data_center_id` 가 모든 tool 의 첫 인자** (멀티 데이터센터 대응).
- **단건 조회는 미존재 시 `None` 반환**, 예외 던지지 않는다.
- **시크릿은 `.env` 환경변수로만**. yaml/코드/Git 에 절대 하드코딩 금지.
- **Python 3.13**, `uv` 관리. `pip install` 직접 실행 금지.

## 2. 디렉토리 구조

```
src/maria_mcp/
├── __init__.py
├── __main__.py
├── server.py
├── config.py
├── db.py                # asyncmy pool — maria_mcp 고유
├── tools.py
├── queries.py           # SQL 상수 — maria_mcp 고유
├── models.py
├── logging_setup.py
└── diagnostics.py
```

## 3. maria_mcp 고유 패턴

### 3.1 asyncmy 풀 + DictCursor

```python
# db.py — 모듈-전역 _pool, autocommit=True (read-only)
_pool: Any = None

async def init_pool() -> None:
    global _pool
    if _pool is not None: return
    s = get_settings()
    _pool = await asyncmy.create_pool(
        host=s.maria_host, port=s.maria_port,
        user=s.maria_user, password=s.maria_password, db=s.maria_db,
        minsize=s.maria_pool_min, maxsize=s.maria_pool_max,
        autocommit=True, charset="utf8mb4",
    )

@asynccontextmanager
async def cursor() -> AsyncIterator[DictCursor]:
    if _pool is None:
        raise RuntimeError("DB pool is not initialized. Call init_pool() first.")
    async with _pool.acquire() as conn:
        async with conn.cursor(cursor=DictCursor) as cur:
            yield cur
```

- **DictCursor 고정** (Pydantic 모델 매핑 단순화).
- 풀 lifecycle 은 FastMCP `lifespan` 에서만 관리.
- `fetch_one` / `fetch_all` 헬퍼로 통일하고 안에서 `log_query` 호출.

### 3.2 SQL 은 별도 파일

`queries.py` 에 `SELECT_*` 상수로 둔다. tool 코드에 인라인 SQL 금지.
파라미터 바인딩은 `%s` (asyncmy). **f-string 금지 (SQLi 위험)**.

### 3.3 limit / hours 클램프

```python
# tools.py
_ALARM_LIMIT_MAX = 200
_HOURS_MAX = 720  # 30일

def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
```

각 tool 의 max 값은 `maria_mcp_spec.md` 4.x 표를 따른다 (active=100, by_time/device=200, hours=720).

## 4. 환경변수

```
MARIA_HOST=
MARIA_PORT=3306
MARIA_USER=
MARIA_PASSWORD=
MARIA_DB=
MCP_HOST=0.0.0.0
MCP_PORT=8001
MCP_API_KEY=
LOG_LEVEL=INFO
```

`MARIA_PASSWORD` / `MCP_API_KEY` 는 절대 chat/PR/yaml 에 노출하지 않는다.

## 5. 진단 (`diagnostics.py`)

`uv run maria-mcp-diag` 가 출력해야 하는 것:
- DB 접속 성공 여부 (host/db 표시)
- `im_device_inf` / `fm_fault_alarm_cur` / `fm_fault_alarm_his` row count
- 샘플 `(data_center_id, device_id)`, 샘플 `(data_center_id, alarm_id)` (테스트 fixture 와 동일 쿼리)

## 6. 테스트

두 레이어 병행 운영:

| 파일 | 종류 | DB |
|------|------|----|
| `tests/test_maria_mcp_tools.py` | 단위 테스트 | AsyncMock (빠름, 0.1s 이내) |
| `tests/test_maria_mcp_integration.py` | 통합 테스트 | 실 DB (`MARIA_HOST` 없으면 skip) |

`conftest.py` session-scoped fixture (통합 테스트용):
- `_pool` — `init_pool()` → yield → `close_pool()`, DB 실패 시 `pytest.skip`
- `sample_device` — `im_device_inf WHERE use_yn='Y'` 에서 1건
- `sample_alarm` — `fm_fault_alarm_cur` 에서 최신 1건

테스트 실행: `! uv run pytest tests/ -v` (`!` 프리픽스로 직접 실행해서 결과 확인할 것)

## 7. 새 tool 추가 시 절차 (TDD)

**테스트 먼저 작성 후 구현한다.**

1. `tests/test_maria_mcp_tools.py` 에 `TestXxx` 클래스 + 5개 케이스 작성 (정상 2·엣지 2·실패 1).
2. `! uv run pytest tests/ -k "TestXxx" -v` → 실패(Red) 확인.
3. `docs/spec/maria_mcp_spec.md` 4.x 에 spec 항목 추가 (파라미터·응답·SQL 대상·정렬·limit).
4. `models.py` 에 응답 Pydantic 모델 (필요 시 새로 정의).
5. `queries.py` 에 `SELECT_*` 상수.
6. `tools.py` 에 본체 함수 (`log_tool_call` + `_clamp` + 모델 변환).
7. `server.py` 에 `@mcp.tool` 위임 함수 (1-2줄 + 한 줄 docstring).
8. `! uv run pytest tests/ -v` → 전체 통과(Green) 확인.
9. §8 검증 체크리스트 전부 실행.

## 8. 실행 / 검증 체크리스트

```bash
uv run python -c "from maria_mcp import server; print(server.mcp.name)"
uv run python -c "import asyncio; from maria_mcp.server import mcp; \
    print([t.name for t in asyncio.run(mcp.list_tools())])"
uv run maria-mcp-diag
uv run pytest tests/ -v
uv run maria-mcp
# (다른 터미널)
uv run mcp-client-diag
```

## 9. 흔한 함정 (maria_mcp 고유)

- **`asyncio_default_test_loop_scope` 누락** → `Future attached to a different loop`. 반드시 `session`.
- **f-string SQL** → 절대 금지. `%s` 바인딩만.
- **풀을 tool 안에서 init** → race condition. 오직 `lifespan` 에서만 init/close.
- **dict 직반환** → 응답 스키마 드리프트. Pydantic 모델 강제.
- **`Settings()` 모듈 최상단 호출** → import 만으로 ValidationError. `get_settings()` 사용.

## 10. 본 스킬 범위 외

- `llm_analysis_result` 저장 / Notification tool 추가 → spec 결정 후 별도 작업.
- 공통 모듈(`mcp_common`) 추출 → 두 번째 MCP 서버 구현 후 반복 패턴 관찰 시 재검토.
- read/write 분리 또는 트랜잭션 도입 → 현재 read-only 가정을 깨야 할 명확한 요구가 있을 때만.
