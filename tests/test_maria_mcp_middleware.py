"""_ApiKeyMiddleware 단위 테스트.

실제 DB 연결 없이 Starlette TestClient 를 사용해
인증 미들웨어 동작만 검증한다.

핵심: get_settings() 는 @lru_cache 싱글톤이므로 patch 는 반드시
      TestClient.get() 호출 시점까지 활성 상태를 유지해야 한다.
      따라서 patch 컨텍스트 안에서 앱 생성 + 요청을 모두 수행한다.

테스트 대상: maria_mcp.server._ApiKeyMiddleware
"""

from __future__ import annotations

import logging
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
# 헬퍼: 더미 ASGI 앱 및 TestClient 생성
# ---------------------------------------------------------------------------

async def _ok_endpoint(request: Request) -> JSONResponse:
    """인증 통과 후 도달하는 더미 엔드포인트."""
    return JSONResponse({"status": "ok"})


def _build_app_and_client(api_key: str) -> tuple[Starlette, MagicMock]:
    """Starlette 앱과 mock_settings 를 반환.

    patch 컨텍스트 밖에서 TestClient.get() 이 호출될 수 있으므로
    앱 객체와 mock_settings 만 반환하고, 실제 요청은 호출부의 patch 블록에서 수행.
    """
    mock_settings = MagicMock()
    mock_settings.mcp_api_key = api_key
    app = Starlette(
        routes=[Route("/probe", _ok_endpoint)],
        middleware=[Middleware(_ApiKeyMiddleware)],
    )
    return app, mock_settings


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------

class TestApiKeyMiddlewareAuth:
    """_ApiKeyMiddleware 인증 동작 검증.

    각 테스트에서 patch 컨텍스트를 앱 생성과 요청 전체를 감싸도록 작성한다.
    """

    def test_valid_api_key_passes(self) -> None:
        """올바른 API Key 헤더를 포함한 요청은 200 으로 통과해야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        # patch 컨텍스트가 TestClient.get() 시점까지 유지되어야 한다
        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            response = client.get("/probe", headers={"X-API-Key": _TEST_API_KEY})

        # Assert
        assert response.status_code == 200, "올바른 API Key 로는 200 응답을 받아야 한다"
        assert response.json() == {"status": "ok"}

    def test_wrong_api_key_returns_401(self) -> None:
        """잘못된 API Key 헤더를 포함한 요청은 401 을 반환해야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            response = client.get("/probe", headers={"X-API-Key": "wrong-key"})

        # Assert
        assert response.status_code == 401, "잘못된 API Key 로는 401 응답을 받아야 한다"

    def test_missing_api_key_returns_401(self) -> None:
        """X-API-Key 헤더가 없는 요청은 401 을 반환해야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act — 헤더 없이 요청
            response = client.get("/probe")

        # Assert
        assert response.status_code == 401, "API Key 헤더 없이는 401 응답을 받아야 한다"

    def test_unauthorized_response_body(self) -> None:
        """401 응답 본문이 정확히 {"error": "Unauthorized"} 여야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            response = client.get("/probe", headers={"X-API-Key": "bad-key"})

        # Assert
        assert response.json() == {"error": "Unauthorized"}, (
            '401 응답 본문은 반드시 {"error": "Unauthorized"} 여야 한다'
        )

    def test_auth_failure_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """인증 실패 시 maria_mcp.auth 로거에 WARNING 레벨로 기록되어야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
                client.get("/probe", headers={"X-API-Key": "bad-key"})

        # Assert
        auth_records = [
            r for r in caplog.records if r.name == "maria_mcp.auth"
        ]
        assert len(auth_records) >= 1, "인증 실패 시 maria_mcp.auth 로거에 최소 1건 기록되어야 한다"
        assert all(r.levelno == logging.WARNING for r in auth_records), (
            "인증 실패 로그는 WARNING 레벨이어야 한다"
        )

    def test_auth_failure_log_contains_path(self, caplog: pytest.LogCaptureFixture) -> None:
        """인증 실패 로그에 요청 경로가 포함되어야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
                client.get("/probe", headers={"X-API-Key": "bad-key"})

        # Assert
        auth_messages = [r.getMessage() for r in caplog.records if r.name == "maria_mcp.auth"]
        assert any("/probe" in msg for msg in auth_messages), (
            "인증 실패 로그에 요청 경로 /probe 가 포함되어야 한다"
        )

    def test_empty_api_key_returns_401(self) -> None:
        """빈 문자열 API Key 는 잘못된 키로 처리되어 401 을 반환해야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            response = client.get("/probe", headers={"X-API-Key": ""})

        # Assert
        assert response.status_code == 401, "빈 문자열 API Key 는 401 응답을 받아야 한다"

    def test_valid_key_does_not_log_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """인증 성공 시 maria_mcp.auth 로거에 WARNING 이 기록되지 않아야 한다."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.mcp_api_key = _TEST_API_KEY

        with patch("maria_mcp.server.get_settings", return_value=mock_settings):
            app = Starlette(
                routes=[Route("/probe", _ok_endpoint)],
                middleware=[Middleware(_ApiKeyMiddleware)],
            )
            client = TestClient(app, raise_server_exceptions=False)

            # Act
            with caplog.at_level(logging.WARNING, logger="maria_mcp.auth"):
                client.get("/probe", headers={"X-API-Key": _TEST_API_KEY})

        # Assert
        auth_warnings = [
            r for r in caplog.records
            if r.name == "maria_mcp.auth" and r.levelno >= logging.WARNING
        ]
        assert len(auth_warnings) == 0, "인증 성공 시 WARNING 로그가 기록되어서는 안 된다"
