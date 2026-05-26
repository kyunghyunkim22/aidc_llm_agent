"""REPL 메인 루프.

- 화면: 최종 LLM 답변만 출력
- 파일: 질문 / tool 호출 인자 / tool 결과 / 최종 답변 / 토큰·소요시간 기록
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .agent import build_agent
from .llm import build_llm  # noqa: F401  (.env 로딩 순서 보장용 — 실제 호출은 agent 내부)
from .logging_setup import setup_file_logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "docs" / "test_results"

EXIT_COMMANDS = {":exit", ":quit", ":q"}



def _read_question() -> str | None:
    """블로킹 input(). 엔터 한 번에 즉시 실행. None 이면 종료 시그널."""
    try:
        line = input(">>> ")
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if line.strip() in EXIT_COMMANDS:
        return None
    if not line.strip():
        return ""
    return line


async def _run_one(agent: Any, question: str, logger: Any) -> None:
    logger.info("Q: %s", question.replace("\n", " ⏎ "))
    start = time.monotonic()
    final_answer = ""
    in_tok = 0
    out_tok = 0
    pending: dict[str, Any] = {}

    try:
        async for event in agent.astream_events(
            {"messages": [("human", question)]}, version="v2"
        ):
            kind = event["event"]
            if kind == "on_tool_start":
                name = event["name"]
                tool_input = event["data"].get("input")
                logger.info("TOOL_CALL name=%s args=%s", name, tool_input)
                pending["name"] = name
            elif kind == "on_tool_end":
                tool_output = event["data"].get("output")
                content = (
                    getattr(tool_output, "content", None)
                    if tool_output is not None else None
                )
                if content is None:
                    output_str = str(tool_output) if tool_output is not None else ""
                elif isinstance(content, list):
                    parts: list[str] = []
                    for item in content:
                        text = getattr(item, "text", None)
                        parts.append(text if isinstance(text, str) else str(item))
                    output_str = "\n".join(parts)
                else:
                    output_str = content if isinstance(content, str) else str(content)
                preview = output_str[:1000].replace("\n", " ⏎ ")
                logger.info(
                    "TOOL_RESULT name=%s len=%d preview=%s",
                    pending.get("name", "?"),
                    len(output_str),
                    preview,
                )
            elif kind == "on_chat_model_end":
                msg = event["data"].get("output")
                if msg:
                    usage = getattr(msg, "usage_metadata", None) or {}
                    in_tok += usage.get("input_tokens", 0)
                    out_tok += usage.get("output_tokens", 0)
                    if hasattr(msg, "content") and msg.content:
                        if not getattr(msg, "tool_calls", []):
                            final_answer = msg.content
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.exception("ERROR: %s", e)
        print(f"[오류] {e}")
        print(f"(elapsed={elapsed:.1f}s)")
        return

    elapsed = time.monotonic() - start
    logger.info(
        "ANSWER (in_tok=%d out_tok=%d elapsed=%.1fs):\n%s",
        in_tok, out_tok, elapsed, final_answer,
    )
    print(final_answer if final_answer else "(빈 응답)")
    print(f"(elapsed={elapsed:.1f}s, tokens in={in_tok} out={out_tok})")


async def run_repl() -> int:
    load_dotenv()

    logger, log_path = setup_file_logger(LOG_DIR)
    print(f"[INFO] 로그 파일: {log_path}")
    print("[INFO] MCP/agent 초기화 중...")

    try:
        agent, tools = await build_agent()
    except Exception as e:
        print(f"[ERROR] agent 초기화 실패: {e}")
        logger.exception("init failed")
        return 1

    tool_names = ", ".join(t.name for t in tools)
    logger.info("INIT tools(%d)=[%s]", len(tools), tool_names)
    print(f"[INFO] MCP tool {len(tools)}개 로드됨")
    print("질문을 입력하세요. 종료: :exit / :quit / :q (Ctrl+D 도 가능)")
    print("-" * 60)

    while True:
        question = _read_question()
        if question is None:
            print("종료.")
            return 0
        if not question:
            continue
        await _run_one(agent, question, logger)
        print("-" * 60)


def main() -> None:
    raise SystemExit(asyncio.run(run_repl()))
