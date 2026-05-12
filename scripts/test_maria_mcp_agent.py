"""DCIM LangGraph ReAct 에이전트 테스트 스크립트.

LLM 클라이언트는 OpenAI 호환 API (ChatOpenAI). Ollama `/v1` 와 vLLM 모두 동일 경로.

실행 전 준비:
  1. maria_mcp 서버 기동: uv run maria-mcp
  2. LLM 서버 기동:
       - 로컬: ollama serve (이미 설치된 모델 — 예: gemma4)
       - 운영: vLLM 서버 (모델: google/gemma-4-e4b-it)
  3. .env 에 다음 키 설정:
       MARIA_MCP_URL, MCP_API_KEY (선택), LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
  4. 이 스크립트 실행: uv run python scripts/test_maria_mcp_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 프로젝트 루트를 sys.path 에 추가 (scripts/ 위치에서 실행 시)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_client import McpToolClient  # noqa: E402

load_dotenv()

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")

SYSTEM_PROMPT = """[필수 행동 규칙]
1. 사용자 메시지를 받으면 인사말, 자기소개, 설명 없이 즉시 도구를 호출하라.
2. 도구 호출 결과를 받은 후에만 텍스트로 답변하라.
3. 파라미터가 불명확할 때 절대 되묻지 말고 아래 기본값으로 즉시 호출하라.
   - data_center_id=1
   - limit=20
   - 시간 범위 미지정 시 start_time=지금으로부터 24시간 전, end_time=지금

[역할]
DCIM 데이터센터 장비·알람 조회 에이전트. 도구 결과를 한국어로 간결하게 요약한다."""


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        temperature=0,
    )


async def build_agent(mcp_client: McpToolClient) -> Any:
    tools = await mcp_client.get_tools()
    if not tools:
        raise RuntimeError("MCP 서버에서 tool을 가져오지 못했습니다. maria_mcp 서버가 실행 중인지 확인하세요.")

    print(f"[INFO] 로드된 MCP tool 목록: {[t.name for t in tools]}")

    llm = build_llm()
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    return agent


async def run_repl(agent: Any) -> None:
    print("\nDCIM LangGraph 에이전트 테스트")
    print("종료하려면 'quit' 또는 'exit' 입력\n")
    print("예시 질문:")
    print("  - 장비 ID 54의 정보를 알려줘")
    print("  - 현재 활성 알람 목록 보여줘")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n질문: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("종료합니다.")
            break

        try:
            final_content = ""
            async for event in agent.astream_events(
                {"messages": [("human", user_input)]}, version="v2"
            ):
                kind = event["event"]
                if kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    print(f"\n[TOOL CALL] {tool_name}")
                    print(f"  input: {tool_input}")
                elif kind == "on_tool_end":
                    tool_name = event["name"]
                    tool_output = event["data"].get("output", "")
                    output_str = str(tool_output)
                    preview = output_str[:200] + "..." if len(output_str) > 200 else output_str
                    print(f"[TOOL RESULT] {tool_name}")
                    print(f"  output: {preview}")
                elif kind == "on_chat_model_end":
                    msg = event["data"].get("output")
                    if msg and hasattr(msg, "content") and msg.content:
                        # tool_calls가 있는 단계(도구 호출 결정)는 최종 답변이 아님
                        tool_calls = getattr(msg, "tool_calls", [])
                        if not tool_calls:
                            final_content = msg.content
            print(f"\n에이전트: {final_content}" if final_content else "\n에이전트: (응답 없음)")
        except Exception as e:
            print(f"\n[ERROR] 에이전트 실행 오류: {e}")


async def main() -> None:
    mcp_client = McpToolClient()

    try:
        agent = await build_agent(mcp_client)
    except RuntimeError as e:
        print(f"[ERROR] 에이전트 초기화 실패: {e}")
        sys.exit(1)

    await run_repl(agent)


if __name__ == "__main__":
    asyncio.run(main())
