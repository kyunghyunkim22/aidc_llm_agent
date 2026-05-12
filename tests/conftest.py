"""maria_mcp 통합 테스트용 공통 fixture.

실제 MariaDB 인스턴스에 접속하여, 테이블에서 샘플 ID를 자동 발견 후 각 tool에 주입.
DB가 비어있거나 도달 불가능하면 해당 fixture가 의존하는 테스트는 skip 된다.

미들웨어 등 DB가 필요 없는 테스트(test_maria_mcp_middleware.py)는
이 fixture 와 무관하게 독립적으로 실행된다.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from maria_mcp import db
from maria_mcp.logging_setup import configure_logging


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """통합 테스트(integration)와 미들웨어 테스트를 마커로 구분."""
    pass


@pytest_asyncio.fixture(scope="session")
async def _pool() -> Any:
    """DB pool을 초기화하고 세션 종료 시 해제.

    DB 연결에 실패하면 RuntimeError 를 발생시켜 해당 fixture를 의존하는
    테스트 전체를 skip 한다.
    """
    configure_logging()
    try:
        await db.init_pool()
    except Exception as e:
        pytest.skip(f"DB 초기화 실패 — 통합 테스트를 건너뜀: {e}")
    yield
    await db.close_pool()


@pytest_asyncio.fixture(scope="session")
async def sample_device(_pool: Any) -> dict[str, int]:
    """im_device_inf 에서 활성 장비 1건을 찾아 반환."""
    async with db.cursor() as cur:
        await cur.execute(
            "SELECT data_center_id, device_id "
            "FROM im_device_inf WHERE use_yn='Y' "
            "ORDER BY data_center_id, device_id LIMIT 1"
        )
        row = await cur.fetchone()
    if row is None:
        pytest.skip("im_device_inf 에 활성 장비 데이터 없음")
    return row  # type: ignore[return-value]


@pytest_asyncio.fixture(scope="session")
async def sample_alarm(_pool: Any) -> dict[str, Any]:
    """fm_fault_alarm_cur 에서 알람 1건을 찾아 반환."""
    async with db.cursor() as cur:
        await cur.execute(
            "SELECT data_center_id, id, device_id "
            "FROM fm_fault_alarm_cur WHERE id IS NOT NULL "
            "ORDER BY log_date DESC LIMIT 1"
        )
        row = await cur.fetchone()
    if row is None:
        pytest.skip("fm_fault_alarm_cur 에 알람 데이터 없음")
    return row  # type: ignore[return-value]
