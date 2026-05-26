"""bench_run.py phase3 가 중단된 경우 /tmp/phase3.log 를 파싱해 JSON 복원.

사용법:
  uv run python scripts/bench_recover_phase3.py [--log /tmp/phase3.log] [--output ...]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_common import (  # noqa: E402
    ensure_results_dir,
    env_snapshot,
    save_json,
    summarize,
    ts,
)

HEADER_RE = re.compile(r"\[phase3\] target_input=(\d+) reps=(\d+)")
OK_RE = re.compile(
    r"rep (\d+)/(\d+) OK actual=(\d+) ttft=([\d.]+)s total=([\d.]+)s(?: out_tps=([\d.]+))?"
)
FAIL_RE = re.compile(r"rep (\d+)/(\d+) FAIL (.+)")
SAVE_RE = re.compile(r"\[phase3\] 저장: ")


def parse_log(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        ttfts: list[float] = [a["ttft_s"] for a in current["attempts"] if a.get("ok") and a.get("ttft_s") is not None]
        totals: list[float] = [a["total_s"] for a in current["attempts"] if a.get("ok") and a.get("total_s") is not None]
        out_tps: list[float] = [a["output_tps"] for a in current["attempts"] if a.get("ok") and a.get("output_tps") is not None]
        current["ok_count"] = sum(1 for a in current["attempts"] if a.get("ok"))
        current["fail_count"] = sum(1 for a in current["attempts"] if not a.get("ok"))
        current["ttft_s"] = summarize(ttfts)
        current["total_s"] = summarize(totals)
        current["output_tps"] = summarize(out_tps)
        current["total_tps"] = summarize([])
        results.append(current)
        current = None

    for line in text.splitlines():
        m = HEADER_RE.search(line)
        if m:
            flush()
            current = {
                "target_input": int(m.group(1)),
                "actual_input_first": None,
                "actual_input_all": [],
                "output_tokens": 256,
                "reps_planned": int(m.group(2)),
                "attempts": [],
                "prompt_gen_error": None,
            }
            continue
        if current is None:
            continue
        m = OK_RE.search(line)
        if m:
            rep_idx = int(m.group(1))
            actual = int(m.group(3))
            ttft = float(m.group(4))
            total = float(m.group(5))
            out_tps_raw = m.group(6)
            out_tps = float(out_tps_raw) if out_tps_raw else None
            if current["actual_input_first"] is None:
                current["actual_input_first"] = actual
            current["actual_input_all"].append(actual)
            current["attempts"].append({
                "ok": True,
                "status": 200,
                "error": None,
                "ttft_s": ttft,
                "total_s": total,
                "output_tps": out_tps,
                "rep": rep_idx,
            })
            continue
        m = FAIL_RE.search(line)
        if m:
            current["attempts"].append({
                "ok": False,
                "status": None,
                "error": m.group(3).strip(),
                "rep": int(m.group(1)),
            })
            continue
    flush()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="phase3 로그 → JSON 복원")
    parser.add_argument("--log", type=Path, default=Path("/tmp/phase3.log"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.log.exists():
        print(f"로그 파일 없음: {args.log}")
        return 1

    text = args.log.read_text(encoding="utf-8", errors="replace")
    results = parse_log(text)
    if not results:
        print("파싱된 결과 없음")
        return 1

    out = {
        "phase": 3,
        "recovered_from_log": str(args.log),
        "env": env_snapshot(),
        "params": {
            "reps_override": None,
            "reps_by_size": {r["target_input"]: r["reps_planned"] for r in results},
            "output_tokens": 256,
            "sizes": [r["target_input"] for r in results],
            "shuffle": True,
        },
        "results": results,
    }
    output = args.output or (ensure_results_dir() / f"phase3_{ts()}_recovered.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, out)
    print(f"복원 저장: {output}")
    print("\n== 요약 ==")
    for r in results:
        ttft = r["ttft_s"].get("median")
        out_tps = r["output_tps"].get("median")
        print(
            f"  input={r['target_input']:>6} ok={r['ok_count']}/{r['ok_count']+r['fail_count']} "
            f"TTFT_med={ttft if ttft is not None else '-'} "
            f"out_tps_med={out_tps if out_tps is not None else '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
