"""_ApiKeyMiddleware 단위 테스트.

실제 DB 연결 없이 Starlette TestClient 를 사용해
인증 미들웨어 동작만 검증한다.

핵심: get_settings() 는 @lru_cache 싱글톤이므로 patch 는 반드시
      TestClient.get() 호출 시점까지 활성 상태를 유지해야 한다.
      `make_client` 픽스처가 patch 컨텍스트를 테스트 전체 동안 유지한다.

테스트 대상:
- maria_mcp.server._ApiKeyMiddleware  — 인증 미들웨어 자체
- maria_mcp.server.run                — 미들웨어 조건부 등록 로직
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from maria_mcp.server import _ApiKeyMiddleware


_TEST_API_KEY = "test-secret-key-12345"


# ---------------------------------------------------------------------------
# 헬퍼 / 픽스처
# ---------------------------------------------------------------------------

async def _ok_endpoint(request: Request) -> JSONResponse:
    """인증 통과 후 도달하는 더미 엔드포인트."""
    return JSONResponse({"status": "ok"})


@pytest.fixture
def make_client() -> Iterator[Callable[..., TestClient]]:
    """patch(get_settings) + Starlette + TestClient 를 일괄 생성.

    각 테스트는 `client = make_client(api_key=...)` 한 줄로 셋업 끝.
    patch 컨텍스트는 픽스처 teardown 까지 유지되므로
    `client.get()` 시점에도 mock_settings 가 살아있다.
    """
    contexts: list = []

    def _make(
        api_key: str = _TEST_API_KEY,
        *,
        methods: list[str] | None = None,
    ) -> TestClient:
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = api_key
        ctx = patch("maria_mcp.server.get_settings", return_value=mock_settings)
        ctx.__enter__()
        contexts.append(ctx)

        route = Route("/probe", _ok_endpoint, methods=methods or ["GET"])
        app = Starlette(
            routes=[route],
            middleware=[Middleware(_ApiKeyMiddleware)],
        )
        return TestClient(app, raise_server_exceptions=False)

    yield _make

    for ctx in contexts:
        ctx.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# _ApiKeyMiddleware 인증 동작 검증
# ---------------------------------------------------------------------------

class TestApiKeyMiddlewareAuth:
    """_ApiKeyMiddleware 인증 동작 검증."""

    def test_valid_api_key_passes(self, make_client: Callable[..., TestClient]) -> None:
        """올바른 API Key 헤더를 포함한 요청은 200 으로 통과해야 한다."""
        # Arrange
        client = make_client()

        # Act
        response = client.get("/probe", headers={"X-API-Key": _TEST_API_KEY})

        # Assert
        assert response.status_code == 200, "올바른 API Key 로는 200 응답을 받아야 한다"
        assert response.json() == {"status": "ok"}

    def test_wrong_api_key_returns_401_with_unauthorized_body(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        """잘못된 API Key 는 401 + {"error": "Unauthorized"} 본문을 반환해야 한다."""
        # Arrange
        client = make_client()

        # Act
        response = client.get("/probe", headers={"X-API-Key": "wrong-key"})

        # Assert
        assert response.status_code == 401, "잘못된 API Key 로는 401 응답을 받아야 한다"
        assert response.json() == {"error": "Unauthorized"}, (
            '401 응답 본문은 반드시 {"error": "Unauthorized"} 여야 한다'
        )

    def test_missing_api_key_returns_401(self, make_client: Callable[..., TestClient]) -> None:
        """X-API-Key 헤더가 없는 요청은 401 을 반환해야 한다."""
        # Arrange
        client = make_client()

        # Act — 헤더 없이 요청
        response = client.get("/probe")

        # Assert
        assert response.status_code == 401, "API Key 헤더 없이는 401 응답을 받아야 한다"

    def test_empty_api_key_returns_401(self, make_client: Callable[..., TestClient]) -> None:
        """서버 키가 유효한데 헤더 값이 빈 문자열이면 401 을 반환해야 한다."""
        # Arrange
        client = make_client()

        # Act
        response = client.get("/probe", headers={"X-API-Key": ""})

        # Assert
        assert response.status_code == 401, "빈 문자열 API Key 는 401 응답을 받아야 한다"

    def test_auth_failure_logs_warning(
        self, make_client: Callable[..., TestClient], caplog: pytest.LogCaptureFixture
    ) -> None:
        """인증 실패 시 maria_mcp.auth 로거에 WARNING 레벨로 기록되어야 한다."""
        # Arrange
        client = make_client()

        # Act
        with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
            client.get("/probe", headers={"X-API-Key": "bad-key"})

        # Assert
        auth_records = [r for r in caplog.records if r.name == "maria_mcp.auth"]
        assert len(auth_records) >= 1, "인증 실패 시 maria_mcp.auth 로거에 최소 1건 기록되어야 한다"
        assert all(r.levelno == logging.WARNING for r in auth_records), (
            "인증 실패 로그는 WARNING 레벨이어야 한다"
        )

    def test_auth_failure_log_contains_path(
        self, make_client: Callable[..., TestClient], caplog: pytest.LogCaptureFixture
    ) -> None:
        """인증 실패 로그에 요청 경로가 포함되어야 한다."""
        # Arrange
        client = make_client()

        # Act
        with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
            client.get("/probe", headers={"X-API-Key": "bad-key"})

        # Assert
        auth_messages = [r.getMessage() for r in caplog.records if r.name == "maria_mcp.auth"]
        assert len(auth_messages) >= 1, "maria_mcp.auth 로그가 최소 1건 캡처되어야 한다"
        assert any("/probe" in msg for msg in auth_messages), (
            f"인증 실패 로그에 요청 경로 /probe 가 포함되어야 한다 (captured={auth_messages!r})"
        )

    def test_auth_failure_log_contains_client_info(
        self, make_client: Callable[..., TestClient], caplog: pytest.LogCaptureFixture
    ) -> None:
        """인증 실패 로그에 클라이언트 host:port 또는 'unknown' 이 포함되어야 한다.

        server.py:36-40 — auth_logger.warning("auth_failed client=%s path=%s", ...)
        client 정보는 request.client 가 None 일 경우 'unknown' 으로 폴백된다.
        """
        # Arrange
        client = make_client()

        # Act
        with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
            client.get("/probe", headers={"X-API-Key": "bad-key"})

        # Assert
        auth_messages = [r.getMessage() for r in caplog.records if r.name == "maria_mcp.auth"]
        assert len(auth_messages) >= 1, "maria_mcp.auth 로그가 최소 1건 캡처되어야 한다"
        assert any("client=" in msg for msg in auth_messages), (
            "인증 실패 로그에 'client=' 필드가 포함되어야 한다"
        )
        for msg in auth_messages:
            if "client=" in msg:
                after_client = msg.split("client=", 1)[1].split(" ")[0]
                assert after_client != "", "client= 뒤의 값이 비어있어서는 안 된다"

    def test_valid_key_does_not_log_warning(
        self, make_client: Callable[..., TestClient], caplog: pytest.LogCaptureFixture
    ) -> None:
        """인증 성공 시 maria_mcp.auth 로거에 WARNING 이 기록되지 않아야 한다."""
        # Arrange
        client = make_client()

        # Act
        with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
            client.get("/probe", headers={"X-API-Key": _TEST_API_KEY})

        # Assert
        auth_warnings = [
            r for r in caplog.records
            if r.name == "maria_mcp.auth" and r.levelno >= logging.WARNING
        ]
        assert len(auth_warnings) == 0, "인증 성공 시 WARNING 로그가 기록되어서는 안 된다"

    def test_lowercase_header_name_passes(self, make_client: Callable[..., TestClient]) -> None:
        """소문자 헤더 이름(x-api-key)으로 올바른 키를 보내도 200 으로 통과해야 한다.

        HTTP 헤더는 대소문자 무관(RFC 7230). Starlette Headers 는 case-insensitive lookup 지원.
        """
        # Arrange
        client = make_client()

        # Act
        response = client.get("/probe", headers={"x-api-key": _TEST_API_KEY})

        # Assert
        assert response.status_code == 200, (
            "소문자 헤더 이름 x-api-key 도 X-API-Key 와 동일하게 취급되어 200 이어야 한다"
        )

    def test_header_value_with_leading_trailing_spaces_returns_401(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        """헤더값 앞뒤 공백은 strip 되지 않으므로 401 을 반환해야 한다.

        server.py:34 의 `!=` 단순 비교는 strip 을 하지 않는다.
        """
        # Arrange
        client = make_client()

        # Act
        response = client.get("/probe", headers={"X-API-Key": f" {_TEST_API_KEY} "})

        # Assert
        assert response.status_code == 401, (
            "앞뒤 공백이 포함된 API Key 는 strip 처리 없이 불일치로 판단해 401 이어야 한다"
        )

    def test_post_method_without_api_key_returns_401(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        """POST 메서드에서도 API Key 헤더 없이는 401 을 반환해야 한다."""
        # Arrange
        client = make_client(methods=["GET", "POST"])

        # Act
        response = client.post("/probe")

        # Assert
        assert response.status_code == 401, "POST 메서드에서도 API Key 없이는 401 이어야 한다"

    def test_post_method_with_valid_api_key_passes(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        """POST 메서드에서도 올바른 API Key 헤더를 포함하면 200 으로 통과해야 한다."""
        # Arrange
        client = make_client(methods=["GET", "POST"])

        # Act
        response = client.post("/probe", headers={"X-API-Key": _TEST_API_KEY})

        # Assert
        assert response.status_code == 200, "POST 메서드에서도 올바른 API Key 로는 200 이어야 한다"


# ---------------------------------------------------------------------------
# 빈 mcp_api_key 시 동작 — 보안 회귀 위험 영역
# ---------------------------------------------------------------------------

class TestEmptyServerApiKey:
    """`mcp_api_key=""` 일 때 미들웨어가 어떻게 반응하는지 명세 고정.

    `run()` 의 외부 가드(server.py:245)가 빈 키일 때 미들웨어 자체를 등록하지 않으므로
    이 클래스 케이스들은 운영 흐름에서는 도달하지 않지만,
    누군가 가드를 우회해서 미들웨어를 직접 등록할 경우의 동작을 문서화한다.
    """

    def test_empty_server_key_no_header_returns_401(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        """서버 키가 빈 문자열이고 헤더가 없으면 401 (None != "")."""
        # Arrange — 서버 측 키를 빈 문자열로 설정
        client = make_client(api_key="")

        # Act — 헤더 없이 요청
        response = client.get("/probe")

        # Assert
        assert response.status_code == 401, (
            "서버 키가 빈 문자열이라도 헤더 자체가 없으면 None != '' True → 401 이어야 한다"
        )

    def test_empty_server_key_with_empty_header_passes_documented_bypass(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        """서버 키 빈 문자열 + 빈 헤더값 → '' != '' False → 통과 (의도된 우회 명세 고정).

        이 동작은 보안 위험으로 보일 수 있으나 server.py:245 의 `if s.mcp_api_key:` 가드가
        운영에서 미들웨어 자체를 등록하지 않기 때문에 실제로는 도달하지 않는다.
        이 테스트는 가드가 사라지거나 우회될 경우의 동작을 명시적으로 문서화한다.
        """
        # Arrange
        client = make_client(api_key="")

        # Act
        response = client.get("/probe", headers={"X-API-Key": ""})

        # Assert
        assert response.status_code == 200, (
            "서버 키 빈 문자열 + 빈 헤더 → 통과는 현재 구현의 명세. "
            "이 동작이 의도치 않게 깨지면 run() 가드 동작과 함께 재검토 필요."
        )


# ---------------------------------------------------------------------------
# run() 의 조건부 미들웨어 등록 로직
# ---------------------------------------------------------------------------

class TestRunMiddlewareRegistration:
    """`run()` 이 `mcp_api_key` 설정 여부에 따라 미들웨어를 조건부 등록하는지 검증.

    `mcp.run()` 은 patch 해서 호출 인자만 캡처한다 — 실제 서버 기동은 하지 않는다.
    """

    def test_run_registers_middleware_when_api_key_set(self) -> None:
        """`mcp_api_key` 가 설정되어 있으면 `_ApiKeyMiddleware` 가 등록되어야 한다."""
        # Arrange
        from maria_mcp import server as server_mod

        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY
        mock_settings.mcp_host = "127.0.0.1"
        mock_settings.mcp_port = 0

        with (
            patch.object(server_mod, "get_settings", return_value=mock_settings),
            patch.object(server_mod, "configure_logging"),
            patch.object(server_mod.mcp, "run") as mock_mcp_run,
        ):
            # Act
            server_mod.run()

        # Assert
        mock_mcp_run.assert_called_once()
        middleware_arg = mock_mcp_run.call_args.kwargs.get("middleware")
        assert middleware_arg is not None, "mcp.run() 에 middleware 인자가 전달되어야 한다"
        assert len(middleware_arg) == 1, (
            f"mcp_api_key 설정 시 미들웨어 1개가 등록되어야 한다 (실제={len(middleware_arg)})"
        )
        assert middleware_arg[0].cls is _ApiKeyMiddleware, (
            "등록된 미들웨어는 _ApiKeyMiddleware 여야 한다"
        )

    def test_run_skips_middleware_when_api_key_empty(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """`mcp_api_key` 가 빈 문자열이면 미들웨어를 등록하지 않고 WARNING 을 남겨야 한다."""
        # Arrange
        from maria_mcp import server as server_mod

        mock_settings = MagicMock()
        mock_settings.mcp_api_key = ""
        mock_settings.mcp_host = "127.0.0.1"
        mock_settings.mcp_port = 0

        with (
            patch.object(server_mod, "get_settings", return_value=mock_settings),
            patch.object(server_mod, "configure_logging"),
            patch.object(server_mod.mcp, "run") as mock_mcp_run,
            caplog.at_level(logging.WARNING, logger="maria_mcp.auth"),
        ):
            # Act
            server_mod.run()

        # Assert
        mock_mcp_run.assert_called_once()
        middleware_arg = mock_mcp_run.call_args.kwargs.get("middleware")
        assert middleware_arg == [], (
            f"mcp_api_key 미설정 시 미들웨어 리스트가 비어있어야 한다 (실제={middleware_arg!r})"
        )

        auth_warnings = [
            r.getMessage() for r in caplog.records
            if r.name == "maria_mcp.auth" and r.levelno == logging.WARNING
        ]
        assert any("MCP_API_KEY" in msg for msg in auth_warnings), (
            f"미설정 경고 로그에 'MCP_API_KEY' 가 포함되어야 한다 (captured={auth_warnings!r})"
        )
