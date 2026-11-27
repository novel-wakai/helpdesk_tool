"""アプリ全体の設定（API の説明画面・安全のためのヘッダー・CORS・DB の時刻）のテスト。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import create_app

DOCS_PATHS = ["/docs", "/redoc", "/openapi.json"]


def test_api_docs_are_disabled_by_default() -> None:
    """ENABLE_API_DOCS を設定し忘れても、API の説明画面は表示しない（安全な側が既定）こと。"""
    assert type(settings).model_fields["enable_api_docs"].default is False


@pytest.mark.parametrize("path", DOCS_PATHS)
def test_api_docs_hidden_when_disabled(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setattr(settings, "enable_api_docs", False)

    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", DOCS_PATHS)
def test_api_docs_shown_when_enabled(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setattr(settings, "enable_api_docs", True)

    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 200


def test_security_headers(client: TestClient) -> None:
    """すべての応答に、ブラウザ向けの安全のためのヘッダーが付くこと。"""
    response = client.get("/api/v1/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    ("method", "allowed"),
    [("POST", True), ("GET", True), ("DELETE", False), ("PUT", False)],
)
def test_cors_allows_only_needed_methods(client: TestClient, method: str, allowed: bool) -> None:
    """画面（localhost:5173）から使うメソッドだけが、CORS で許可されること。"""
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert (response.status_code == 200) is allowed


def test_db_session_uses_utc(db_session: Session) -> None:
    """DB への接続のタイムゾーンが UTC で、NOW() が UTC の時刻になること。"""
    row = db_session.execute(
        text("SELECT @@session.time_zone, TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), NOW())")
    ).one()

    print(f"\nsession time_zone={row[0]}, NOW() と UTC の差={row[1]} 秒")
    assert row[0] == "+00:00"
    assert row[1] == 0
