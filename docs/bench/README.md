# vLLM 처리량 벤치마크

대상: `gemma-4-E4B-it-W4A16` (gptq_marlin, `max-model-len=131072`, `max-num-seqs=10`).

## 1. 목표

1. **실제 처리 가능 컨텍스트 한계** — 설정값 131072와 실제 OOM 없이 처리되는 최대 입력 길이 차이 측정.
2. **컨텍스트 길이별 단발 성능** — TTFT, 출력 TPS의 입력 길이 의존성.
3. **동시성 처리량** — `max-num-seqs=10` 환경에서 1·4·8·10 동시 요청 시 aggregate TPS.

## 2. 사전 준비

### 2.1 GPU 서버 (vLLM 컨테이너 기동)

```bash
# GPU 서버에서
cd /home/aidc/vllm
docker compose -f docker-compose.gemma4_gptq.yml up -d
docker logs -f vllm-gemma4   # "Application startup complete" 확인
```

> `docker-compose.gemma4_gptq.yml` 은 듀얼 운영 규칙상 fp8 파일과 별도로 관리. fp8 파일은 손대지 않음.

### 2.2 클라이언트 측 (.env)

```env
LLM_BASE_URL=http://<GPU서버IP>:8000/v1
LLM_MODEL=/models/gemma-4-E4B-it-W4A16
LLM_API_KEY=EMPTY
```

또는 SSH 포트 포워딩 시:

```bash
ssh -L 8000:localhost:8000 aidc@<GPU서버IP>
# 그러면 LLM_BASE_URL=http://localhost:8000/v1
```

### 2.3 GPU 모니터링 (선택)

GPU 서버에서 별도 터미널:

```bash
nvidia-smi dmon -s pucvmet -o DT > /tmp/gpu_$(date +%Y%m%d_%H%M%S).log
```

## 3. 실행

### 3.1 Phase 2 — 컨텍스트 한계 탐색

```bash
uv run python scripts/bench_run.py phase2
```

- ladder: 4k, 8k, 16k, 32k, 64k, 96k, 130816(=131072-256)
- 각 단계에서 `output=128` 으로 3회 연속 성공해야 PASS
- 첫 실패 발생 시 (직전 PASS, 첫 FAIL) 사이를 1회 이분 탐색

산출: `docs/bench/results/phase2_<ts>.json`

### 3.2 Phase 3 — 길이별 단발 성능

```bash
uv run python scripts/bench_run.py phase3
```

- 입력 길이: 1k, 4k, 8k, 16k, 32k, 64k, 130816
- 각 길이에서 `output=256` 으로 10회 반복 → p50/p95
- Phase 2 에서 실패한 길이는 그대로 시도하고 실패 횟수 기록

산출: `docs/bench/results/phase3_<ts>.json`

### 3.3 Phase 4 — 동시성 처리량

```bash
uv run python scripts/bench_run.py phase4
```

- 매트릭스: input ∈ {1k, 8k, 32k} × concurrency ∈ {1, 4, 8, 10}
- 각 케이스: `concurrency` 개 요청 동시 발사 × 3 배치 → aggregate TPS p50/p95
- `max-num-seqs=10` 이라 10 초과는 의도적으로 제외

산출: `docs/bench/results/phase4_<ts>.json`

### 3.4 일괄 실행

```bash
uv run python scripts/bench_run.py all
```

## 4. 리포트 생성

```bash
uv run python scripts/bench_report.py
# 최신 phase2/3/4 JSON 자동 선택 → docs/bench/report_<ts>.md
```

수동 지정:

```bash
uv run python scripts/bench_report.py \
  --phase2 docs/bench/results/phase2_20260520_123456.json \
  --phase3 docs/bench/results/phase3_20260520_124500.json \
  --phase4 docs/bench/results/phase4_20260520_130000.json \
  --output docs/bench/report_run1.md
```

## 5. 옵션

`bench_run.py` 옵션:

| 옵션 | 기본값 | 적용 phase | 설명 |
|---|---|---|---|
| `--reps` | phase2=3, phase3=10 | 2, 3 | 반복 횟수 |
| `--output-tokens` | phase2=128, phase3·4=256 | 전체 | max_tokens |
| `--batches` | 3 | 4 | 케이스당 배치 수 |

예시:

```bash
# 빠른 스모크 (phase3 반복 3회만)
uv run python scripts/bench_run.py phase3 --reps 3

# phase4 배치 5회로 늘려 안정도 측정
uv run python scripts/bench_run.py phase4 --batches 5
```

## 6. 결과 해석 가이드

- **stable_max_input**: Phase 2 산출 — 안정적으로 처리 가능한 최대 입력 토큰. 이 값과 설정 `max-model-len(131072)` 의 차이가 KV 캐시·VRAM 제약 정도를 나타냄.
- **Phase 3 TTFT 증가율**: 입력 길이 2배 증가 시 TTFT가 어떻게 증가하는지 — 선형(prefill 대역) vs 초선형(메모리 압박).
- **Phase 3 output TPS**: 길이가 길어져도 decode TPS 가 유지되어야 정상. 급락은 KV 캐시 paging/eviction 의심.
- **Phase 4 aggregate TPS**: concurrency 증가에 따라 1→4 까지는 거의 선형 증가, 그 이상은 포화 → A2 GPU·해당 입력 길이의 sweet spot 식별.

## 7. 알려진 제약

- `--max-num-seqs 10` 이라 동시 요청 11개 이상은 큐잉됨. 본 벤치는 의도적으로 10까지만 측정.
- 130816 같은 초장문 입력은 단발 prefill 만으로도 수십 초가 걸려 timeout 가능 — `bench_common.stream_completion` 의 timeout 기본 600s.
- 벤치 도중 다른 워크로드가 같은 vLLM 인스턴스를 사용하면 결과가 오염됨. 단독 사용 필수.
