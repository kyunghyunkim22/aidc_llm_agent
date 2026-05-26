"""run_test_questions.py 의 단위 테스트."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_test_questions import Question, TestResult, parse_questions, write_results


# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────

def _make_md(content: str, tmp_path: Path) -> Path:
    p = tmp_path / "questions.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ──────────────────────────────────────────────
# parse_questions
# ──────────────────────────────────────────────

class TestParseQuestions:
    def test_numbered_questions_parsed(self, tmp_path: Path) -> None:
        p = _make_md("""
            ### `get_device_info`

            1. 장비 ID 54의 상세 정보 알려줘
            2. 장비 55의 위치 알고 싶어
        """, tmp_path)
        qs = parse_questions(p)
        assert len(qs) == 2
        assert qs[0].section == "get_device_info"
        assert qs[0].index == 1
        assert "54" in qs[0].text
        assert qs[1].index == 2

    def test_code_block_scenario_parsed(self, tmp_path: Path) -> None:
        p = _make_md("""
            ### RCA 시나리오

            ```
            장비 ID 2276에 Critical 알람이 발생했어.
            장애 원인 분석해줘.
            ```
        """, tmp_path)
        qs = parse_questions(p)
        assert len(qs) == 1
        assert qs[0].section == "RCA 시나리오"
        assert "2276" in qs[0].text
        assert "\n" in qs[0].text  # 멀티라인 보존

    def test_multiple_sections_independent_index(self, tmp_path: Path) -> None:
        p = _make_md("""
            ### `tool_a`

            1. 질문 A-1
            2. 질문 A-2

            ### `tool_b`

            1. 질문 B-1
        """, tmp_path)
        qs = parse_questions(p)
        assert qs[0].section == "tool_a"
        assert qs[2].section == "tool_b"
        assert qs[2].index == 1  # 섹션 바뀌면 인덱스 리셋

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        p = _make_md("", tmp_path)
        assert parse_questions(p) == []

    def test_section_without_backtick_parsed(self, tmp_path: Path) -> None:
        p = _make_md("""
            ### 재발 패턴 분석

            ```
            장비 1499에서 반복 알람 패턴 분석해줘.
            ```
        """, tmp_path)
        qs = parse_questions(p)
        assert qs[0].section == "재발 패턴 분석"

    def test_mixed_numbered_and_scenario(self, tmp_path: Path) -> None:
        p = _make_md("""
            ### `get_alarm_info`

            1. 알람 ID 1111 조회해줘
            2. 알람 ID 2222 조회해줘

            ### RCA 시나리오

            ```
            장비 X 분석해줘.
            ```

            ```
            장비 Y 분석해줘.
            ```
        """, tmp_path)
        qs = parse_questions(p)
        assert len(qs) == 4
        assert qs[2].section == "RCA 시나리오"
        assert qs[2].index == 1
        assert qs[3].index == 2


# ──────────────────────────────────────────────
# write_results
# ──────────────────────────────────────────────

class TestWriteResults:
    def _make_result(self, section: str, idx: int, text: str, *, passed: bool = True) -> TestResult:
        r = TestResult(question=Question(section=section, index=idx, text=text))
        if passed:
            r.tools_called = ["get_device_info"]
            r.answer = "장비 정보입니다."
        else:
            r.error = "Timeout (120s)"
        r.elapsed = 1.5
        return r

    def test_file_created(self, tmp_path: Path) -> None:
        out = tmp_path / "result.md"
        write_results([], out)
        assert out.exists()

    def test_summary_counts(self, tmp_path: Path) -> None:
        results = [
            self._make_result("tool_a", 1, "질문1", passed=True),
            self._make_result("tool_a", 2, "질문2", passed=False),
        ]
        out = tmp_path / "result.md"
        write_results(results, out)
        content = out.read_text(encoding="utf-8")
        assert "PASS: 1건" in content
        assert "FAIL: 1건" in content

    def test_pass_fail_labels(self, tmp_path: Path) -> None:
        results = [
            self._make_result("tool_a", 1, "질문1", passed=True),
            self._make_result("tool_a", 2, "질문2", passed=False),
        ]
        out = tmp_path / "result.md"
        write_results(results, out)
        content = out.read_text(encoding="utf-8")
        assert "[PASS]" in content
        assert "[FAIL]" in content

    def test_section_header_written(self, tmp_path: Path) -> None:
        results = [self._make_result("get_device_info", 1, "질문", passed=True)]
        out = tmp_path / "result.md"
        write_results(results, out)
        content = out.read_text(encoding="utf-8")
        assert "## get_device_info" in content

    def test_empty_results_no_crash(self, tmp_path: Path) -> None:
        out = tmp_path / "result.md"
        write_results([], out)
        content = out.read_text(encoding="utf-8")
        assert "전체: 0건" in content
