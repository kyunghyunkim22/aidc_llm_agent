from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncmy
from asyncmy.cursors import DictCursor

from .config import get_settings
from .logging_setup import log_query

_pool: Any = None


async def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    s = get_settings()
    _pool = await asyncmy.create_pool(
        host=s.maria_host,
        port=s.maria_port,
        user=s.maria_user,
        password=s.maria_password,
        db=s.maria_db,
        minsize=s.maria_pool_min,
        maxsize=s.maria_pool_max,
        autocommit=True,
        charset="utf8mb4",
    )


async def close_pool() -> None:
    global _pool
    if _pool is None:
        return
    _pool.close()
    await _pool.wait_closed()
    _pool = None


@asynccontextmanager
async def cursor() -> AsyncIterator[DictCursor]:
    if _pool is None:
        raise RuntimeError("DB pool is not initialized. Call init_pool() first.")
    async with _pool.acquire() as conn:
        async with conn.cursor(cursor=DictCursor) as cur:
            yield cur


async def fetch_one(label: str, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    async with cursor() as cur:
        with log_query(label) as meta:
            await cur.execute(sql, params)
            row = await cur.fetchone()
            meta["rows"] = 1 if row else 0
            return row


async def fetch_all(label: str, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    async with cursor() as cur:
        with log_query(label) as meta:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            meta["rows"] = len(rows)
            return list(rows)
