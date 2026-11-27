from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db(client: TestClient) -> None:
    """テスト用 DB に接続できること。"""
    response = client.get("/api/v1/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class _BrokenSession:
    """DB に接続できないときのように、SQL の実行で失敗するセッション。"""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("internal-detail host=db-internal"))


def test_health_db_hides_internal_details_on_failure() -> None:
    """DB に接続できないときは 500 を返し、SQL 文やエラーの中身を応答に出さない。"""
    app.dependency_overrides[get_db] = lambda: _BrokenSession()
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/api/v1/health/db")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
