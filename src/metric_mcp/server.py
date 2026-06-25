from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import druid, tools
from .config import get_settings
from .logging_setup import auth_logger, configure_logging
from .models import CheckpointHistory


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """HTTP 레벨 API Key 인증 미들웨어 (mcp_common_spec §5 패턴)."""

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
    await druid.init_client()
    try:
        yield
    finally:
        await druid.close_client()


mcp: FastMCP = FastMCP(name="metric_mcp", lifespan=lifespan)


@mcp.tool
async def get_checkpoint_history(
    data_center_id: str,
    device_id: str,
    checkpoint_id: str,
    time: str,
) -> CheckpointHistory:
    """한 체크포인트의 최근 10분 1분 단위 시계열 (닫힌 구간 [time-10min, time], 최대 11 row).

    time 은 ISO 8601 (예: '2026-06-25T10:00:00Z'). 결측 슬롯은 채우지 않고 있는 것만 반환.
    """
    return await tools.get_checkpoint_history(data_center_id, device_id, checkpoint_id, time)


def run() -> None:
    configure_logging()
    s = get_settings()
    middleware: list[Middleware] = []
    if s.mcp_api_key:
        middleware.append(Middleware(_ApiKeyMiddleware))
    else:
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
