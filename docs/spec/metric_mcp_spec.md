# metric_mcp Spec

## 1. 개요

`metric_mcp`는 LangGraph 에이전트가 **Apache Druid (DCIM 메트릭 저장소)** 의 1분 rollup
체크포인트 시계열을 조회할 수 있도록 MCP tool을 노출하는 서버다.

- **위치**: CPU 서버
- **프레임워크**: FastMCP
- **Transport**: Streamable HTTP (FastMCP `transport="http"`)
- **Druid 접근**: SQL over HTTP (`POST /druid/v2/sql`, JSON)
- **언어/런타임**: Python 3.13
- **패키지 관리자**: `uv`

> 본 문서 범위는 **read-only 시계열 조회 1개 tool** 에 한한다.
> 멀티 장비/멀티 체크포인트 조회 등 확장 tool은 실제 RCA 흐름에서 필요해진 시점에 추가한다.
>
> 공통 규약(포트/환경변수/인증/디렉토리/로깅)은 `mcp_common_spec.md` 를 따른다.
> 본 문서에는 metric_mcp 고유 사항만 기술한다.

---

## 2. 디렉토리 구조

`mcp_common_spec.md §6` 의 표준 구조를 따른다. `<backend>.py` 는 `druid.py` 로 둔다.

```
src/metric_mcp/
├── __init__.py
├── __main__.py          # python -m metric_mcp 진입점
├── server.py            # FastMCP 인스턴스, 인증 미들웨어, tool 등록, 실행
├── config.py            # 환경변수 → Settings (lazy get_settings)
├── druid.py             # Druid SQL HTTP 클라이언트 (httpx.AsyncClient)
├── tools.py             # MCP tool 구현 (얇은 어댑터)
├── queries.py           # Druid SQL 문자열 상수
├── models.py            # Pydantic 응답 모델
├── logging_setup.py     # 로거 설정 + 호출/쿼리 컨텍스트 매니저
└── diagnostics.py       # uv run metric-mcp-diag 진단 스크립트
```

`pyproject.toml`:
```toml
[project.scripts]
metric-mcp = "metric_mcp.__main__:main"
metric-mcp-diag = "metric_mcp.diagnostics:main"
```

---

## 3. 환경 변수

`mcp_common_spec.md §4` 의 공통 변수(`MCP_HOST`, `MCP_PORT`, `MCP_API_KEY`, `LOG_LEVEL`)에 더해
`DRUID_*` 접두사로 모듈 전용 변수를 정의한다.

| 변수명 | 필수 | 기본값 | 설명 |
|--------|------|--------|------|
| `DRUID_URL` | O | - | Druid Broker/Router base URL (예: `http://druid-broker:8082`) |
| `DRUID_SQL_PATH` | X | `/druid/v2/sql` | SQL 엔드포인트 경로 |
| `DRUID_USER` | △ | `""` | Basic 인증 사용자 (선택) |
| `DRUID_PASSWORD` | △ | `""` | Basic 인증 비밀번호 (선택, 시크릿) |
| `DRUID_TIMEOUT_SEC` | X | `10` | HTTP 요청 타임아웃 (초) |
| `MCP_PORT` | X | `8003` | FastMCP bind port (mcp_common §3) |

> `DRUID_URL` 등 접속 정보는 운영 환경에서 별도 전달 예정.
> 시크릿(`DRUID_PASSWORD`, `MCP_API_KEY`)은 환경변수로만 주입한다.

---

## 4. 인증

`mcp_common_spec.md §5` 의 `_ApiKeyMiddleware` 패턴을 그대로 적용한다.
로거 이름은 `metric_mcp.auth`.

---

## 5. Druid 데이터 소스

| 항목 | 값 |
|------|---|
| Datasource | `rollup_checkvalue_1min` |
| Granularity | 1분 rollup (1분당 1 row) |
| 시간 컬럼 | `__time` (TIMESTAMP) |

본 모듈이 사용하는 컬럼만 표기:

| 컬럼 | 타입 | 용도 |
|------|------|------|
| `__time` | TIMESTAMP | 시간 슬롯 |
| `data_center_id` | VARCHAR | 필터 |
| `device_id` | VARCHAR | 필터 |
| `checkpoint_id` | VARCHAR | 필터 |
| `last_value` | COMPLEX&lt;serializablePairLongDouble&gt; | 응답 — Druid 표현식으로 double unwrap |
| `max_value` | DOUBLE | 응답 |
| `min_value` | DOUBLE | 응답 |
| `sum_value` | DOUBLE | 응답 |

> `last_value` 는 Druid 복합 타입이므로 SQL에서 그대로 `SELECT last_value` 하면 직렬화 페이로드가 반환된다.
> double 스칼라로 꺼내기 위해 `LATEST(last_value, …)` 또는 동등 표현식으로 unwrap 한다.
> 실제 표현식 형태는 운영 Druid 접속 확보 후 `diagnostics.py` 로 1회 검증해 확정한다.
> (실험 전까지는 구현 코멘트에 후보 표현식 2~3개를 남겨둔다.)

---

## 6. 노출 Tool (1차 — 1개)

### 6.1 `get_checkpoint_history`

**한 장비의 한 체크포인트에 대한 최근 10분 1분 단위 시계열을 반환한다.**

#### 입력

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `data_center_id` | `str` | O | DCIM 데이터센터 ID |
| `device_id` | `str` | O | 장비 ID |
| `checkpoint_id` | `str` | O | 체크포인트 ID |
| `time` | `str` | O | 기준 시각 (ISO 8601, 예: `2026-06-25T10:00:00Z`). 이 시각 포함 10분 이전 구간을 조회. |

> 입력 ID는 모두 **str**. (Druid 스키마가 VARCHAR이며, maria_mcp(int) 와는 별도 모듈이므로 캐스팅하지 않는다.)

#### 시간 범위

- **닫힌 구간**: `__time >= (time - 10min)` AND `__time <= time`
- 1분 rollup이므로 결과는 **최대 11 row** (정확히 10분 차이 + 양 끝 포함)
- 결측 슬롯은 채우지 않고 **있는 것만 반환** (forward-fill / zero-fill 금지)

#### 응답 모델 (Pydantic)

```python
class CheckpointPoint(BaseModel):
    time: datetime        # __time (UTC)
    last_value: float | None
    max_value: float | None
    min_value: float | None
    sum_value: float | None

class CheckpointHistory(BaseModel):
    data_center_id: str
    device_id: str
    checkpoint_id: str
    range_start: datetime  # time - 10min
    range_end: datetime    # time (입력값)
    points: list[CheckpointPoint]  # __time ASC
```

- 조회 결과가 비어 있으면 `points=[]` 로 반환 (예외 던지지 않음).

#### SQL (개요)

```sql
SELECT
  __time,
  <LAST_VALUE_UNWRAP_EXPR>(last_value)    AS last_value,
  max_value,
  min_value,
  sum_value
FROM rollup_checkvalue_1min
WHERE data_center_id = :dc
  AND device_id      = :dev
  AND checkpoint_id  = :cp
  AND __time >= TIME_PARSE(:range_start)
  AND __time <= TIME_PARSE(:range_end)
ORDER BY __time ASC
```

- Druid SQL parameterized query (`parameters` 배열) 로 전송. 문자열 직접 보간 금지.
- `<LAST_VALUE_UNWRAP_EXPR>` 는 §5 단서에 따라 운영 접속 확인 후 확정.

#### 정렬 / 페이징

- 정렬: `__time ASC` 고정 (mcp_common §7 의 "디폴트 1개만 제공" 원칙).
- 페이징 미제공. row 수가 본질적으로 작다(≤11).

---

## 7. 로깅

`mcp_common_spec.md §8` 컨트랙트를 따른다.

| 로거 | 용도 |
|------|------|
| `metric_mcp.tool` | tool 진입/종료 (`elapsed_ms`, `result_count`) |
| `metric_mcp.auth` | 인증 성공/실패 |
| `metric_mcp.client` | Druid HTTP 호출 (요약 SQL, `elapsed_ms`, `rows`) |

컨텍스트 매니저 `log_tool_call`, `log_query` 를 `logging_setup.py` 에 둔다 (maria_mcp 동일 패턴).

---

## 8. 진단 (`metric-mcp-diag`)

`mcp_common_spec.md §9` 에 따라 진단 스크립트를 필수 포함한다. 점검 항목:

1. `DRUID_URL` 접속 확인 (`SELECT 1`).
2. `rollup_checkvalue_1min` 데이터소스 존재 확인 (segmentMetadata 또는 `SHOW TABLES`).
3. 최근 1시간 내 임의 row 1건 샘플 출력 (`data_center_id`, `device_id`, `checkpoint_id`, `__time`).
4. `last_value` unwrap 표현식 후보 동작 여부 확인 (성공한 표현식을 stdout 에 출력 → §5 확정에 활용).

---

## 9. 테스트

- 실 Druid 접속 가능한 환경에서 통합 테스트 수행 (mock 지양 — mcp_common §11).
- 케이스:
  1. 정상: 알려진 `(dc, dev, cp)` + 최근 시각 → row ≥1 반환, `__time ASC`.
  2. 빈 결과: 미래 시각 또는 미존재 ID → `points=[]`.
  3. 결측 슬롯: 일부 1분 결측 → 누락된 슬롯은 응답에 없음 (zero-fill 안됨 확인).
  4. 잘못된 time 포맷: `ValueError` (FastMCP 단에서 400 변환).
  5. Druid HTTP 오류: 5xx → tool 측에서 예외 그대로 전파 (재시도/숨김 금지).

테스트 결과 파일은 `docs/test_results/YYYYMMDD_HHMMSS_metric_mcp_<case>.md` 규칙(`CLAUDE.md` 코딩규칙)을 따른다.

---

## 10. 본 문서 범위 외 (TBD)

다음은 1차 구현에서 제외. 실제 RCA 시나리오에서 필요해진 시점에 추가:

- 다중 device 동시 조회 (장비 N개 × 체크포인트 1개)
- 다중 checkpoint 동시 조회 (장비 1개 × 체크포인트 N개)
- zone/floor 단위 평균/합 집계
- 임의 시간 윈도우 (현재는 10분 고정)
- 1분 외 granularity (5분/1시간 rollup datasource 지원)
- 분석결과/이벤트 쓰기 경로 (Druid 본 모듈은 read-only)
