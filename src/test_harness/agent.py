"""LangGraph react agent 생성 — mcp_client 로 tool 주입."""

from __future__ import annotations

from typing import Any

from langgraph.prebuilt import create_react_agent

from mcp_client import McpToolClient

from .llm import build_llm
from .prompts import SYSTEM_PROMPT


async def build_agent() -> tuple[Any, list[Any]]:
    """MCP tool 로드 → react agent 구성. (agent, tools) 반환."""
    client = McpToolClient()
    tools = await client.get_tools()
    if not tools:
        raise RuntimeError("MCP tool 로드 실패 — maria_mcp 서버 기동 여부 확인")
    llm = build_llm()
    agent = create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
    return agent, tools
