"""test_questions.md 의 모든 질문을 배치로 실행하는 스크립트.

실행 전 준비:
  1. maria_mcp 서버 기동: uv run maria-mcp
  2. vLLM 또는 Ollama 서버 기동
  3. .env 설정: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, MARIA_MCP_URL, MCP_API_KEY
  4. 실행: uv run python scripts/run_test_questions.py [옵션]

옵션:
  --section  -s  섹션 이름 부분 매칭 필터, 복수 지정 가능 (예: -s get_device_info list_nearby_devices)
  --dry-run      질문 목록만 출력, 실행 안 함
  --timeout  -t  질문당 타임아웃(초), 기본 120
  --output   -o  결과 파일 경로 (기본: docs/test_results/<timestamp>.md)
  --stop-on-error  첫 오류 발생 시 중단
  --expected -e  예상 결과 파일 경로 (기본: docs/test_a_db_results.md)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_client import McpToolClient  # noqa: E402

load_dotenv()

# .env에 값 없을때 값 세팅
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")

DOCS_DIR = Path(__file__).parent.parent / "docs"
TEST_RESULTS_DIR = DOCS_DIR / "test_results"
TEST_QUESTIONS_FILE = DOCS_DIR / "test_questions.md"
EXPECTED_RESULTS_FILE = DOCS_DIR / "test_a_db_results.md"


SYSTEM_PROMPT = """[필수 행동 규칙]
1. 사용자 메시지를 받으면 인사말, 자기소개, 설명 없이 즉시 도구를 호출하라.
2. 도구 호출 결과를 받은 후에만 텍스트로 답변하라.
3. 파라미터가 불명확할 때 절대 되묻지 말고 아래 기본값으로 즉시 호출하라.
   - data_center_id=1
   - limit=15
   - 시간 범위 미지정 시 start_time=지금으로부터 24시간 전, end_time=지금
3-A. 사용자 질문에 "데이터센터" 단어가 없어도 모든 tool 호출 시 data_center_id=1 을 반드시 인자로 포함하라.
     특히 get_alarm_info, get_device_info 처럼 alarm_id/device_id 만 명시되는 단건 조회에서 절대 누락 금지.
3-B. "최근 N시간/N일/N분" 같은 상대 시간 표현은 hours/days 정수 인자를 받는 tool을 우선 사용하라.
     예: "최근 2500시간 알람" → get_device_alarms(hours=2500). 절대 get_device_alarms_by_time(start_time='... ago') 형태로
     문자열을 datetime 자리에 넣지 마라.
4. 사용자가 명시한 장비 타입명·카테고리명은 변환·추론 없이 그대로 파라미터로 전달하라.
   (예: 사용자가 "CRAC"이라 했으면 "CRAH"로 바꾸지 말 것)
5. 다중 조건 질문은 모든 조건을 빠짐없이 파라미터에 포함하라.
6. 특정 장비의 "주변 구역 알람" 또는 "같은 구역 알람"을 조회할 때는 반드시 get_nearby_alarms(device_id)를 사용하라.
   존재하지 않는 tool(예: list_nearby_alarms)을 호출하지 말 것.
6-A. get_active_alarms_for_devices 호출 시 인자 매핑 엄수:
     - data_center_id 는 데이터센터 ID (default 1). device_id 값을 절대 여기 넣지 마라.
     - device_ids 는 장비 ID 정수 리스트.
     예: 사용자 "장비 [2208,2210,2211] 활성 알람" → get_active_alarms_for_devices(data_center_id=1, device_ids=[2208,2210,2211]).
7. 검색 결과가 다수(2개 이상)일 때 모든 항목을 반복 분석하지 말고, 첫 번째 항목 1개만 선택하여 상세 분석하라.
8. 동일 인자로 동일 도구를 2회 이상 호출하지 마라. 결과가 0건이면 인자를 바꾸거나(예: device_category_name → device_type_name) 빈 결과임을 그대로 보고하라.
9. 도구가 반환한 결과에 없는 장비/알람 정보를 절대 만들어내지 마라. 결과가 비었으면 "조회 결과 없음"으로만 답하라. 환각 금지.

[device_category_name vs device_type_name 분류 — 엄수]
- device_category_name 유효값(상위 분류): 'HVAC', 'IT', 'Electric Power', 'BMS' — 이 4개 외 값을 넣지 말 것.
- device_type_name 값(구체 타입): 'Switchboard', 'CRAC', 'CRAH', 'Rack', 'Temp/Hum Sensor' 등.
- 매핑 예:
  · "Switchboard 장비"   → device_type_name='Switchboard' (device_category_name 아님!)
  · "CRAC 타입"         → device_type_name='CRAC'
  · "Rack"              → device_type_name='Rack'
  · "카테고리 HVAC"      → device_category_name='HVAC'
  · "Electric Power 카테고리" → device_category_name='Electric Power'

[응답 형식 규칙]
- 결과 0건이면 정확히 "조회 결과 없음" 한 줄로만 답하라. 다른 어떤 데이터(device_id, 이름 등)도 만들어내지 말 것.
- 결과가 1건이면 모든 주요 필드를 키:값 형태로 출력하라.
- 결과가 2건 이상이면 다음 두 가지를 모두 포함하라(카운트만 답하면 안 됨):
  (1) 총 N건이라는 카운트
  (2) 첫 번째 항목 1개의 상세 정보 (모든 주요 필드 키:값)
  · 장비 주요 필드: device_id, device_name, device_category_name, device_type_name, location, manufacturer_name
  · 알람 주요 필드: alarm_id, device_id, severity, checkpoint_name, occur_time, message

[역할]
DCIM 데이터센터 장비·알람 조회 에이전트. 도구 결과를 한국어로 정확히 요약한다."""


@dataclass
class Question:
    section: str
    index: int
    text: str


@dataclass
class TestResult:
    question: Question
    tools_called: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    error: str = ""
    elapsed: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def hallucinated(self) -> bool:
        """tool 결과에 없는 device_id/alarm_id 가 answer 에 등장하면 환각으로 판정."""
        if not self.tool_calls or not self.answer:
            return False
        outputs_text = " ".join(
            str(tc.get("output") or "") for tc in self.tool_calls
        )
        if "device_id" not in outputs_text and re.search(r'device_id["\s:=]+\d+', self.answer):
            return True
        if "alarm_id" not in outputs_text and re.search(r'alarm_id["\s:=]+\d+', self.answer):
            return True
        return False

    @property
    def passed(self) -> bool:
        return (
            not self.error
            and bool(self.tools_called)
            and bool(self.answer.strip())
            and not self.hallucinated
        )


def parse_questions(path: Path) -> list[Question]:
    """test_questions.md 에서 질문을 추출한다."""
    text = path.read_text(encoding="utf-8")
    questions: list[Question] = []
    current_section = "unknown"
    numbered_index = 0
    scenario_index = 0

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("### "):
            m = re.match(r"###\s+`(.+?)`", line)
            current_section = m.group(1) if m else line[4:].strip()
            numbered_index = 0
            scenario_index = 0
            i += 1
            continue

        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m:
            numbered_index += 1
            questions.append(Question(
                section=current_section,
                index=numbered_index,
                text=m.group(2).strip(),
            ))
            i += 1
            continue

        # 코드 블록 = RCA 시나리오
        if line.strip() == "```":
            i += 1
            scenario_lines: list[str] = []
            while i < len(lines) and lines[i].strip() != "```":
                scenario_lines.append(lines[i])
                i += 1
            scenario_text = "\n".join(scenario_lines).strip()
            if scenario_text:
                scenario_index += 1
                questions.append(Question(
                    section=current_section,
                    index=scenario_index,
                    text=scenario_text,
                ))
            i += 1
            continue

        i += 1

    return questions


def parse_expected_results(path: Path) -> dict[str, dict[int, str]]:
    """test_a_db_results.md 에서 섹션별 예상 결과를 추출한다.

    반환: {section_name: {q_index: expected_str}}
    """
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    results: dict[str, dict[int, str]] = {}
    current_section = ""

    for line in text.splitlines():
        # ## 섹션 헤더
        m = re.match(r"^## (.+)$", line)
        if m:
            current_section = m.group(1).strip()
            results.setdefault(current_section, {})
            continue

        if not current_section:
            continue

        # | Q | 질문 | DB 결과 | 형태의 테이블 행
        m = re.match(r"^\|\s*(\d+)\s*\|[^|]+\|(.+)\|", line)
        if m:
            idx = int(m.group(1))
            expected = m.group(2).strip()
            results[current_section][idx] = expected

    return results


async def run_question(agent: Any, question: Question, timeout: int) -> TestResult:
    result = TestResult(question=question)
    start = time.monotonic()

    try:
        async with asyncio.timeout(timeout):
            async for event in agent.astream_events(
                {"messages": [("human", question.text)]}, version="v2"
            ):
                kind = event["event"]
                if kind == "on_tool_start":
                    result.tools_called.append(event["name"])
                    tool_input = event["data"].get("input")
                    result.tool_calls.append({
                        "name": event["name"],
                        "input": tool_input,
                        "output": None,
                    })
                elif kind == "on_tool_end":
                    tool_output = event["data"].get("output")
                    output_str = (
                        getattr(tool_output, "content", None)
                        if tool_output is not None else None
                    ) or (str(tool_output) if tool_output is not None else "")
                    if result.tool_calls and result.tool_calls[-1]["output"] is None:
                        result.tool_calls[-1]["output"] = output_str
                elif kind == "on_chat_model_end":
                    msg = event["data"].get("output")
                    if msg:
                        usage = getattr(msg, "usage_metadata", None) or {}
                        result.input_tokens += usage.get("input_tokens", 0)
                        result.output_tokens += usage.get("output_tokens", 0)
                        if hasattr(msg, "content") and msg.content:
                            if not getattr(msg, "tool_calls", []):
                                result.answer = msg.content
    except asyncio.TimeoutError:
        result.error = f"Timeout ({timeout}s)"
    except Exception as e:
        result.error = str(e)

    result.elapsed = time.monotonic() - start
    return result


def write_results(
    results: list[TestResult],
    path: Path,
    expected: dict[str, dict[int, str]] | None = None,
) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    exp = expected or {}

    lines: list[str] = [
        f"# 테스트 결과 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- 전체: {total}건 / PASS: {passed}건 / FAIL: {failed}건",
        f"- LLM: {LLM_BASE_URL} / {LLM_MODEL}",
        "",
        "---",
    ]

    current_section = None
    for r in results:
        if r.question.section != current_section:
            current_section = r.question.section
            lines.append(f"\n## {current_section}")

        status = "PASS" if r.passed else "FAIL"
        suffix = " (환각)" if r.hallucinated else ""
        q_preview = r.question.text[:80].replace("\n", " ")
        lines.append(f"\n### [{status}]{suffix} Q{r.question.index}: {q_preview}")
        lines.append(f"- 호출 tool: {', '.join(r.tools_called) if r.tools_called else '없음'}")
        lines.append(f"- 소요시간: {r.elapsed:.1f}s")
        lines.append(f"- 토큰: input={r.input_tokens} output={r.output_tokens} total={r.total_tokens}")

        # 예상 결과
        section_exp = exp.get(current_section, {})
        expected_str = section_exp.get(r.question.index, "")
        if expected_str:
            lines.append(f"- 예상 결과: {expected_str}")

        # tool 호출 인자/결과 (디버깅용)
        for idx, tc in enumerate(r.tool_calls, 1):
            tc_input = tc.get("input")
            tc_output = tc.get("output") or ""
            output_preview = tc_output[:500].replace("\n", " ") if isinstance(tc_output, str) else str(tc_output)[:500]
            lines.append(f"- tool[{idx}] {tc['name']} args={tc_input}")
            lines.append(f"  → output_len={len(tc_output) if isinstance(tc_output, str) else 'N/A'}, preview: {output_preview}")

        if r.error:
            lines.append(f"- 오류: {r.error}")
        if r.answer:
            lines.append(f"- LLM 답변:\n```\n{r.answer}\n```")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_live(result: TestResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    q_preview = result.question.text[:60].replace("\n", " ")
    tools = ", ".join(result.tools_called) if result.tools_called else "없음"
    print(f"  [{status}] {q_preview}")
    print(f"         tool: {tools} / {result.elapsed:.1f}s")
    if result.error:
        print(f"         오류: {result.error}")


async def main(args: argparse.Namespace) -> None:
    questions = parse_questions(TEST_QUESTIONS_FILE)

    if args.section:
        filters = [s.lower() for s in args.section]
        questions = [
            q for q in questions
            if any(f in q.section.lower() for f in filters)
        ]

    if not questions:
        print("해당하는 질문이 없습니다.")
        sys.exit(0)

    print(f"총 {len(questions)}개 질문")
    if args.dry_run:
        for i, q in enumerate(questions, 1):
            print(f"  {i:3d}. [{q.section}] {q.text[:70].replace(chr(10), ' ')}")
        return

    print(f"LLM: {LLM_BASE_URL} / {LLM_MODEL}")
    print("-" * 60)

    mcp_client = McpToolClient()
    tools = await mcp_client.get_tools()
    if not tools:
        print("[ERROR] MCP tool 로드 실패 — maria_mcp 서버가 실행 중인지 확인하세요.")
        sys.exit(1)
    print(f"[INFO] MCP tool {len(tools)}개 로드 완료")

    expected_path = Path(args.expected) if args.expected else EXPECTED_RESULTS_FILE
    expected = parse_expected_results(expected_path)

    llm = ChatOpenAI(base_url=LLM_BASE_URL, model=LLM_MODEL, api_key=LLM_API_KEY, temperature=0, stream_usage=True)
    agent = create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)

    results: list[TestResult] = []
    current_section = None

    for i, question in enumerate(questions, 1):
        if question.section != current_section:
            current_section = question.section
            print(f"\n[{current_section}]")

        print(f"  ({i}/{len(questions)}) 실행 중...", end="", flush=True)
        result = await run_question(agent, question, args.timeout)
        results.append(result)
        print("\r", end="")
        print_live(result)

        if args.stop_on_error and result.error:
            print("\n첫 오류 발생 — 중단합니다.")
            break

    output_path = Path(args.output) if args.output else (
        TEST_RESULTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_run.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_results(results, output_path, expected)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{'='*60}")
    print(f"결과: {passed}/{total} PASS")
    print(f"저장: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="test_questions.md 배치 실행")
    parser.add_argument("-s", "--section", nargs="+", help="섹션 이름 필터 복수 지정 가능 (부분 매칭)")
    parser.add_argument("--dry-run", action="store_true", help="질문 목록만 출력")
    parser.add_argument("-t", "--timeout", type=int, default=120, help="질문당 타임아웃(초)")
    parser.add_argument("-o", "--output", help="결과 파일 경로")
    parser.add_argument("-e", "--expected", help="예상 결과 파일 경로")
    parser.add_argument("--stop-on-error", action="store_true", help="첫 오류 시 중단")
    args = parser.parse_args()

    asyncio.run(main(args))
