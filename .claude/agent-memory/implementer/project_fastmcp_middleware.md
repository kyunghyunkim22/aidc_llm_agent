---
name: FastMCP 3.x 미들웨어 주입 방식
description: FastMCP 3.2.4 에서 HTTP 레벨 Starlette 미들웨어를 주입하는 확정 방법
type: project
---

FastMCP 3.2.4 에서 HTTP 헤더 검사(API Key 인증 등)를 위한 Starlette 미들웨어 주입은
`mcp.run()` 의 `middleware` 파라미터로 직접 전달한다.

```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

mcp.run(
    transport="http",
    host=..., port=...,
    middleware=[Middleware(MyMiddlewareClass)],
)
```

- `starlette.middleware.Middleware` 는 FastMCP 내부에서 `ASGIMiddleware` 로 type alias됨
- `mcp.add_middleware()` 는 MCP 프로토콜 레벨 미들웨어(HTTP 헤더 접근 불가)로 별개
- `mcp.get_asgi_app()` 추출 / uvicorn 직접 기동 불필요
- 2026-05-07 검증, maria_mcp `_ApiKeyMiddleware` 구현 시 확인

**Why:** FastMCP 2.x spec 에 "버전 확인 후 결정" TBD 가 있었음. 실제 3.x API 확인 결과 run() 파라미터로 해결.
**How to apply:** 신규 MCP 서버(rag_mcp, metric_mcp) 인증 미들웨어 추가 시 동일 패턴 사용.
