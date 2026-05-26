"""vLLM 벤치 공통 유틸리티.

- httpx 기반 비동기 /v1/completions 스트리밍 (TTFT/총시간/usage 측정)
- /tokenize, /detokenize 호출
- N토큰 정확 프롬프트 생성
- 통계(percentile) 및 결과 IO
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "/models/gemma-4-E4B-it-W4A16")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "EMPTY")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "docs" / "bench" / "results"

BASE_PARAGRAPH = (
    "데이터센터 인프라 모니터링 시스템은 장비 상태와 알람 이벤트를 실시간으로 수집하여 "
    "분석한다. UPS, CRAC, PDU, 스위치 등 다양한 장비에서 발생하는 신호를 통합 처리하며, "
    "이상 패턴이 감지되면 운영자에게 즉시 통보된다. 운영자는 알람 우선순위와 영향 범위를 "
    "확인하고 대응 절차를 수행한다. 모든 이벤트는 이력 테이블에 적재되어 추후 분석 및 "
    "보고서 생성에 활용된다. "
    "Data center infrastructure management consolidates device telemetry and fault alarms "
    "into a unified pipeline for downstream analysis, notification, and root cause analysis. "
    "Operators rely on dashboards and automated agents to triage incoming events, "
    "correlate them with recent device history, and dispatch remediation workflows. "
    "Long-context language models can summarize hours of telemetry into concise reports "
    "and support interactive question answering over historical incident logs.\n\n"
)


def ts() -> str:
    """YYYYMMDD_HHMMSS 형식 타임스탬프."""

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def percentile(values: list[float], p: float) -> float | None:
    """p는 0~100. 빈 리스트면 None."""

    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def summarize(values: list[float]) -> dict[str, float | None]:
    """리스트 → min/median/mean/p95/max 요약."""

    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "p95": None, "max": None}
    return {
        "count": len(values),
        "min": float(min(values)),
        "median": float(statistics.median(values)),
        "mean": float(statistics.mean(values)),
        "p95": percentile(values, 95),
        "max": float(max(values)),
    }


def ensure_results_dir() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def latest_result(prefix: str) -> Path | None:
    """results 디렉토리에서 prefix 로 시작하는 가장 최근 파일."""

    if not RESULTS_DIR.exists():
        return None
    candidates = sorted(RESULTS_DIR.glob(f"{prefix}*.json"))
    return candidates[-1] if candidates else None


def _tokenize_url() -> str:
    """LLM_BASE_URL 이 .../v1 으로 끝나는 경우를 처리. /tokenize 는 루트에 있음."""

    base = LLM_BASE_URL
    if base.endswith("/v1"):
        return base[:-3] + "/tokenize"
    return base + "/tokenize"


def _detokenize_url() -> str:
    base = LLM_BASE_URL
    if base.endswith("/v1"):
        return base[:-3] + "/detokenize"
    return base + "/detokenize"


async def tokenize(client: httpx.AsyncClient, text: str) -> list[int]:
    """vLLM /tokenize 호출."""

    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    payload = {"model": LLM_MODEL, "prompt": text}
    resp = await client.post(_tokenize_url(), json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    tokens = data.get("tokens")
    if tokens is None:
        count = data.get("count")
        if isinstance(count, int):
            return list(range(count))
        raise RuntimeError(f"tokenize 응답에 tokens/count 없음: {data}")
    return list(tokens)


async def detokenize(client: httpx.AsyncClient, tokens: list[int]) -> str:
    """vLLM /detokenize 호출."""

    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    payload = {"model": LLM_MODEL, "tokens": tokens}
    resp = await client.post(_detokenize_url(), json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    text = data.get("prompt") or data.get("text")
    if not isinstance(text, str):
        raise RuntimeError(f"detokenize 응답 비정상: {data}")
    return text


_BASE_TOKENS_CACHE: list[int] | None = None


async def _get_base_tokens(client: httpx.AsyncClient) -> list[int]:
    """BASE_PARAGRAPH 토큰화 결과를 캐시하고 반환."""

    global _BASE_TOKENS_CACHE
    if _BASE_TOKENS_CACHE is None:
        tokens = await tokenize(client, BASE_PARAGRAPH)
        if not tokens:
            raise RuntimeError("BASE_PARAGRAPH tokenize 결과 비어있음")
        _BASE_TOKENS_CACHE = tokens
    return _BASE_TOKENS_CACHE


async def make_prompt(
    client: httpx.AsyncClient,
    target_tokens: int,
    *,
    tolerance: int = 4,
    shuffle: bool = False,
    seed: int | None = None,
) -> tuple[Any, int]:
    """target_tokens 길이의 프롬프트 생성. (prompt, actual_token_count) 반환.

    shuffle=False (기본):
      - BASE_PARAGRAPH 토큰을 반복 후 detokenize → 자연어 텍스트 (str).
      - 길이 검증 후 텍스트 반환. prefix caching 영향 큼 (반복 패턴).

    shuffle=True:
      - 같은 풀을 seed 기반으로 무작위 셔플.
      - detokenize 우회하고 토큰 ID 리스트(list[int]) 직접 반환.
      - vLLM /v1/completions 는 prompt 로 token id 리스트도 받음.
      - 매 호출마다 다른 seed 를 주면 prefix caching 미스를 유도해 콜드 prefill 측정 가능.
    """

    base_tokens = await _get_base_tokens(client)

    repeat = (target_tokens // len(base_tokens)) + 2
    pool: list[int] = list((base_tokens * repeat)[:target_tokens])

    if shuffle:
        rng = random.Random(seed)
        rng.shuffle(pool)
        return pool, len(pool)

    text = await detokenize(client, pool)

    for _ in range(5):
        actual = await tokenize(client, text)
        diff = len(actual) - target_tokens
        if abs(diff) <= tolerance:
            return text, len(actual)
        if diff > 0:
            actual = actual[:target_tokens]
            text = await detokenize(client, actual)
        else:
            text = text + BASE_PARAGRAPH[: max(1, -diff * 4)]

    actual = await tokenize(client, text)
    return text, len(actual)


async def stream_completion(
    client: httpx.AsyncClient,
    prompt: str | list[int],
    max_tokens: int,
    *,
    temperature: float = 0.0,
    timeout: float = 600.0,
) -> dict[str, Any]:
    """/v1/completions 스트리밍. 결과 dict 반환.

    반환 키:
      ok (bool), status (int|None), error (str|None)
      ttft_s, total_s, prefill_s (= ttft_s)
      prompt_tokens, completion_tokens, total_tokens
      output_tps, total_tps  (None 가능)
    """

    url = f"{LLM_BASE_URL}/completions"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    payload: dict[str, Any] = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    t_start = time.perf_counter()
    t_first: float | None = None
    usage: dict[str, Any] | None = None
    status: int | None = None

    try:
        async with client.stream("POST", url, json=payload, headers=headers, timeout=timeout) as resp:
            status = resp.status_code
            if status != 200:
                body = await resp.aread()
                return {
                    "ok": False,
                    "status": status,
                    "error": body.decode("utf-8", errors="replace")[:800],
                    "ttft_s": None,
                    "total_s": time.perf_counter() - t_start,
                }
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                else:
                    data = line
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if t_first is None:
                    choices = obj.get("choices") or []
                    if choices and (choices[0].get("text") or choices[0].get("delta")):
                        t_first = time.perf_counter()
                if obj.get("usage"):
                    usage = obj["usage"]
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        return {
            "ok": False,
            "status": status,
            "error": f"{type(e).__name__}: {e}",
            "ttft_s": (t_first - t_start) if t_first else None,
            "total_s": time.perf_counter() - t_start,
        }

    t_end = time.perf_counter()
    total_s = t_end - t_start
    ttft_s = (t_first - t_start) if t_first else None
    prompt_tokens = usage.get("prompt_tokens") if usage else None
    completion_tokens = usage.get("completion_tokens") if usage else None
    total_tokens = usage.get("total_tokens") if usage else None

    output_tps = None
    if completion_tokens and ttft_s is not None and total_s > ttft_s:
        decode_s = total_s - ttft_s
        if decode_s > 0:
            output_tps = completion_tokens / decode_s
    total_tps = (total_tokens / total_s) if (total_tokens and total_s > 0) else None

    return {
        "ok": True,
        "status": status,
        "error": None,
        "ttft_s": ttft_s,
        "total_s": total_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "output_tps": output_tps,
        "total_tps": total_tps,
    }


async def wait_for_ready(client: httpx.AsyncClient, retries: int = 30, delay_s: float = 2.0) -> bool:
    """/v1/models 응답이 200 이고 최소 1개 모델이 노출되면 통과.

    매칭 전략 (느슨):
    1. LLM_MODEL == id 정확 일치
    2. LLM_MODEL 의 basename == id (또는 그 역방향)
    3. 위 둘 다 실패해도 200 + 모델 1개 이상이면 통과하되, 경고 출력 후 첫 id 를 LLM_MODEL 로 덮어쓰지는 않고 그대로 사용
    """

    url = f"{LLM_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    last_status: int | None = None
    last_error: str | None = None
    last_ids: list[str] = []
    model_basename = LLM_MODEL.rsplit("/", 1)[-1]

    for attempt in range(retries):
        try:
            resp = await client.get(url, headers=headers, timeout=5.0)
            last_status = resp.status_code
            if resp.status_code == 200:
                data = resp.json()
                ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
                last_ids = ids
                if not ids:
                    last_error = "models 리스트 비어있음"
                else:
                    if LLM_MODEL in ids:
                        return True
                    for i in ids:
                        if i == model_basename or i.endswith(model_basename) or LLM_MODEL.endswith(i):
                            return True
                    print(
                        f"[ready] /models 200 OK 이지만 LLM_MODEL='{LLM_MODEL}' 매칭 실패. "
                        f"노출된 id={ids}. 그래도 진행합니다.",
                        flush=True,
                    )
                    return True
            else:
                last_error = f"HTTP {resp.status_code}"
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
        if attempt == 0 or (attempt + 1) % 5 == 0:
            print(
                f"[ready] attempt {attempt+1}/{retries} url={url} status={last_status} err={last_error}",
                flush=True,
            )
        await asyncio.sleep(delay_s)

    print(
        f"[ready] 실패. 마지막 status={last_status} err={last_error} "
        f"마지막_ids={last_ids} 기대_모델={LLM_MODEL}",
        flush=True,
    )
    return False


def env_snapshot() -> dict[str, str]:
    """결과 파일에 박아둘 환경 정보."""

    return {
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
