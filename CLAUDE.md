# DCIM AI 이벤트 분석 시스템

데이터센터 장비 장애 알람 발생 시, LLM 에이전트가 장애 원인을 자동 분석하여
원인 및 대응책을 담당자에게 제시하는 시스템.

---

## 행동 규칙

- **확인 질문 없이 바로 실행**: 요청을 받으면 추가 확인 없이 즉시 수행한다.
- **애매한 부분은 가정하고 진행**: 불명확한 사항은 합리적으로 가정한 뒤 진행하고, 응답 말미에 가정 사항만 간략히 명시한다.
- **코드는 항상 완성본 제공**: 생략(`# ... 생략`, `pass` 등) 없이 실행 가능한 전체 코드를 제공한다.

---

## 시스템 흐름

```
[DCIM API Server]
    → Collector (이벤트 수집, 주기적)
    → MariaDB (이벤트 정보 저장)
    → Scheduler
    → EventAnalysisDispatcher
        → LLMEventSummaryService  (요약 분석, 스케줄 자동 실행)
        → LLMEventAnalysisService (상세 분석, 담당자 요청 or 스케줄)
    → 담당자 알림 (Notification MCP)
```

---

## 서버 환경

| 항목 | 내용 |
|------|------|
| OS | Rocky Linux 8 |
| CPU 서버 | 4대 — 애플리케이션 및 MCP 서버 실행 |
| GPU 서버 | 1대 — LLM 서빙 전용 (vLLM) |

---

## 기술 스택

| 구분 | 기술                                                     |
|------|--------------------------------------------------------|
| LLM Serving | vLLM (GPU 서버), 모델: `google/gemma-4-e4b-it` (확정) |
| Agent | LangGraph                                              |
| MCP Framework | FastMCP                                                |
| MCP Transport | HTTP + SSE                                             |
| 비동기 DB | asyncmy (MariaDB)                                      |
| Vector DB | Qdrant                                                 |
| 메트릭 DB | Apache Druid (HTTP REST)                               |
| 패키지 관리 | uv (CPU 서버), conda (GPU 서버)                            |
| 임베딩 모델 | bge-m3 (**고정, 교체 불가** — 교체 시 전체 재인덱싱 필요)               |

---

## 패키지 설치 규칙

**절대 uv없이 `pip install <패키지명>`을 직접 실행하지 말 것.**

---

## 모듈 구성

| 모듈 | 위치 | 역할                 | 스펙 | 상태 |
|------|------|--------------------|------|------|
| event_collector | CPU | DCIM API → MariaDB | docs/spec/event_collector_spec.md | 미작성 |
| event_analysis_dispatcher | CPU | 스케줄 기반 분석 라우팅      | docs/spec/event_analysis_dispatcher_spec.md | 미작성 |
| llm_event_summary_service | CPU | 요약 분석 REST API     | docs/spec/llm_event_summary_spec.md | 미작성 |
| llm_event_analysis_service | CPU | 상세 분석 REST API     | docs/spec/llm_event_analysis_spec.md | 미작성 |
| maria_mcp | CPU | MariaDB 조회/저장 MCP (1차: 조회 only)  | docs/spec/maria_mcp_spec.md | **2차 구현 완료** |
| rag_mcp | CPU | Qdrant 벡터 검색 MCP   | docs/spec/rag_mcp_spec.md | 미작성 |
| metric_mcp | CPU | Druid 메트릭 조회 MCP   | docs/spec/metric_mcp_spec.md | 미작성 |
| rag_preprocessor | CPU | 문서 임베딩 → Qdrant  | docs/spec/rag_preprocessor_spec.md | 미작성 |
| llm_serving | GPU | vLLM 기반 LLM 서빙     | docs/spec/llm_serving_spec.md | 미작성 |
| mcp_client | CPU | MCP 서버들에 연결해 LangChain tool 로 노출 (MultiServerMCPClient 래퍼) | (스펙 없음, 단순 래퍼) | **구현 완료** |

**모듈 작업 전 반드시 해당 spec 문서를 먼저 읽을 것.**

**MCP 서버 모듈 (`*_mcp`) 신규 추가 시에는 `docs/spec/mcp_common_spec.md` 도 반드시 함께 읽을 것.**
포트 할당, 환경변수 컨벤션, 디렉토리 구조, 로깅 컨트랙트, tool 설계 원칙이 정의되어 있다.

**신규 MCP 서버 구현 시 `/new-mcp-server-scaffold` 스킬을 먼저 참조할 것.**
검증된 파일 구조·코드 스텁·체크리스트가 정리되어 있다.

> 설계도(`MCP_server_설계도.png`)는 MariaDB 사용 MCP를 Config / Event / Notification 으로 분리해
> 그렸으나, 실제 구현은 **단일 `maria_mcp` 로 통합**한다. Notification 관련 tool은 요구사항 확정 후 추가.

---

## 아키텍처 설계도

작업 전 반드시 관련 설계도를 참고할 것.

| 설계도               | 경로                                        |
|-------------------|-------------------------------------------|
| 전체 구조             | docs/diagrams/전체설계도.png                   |
| 상세 분석 흐름          | docs/diagrams/상세분석설계도.png                 |
| 요약 분석 흐름          | docs/diagrams/요약분석설계도.png                 |
| Dispatcher 흐름     | docs/diagrams/EventAnalysisDispatcher.png |
| RAG 전처리           | docs/diagrams/RAG_preprocessor.png        |
| MCP Server 전체 설계도 | docs/diagrams/MCP_server_설계도.png          |

---

## DB 스키마

- **MariaDB DDL**: `docs/schema/mariadb_schema.sql`

주요 테이블:
- `im_device_inf` — 장비 정보
- `fm_fault_alarm_cur` — 장애 알람 현재
- `fm_fault_alarm_his` — 장애 알람 이력 (`log_date` RANGE 파티션)
- `llm_analysis_result` — LLM 분석결과 저장 **[TBD]**

---

## 핵심 설계 원칙

- **단순성 우선**: 복잡성은 실제 문제가 관찰된 후에 도입한다. 추측성 추상화·확장 포인트 금지.
- **임베딩 모델 고정**: bge-m3은 설정으로 교체 불가. LLM 모델만 config로 교체 가능.
- **MCP 통신**: HTTP + SSE Transport. `MultiServerMCPClient`로 persistent 연결 유지.
- **asyncio Task 사용**: Celery는 SSE 장기 연결과 비호환 → asyncio Task로 대체.

---

## 코딩 규칙

- **Python**: 3.13
- **패키지 관리**: CPU 서버 `uv`, GPU 서버 `conda`
- **비동기**: 모든 DB/HTTP I/O는 `async`/`await`
- **타입힌트**: 모든 함수에 필수
- **설정**: 환경변수 + `config.yaml` 조합. 시크릿은 환경변수로만 관리 (절대 yaml/코드에 하드코딩 금지)
- **로깅**: 모든 MCP tool 호출 및 쿼리 실행 시간을 로깅

---

## 프로젝트 구조

```
aidc_llm_agent/
├── pyproject.toml              # uv 단일 프로젝트 (모든 모듈 공통 의존성)
├── uv.lock
├── .env.example                # 환경변수 샘플
├── config/
│   └── mcp_servers.yaml        # mcp_client 가 연결할 서버 목록
├── src/
│   ├── maria_mcp/              # MariaDB 조회 MCP (구현됨)
│   ├── mcp_client/             # MultiServerMCPClient 래퍼 (구현됨)
│   ├── rag_mcp/                # (예정)
│   ├── metric_mcp/             # (예정)
│   ├── event_collector/        # (예정)
│   └── ...
├── docs/
│   ├── spec/                   # 모듈 스펙
│   ├── schema/mariadb_schema.sql
│   └── diagrams/
└── tests/
```

- **레이아웃**: 단일 `pyproject.toml` + `src/<module>/` 패키지. 의존성 충돌이 실제 관찰되면 uv workspace 분할 검토.
- **모듈 진입점**: `python -m <module>` 또는 `pyproject.toml [project.scripts]` 등록.

---

## 모듈별 상태

### maria_mcp (2차 구현 완료, read-only)

- 위치: `src/maria_mcp/`
- 실행: `uv run maria-mcp` (또는 `uv run python -m maria_mcp`)
- Transport: HTTP, 기본 포트 `8001`
- 환경변수: `.env.example` 참고 (`MARIA_*`, `MCP_HOST/PORT`, `MCP_API_KEY`, `LOG_LEVEL`)
- **인증**: `X-API-Key` 헤더 검증 (Starlette 미들웨어) — 구현 완료
- 노출 tool 15개:
  - **기본 5개**: `get_device_info`, `get_alarm_detail`, `get_active_alarms`, `get_alarms_by_time`, `get_device_alarms`
  - **RCA 확장 10개** (spec §10.1): `list_nearby_devices`, `list_devices_by_type`, `list_devices_by_ups`, `get_alarm_history`, `get_active_alarm_summary`, `get_nearby_alarms`, `get_checkpoint_alarms`, `search_devices`, `get_alarm_history_by_policy`, `get_active_alarms_for_devices`
- 진단: `uv run maria-mcp-diag` (DB 접속 + 샘플 ID + 카운트)
- 통합 테스트: `uv run pytest tests/` (실 DB 접속 — 기본 8개 + RCA 24개 케이스)
- **미포함 (TBD)**: 분석결과 저장(`llm_analysis_result`), Notification 관련 조회/저장.

### mcp_client (구현 완료)

- 위치: `src/mcp_client/`
- 의존: `langchain-mcp-adapters` (MultiServerMCPClient), `pyyaml`
- 설정: `config/mcp_servers.yaml` (또는 `MCP_SERVERS_CONFIG` 환경변수로 경로 지정)
- `mcp_servers.yaml` 의 `headers.X-API-Key: "${MCP_API_KEY}"` 를 환경변수로 자동 치환
- 사용:
  ```python
  from mcp_client import McpToolClient
  client = McpToolClient()
  tools = await client.get_tools()                  # LangGraph 에 그대로 주입 가능
  result = await client.call("get_device_info", data_center_id=1, device_id=54)
  ```
- 진단: `uv run mcp-client-diag` (서버 연결 + tool 목록 출력)
- **공통 모듈로의 추상화는 보류**: 2~3개 MCP 서버 구현 후 실제 반복 패턴이 관찰되면 재검토.


## 문서 동기화 규칙

- 설계 변경 시 반드시 spec 업데이트 후 코드 수정
- 코드가 spec보다 앞서간 경우 phase 완료 시 spec 동기화
- CLAUDE.md의 패턴/규칙 변경은 사람 승인 후에만 수정
- 불일치 발견 시 임의로 맞추지 말고 [CONFLICT] 주석으로 표시 후 보고# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
