---
name: "new-mcp-server-scaffold"
description: "Use this skill when scaffolding a new MCP server module (rag_mcp, metric_mcp, etc.) in the aidc_llm_agent project. Provides the exact verified file layout, code stubs, and checklist that all MCP servers share — derived from maria_mcp as the reference implementation. Trigger when the user says they want to create or start a new *_mcp module."
---

# 신규 MCP 서버 스캐폴드 플레이북

`maria_mcp` 가 레퍼런스 구현이다. 아래 패턴은 모두 실제 동작이 검증됐다.
새 모듈을 만들 때 이 파일의 순서대로 따라간다.

## 0. 작업 전 필독 (전체 읽기, 부분 읽기 금지)

1. `CLAUDE.md` — 시스템 흐름, 코딩 규칙
2. `docs/spec/mcp_common_spec.md` — 포트·환경변수·로깅 공통 규약
3. 해당 모듈 spec (예: `docs/spec/rag_mcp_spec.md`)
4. 백엔드 접속 대상 DDL / API 스펙

---

## 1. 포트 할당

| 모듈 | 포트 | URL |
|------|------|-----|
| `maria_mcp` | 8001 | `http://localhost:8001/mcp/` |
| `rag_mcp` | 8002 | `http://localhost:8002/mcp/` |
| `metric_mcp` | 8003 | `http://localhost:8003/mcp/` |
| `notification_mcp` (TBD) | 8004 | `http://localhost:8004/mcp/` |

---

## 2. 디렉토리 구조

```
src/<module>_mcp/
├── __init__.py          # 한 줄 docstring만
├── __main__.py          # run() 위임
├── server.py            # FastMCP + lifespan + _ApiKeyMiddleware + @mcp.tool
├── config.py            # Settings(BaseSettings) + lazy get_settings()
├── tools.py             # tool 본체 (비즈니스 로직)
├── models.py            # Pydantic 응답 모델
├── logging_setup.py     # configure_logging + log_tool_call + log_query/log_call
├── <backend>.py         # DB/HTTP 클라이언트 (예: db.py, client.py)
└── diagnostics.py       # uv run <module>-mcp-diag
```

`queries.py` 또는 `prompts.py` 등 모듈 특성에 맞는 파일은 추가 가능.

---

## 3. 파일별 구현 스텁

### 3.1 `__init__.py`

```python
"""<module>_mcp — <한 줄 역할 설명> MCP 서버."""
```

### 3.2 `__main__.py`

```python
from .server import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
```

### 3.3 `config.py`

환경변수 접두사는 모듈별로 다르다 (`QDRANT_*`, `DRUID_*` 등).
`Settings()` 를 모듈 최상단에 두면 import 만으로 ValidationError → **절대 금지**.

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── 백엔드 접속 (모듈별 접두사 사용) ──
    qdrant_host: str = "localhost"   # 예시: rag_mcp
    qdrant_port: int = 6333
    # druid_url: str                 # 예시: metric_mcp

    # ── 공통 ──
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8002             # 모듈별 기본값
    mcp_api_key: str = ""            # 빈 문자열 = 개발 모드(인증 비활성화)
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

### 3.4 `logging_setup.py`

로거 이름은 `<module>_mcp.tool` / `<module>_mcp.auth` / `<module>_mcp.db` 로 고정.

```python
import logging
import time
from contextlib import contextmanager
from collections.abc import Iterator

from .config import get_settings


def configure_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


tool_logger = logging.getLogger("<module>_mcp.tool")
auth_logger = logging.getLogger("<module>_mcp.auth")
client_logger = logging.getLogger("<module>_mcp.db")   # 또는 .client


@contextmanager
def log_tool_call(name: str, **args: object) -> Iterator[dict[str, object]]:
    meta: dict[str, object] = {}
    started = time.perf_counter()
    tool_logger.info("tool=%s args=%s start", name, args)
    try:
        yield meta
    except Exception as e:
        elapsed_ms = (time.perf_counter() - started) * 1000
        tool_logger.exception("tool=%s args=%s elapsed_ms=%.2f error=%s", name, args, elapsed_ms, e)
        raise
    else:
        elapsed_ms = (time.perf_counter() - started) * 1000
        tool_logger.info("tool=%s args=%s elapsed_ms=%.2f meta=%s", name, args, elapsed_ms, meta)


@contextmanager
def log_query(label: str) -> Iterator[dict[str, object]]:
    meta: dict[str, object] = {}
    started = time.perf_counter()
    try:
        yield meta
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        client_logger.info("op=%s elapsed_ms=%.2f rows=%s", label, elapsed_ms, meta.get("rows"))
```

### 3.5 `server.py`

`_ApiKeyMiddleware` 는 모든 서버에 동일하게 복사한다 (아직 공통 패키지 미추출).

```python
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import <backend>   # db, client, ...
from .config import get_settings
from .logging_setup import auth_logger, configure_logging
from .models import SomeModel
from . import tools


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
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


@asynccontextmanager
async def lifespan(_: FastMCP) -> AsyncIterator[None]:
    await <backend>.init()      # 풀/클라이언트 초기화
    try:
        yield
    finally:
        await <backend>.close()


mcp: FastMCP = FastMCP(name="<module>_mcp", lifespan=lifespan)


@mcp.tool
async def example_tool(data_center_id: int, some_id: int) -> SomeModel | None:
    """한 줄 설명 — 무엇을 하는지 + 어느 백엔드를 쓰는지."""
    return await tools.example_tool(data_center_id, some_id)


def run() -> None:
    configure_logging()   # 항상 run() 첫 줄에서만 호출 (lifespan에 두면 API key 유무에 따라 초기화 경로 분기됨)
    s = get_settings()
    middleware: list[Middleware] = []
    if s.mcp_api_key:
        middleware.append(Middleware(_ApiKeyMiddleware))
    else:
        auth_logger.warning(
            "MCP_API_KEY 미설정 — API Key 인증이 비활성화되었습니다 (개발 모드). "
            "운영 배포 전 반드시 환경변수 MCP_API_KEY 를 설정하세요."
        )
    mcp.run(transport="http", host=s.mcp_host, port=s.mcp_port, middleware=middleware)
```

**핵심 규칙:**
- `@mcp.tool` 본체는 1-2줄 위임만. 로직은 `tools.py` 에.
- docstring 은 sLLM 이 읽는다 — 한 줄로 *무엇을 하는지 + 어느 백엔드를 쓰는지* 명시.
- transport 는 `"http"` (FastMCP 의 streamable_http).

### 3.6 `tools.py`

```python
from .logging_setup import log_tool_call
from . import <backend>
from .models import SomeModel

_LIMIT_MAX = 50   # spec 에 따라 조정


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


async def example_tool(data_center_id: int, some_id: int) -> SomeModel | None:
    with log_tool_call("example_tool", data_center_id=data_center_id, some_id=some_id) as meta:
        row = await <backend>.fetch_one(data_center_id, some_id)
        meta["result_count"] = 0 if row is None else 1
    return SomeModel(**row) if row else None
```

### 3.7 `diagnostics.py`

```python
"""<module>_mcp 진단 스크립트.

실행:
    uv run <module>-mcp-diag
"""

from __future__ import annotations

import asyncio

from . import <backend>
from .config import get_settings
from .logging_setup import configure_logging


async def run() -> None:
    s = get_settings()
    print("=== <module>_mcp 진단 ===")
    # 접속 정보 출력
    # 백엔드 health check
    # 샘플 데이터 조회 (테스트 fixture 와 동일한 쿼리)
    print("OK — 접속/조회 정상")


def main() -> None:
    configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

---

## 4. `pyproject.toml` 등록

```toml
[project.scripts]
<module>-mcp = "<module>_mcp.__main__:main"
<module>-mcp-diag = "<module>_mcp.diagnostics:main"
```

---

## 5. `config/mcp_servers.yaml` 항목 추가

```yaml
<module>_mcp:
  transport: streamable_http
  url: http://localhost:<PORT>/mcp/
  headers:
    X-API-Key: "${MCP_API_KEY}"
```

---

## 6. pytest 설정

`pyproject.toml` 에 이미 있어야 할 설정 (없으면 추가):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"   # 둘 다 session — pool 공유 필수
testpaths = ["tests"]
```

`asyncio_default_test_loop_scope` 누락 시 `Future attached to a different loop` 에러.

### 6.1 `tests/conftest.py` 추가 패턴

```python
import pytest
import pytest_asyncio
from <module>_mcp import <backend>
from <module>_mcp.logging_setup import configure_logging


@pytest_asyncio.fixture(scope="session")
async def _pool() -> None:
    configure_logging()
    try:
        await <backend>.init()
    except Exception as e:
        pytest.skip(f"백엔드 초기화 실패 — 통합 테스트를 건너뜀: {e}")
    yield
    await <backend>.close()


@pytest_asyncio.fixture(scope="session")
async def sample_item(_pool: None) -> dict:
    """백엔드에서 샘플 1건 조회 — 테스트 fixture."""
    row = await <backend>.fetch_sample()
    if row is None:
        pytest.skip("샘플 데이터 없음")
    return row
```

---

## 7. 검증 체크리스트

작업 후 PR 전에 모두 통과:

```bash
# 1. import sanity
uv run python -c "from <module>_mcp import server; print(server.mcp.name)"

# 2. tool 목록 확인
uv run python -c "import asyncio; from <module>_mcp.server import mcp; \
    print([t.name for t in asyncio.run(mcp.list_tools())])"

# 3. 백엔드 접속 + 샘플 데이터
uv run <module>-mcp-diag

# 4. 통합 테스트
uv run pytest tests/ -v

# 5. 서버 기동
uv run <module>-mcp
# (다른 터미널)
uv run mcp-client-diag   # mcp_client 가 tool 목록 정상 발견 확인
```

---

## 8. 흔한 함정

| 함정 | 원인 | 해결 |
|------|------|------|
| import 만으로 ValidationError | `Settings()` 를 모듈 최상단에 직접 호출 | `@lru_cache get_settings()` 로 감싸기 |
| `Future attached to a different loop` | `asyncio_default_test_loop_scope` 누락 | `session` 으로 설정 |
| `@mcp.tool` 함수에 로직 직접 작성 | 테스트 불가 | `tools.py` 에 분리 |
| dict 직반환 | 응답 스키마 드리프트 | Pydantic 모델 강제 |
| 풀을 tool 안에서 init | race condition | `lifespan` 에서만 init/close |
| API key 미설정인데 운영 배포 | 개발 모드 경고 무시 | `MCP_API_KEY` 환경변수 필수 설정 |
