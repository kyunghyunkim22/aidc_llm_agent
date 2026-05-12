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


tool_logger = logging.getLogger("maria_mcp.tool")
db_logger = logging.getLogger("maria_mcp.db")
auth_logger = logging.getLogger("maria_mcp.auth")


@contextmanager
def log_tool_call(name: str, **args: object) -> Iterator[dict[str, object]]:
    """Tool 진입/종료 시간을 기록. yield 한 dict 에 result_count 등 메타를 채울 수 있다."""
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
        db_logger.info("sql=%s elapsed_ms=%.2f rows=%s", label, elapsed_ms, meta.get("rows"))
