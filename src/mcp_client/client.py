from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import load_server_configs


class McpToolClient:
    """MultiServerMCPClient 얇은 래퍼.

    역할:
      - yaml 설정에서 다중 MCP 서버 connection 을 로드해 single 클라이언트 구성
      - 모든 서버의 tool 을 LangChain `BaseTool` 리스트로 노출
      - 이름으로 단일 tool 호출 헬퍼 제공
    """

    def __init__(
        self,
        servers: dict[str, dict[str, Any]] | None = None,
        config_path: str | None = None,
    ) -> None:
        self._connections = servers or load_server_configs(config_path)
        self._client = MultiServerMCPClient(self._connections)
        self._tools_cache: list[BaseTool] | None = None

    @property
    def server_names(self) -> list[str]:
        return list(self._connections.keys())

    async def get_tools(self, *, refresh: bool = False) -> list[BaseTool]:
        """모든 서버의 tool 목록을 반환. refresh=True 면 재조회."""
        if self._tools_cache is None or refresh:
            self._tools_cache = await self._client.get_tools()
        return self._tools_cache

    async def get_tool(self, name: str) -> BaseTool:
        for t in await self.get_tools():
            if t.name == name:
                return t
        raise KeyError(f"tool not found: {name}")

    async def call(self, name: str, **kwargs: Any) -> Any:
        """이름과 키워드 인자로 단일 tool 실행 (LangChain ainvoke)."""
        tool = await self.get_tool(name)
        return await tool.ainvoke(kwargs)
