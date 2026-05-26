"""vLLM 처리량 벤치마크 실행기.

Phase 2: 컨텍스트 길이 한계 탐색
Phase 3: 컨텍스트 길이별 단발 성능
Phase 4: 동시성별 처리량

사용법:
  uv run python scripts/bench_run.py phase2
  uv run python scripts/bench_run.py phase3
  uv run python scripts/bench_run.py phase4
  uv run python scripts/bench_run.py all

환경변수: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_common import (  # noqa: E402
    LLM_BASE_URL,
    LLM_MODEL,
    detokenize,
    ensure_results_dir,
    env_snapshot,
    make_prompt,
    save_json,
    stream_completion,
    summarize,
    ts,
    tokenize,
    wait_for_ready,
)

PHASE2_LADDER = [4096, 8192, 16384, 32768, 65536, 98304, 130816]
PHASE2_OUTPUT_TOKENS = 128
PHASE2_SUCCESS_REPS = 3

PHASE3_SIZES = [1024, 4096, 8192, 16384, 32768, 65536, 114560]
PHASE3_OUTPUT_TOKENS = 256
PHASE3_REPS = 10
PHASE3_REPS_BY_SIZE: dict[int, int] = {
    1024: 10,
    4096: 10,
    8192: 10,
    16384: 8,
    32768: 5,
    65536: 3,
    114560: 3,
}


def _phase3_reps(size: int, override: int | None) -> int:
    if override is not None:
        return override
    return PHASE3_REPS_BY_SIZE.get(size, 5)

PHASE4_INPUTS = [1024, 8192, 32768]
PHASE4_CONCURRENCY = [1, 4, 8, 10]
PHASE4_OUTPUT_TOKENS = 256
PHASE4_BATCHES = 3


def _print(msg: str) -> None:
    print(msg, flush=True)


async def _warmup(client: httpx.AsyncClient) -> None:
    """짧은 요청 1회로 모델 워밍업."""

    _print("[warmup] 짧은 요청 1건 실행…")
    text, _ = await make_prompt(client, 256)
    res = await stream_completion(client, text, max_tokens=32)
    if not res["ok"]:
        _print(f"[warmup] 실패 (계속 진행): {res.get('error')}")
    else:
        _print(f"[warmup] OK ttft={res['ttft_s']:.2f}s total={res['total_s']:.2f}s")


async def run_phase2(reps: int = PHASE2_SUCCESS_REPS, output_tokens: int = PHASE2_OUTPUT_TOKENS) -> dict[str, Any]:
    """컨텍스트 길이 한계 탐색.

    각 ladder 길이에서 reps 회 연속 성공해야 PASS.
    실패가 처음 발생하면 (직전 성공, 실패) 사이를 1회 이분 탐색해 안정 한계 산출.
    """

    _print(f"\n=== Phase 2: 컨텍스트 길이 한계 탐색 (output={output_tokens}, reps={reps}) ===")
    results: list[dict[str, Any]] = []
    last_pass: int | None = None
    first_fail: int | None = None
    first_fail_reason: str | None = None

    async with httpx.AsyncClient() as client:
        if not await wait_for_ready(client):
            _print("[phase2] vLLM 서버 ready 실패")
            return {"phase": 2, "error": "server_not_ready", "env": env_snapshot()}
        await _warmup(client)

        for target in PHASE2_LADDER:
            _print(f"\n[phase2] target_input={target} 토큰 프롬프트 생성…")
            try:
                prompt, actual = await make_prompt(client, target)
            except Exception as e:
                _print(f"[phase2] 프롬프트 생성 실패: {e}")
                results.append({"target_input": target, "actual_input": None, "ok": False, "error": f"prompt_gen: {e}"})
                first_fail = target
                first_fail_reason = f"prompt_gen: {e}"
                break
            _print(f"[phase2] actual_input={actual}")

            entry: dict[str, Any] = {
                "target_input": target,
                "actual_input": actual,
                "output_tokens": output_tokens,
                "attempts": [],
            }
            pass_count = 0
            for i in range(reps):
                _print(f"[phase2] attempt {i+1}/{reps} (input≈{actual}, out={output_tokens})…")
                res = await stream_completion(client, prompt, max_tokens=output_tokens)
                entry["attempts"].append(res)
                if res["ok"]:
                    pass_count += 1
                    _print(
                        f"  OK ttft={res['ttft_s']:.2f}s total={res['total_s']:.2f}s "
                        f"prompt_tok={res.get('prompt_tokens')} compl_tok={res.get('completion_tokens')}"
                    )
                else:
                    _print(f"  FAIL status={res.get('status')} err={(res.get('error') or '')[:200]}")
                    break

            entry["pass_count"] = pass_count
            entry["passed"] = pass_count == reps
            results.append(entry)

            if entry["passed"]:
                last_pass = target
            else:
                first_fail = target
                first_fail_reason = (entry["attempts"][-1].get("error") or str(entry["attempts"][-1].get("status")))[:300]
                break

        bisect_result: dict[str, Any] | None = None
        if last_pass is not None and first_fail is not None and first_fail > last_pass:
            mid = (last_pass + first_fail) // 2
            _print(f"\n[phase2] 이분 탐색 1회 mid={mid} (last_pass={last_pass}, first_fail={first_fail})")
            try:
                prompt, actual = await make_prompt(client, mid)
                attempts: list[dict[str, Any]] = []
                ok_count = 0
                for i in range(reps):
                    res = await stream_completion(client, prompt, max_tokens=output_tokens)
                    attempts.append(res)
                    if res["ok"]:
                        ok_count += 1
                        _print(f"  bisect OK ttft={res['ttft_s']:.2f}s total={res['total_s']:.2f}s")
                    else:
                        _print(f"  bisect FAIL {(res.get('error') or '')[:200]}")
                        break
                bisect_result = {
                    "target_input": mid,
                    "actual_input": actual,
                    "passed": ok_count == reps,
                    "attempts": attempts,
                }
                if ok_count == reps:
                    last_pass = mid
            except Exception as e:
                bisect_result = {"target_input": mid, "error": f"prompt_gen: {e}"}

    summary = {
        "stable_max_input": last_pass,
        "first_fail_input": first_fail,
        "first_fail_reason": first_fail_reason,
    }
    out = {
        "phase": 2,
        "env": env_snapshot(),
        "params": {"reps": reps, "output_tokens": output_tokens, "ladder": PHASE2_LADDER},
        "summary": summary,
        "results": results,
        "bisect": bisect_result,
    }
    path = ensure_results_dir() / f"phase2_{ts()}.json"
    save_json(path, out)
    _print(f"\n[phase2] 저장: {path}")
    _print(f"[phase2] 안정 최대 입력: {summary['stable_max_input']} / 첫 실패: {summary['first_fail_input']}")
    return out


async def run_phase3(reps: int | None = None, output_tokens: int = PHASE3_OUTPUT_TOKENS) -> dict[str, Any]:
    """컨텍스트 길이별 단발 성능 (concurrency=1, 셔플 프롬프트로 콜드 prefill 보장).

    각 rep 마다 seed 가 다른 shuffled 프롬프트를 새로 생성 → prefix caching 미스 유도.
    """

    _print(f"\n=== Phase 3: 길이별 단발 성능 (output={output_tokens}, shuffle=on) ===")
    all_results: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        if not await wait_for_ready(client):
            _print("[phase3] vLLM 서버 ready 실패")
            return {"phase": 3, "error": "server_not_ready", "env": env_snapshot()}
        await _warmup(client)

        for target in PHASE3_SIZES:
            n_reps = _phase3_reps(target, reps)
            _print(f"\n[phase3] target_input={target} reps={n_reps}")

            ttfts: list[float] = []
            totals: list[float] = []
            output_tps_list: list[float] = []
            total_tps_list: list[float] = []
            ok_count = 0
            attempts: list[dict[str, Any]] = []
            actual_inputs: list[int] = []
            prompt_gen_error: str | None = None

            for i in range(n_reps):
                try:
                    prompt, actual = await make_prompt(client, target, shuffle=True, seed=i * 1009 + target)
                except Exception as e:
                    prompt_gen_error = f"prompt_gen: {e}"
                    _print(f"  rep {i+1}/{n_reps} 프롬프트 생성 실패: {e}")
                    break
                actual_inputs.append(actual)

                res = await stream_completion(client, prompt, max_tokens=output_tokens)
                attempts.append(res)
                if not res["ok"]:
                    _print(f"  rep {i+1}/{n_reps} FAIL {(res.get('error') or '')[:160]}")
                    continue
                ok_count += 1
                if res["ttft_s"] is not None:
                    ttfts.append(res["ttft_s"])
                if res["total_s"] is not None:
                    totals.append(res["total_s"])
                if res["output_tps"] is not None:
                    output_tps_list.append(res["output_tps"])
                if res["total_tps"] is not None:
                    total_tps_list.append(res["total_tps"])
                _print(
                    f"  rep {i+1}/{n_reps} OK actual={actual} ttft={res['ttft_s']:.2f}s "
                    f"total={res['total_s']:.2f}s out_tps={res['output_tps']:.1f}"
                    if res["output_tps"]
                    else f"  rep {i+1}/{n_reps} OK actual={actual} ttft={res['ttft_s']:.2f}s total={res['total_s']:.2f}s"
                )

            entry = {
                "target_input": target,
                "actual_input_first": actual_inputs[0] if actual_inputs else None,
                "actual_input_all": actual_inputs,
                "output_tokens": output_tokens,
                "reps_planned": n_reps,
                "ok_count": ok_count,
                "fail_count": len(attempts) - ok_count,
                "ttft_s": summarize(ttfts),
                "total_s": summarize(totals),
                "output_tps": summarize(output_tps_list),
                "total_tps": summarize(total_tps_list),
                "attempts": attempts,
                "prompt_gen_error": prompt_gen_error,
            }
            all_results.append(entry)

    out = {
        "phase": 3,
        "env": env_snapshot(),
        "params": {
            "reps_override": reps,
            "reps_by_size": PHASE3_REPS_BY_SIZE,
            "output_tokens": output_tokens,
            "sizes": PHASE3_SIZES,
            "shuffle": True,
        },
        "results": all_results,
    }
    path = ensure_results_dir() / f"phase3_{ts()}.json"
    save_json(path, out)
    _print(f"\n[phase3] 저장: {path}")
    return out


async def run_phase4(output_tokens: int = PHASE4_OUTPUT_TOKENS, batches: int = PHASE4_BATCHES) -> dict[str, Any]:
    """동시성별 처리량."""

    _print(f"\n=== Phase 4: 동시성 처리량 (output={output_tokens}, batches per case={batches}) ===")
    cases: list[dict[str, Any]] = []

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=64, max_keepalive_connections=64)) as client:
        if not await wait_for_ready(client):
            _print("[phase4] vLLM 서버 ready 실패")
            return {"phase": 4, "error": "server_not_ready", "env": env_snapshot()}
        await _warmup(client)

        for target_input in PHASE4_INPUTS:
            _print(f"\n[phase4] target_input={target_input}")

            for conc in PHASE4_CONCURRENCY:
                _print(f"[phase4] input={target_input} conc={conc} batches={batches} (shuffle=on, unique seeds)")
                batch_results: list[dict[str, Any]] = []

                for b in range(batches):
                    try:
                        prompts: list[Any] = []
                        actuals: list[int] = []
                        for req_idx in range(conc):
                            seed = b * 100003 + req_idx * 1009 + target_input
                            p, a = await make_prompt(client, target_input, shuffle=True, seed=seed)
                            prompts.append(p)
                            actuals.append(a)
                    except Exception as e:
                        _print(f"  batch {b+1}/{batches} 프롬프트 생성 실패: {e}")
                        batch_results.append({
                            "batch": b,
                            "wall_s": None,
                            "ok": 0,
                            "fail": conc,
                            "error": f"prompt_gen: {e}",
                        })
                        continue

                    import time as _t
                    t0 = _t.perf_counter()
                    coros = [
                        stream_completion(client, prompts[i], max_tokens=output_tokens, timeout=1200.0)
                        for i in range(conc)
                    ]
                    results = await asyncio.gather(*coros, return_exceptions=False)
                    t1 = _t.perf_counter()
                    wall = t1 - t0
                    ok_results = [r for r in results if r.get("ok")]
                    sum_completion = sum((r.get("completion_tokens") or 0) for r in ok_results)
                    sum_total = sum((r.get("total_tokens") or 0) for r in ok_results)
                    ttfts = [r["ttft_s"] for r in ok_results if r.get("ttft_s") is not None]
                    totals = [r["total_s"] for r in ok_results if r.get("total_s") is not None]
                    batch_results.append({
                        "batch": b,
                        "wall_s": wall,
                        "ok": len(ok_results),
                        "fail": conc - len(ok_results),
                        "sum_completion_tokens": sum_completion,
                        "sum_total_tokens": sum_total,
                        "aggregate_output_tps": (sum_completion / wall) if wall > 0 else None,
                        "aggregate_total_tps": (sum_total / wall) if wall > 0 else None,
                        "ttft_s": summarize(ttfts),
                        "total_s": summarize(totals),
                        "errors": [(r.get("status"), (r.get("error") or "")[:200]) for r in results if not r.get("ok")],
                    })
                    _print(
                        f"  batch {b+1}/{batches} wall={wall:.2f}s ok={len(ok_results)}/{conc} "
                        f"agg_out_tps={(sum_completion/wall):.1f}" if wall > 0 else f"  batch {b+1}/{batches}"
                    )

                agg_out_tps = [bb.get("aggregate_output_tps") for bb in batch_results if bb.get("aggregate_output_tps") is not None]
                agg_total_tps = [bb.get("aggregate_total_tps") for bb in batch_results if bb.get("aggregate_total_tps") is not None]
                ttft_all: list[float] = []
                for bb in batch_results:
                    ttft = bb.get("ttft_s") or {}
                    if ttft.get("count"):
                        ttft_all.append(ttft["median"])

                cases.append({
                    "target_input": target_input,
                    "concurrency": conc,
                    "output_tokens": output_tokens,
                    "batches": batch_results,
                    "aggregate_output_tps": summarize(agg_out_tps),
                    "aggregate_total_tps": summarize(agg_total_tps),
                    "ttft_median_across_batches": summarize(ttft_all),
                })

    out = {
        "phase": 4,
        "env": env_snapshot(),
        "params": {
            "inputs": PHASE4_INPUTS,
            "concurrency": PHASE4_CONCURRENCY,
            "output_tokens": output_tokens,
            "batches": batches,
        },
        "results": cases,
    }
    path = ensure_results_dir() / f"phase4_{ts()}.json"
    save_json(path, out)
    _print(f"\n[phase4] 저장: {path}")
    return out


async def main() -> int:
    parser = argparse.ArgumentParser(description="vLLM 처리량 벤치마크")
    parser.add_argument("phase", choices=["phase2", "phase3", "phase4", "all"])
    parser.add_argument("--reps", type=int, default=None, help="phase2/3 의 반복 횟수")
    parser.add_argument("--output-tokens", type=int, default=None, help="max_tokens 오버라이드")
    parser.add_argument("--batches", type=int, default=None, help="phase4 케이스당 배치 수")
    args = parser.parse_args()

    _print(f"LLM_BASE_URL={LLM_BASE_URL}")
    _print(f"LLM_MODEL={LLM_MODEL}")

    if args.phase in ("phase2", "all"):
        await run_phase2(
            reps=args.reps or PHASE2_SUCCESS_REPS,
            output_tokens=args.output_tokens or PHASE2_OUTPUT_TOKENS,
        )
    if args.phase in ("phase3", "all"):
        await run_phase3(
            reps=args.reps,
            output_tokens=args.output_tokens or PHASE3_OUTPUT_TOKENS,
        )
    if args.phase in ("phase4", "all"):
        await run_phase4(
            output_tokens=args.output_tokens or PHASE4_OUTPUT_TOKENS,
            batches=args.batches or PHASE4_BATCHES,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
