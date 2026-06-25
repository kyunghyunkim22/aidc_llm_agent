"""Druid SQL over HTTP 클라이언트.

POST {DRUID_URL}{DRUID_SQL_PATH}
Body:
  {
    "query": "SELECT ... WHERE ? AND ? ...",
    "parameters": [ {"type": "VARCHAR", "value": "..."} , ... ],
    "resultFormat": "object"
  }
응답: list[dict] (`resultFormat=object`).

ref: https://druid.apache.org/docs/latest/querying/sql-api/
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import get_settings
from .logging_setup import log_query

_client: httpx.AsyncClient | None = None


def _make_client() -> httpx.AsyncClient:
    s = get_settings()
    auth: httpx.BasicAuth | None = None
    if s.druid_user:
        auth = httpx.BasicAuth(s.druid_user, s.druid_password)
    return httpx.AsyncClient(
        base_url=s.druid_url,
        timeout=s.druid_timeout_sec,
        auth=auth,
    )


async def init_client() -> None:
    global _client
    if _client is not None:
        return
    _client = _make_client()


async def close_client() -> None:
    global _client
    if _client is None:
        return
    await _client.aclose()
    _client = None


def _infer_param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    return "VARCHAR"


async def sql_query(
    label: str,
    sql: str,
    parameters: list[Any],
) -> list[dict[str, Any]]:
    """Druid SQL parameterized query. resultFormat=object 로 list[dict] 반환."""
    if _client is None:
        raise RuntimeError("Druid client is not initialized. Call init_client() first.")

    s = get_settings()
    body = {
        "query": sql,
        "parameters": [
            {"type": _infer_param_type(p), "value": p} for p in parameters
        ],
        "resultFormat": "object",
    }
    with log_query(label) as meta:
        resp = await _client.post(s.druid_sql_path, json=body)
        resp.raise_for_status()
        rows: list[dict[str, Any]] = resp.json()
        meta["rows"] = len(rows)
        return rows
