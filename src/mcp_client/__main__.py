"""mcp_client 진단 — 설정된 모든 MCP 서버에 연결해 tool 목록을 출력.

실행:
    uv run python -m mcp_client
또는:
    uv run mcp-client-diag
"""

from __future__ import annotations

import asyncio
import sys

from .client import McpToolClient


async def run() -> int:
    client = McpToolClient()
    print("=== MCP Client 진단 ===")
    print(f"Servers ({len(client.server_names)}):")
    for name in client.server_names:
        print(f"  - {name}")
    print()

    try:
        tools = await client.get_tools()
    except Exception as e:
        print(f"!! 연결/도구 로드 실패: {type(e).__name__}: {e}")
        return 1

    print(f"Tools ({len(tools)}):")
    for t in tools:
        first_line = (t.description or "").splitlines()[0] if t.description else ""
        print(f"  - {t.name:30s} {first_line}")
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
