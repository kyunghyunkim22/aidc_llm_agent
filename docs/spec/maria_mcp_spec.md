# maria_mcp Spec

## 1. 개요

`maria_mcp`는 LangGraph 에이전트가 **MariaDB(DCIM 운영 DB)** 의 장비/장애 알람 정보를
조회할 수 있도록 MCP tool을 노출하는 서버다.

- **위치**: CPU 서버
- **프레임워크**: FastMCP
- **Transport**: HTTP + SSE
- **DB 드라이버**: `asyncmy` (async MariaDB)
- **언어/런타임**: Python 3.13
- **패키지 관리자**: `uv`

> 본 문서 범위는 **조회(read-only)** 기능에 한한다.
> 분석결과 저장(`llm_analysis_result`) / Notification 관련 tool은 향후 별도 정의 (§10).

---

## 2. 디렉토리 구조

```
src/maria_mcp/
├── __init__.py
├── __main__.py          # python -m maria_mcp 진입점
├── server.py            # FastMCP 인스턴스, tool 등록, 실행
├── config.py            # 환경변수 → Settings 모델
├── db.py                # asyncmy connection pool 관리
├── tools.py             # MCP tool 구현
├── queries.py           # SQL 문자열 상수
├── models.py            # Pydantic 응답 모델
└── logging_setup.py     # 공통 로거 설정
```

---

## 3. 환경 변수

| 변수명 | 필수 | 기본값 | 설명 |
|--------|------|--------|------|
| `MARIA_HOST` | O | - | MariaDB 호스트 |
| `MARIA_PORT` | X | `3306` | MariaDB 포트 |
| `MARIA_USER` | O | - | 접속 계정 |
| `MARIA_PASSWORD` | O | - | 접속 비밀번호 |
| `MARIA_DB` | O | - | 데이터베이스 명 |
| `MARIA_POOL_MIN` | X | `2` | asyncmy 풀 최소 |
| `MARIA_POOL_MAX` | X | `5` | asyncmy 풀 최대 |
| `MCP_HOST` | X | `0.0.0.0` | FastMCP bind host |
| `MCP_PORT` | X | `8001` | FastMCP bind port |
| `MCP_API_KEY` | △ | `""` | 클라이언트 인증용 API 키. 미설정/빈 값이면 인증 비활성화 + WARNING 로그 (개발 모드). 운영 배포 시 필수. |
| `LOG_LEVEL` | X | `INFO` | 로그 레벨 |

**시크릿(MARIA_PASSWORD, MCP_API_KEY 등)은 yaml/코드에 절대 하드코딩 금지.** 환경변수로만 주입.

---

## 4. 인증 (API Key 검증)

`mcp_common_spec.md §5` 의 공통 패턴을 따른다.

- 모든 HTTP 요청에 대해 `X-API-Key` 헤더를 검사한다.
- 헤더 누락 또는 값 불일치 → `401 Unauthorized` 반환.
- `Settings` 에 `mcp_api_key: str` 필드 추가 (필수).
- 구현: `server.py` 내 `_ApiKeyMiddleware` (Starlette 미들웨어).
- 인증 실패는 `maria_mcp.auth` 로거에 `WARNING` 으로 기록 (클라이언트 IP 포함).

**구현 완료 (FastMCP 3.2.4)**

FastMCP 3.x 는 `mcp.run()` / `mcp.run_http_async()` 에 `middleware: list[starlette.middleware.Middleware]`
파라미터를 직접 지원한다. `mcp.get_asgi_app()` 을 꺼내거나 uvicorn 을 별도 기동할 필요가 없다.

```python
# server.py
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class _ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = get_settings().mcp_api_key
        if request.headers.get("X-API-Key") != expected:
            client = request.client
            auth_logger.warning(
                "auth_failed client=%s path=%s",
                f"{client.host}:{client.port}" if client else "unknown",
                request.url.path,
            )
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

def run() -> None:
    s = get_settings()
    middleware: list[Middleware] = []
    if s.mcp_api_key:
        middleware.append(Middleware(_ApiKeyMiddleware))
    else:
        # MCP_API_KEY 미설정 시 인증 비활성화 + WARNING (개발 모드)
        auth_logger.warning(
            "MCP_API_KEY 미설정 — API Key 인증이 비활성화되었습니다 (개발 모드). "
            "운영 배포 전 반드시 환경변수 MCP_API_KEY 를 설정하세요."
        )
    mcp.run(
        transport="http",
        host=s.mcp_host,
        port=s.mcp_port,
        middleware=middleware,
    )
```

---

## 5. DB 접속 / 연결 풀

- `asyncmy.create_pool()` 을 서버 시작 시 1회 생성, 종료 시 close.
- 모든 tool은 풀에서 conn을 획득해 사용.
- 트랜잭션 미사용(read-only).
- 커서는 `DictCursor` 사용 → DB 컬럼 → Pydantic 모델 매핑 단순화.

---

## 6. 로깅

`mcp_common_spec.md §8` 의 컨트랙트를 따른다.

| 로거 | 용도 |
|------|------|
| `maria_mcp.tool` | tool 진입/종료, elapsed_ms, result_count |
| `maria_mcp.auth` | 인증 성공/실패 (클라이언트 IP) |
| `maria_mcp.db` | SQL elapsed_ms, rows |

구현은 `logging_setup.py` 의 `log_tool_call` / `log_query` 컨텍스트 매니저로 통일.

---

## 7. 실행

```bash
# 개발
uv run python -m maria_mcp

# 또는
uv run maria-mcp   # pyproject.toml [project.scripts] 등록 시
```

FastMCP는 `streamable_http` transport로 `/mcp/` 엔드포인트 노출.

---

## 8. 의존성

`pyproject.toml`:
- `fastmcp`
- `asyncmy`
- `pydantic`
- `pydantic-settings`
- `python-dotenv` (개발용, 선택)

---

## 9. MCP Tools

### 공통 사항

- 모든 tool은 `data_center_id` (int) 를 첫 인자로 받는다 (멀티 데이터센터 대응).
- 응답은 Pydantic 모델로 정의된 dict 또는 dict의 list.
- 페이징은 제공하지 않으며 `limit` 파라미터로 결과 수를 제한한다.
- **`limit` 전역 상한 `_LIMIT_MAX = 15`**: 테스트·운영 공통 적용. 성능 최적화에 따라 변경 가능 (`tools.py`). 호출자가 더 큰 값을 전달해도 15로 clamp 된다.
- 결과 정렬은 각 tool의 디폴트(아래 명시)를 따른다.

---

### Tool 목록 (총 16개)

| tool | 분류 | 섹션 |
|------|------|------|
| `get_device_info` | 장비 단건 조회 | §9.1 |
| `search_devices` | 다중 조건 장비 검색 | §9.2 |
| `list_nearby_devices` | 같은 구역 장비 목록 | §9.3 |
| `list_devices_by_type` | 카테고리/유형별 장비 | §9.4 |
| `list_devices_by_ups` | UPS 연결 장비 목록 | §9.5 |
| `get_alarm_info` | 알람 단건 조회 | §9.6 |
| `get_active_alarms` | 미종료 알람 목록 | §9.7 |
| `get_alarms_by_time` | 시간 범위 알람 | §9.8 |
| `get_device_alarms` | 장비별 최근 N시간 알람 | §9.9 |
| `get_device_alarms_by_time` | 장비별 절대 기간 알람 | §9.10 |
| `get_alarm_history` | 알람 이력 조회 | §9.11 |
| `get_active_alarm_summary` | 알람 카운트 요약 | §9.12 |
| `get_nearby_alarms` | 같은 구역 활성 알람 | §9.13 |
| `get_checkpoint_alarms` | 동일 체크포인트 알람 | §9.14 |
| `get_alarm_history_by_policy` | 알람 정책별 이력 | §9.15 |
| `get_active_alarms_for_devices` | 다중 장비 활성 알람 | §9.16 |

---

### Tool 선택 기준

#### 장비 조회

대상 테이블이 `im_device_inf` 단일 테이블이므로 `search_devices` 하나로 대부분의 질문 케이스를 커버할 수 있다.

| 질문 유형 | 사용 tool |
|---|---|
| 장비명 부분 일치 검색 | `search_devices(device_nm=...)` |
| 위치 기준 검색 | `search_devices(location=...)` |
| 카테고리·유형 조합 검색 | `search_devices(device_category_name=..., device_type_name=...)` |
| device_id 이미 알고 있을 때 | `get_device_info(device_id=...)` |
| 카테고리·유형 정확 매칭 목록 | `list_devices_by_type` |
| UPS 연결 장비 목록 | `list_devices_by_ups` |
| 같은 구역 장비 목록 | `list_nearby_devices` |

#### 알람 조회

`fm_fault_alarm_cur`(활성) / `fm_fault_alarm_his`(이력) 두 테이블에 케이스별로 JOIN 패턴이 달라 질문 케이스마다 전용 tool로 대응한다.

| 조회 기준 | 대상 테이블 | tool |
|---|---|---|
| 전체 활성 알람 | cur | `get_active_alarms` |
| 시간 범위 | cur | `get_alarms_by_time` |
| 특정 장비 최근 N시간 | cur | `get_device_alarms` |
| 같은 구역 활성 알람 | cur + device JOIN | `get_nearby_alarms` |
| 동일 체크포인트 전 장비 | cur | `get_checkpoint_alarms` |
| 다중 장비 일괄 조회 | cur (IN 절) | `get_active_alarms_for_devices` |
| 심각도별 카운트 요약 | cur (GROUP BY) | `get_active_alarm_summary` |
| 특정 장비 이력 (N일) | his | `get_alarm_history` |
| 알람 정책 기준 전 장비 이력 | his | `get_alarm_history_by_policy` |
| 특정 장비 + 절대 datetime 범위 | cur + his UNION | `get_device_alarms_by_time` |

> 구현되지 않은 질문 케이스가 발생하면 해당 패턴에 맞는 신규 tool을 추가한다.

#### Tool 수 증가에 따른 컨텍스트 비용

LLM은 tool definition 전체를 컨텍스트에 포함하므로 tool 수가 늘수록 매 요청마다 소비되는 토큰이 증가한다 (현재 16개 ≈ 1,100 토큰 추정).
tool 추가 시 아래 기준을 만족해야 한다:

1. 기존 tool의 파라미터 조합으로 해결 불가한 쿼리 패턴인가
2. 실제 질문 케이스가 반복적으로 발생하는가
3. 추가 후 LLM의 tool 선택 혼동 가능성은 없는가 (docstring 구분 문구 필수)

#### Gemma4 docstring 원칙

유사 tool 간 혼동을 막기 위해 핵심 구분 문구를 docstring 첫 줄에 명시.

| tool | 분류 | docstring 핵심 구분 문구 |
|------|------|------------------------|
| `get_device_info` | 장비 | "**단건** 장비 핵심 정보" |
| `search_devices` | 장비 | "device_id 불명 시 **다중 조건 부분 문자열 검색**" |
| `list_nearby_devices` | 장비 | "같은 구역 **장비 목록** (알람 아님)" |
| `list_devices_by_type` | 장비 | "동일 카테고리/유형 **장비 목록**" |
| `list_devices_by_ups` | 장비 | "특정 UPS에 **연결된 장비 목록**" |
| `get_alarm_info` | 알람 | "알람 **단건** 상세 조회" |
| `get_active_alarms` | 알람 | "**전체** 데이터센터 미종료 알람 목록" |
| `get_alarms_by_time` | 알람 | "**절대 시간 범위** 알람 (device 무관, cur 테이블)" |
| `get_device_alarms` | 알람 | "최근 N시간 내 **현재 진행 중** 알람 (cur 테이블)" |
| `get_device_alarms_by_time` | 알람 | "특정 장비 + **절대 datetime 범위** 알람 (cur + his UNION)" |
| `get_alarm_history` | 알람 | "과거 N일 **완료된** 알람 이력 (his 테이블)" |
| `get_active_alarm_summary` | 알람 | "심각도별 **카운트 요약** (상세 목록 아님)" |
| `get_nearby_alarms` | 알람 | "같은 구역 다른 장비 **활성 알람**" |
| `get_checkpoint_alarms` | 알람 | "**동일 모니터링 항목** 전 장비 활성 알람" |
| `get_alarm_history_by_policy` | 알람 | "알람 정책명 기준 **전 장비** 완료 이력 (his 테이블)" |
| `get_active_alarms_for_devices` | 알람 | "**다중 장비** 활성 알람 일괄 조회 (IN 쿼리, N+1 방지)" |

---

### 장비 조회 (5개)

#### §9.1 `get_device_info`

장비 단건의 핵심 정보 조회.

**SQL 대상**: `im_device_inf` (PK 단건)

**파라미터**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `data_center_id` | int | O | 데이터센터 ID |
| `device_id` | int | O | 장비 ID |

**응답 (DeviceInfo)**

| 필드 | DB 컬럼 | 설명 |
|------|---------|------|
| `data_center_id` | data_center_id | |
| `device_id` | device_id | |
| `device_name` | device_nm | 장비명 |
| `device_category_name` | device_category_name | 카테고리 |
| `device_type_name` | device_type_name | 타입 |
| `device_model_name` | device_model_name | 모델 |
| `manufacturer_name` | manufacturer_name | 제조사 |
| `maintenance_provider_name` | maintenance_provider_name | 유지보수 업체 |
| `location` | location | 위치 (Floor>Room>Section) |
| `enable_monitor` | enable_monitor | 모니터링 상태 |
| `device_desc` | device_desc | 설명 |

장비가 없으면 `None` 반환.

---

#### §9.2 `search_devices`

`device_id` 를 모를 때 이름·유형·위치·제조사·UPS 등 다중 조건으로 장비를 검색.
각 문자열 파라미터는 LIKE 부분 일치(양쪽 `%`)로 적용한다.
`data_center_id` 외 모든 조건이 None 이면 전체 조회를 방지하기 위해 빈 리스트 반환.

**SQL 대상**: `im_device_inf` (동적 WHERE 절 — None 인 파라미터는 조건 미포함)

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_nm` | str | X | None | 장비명 부분 일치 |
| `device_type_name` | str | X | None | 유형명 부분 일치 |
| `device_category_name` | str | X | None | 카테고리명 부분 일치 |
| `location` | str | X | None | 위치 텍스트 부분 일치 (층·구역·방 이름 등) |
| `floor_id` | int | X | None | 층 내부 ID 정확 일치 (정확한 ID 값을 알 때만 사용) |
| `zone_id` | int | X | None | 구역 내부 ID 정확 일치 (정확한 ID 값을 알 때만 사용) |
| `connected_ups` | str | X | None | UPS 이름 부분 일치 |
| `manufacturer_name` | str | X | None | 제조사명 부분 일치 |
| `limit` | int | X | 15 | 최대 15 |

**필터**: `data_center_id = ? AND use_yn = 'Y'` + 지정된 조건 (LIKE 또는 exact)
**정렬**: `location ASC, device_nm ASC`

**응답 (DeviceSearchResult list)** — `DeviceSummary` + `manufacturer_name`, `connected_ups` 추가 필드

| 필드 | DB 컬럼 |
|------|---------|
| `device_id` | device_id |
| `device_name` | device_nm |
| `device_category_name` | device_category_name |
| `device_type_name` | device_type_name |
| `location` | location |
| `enable_monitor` | enable_monitor |
| `manufacturer_name` | manufacturer_name |
| `connected_ups` | connected_ups |

**파라미터 선택 기준**:
- `location`: 층·구역·방 이름 텍스트 LIKE 검색. 예) `'3층'`, `'A구역'`, `'서버실'`.
- `floor_id` / `zone_id`: DB 내부 정수 ID (층 번호가 아님). 정확한 ID 값을 알고 있을 때만 사용.

> `list_devices_by_type` / `list_devices_by_ups` 는 정확 매칭(exact)인 반면,
> `search_devices` 는 부분 문자열(LIKE) 및 다중 조건 조합을 지원한다.

---

#### §9.3 `list_nearby_devices`

기준 장비와 같은 구역(`zone_id`)의 다른 장비 목록 조회. 영향 범위 파악용.
`get_nearby_alarms`(같은 구역 알람) 와 달리 **알람 여부와 무관하게 장비 목록** 을 반환한다.
LLM 이 `zone_id` 를 직접 추출하지 않아도 되도록 내부 JOIN 으로 처리.

**SQL 대상**: `im_device_inf` (self JOIN, zone_id 기준)

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_id` | int | O | - | 기준 장비 (이 장비의 zone 내 타 장비 목록) |
| `limit` | int | X | 15 | 최대 15 |

**필터**: `zone_id = (SELECT zone_id FROM im_device_inf WHERE ...) AND device_id != ? AND use_yn = 'Y'`
**정렬**: `device_category_name ASC, device_nm ASC`

**응답 (DeviceSummary list)** — 기준 장비 자신은 제외

| 필드 | DB 컬럼 |
|------|---------|
| `device_id` | device_id |
| `device_name` | device_nm |
| `device_category_name` | device_category_name |
| `device_type_name` | device_type_name |
| `location` | location |
| `enable_monitor` | enable_monitor |

**Gemma4 사용 시점**: "이 장비 주변 같은 구역에 어떤 장비들이 있는지 목록 확인"

---

#### §9.4 `list_devices_by_type`

특정 카테고리 또는 유형의 장비 전체 목록 조회. 동일 유형 장비의 영향 범위 파악.

**SQL 대상**: `im_device_inf`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_category_name` | str | X | None | 카테고리명 필터 (예: "UPS", "Server") |
| `device_type_name` | str | X | None | 유형명 필터. category 와 type 중 하나는 필수 |
| `limit` | int | X | 15 | 최대 15 |

**필터**: `(category IS NOT NULL AND device_category_name = ?) OR (type IS NOT NULL AND device_type_name = ?)` AND `use_yn = 'Y'`
**정렬**: `location ASC, device_nm ASC`

> category 와 type 중 하나 이상 반드시 지정해야 한다. 둘 다 None 이면 빈 리스트 반환 (에러 아님).
> 부분 문자열 검색이나 둘 이상의 조건 조합이 필요하면 `search_devices` 사용.

**응답 (DeviceSummary list)**

**Gemma4 사용 시점**: "모든 UPS 장비 목록", "같은 유형 장비가 몇 대인지 파악"

---

#### §9.5 `list_devices_by_ups`

특정 UPS 에 연결된 장비 목록 조회. 전원 cascade 분석의 핵심 도구.
`im_device_inf.connected_ups` 컬럼(UPS 이름 문자열)을 기준으로 조회한다.

**SQL 대상**: `im_device_inf`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `ups_name` | str | O | - | UPS 이름 (`connected_ups` 컬럼값, `search_devices` 응답의 `connected_ups` 필드 활용) |
| `limit` | int | X | 15 | 최대 15 |

**필터**: `connected_ups = ? AND use_yn = 'Y'`
**정렬**: `location ASC, device_nm ASC`

**응답 (DeviceSummary list)**

**Gemma4 사용 시점**: "이 UPS 에 연결된 장비들이 뭔지 확인 — 전원 공급 cascade 분석"

> `ups_name` 은 `search_devices` 응답의 `connected_ups` 필드에서 그대로 가져온다.
> `DeviceInfo` 모델에는 `connected_ups` 필드가 없으므로, LLM이 먼저 `search_devices`로 장비를 검색해
> `DeviceSearchResult.connected_ups` 값을 획득한 뒤 이 tool을 호출하는 2-step 패턴.

---

### 알람 조회 (11개)

#### §9.6 `get_alarm_info`

알람 단건 상세 조회.

**SQL 대상**: `fm_fault_alarm_cur` (UK: `(data_center_id, id)`)

**파라미터**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `data_center_id` | int | O | |
| `alarm_id` | int | O | `fm_fault_alarm_cur.id` |

**응답 (AlarmDetail)**

| 필드 | DB 컬럼 |
|------|---------|
| `alarm_id` | id |
| `alarm_name` | alarm_policy_display_name |
| `device_id` | device_id |
| `device_name` | device_name |
| `checkpoint_id` | checkpoint_id |
| `checkpoint_name` | checkpoint_name |
| `severity` | alarm_severity_name |
| `confirm_state` | confirm_state_name |
| `log_date` | log_date |
| `message` | message |
| `acknowledged_date` | acknowledged_date |
| `acknowledged_message` | acknowledged_message |
| `closed_date` | closed_date |
| `closed_message` | closed_message |

알람이 없으면 `None` 반환.

---

#### §9.7 `get_active_alarms`

현재 종료되지 않은 알람 목록 조회.

**SQL 대상**: `fm_fault_alarm_cur`
**필터**: `closed_date IS NULL` (= 미종료)
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `severity` | str | X | None | 등급명 필터 (`alarm_severity_name`) |
| `limit` | int | X | 15 | 최대 15 |

**응답 (AlarmSummary list)**

| 필드 | DB 컬럼 |
|------|---------|
| `alarm_id` | id |
| `alarm_name` | alarm_policy_display_name |
| `device_id` | device_id |
| `device_name` | device_name |
| `checkpoint_name` | checkpoint_name |
| `severity` | alarm_severity_name |
| `confirm_state` | confirm_state_name |
| `log_date` | log_date |
| `closed_date` | closed_date |
| `message` | message |

---

#### §9.8 `get_alarms_by_time`

지정한 시간 범위 내 발생한 알람 조회. 장비 무관, cur 테이블만 대상.

**SQL 대상**: `fm_fault_alarm_cur`
**필터**: `log_date >= start_time AND log_date < end_time`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `start_time` | datetime | O | - | inclusive |
| `end_time` | datetime | O | - | exclusive |
| `severity` | str | X | None | 등급명 필터 |
| `limit` | int | X | 15 | 최대 15 |

**응답**: `AlarmSummary` list (§9.7과 동일 스키마)

---

#### §9.9 `get_device_alarms`

특정 장비의 최근 N시간 알람. cur 테이블만 조회하므로 현재 활성 상태인 알람만 반환.
절대 기간 지정이나 종료된 이력까지 필요하면 `get_device_alarms_by_time` 사용.

**SQL 대상**: `fm_fault_alarm_cur`
**필터**: `device_id = ? AND log_date >= NOW() - INTERVAL ? HOUR`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_id` | int | O | - | |
| `hours` | int | X | 24 | 1~3000 |
| `limit` | int | X | 15 | 최대 15 |

**응답**: `AlarmSummary` list

---

#### §9.10 `get_device_alarms_by_time`

특정 장비의 절대 datetime 범위 알람 조회. `cur`(활성) 와 `his`(이력) UNION ALL.
`get_device_alarms`(최근 N시간, cur only) 와 달리 **start_time/end_time 절대 기간**으로 지정하며
이력 테이블까지 함께 조회하므로 과거 특정 구간의 알람을 빠짐없이 확인할 때 사용한다.

**SQL 대상**: `fm_fault_alarm_cur` UNION ALL `fm_fault_alarm_his`
- `his` 테이블은 `log_date` RANGE 파티션 — `start_time`/`end_time` 을 WHERE 에 명시해 파티션 프루닝 활용

**필터 (cur + his 각각 동일)**: `data_center_id = ? AND device_id = ? AND log_date >= ? AND log_date < ? AND (? IS NULL OR alarm_severity_name = ?)`
**정렬**: `log_date DESC` (UNION 전체에 적용)

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_id` | int | O | - | |
| `start_time` | datetime | O | - | 조회 시작 (inclusive) |
| `end_time` | datetime | O | - | 조회 종료 (exclusive) |
| `severity` | str | X | None | 등급명 필터 |
| `limit` | int | X | 15 | 최대 15 |

**응답**: `AlarmSummary` list

**Gemma4 사용 시점**: "이 장비에서 특정 날짜·시간대에 발생한 알람을 cur/his 구분 없이 전체 확인"

> `get_device_alarms` 는 cur only + 상대 시간(N시간). `get_device_alarms_by_time` 은 cur+his UNION + 절대 기간.

---

#### §9.11 `get_alarm_history`

장비의 과거 완료된 알람 재발 패턴 파악. `get_device_alarms`(진행 중) 와 달리 종료된 이력 조회.

**SQL 대상**: `fm_fault_alarm_his` (일별 RANGE 파티션 — `days` 범위를 파티션 프루닝에 활용)
**필터**: `device_id = ? AND log_date >= NOW() - INTERVAL ? DAY`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_id` | int | O | - | |
| `days` | int | X | 30 | 최대 365 (파티션 보존 기간 이내) |
| `limit` | int | X | 15 | 최대 15 |

**응답 (AlarmSummary list)**

| 필드 | DB 컬럼 |
|------|---------|
| `alarm_id` | id |
| `alarm_name` | alarm_policy_display_name |
| `device_id` | device_id |
| `device_name` | device_name |
| `checkpoint_name` | checkpoint_name |
| `severity` | alarm_severity_name |
| `confirm_state` | confirm_state_name |
| `log_date` | log_date |
| `closed_date` | closed_date |
| `message` | message |

**Gemma4 사용 시점**: "이 장비에 같은 알람이 반복 발생하는지 확인"

---

#### §9.12 `get_active_alarm_summary`

전체 활성 알람의 심각도·상태 분포 카운트. 분석 시작 시 가장 먼저 호출해 전체 상황 파악.

**SQL 대상**: `fm_fault_alarm_cur` (GROUP BY)
**필터**: `closed_date IS NULL`

**파라미터**

| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `data_center_id` | int | O | |

**응답 (`AlarmSummaryStats`)**

| 필드 | 설명 |
|------|------|
| `total_active` | 전체 미종료 알람 수 |
| `by_severity` | `{severity_name: count}` dict |
| `unacknowledged` | 미확인(`confirm_state_name` = 미확인) 건수 |

**Gemma4 사용 시점**: "분석 시작 전 전체 심각도 현황 파악 — 상세 목록이 아닌 카운트만 필요할 때"

---

#### §9.13 `get_nearby_alarms`

기준 장비와 같은 구역(`zone_id`)의 다른 장비 활성 알람 조회. 위치 기반 cascade 탐지.
LLM 이 `zone_id` 를 직접 추출하지 않아도 되도록 내부 JOIN 으로 처리.

**SQL 대상**: `fm_fault_alarm_cur` JOIN `im_device_inf` (zone_id 기준)
**필터**: `zone_id = (SELECT zone_id FROM im_device_inf WHERE ...) AND device_id != ?`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_id` | int | O | - | 기준 장비 (이 장비의 zone 내 타 장비 알람 조회) |
| `limit` | int | X | 15 | 최대 15 |

**응답 (AlarmSummary list)** — 기준 장비 자신의 알람은 제외

**Gemma4 사용 시점**: "이 장비 주변 같은 구역에 동시 알람이 있는지 확인"

---

#### §9.14 `get_checkpoint_alarms`

동일 체크포인트명(온도·전압·전류 등)의 활성 알람이 여러 장비에 동시 발생하는지 확인. 공통 원인(냉각 이상, 전원 이상) 탐지.

**SQL 대상**: `fm_fault_alarm_cur`
**필터**: `checkpoint_name = ? AND closed_date IS NULL`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `checkpoint_name` | str | O | - | 체크포인트명 (알람의 `checkpoint_name` 필드값) |
| `limit` | int | X | 15 | 최대 15 |

**응답 (AlarmSummary list)**

**Gemma4 사용 시점**: "알람의 checkpoint_name 을 기준으로 동일 항목이 다른 장비에도 발생했는지 확인"

---

#### §9.15 `get_alarm_history_by_policy`

특정 알람 정책(`alarm_policy_name`)이 과거 N일간 어떤 장비들에서 발생했는지 이력 조회.
`get_alarm_history`(단일 device_id 기준)와 달리 **알람 종류 기준으로 전 장비 이력**을 반환한다.
동일 알람이 반복 발생하는지, 여러 장비에 걸쳐 나타나는 패턴인지 파악할 때 사용.

**SQL 대상**: `fm_fault_alarm_his`
**필터**: `alarm_policy_name = ? AND log_date >= NOW() - INTERVAL ? DAY`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `alarm_policy_name` | str | O | - | 알람 내부 이름 (`alarm_policy_name` 컬럼, 알람 상세의 `alarm_name` 필드에서 획득) |
| `days` | int | X | 30 | 최대 365 |
| `limit` | int | X | 15 | 최대 15 |

**응답**: `AlarmSummary` list

**Gemma4 사용 시점**: "이 알람 종류가 이 장비에만 발생했는지, 다른 장비에서도 반복되는 패턴인지 확인"

---

#### §9.16 `get_active_alarms_for_devices`

여러 장비의 활성 알람을 단일 쿼리로 조회. `list_nearby_devices`로 장비 목록을 얻은 뒤
각 장비의 알람을 N번 조회하는 대신 **한 번의 IN 쿼리**로 처리한다.

**SQL 대상**: `fm_fault_alarm_cur`
**필터**: `device_id IN (...) AND closed_date IS NULL`
**정렬**: `log_date DESC`

**파라미터**

| 이름 | 타입 | 필수 | 기본 | 설명 |
|------|------|------|------|------|
| `data_center_id` | int | O | - | |
| `device_ids` | list[int] | O | - | 조회할 장비 ID 목록. 최대 50개 (초과 시 앞 50개만 처리). 빈 리스트 → 빈 리스트 반환. |
| `limit` | int | X | 15 | 최대 15 |

**응답**: `AlarmSummary` list

**Gemma4 사용 시점**: "list_nearby_devices 로 얻은 주변 장비들의 알람을 한 번에 확인"

---

## 10. 미결 항목

- `llm_analysis_result` 저장 tool — 스키마 결정 후
- Notification 관련 사용자 조회 tool — 요구사항 확정 후
