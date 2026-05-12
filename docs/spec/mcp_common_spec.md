# MCP 서버 공통 스펙

본 문서는 `aidc_llm_agent` 의 MCP 서버 모듈들(`maria_mcp`, `rag_mcp`, `metric_mcp`, …)이
공통으로 따르는 **이미 검증된 규약**만 모은 문서다.

> 추상 베이스 클래스나 공통 프레임워크 모듈은 의도적으로 정의하지 않는다.
> "두 번째 MCP 구현 후 실제 반복 패턴이 관찰되면" 추출 여부를 재검토한다 (rule of three).

---

## 1. 적용 대상

| 모듈 | 상태 |
|------|------|
| `maria_mcp` | 1차 구현 완료 — 본 규약의 레퍼런스 구현 |
| `rag_mcp` | 예정 |
| `metric_mcp` | 예정 |
| `notification_mcp` (또는 `maria_mcp` 통합) | 미정 |

신규 MCP 서버 모듈을 추가할 때는 **본 문서의 규약을 그대로 따른다**.
규약을 벗어나야 한다면 그 이유를 해당 모듈 spec 에 명시한다.

---

## 2. 기술 스택

| 항목 | 값 |
|------|---|
| 언어/런타임 | Python 3.13 |
| 패키지 관리 | `uv` (CPU 서버 공통) |
| MCP 프레임워크 | FastMCP |
| Transport | `streamable_http` (HTTP + SSE) |
| 응답 모델 | Pydantic v2 |
| 설정 로딩 | `pydantic-settings` + `.env` |

---

## 3. 포트 / Transport

각 MCP 서버는 **고정 포트**를 사용하며 `config/mcp_servers.yaml` 의 `url` 과 일치해야 한다.

| 모듈 | 포트 | URL |
|------|------|-----|
| `maria_mcp` | 8001 | `http://localhost:8001/mcp/` |
| `rag_mcp` | 8002 | `http://localhost:8002/mcp/` |
| `metric_mcp` | 8003 | `http://localhost:8003/mcp/` |
| `notification_mcp` (TBD) | 8004 | `http://localhost:8004/mcp/` |

- Transport 는 `streamable_http` 기본. 필요 시 `sse` 허용.
- 엔드포인트 경로는 FastMCP 디폴트 `/mcp/` 를 그대로 사용.

---

## 4. 환경변수 컨벤션

### 4.1 모듈 전용 변수 — `<MODULE>_*` 접두사

| 모듈 | 접두사 |
|------|--------|
| `maria_mcp` | `MARIA_*` (`MARIA_HOST`, `MARIA_USER`, …) |
| `rag_mcp` | `QDRANT_*` |
| `metric_mcp` | `DRUID_*` |

### 4.2 모든 MCP 서버 공통

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `MCP_HOST` | `0.0.0.0` | FastMCP bind host |
| `MCP_PORT` | (모듈별, §3 참고) | FastMCP bind port |
| `MCP_API_KEY` | 필수 | 클라이언트 인증용 API 키 (시크릿) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

### 4.3 시크릿 관리

- 비밀번호/토큰/API 키는 **환경변수로만** 주입. yaml/코드/Git 에 절대 하드코딩 금지.
- 로컬 개발은 `.env` 파일 사용 (`.env.example` 을 레포에 커밋).
- 서버 환경은 systemd `EnvironmentFile=` 또는 컨테이너 시크릿으로 주입.

### 4.4 Settings 로딩 패턴

`config.py` 에서 `pydantic_settings.BaseSettings` 로 정의하고, **import 시점에 인스턴스화하지 않는다**:

```python
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

→ 환경변수 누락 시 import 만으로 ValidationError 가 나는 것을 방지 (테스트/진단 도구가 죽지 않도록).

---

## 5. 인증 (API Key 검증)

### 5.1 개요

설계도의 **"인증 검증"** 단계에 해당한다. MCP 클라이언트에서 HTTP 요청이 들어오면
`X-API-Key` 헤더를 검사해 유효하지 않으면 **401** 을 반환한다.
모든 MCP 서버에 공통으로 적용한다.

### 5.2 서버 구현 패턴 (Starlette 미들웨어)

`server.py` 에 미들웨어를 추가한다. 별도 파일로 분리하지 않는다.

```python
# server.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class _ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = get_settings().mcp_api_key
        if request.headers.get("X-API-Key") != expected:
            auth_logger.warning("auth_failed client=%s", request.client)
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
```

FastMCP 는 내부적으로 Starlette ASGI 앱을 사용한다.

**확정된 주입 방식 (FastMCP 3.2.4, 2026-05-07 검증)**

`mcp.run()` 의 `middleware: list[starlette.middleware.Middleware]` 파라미터를 사용한다.
별도 ASGI 앱 추출이나 uvicorn 직접 기동 없이 클래스만 전달하면 된다:

```python
mcp.run(
    transport="http",
    host=..., port=...,
    middleware=[Middleware(_ApiKeyMiddleware)],
)
```

실제 구현 및 동작 패턴은 `maria_mcp_spec.md §5` 참조.

`Settings` 에 추가:
```python
mcp_api_key: str  # 필수, 기본값 없음
```

로거:
```python
auth_logger = logging.getLogger("<module>_mcp.auth")
```

### 5.3 인증 실패 응답

| 조건 | HTTP 상태 | 응답 본문 |
|------|-----------|----------|
| 헤더 없음 또는 값 불일치 | `401 Unauthorized` | `{"error": "Unauthorized"}` |

인증 실패는 `<module>_mcp.auth` 로거에 `WARNING` 으로 기록한다 (클라이언트 IP 포함).

### 5.4 결과 SSE push

설계도의 **"결과 SSE push"** 는 **FastMCP `streamable_http` transport 가 자동 처리**한다.
별도 SSE 전송 코드를 작성하지 않는다.
tool 함수가 값을 `return` 하면 FastMCP 가 SSE 스트림으로 클라이언트에 전달한다.

---

## 6. 디렉토리 구조

`maria_mcp` 의 구조를 표준으로 사용한다.

```
src/<module>_mcp/
├── __init__.py
├── __main__.py          # python -m <module>_mcp 진입점
├── server.py            # FastMCP 인스턴스, 미들웨어(인증), tool 등록, 실행
├── config.py            # 환경변수 → Settings (lazy get_settings)
├── tools.py             # MCP tool 구현 (얇은 어댑터)
├── models.py            # Pydantic 응답 모델
├── logging_setup.py     # 로거 설정 + 호출/쿼리 컨텍스트 매니저
└── <backend>.py         # DB/HTTP 클라이언트 (예: maria_mcp/db.py)
```

특수 파일은 모듈 성격에 따라 추가 가능 (예: `maria_mcp/queries.py`).

`pyproject.toml` 에 진입점/진단 스크립트 등록:

```toml
[project.scripts]
<module>-mcp = "<module>_mcp.__main__:main"
<module>-mcp-diag = "<module>_mcp.diagnostics:main"
```

---

## 7. Tool 설계 원칙

- **응답 컬럼은 핵심만**. sLLM 컨텍스트 최소화.
- **페이징 미제공**. 필요 시 `limit` 파라미터로 결과 수 제한 (각 tool 의 max 명시).
- **정렬은 디폴트 1개만 제공**. tool 마다 spec 에 명시.
- **멀티 데이터센터를 다루는 모듈** 은 `data_center_id` 를 첫 인자로 받는다.
- **응답은 Pydantic 모델** 또는 그 list. dict 직반환 금지.
- 단건 조회 tool 은 미존재 시 `None` 반환 (예외 던지지 않음).

---

## 8. 로깅 컨트랙트

CLAUDE.md 규칙: **모든 MCP tool 호출 및 쿼리/외부호출 실행 시간을 로깅**.

### 8.1 로거 이름

| 로거 | 용도 |
|------|------|
| `<module>_mcp.tool` | tool 진입/종료 |
| `<module>_mcp.auth` | 인증 성공/실패 |
| `<module>_mcp.db` (또는 `.client`) | 백엔드 호출 (SQL/HTTP) |

### 8.2 로그 포맷

tool 호출:
```
[<module>_mcp] tool=<name> args=<...> elapsed_ms=<...> result_count=<...>
```

백엔드 호출:
```
[<module>_mcp.db] sql=<요약> elapsed_ms=<...> rows=<...>
```

인증 실패:
```
[<module>_mcp.auth] WARNING auth_failed client=<ip:port>
```

구현은 컨텍스트 매니저로 (`maria_mcp/logging_setup.py` 의 `log_tool_call`, `log_query` 참고).

---

## 9. 실행 / 진단

```bash
# 서버 실행
uv run <module>-mcp

# 또는
uv run python -m <module>_mcp

# 진단 (백엔드 접속 + 샘플 데이터 점검)
uv run <module>-mcp-diag
```

진단 스크립트는 모든 MCP 서버 모듈에 **필수 포함**한다 (외부 의존성 살아있는지 1회 점검 목적).

---

## 10. 클라이언트 연동

LangGraph 에이전트는 `mcp_client.McpToolClient` 를 통해서만 MCP 서버에 접근한다.

### 10.1 mcp_servers.yaml

모듈 추가 시 `config/mcp_servers.yaml` 에 항목 추가. **`headers` 에 API 키 포함 필수**:

```yaml
<module>_mcp:
  transport: streamable_http
  url: http://localhost:<PORT>/mcp/
  headers:
    X-API-Key: "${MCP_API_KEY}"
```

### 10.2 환경변수 치환

yaml 의 `${VAR}` 는 PyYAML 이 처리하지 않는다.
`mcp_client/config.py` 의 `load_server_configs()` 에서 값을 읽은 뒤
`os.environ` 치환을 적용해야 한다:

```python
import re, os

def _expand_env(value: str) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)

# load_server_configs() 내부 — headers 값에 적용
for name, cfg in raw.items():
    if "headers" in cfg:
        cfg["headers"] = {k: _expand_env(v) for k, v in cfg["headers"].items()}
```

### 10.3 Tool 이름 충돌 방지

tool 이름은 **모듈 간 충돌 없도록** 짧고 의미 있게.
접두사는 사용하지 않는다 (서버 이름이 자연스럽게 namespace 역할).

---

## 11. 의존성

각 모듈 `pyproject.toml` 에 공통으로 필요한 것:

- `fastmcp`
- `pydantic`, `pydantic-settings`
- (모듈별) DB/HTTP 드라이버

테스트:
- `pytest`, `pytest-asyncio` (`asyncio_mode = "auto"`, 세션 루프 스코프)
- 통합 테스트는 실제 백엔드에 접속하는 것을 원칙으로 한다 (mock 지양).

---

## 12. 본 문서 범위 외 (추후 추출 후보)

다음 항목들은 **2개 이상 모듈에서 동일 패턴이 반복 관찰되면** 별도 `mcp_common` 모듈로 추출 검토:

- **`_ApiKeyMiddleware`** — 모든 서버에서 동일하므로 최우선 추출 후보
- 공통 `BaseSettings` (MCP_HOST/PORT/MCP_API_KEY/LOG_LEVEL 부분)
- `configure_logging` / `log_tool_call` / `log_query` 유틸
- FastMCP lifespan 관리 헬퍼

현재는 각 모듈이 자체 구현을 갖는다 (premature abstraction 회피).
