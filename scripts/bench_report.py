"""Phase JSON 결과 → 마크다운 리포트 생성기.

사용법:
  uv run python scripts/bench_report.py
    (results 디렉토리에서 phase2/phase3/phase4 최신 파일 자동 선택)

  uv run python scripts/bench_report.py \
    --phase2 docs/bench/results/phase2_xxx.json \
    --phase3 docs/bench/results/phase3_xxx.json \
    --phase4 docs/bench/results/phase4_xxx.json \
    --output docs/bench/report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_common import RESULTS_DIR, latest_result, load_json, ts  # noqa: E402


def _fmt(value: Any, fmt: str = ".2f") -> str:
    if value is None:
        return "-"
    try:
        return format(value, fmt)
    except (TypeError, ValueError):
        return str(value)


def _summary_row(label: str, s: dict[str, Any] | None, fmt: str = ".2f") -> str:
    if not s or not s.get("count"):
        return f"| {label} | - | - | - | - | - |"
    return (
        f"| {label} | {_fmt(s['min'], fmt)} | {_fmt(s['median'], fmt)} | "
        f"{_fmt(s['mean'], fmt)} | {_fmt(s['p95'], fmt)} | {_fmt(s['max'], fmt)} |"
    )


def report_phase2(data: dict[str, Any]) -> str:
    if not data:
        return "## Phase 2 — 데이터 없음\n"
    lines: list[str] = []
    lines.append("## Phase 2 — 컨텍스트 길이 한계 탐색\n")
    env = data.get("env", {})
    params = data.get("params", {})
    summary = data.get("summary", {})
    lines.append(f"- 모델: `{env.get('model')}`")
    lines.append(f"- 엔드포인트: `{env.get('base_url')}`")
    lines.append(f"- 출력 토큰: {params.get('output_tokens')}, 연속 성공 기준: {params.get('reps')}회")
    lines.append("")
    lines.append(f"**안정 최대 입력 토큰:** `{summary.get('stable_max_input')}`  ")
    lines.append(f"**최초 실패 입력 토큰:** `{summary.get('first_fail_input')}`  ")
    if summary.get("first_fail_reason"):
        lines.append(f"**실패 사유:** `{summary['first_fail_reason'][:200]}`")
    lines.append("")
    lines.append("| target_input | actual_input | 결과 | pass/총 | 1회차 TTFT(s) | 1회차 total(s) | 비고 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in data.get("results", []):
        attempts = r.get("attempts", [])
        first = attempts[0] if attempts else {}
        ttft = _fmt(first.get("ttft_s")) if first.get("ok") else "-"
        total = _fmt(first.get("total_s")) if first.get("ok") else "-"
        status = "PASS" if r.get("passed") else "FAIL"
        note = ""
        if not r.get("passed") and attempts:
            note = (attempts[-1].get("error") or str(attempts[-1].get("status") or ""))[:80]
        lines.append(
            f"| {r.get('target_input')} | {r.get('actual_input')} | {status} | "
            f"{r.get('pass_count', 0)}/{params.get('reps')} | {ttft} | {total} | {note} |"
        )
    bisect = data.get("bisect")
    if bisect:
        lines.append("")
        lines.append("### 이분 탐색 결과")
        lines.append(f"- target_input: {bisect.get('target_input')}")
        lines.append(f"- actual_input: {bisect.get('actual_input')}")
        lines.append(f"- passed: {bisect.get('passed')}")
    lines.append("")
    return "\n".join(lines)


def report_phase3(data: dict[str, Any]) -> str:
    if not data:
        return "## Phase 3 — 데이터 없음\n"
    lines: list[str] = []
    lines.append("## Phase 3 — 컨텍스트 길이별 단발 성능 (concurrency=1)\n")
    env = data.get("env", {})
    params = data.get("params", {})
    lines.append(f"- 모델: `{env.get('model')}`")
    lines.append(f"- 출력 토큰: {params.get('output_tokens')}, 반복: {params.get('reps')}회")
    lines.append("")
    lines.append("| input | actual | ok/total | TTFT med(s) | TTFT p95(s) | total med(s) | total p95(s) | out_TPS med | out_TPS p95 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in data.get("results", []):
        ttft = r.get("ttft_s") or {}
        total = r.get("total_s") or {}
        out_tps = r.get("output_tps") or {}
        actual = r.get("actual_input") or r.get("actual_input_first")
        lines.append(
            f"| {r.get('target_input')} | {actual} | "
            f"{r.get('ok_count')}/{r.get('ok_count', 0)+r.get('fail_count', 0)} | "
            f"{_fmt(ttft.get('median'))} | {_fmt(ttft.get('p95'))} | "
            f"{_fmt(total.get('median'))} | {_fmt(total.get('p95'))} | "
            f"{_fmt(out_tps.get('median'), '.1f')} | {_fmt(out_tps.get('p95'), '.1f')} |"
        )
    lines.append("")
    return "\n".join(lines)


def report_phase4(data: dict[str, Any]) -> str:
    if not data:
        return "## Phase 4 — 데이터 없음\n"
    lines: list[str] = []
    lines.append("## Phase 4 — 동시성 처리량\n")
    env = data.get("env", {})
    params = data.get("params", {})
    lines.append(f"- 모델: `{env.get('model')}`")
    lines.append(
        f"- 출력 토큰: {params.get('output_tokens')}, 배치 수: {params.get('batches')}, "
        f"inputs={params.get('inputs')}, conc={params.get('concurrency')}"
    )
    lines.append("")
    lines.append("| input | conc | agg out_TPS med | agg out_TPS p95 | TTFT med(s) | TTFT p95(s) | ok 비율 |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in data.get("results", []):
        if c.get("error"):
            lines.append(f"| {c.get('target_input')} | {c.get('concurrency')} | ERROR | - | - | - | - |")
            continue
        agg = c.get("aggregate_output_tps") or {}
        ttft = c.get("ttft_median_across_batches") or {}
        batches = c.get("batches", [])
        ok_sum = sum(b.get("ok", 0) for b in batches)
        total_sum = sum(b.get("ok", 0) + b.get("fail", 0) for b in batches)
        lines.append(
            f"| {c.get('actual_input', c.get('target_input'))} | {c.get('concurrency')} | "
            f"{_fmt(agg.get('median'), '.1f')} | {_fmt(agg.get('p95'), '.1f')} | "
            f"{_fmt(ttft.get('median'))} | {_fmt(ttft.get('p95'))} | "
            f"{ok_sum}/{total_sum} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="벤치 리포트 생성")
    parser.add_argument("--phase2", type=Path, default=None)
    parser.add_argument("--phase3", type=Path, default=None)
    parser.add_argument("--phase4", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    p2 = args.phase2 or latest_result("phase2_")
    p3 = args.phase3 or latest_result("phase3_")
    p4 = args.phase4 or latest_result("phase4_")

    sections: list[str] = ["# vLLM 처리량 벤치마크 리포트", ""]
    sections.append(f"- 생성 시각: {ts()}")
    sources = []
    if p2:
        sources.append(f"  - phase2: `{p2.name}`")
    if p3:
        sources.append(f"  - phase3: `{p3.name}`")
    if p4:
        sources.append(f"  - phase4: `{p4.name}`")
    if sources:
        sections.append("- 입력 파일:")
        sections.extend(sources)
    sections.append("")

    if p2:
        sections.append(report_phase2(load_json(p2)))
    else:
        sections.append("## Phase 2 — 데이터 없음\n")
    if p3:
        sections.append(report_phase3(load_json(p3)))
    else:
        sections.append("## Phase 3 — 데이터 없음\n")
    if p4:
        sections.append(report_phase4(load_json(p4)))
    else:
        sections.append("## Phase 4 — 데이터 없음\n")

    md = "\n".join(sections)
    output = args.output or (RESULTS_DIR.parent / f"report_{ts()}.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md, encoding="utf-8")
    print(f"리포트 저장: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
