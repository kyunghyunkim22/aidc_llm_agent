from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import db, tools
from .config import get_settings
from .logging_setup import auth_logger, configure_logging
from .models import AlarmDetail, AlarmSummary, AlarmSummaryStats, DeviceInfo, DeviceSearchResult, DeviceSummary


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """HTTP 레벨 API Key 인증 미들웨어.

    모든 요청의 X-API-Key 헤더를 검사한다.
    불일치 시 401 {"error": "Unauthorized"} 반환.
    인증 실패는 maria_mcp.auth 로거에 WARNING 으로 기록 (클라이언트 IP 포함).

    FastMCP 3.x 주입 방식:
        mcp.run(..., middleware=[Middleware(_ApiKeyMiddleware)])
    starlette.middleware.Middleware 는 ASGI 앱 래핑 시 클래스와 kwargs 를 함께 전달한다.

    전체 흐름
     Middleware → FastMCP ASGI → tool 함수 -> 결과 반환
    """

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
    await db.init_pool()
    try:
        yield
    finally:
        await db.close_pool()


mcp: FastMCP = FastMCP(name="maria_mcp", lifespan=lifespan)


@mcp.tool
async def get_device_info(data_center_id: int, device_id: int) -> DeviceInfo | None:
    """장비 단건 핵심 정보 조회 (im_device_inf)."""
    return await tools.get_device_info(data_center_id, device_id)


@mcp.tool
async def get_alarm_info(data_center_id: int, alarm_id: int) -> AlarmDetail | None:
    """알람 단건 상세 (fm_fault_alarm_cur)."""
    return await tools.get_alarm_info(data_center_id, alarm_id)


@mcp.tool
async def get_active_alarms(
    data_center_id: int,
    severity: str | None = None,
    limit: int = 20,
) -> list[AlarmSummary]:
    """현재 종료되지 않은 알람 목록 (closed_date IS NULL). limit 최대 100."""
    return await tools.get_active_alarms(data_center_id, severity, limit)


@mcp.tool
async def get_alarms_by_time(
    data_center_id: int,
    start_time: datetime,
    end_time: datetime,
    severity: str | None = None,
    limit: int = 50,
) -> list[AlarmSummary]:
    """지정 시간 범위 [start_time, end_time) 내 알람. limit 최대 200."""
    return await tools.get_alarms_by_time(data_center_id, start_time, end_time, severity, limit)


@mcp.tool
async def get_device_alarms(
    data_center_id: int,
    device_id: int,
    hours: int = 24,
    limit: int = 50,
) -> list[AlarmSummary]:
    """최근 N시간 내 현재 진행 중 알람 (cur 테이블). hours 최대 720(30일), limit 최대 200."""
    return await tools.get_device_alarms(data_center_id, device_id, hours, limit)


# ── RCA 확장 tool (§10.1) ─────────────────────────────────────────────────────

@mcp.tool
async def list_nearby_devices(
    data_center_id: int,
    device_id: int,
    limit: int = 20,
) -> list[DeviceSummary]:
    """같은 구역 장비 목록 (알람 아님) — 기준 장비 자신 제외. limit 최대 50."""
    return await tools.list_nearby_devices(data_center_id, device_id, limit)


@mcp.tool
async def list_devices_by_type(
    data_center_id: int,
    device_category_name: str | None = None,
    device_type_name: str | None = None,
    limit: int = 30,
) -> list[DeviceSummary]:
    """동일 카테고리/유형 장비 목록 — category 또는 type 중 하나 이상 지정. limit 최대 100."""
    return await tools.list_devices_by_type(
        data_center_id, device_category_name, device_type_name, limit
    )


@mcp.tool
async def list_devices_by_ups(
    data_center_id: int,
    ups_name: str,
    limit: int = 30,
) -> list[DeviceSummary]:
    """특정 UPS에 연결된 장비 목록 — connected_ups 컬럼 기준. limit 최대 100."""
    return await tools.list_devices_by_ups(data_center_id, ups_name, limit)


@mcp.tool
async def get_alarm_history(
    data_center_id: int,
    device_id: int,
    days: int = 30,
    limit: int = 20,
) -> list[AlarmSummary]:
    """과거 N일 완료된 알람 이력 (his 테이블) — 재발 패턴 파악. days 최대 90, limit 최대 100."""
    return await tools.get_alarm_history(data_center_id, device_id, days, limit)


@mcp.tool
async def get_active_alarm_summary(data_center_id: int) -> AlarmSummaryStats:
    """심각도별 카운트 요약 (상세 목록 아님) — 분석 시작 전 전체 현황 파악."""
    return await tools.get_active_alarm_summary(data_center_id)


@mcp.tool
async def get_nearby_alarms(
    data_center_id: int,
    device_id: int,
    limit: int = 10,
) -> list[AlarmSummary]:
    """같은 구역 다른 장비 활성 알람 — 기준 장비 자신 알람 제외. limit 최대 50."""
    return await tools.get_nearby_alarms(data_center_id, device_id, limit)


@mcp.tool
async def get_checkpoint_alarms(
    data_center_id: int,
    checkpoint_name: str,
    limit: int = 15,
) -> list[AlarmSummary]:
    """동일 모니터링 항목 전 장비 활성 알람 — checkpoint_name 기준 공통 원인 탐지. limit 최대 50."""
    return await tools.get_checkpoint_alarms(data_center_id, checkpoint_name, limit)


@mcp.tool
async def get_alarm_history_by_policy(
    data_center_id: int,
    alarm_policy_name: str,
    days: int = 30,
    limit: int = 50,
) -> list[AlarmSummary]:
    """과거 N일 특정 알람 정책 전 장비 이력 (his 테이블) — 알람 종류별 재발 패턴·영향 장비 파악.
    get_alarm_history(단일 장비 기준) 와 달리 alarm_policy_name 으로 전 장비 이력 조회. days 최대 90, limit 최대 200."""
    return await tools.get_alarm_history_by_policy(data_center_id, alarm_policy_name, days, limit)


@mcp.tool
async def get_active_alarms_for_devices(
    data_center_id: int,
    device_ids: list[int],
    limit: int = 50,
) -> list[AlarmSummary]:
    """여러 장비의 활성 알람을 한 번에 조회 — list_nearby_devices 결과 후속 N+1 호출 방지.
    device_ids 최대 50개. 빈 리스트 입력 시 빈 리스트 반환. limit 최대 200."""
    return await tools.get_active_alarms_for_devices(data_center_id, device_ids, limit)


@mcp.tool
async def get_device_alarms_by_time(
    data_center_id: int,
    device_id: int,
    start_time: datetime,
    end_time: datetime,
    severity: str | None = None,
    limit: int = 15,
) -> list[AlarmSummary]:
    """특정 장비 + 절대 datetime 범위 알람 조회 (cur 활성 + his 이력 UNION).
    get_device_alarms(최근 N시간)와 달리 start_time/end_time으로 절대 기간을 지정한다. limit 최대 15."""
    return await tools.get_device_alarms_by_time(
        data_center_id, device_id, start_time, end_time, severity, limit
    )


@mcp.tool
async def search_devices(
    data_center_id: int,
    device_nm: str | None = None,
    device_type_name: str | None = None,
    device_category_name: str | None = None,
    location: str | None = None,
    floor_id: int | None = None,
    zone_id: int | None = None,
    connected_ups: str | None = None,
    manufacturer_name: str | None = None,
    limit: int = 30,
) -> list[DeviceSearchResult]:
    """device_id 불명 시 다중 조건 부분 문자열 검색. data_center_id 외 조건이 모두 None이면 빈 리스트 반환. limit 최대 100."""
    return await tools.search_devices(
        data_center_id=data_center_id,
        device_nm=device_nm,
        device_type_name=device_type_name,
        device_category_name=device_category_name,
        location=location,
        floor_id=floor_id,
        zone_id=zone_id,
        connected_ups=connected_ups,
        manufacturer_name=manufacturer_name,
        limit=limit,
    )


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
