"""同時に来たログインのリクエストのテスト。

ほかのテストは 1 つの DB セッションを共有し、最後に巻き戻す（同時の処理を再現できない）。
ここでは本番と同じく、リクエストごとに別のセッションで実際に DB へ確定（commit）し、
同時に送ったリクエストが、ロックの回数の上限をすり抜けないことを確かめる。
"""

import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.domain.user_role import UserRole
from app.main import app
from app.models.login_attempt import LoginAttempt
from app.models.user import User
from app.services import auth as auth_service
from tests.conftest import test_engine

PASSWORD = "Password123"
EMAIL = "race@example.com"
UNKNOWN_EMAIL = "race-unknown@example.com"
CONCURRENT_REQUESTS = 30

# 本番の SessionLocal と同じ設定
RealSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def real_db(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """リクエストごとに別のセッションを使い、実際に DB へ確定する状態にする。終わったら消す。"""
    monkeypatch.setattr(settings, "cookie_secure", False)

    def get_real_db() -> Generator[Session]:
        with RealSession() as db:
            yield db

    with RealSession() as db:
        db.add(
            User(
                display_name="Race.User",
                email=EMAIL,
                password_hash=hash_password(PASSWORD),
                role=UserRole.EMPLOYEE,
            )
        )
        db.commit()
    app.dependency_overrides[get_db] = get_real_db
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        with RealSession() as db:
            db.execute(delete(LoginAttempt).where(LoginAttempt.email.in_([EMAIL, UNKNOWN_EMAIL])))
            db.execute(delete(User).where(User.email == EMAIL))
            db.commit()


def count_password_checks(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """パスワードの照合（本物・ダミー）が何回行われたかを数える。"""
    calls: list[int] = []
    lock = threading.Lock()
    original_verify = auth_service.verify_password
    original_verify_and_update = auth_service.verify_and_update_password

    def verify(password: str, hashed: str) -> bool:
        with lock:
            calls.append(1)
        return original_verify(password, hashed)

    def verify_and_update(password: str, hashed: str) -> tuple[bool, str | None]:
        with lock:
            calls.append(1)
        return original_verify_and_update(password, hashed)

    monkeypatch.setattr(auth_service, "verify_password", verify)
    monkeypatch.setattr(auth_service, "verify_and_update_password", verify_and_update)
    return calls


def send_concurrently(email: str, password: str) -> list[int]:
    def login(_: int) -> int:
        with TestClient(app) as client:
            body = {"email": email, "password": password}
            return client.post("/api/v1/auth/login", json=body).status_code

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        return list(pool.map(login, range(CONCURRENT_REQUESTS)))


@pytest.mark.parametrize("email", [EMAIL, UNKNOWN_EMAIL], ids=["registered", "unknown"])
def test_concurrent_failures_do_not_exceed_limit(
    real_db: None, monkeypatch: pytest.MonkeyPatch, email: str
) -> None:
    """同時に 30 件の誤ったパスワードを送っても、照合に進むのは上限の 5 件だけで、ロックされること。

    未登録のメールアドレスでも同じ（同時の行の作成でデッドロックしても、やり直して 500 にしない）。
    """
    calls = count_password_checks(monkeypatch)

    statuses = send_concurrently(email, "WrongPassword1")

    with RealSession() as db:
        attempt = db.get(LoginAttempt, email)
    print(
        f"\n応答: {sorted(set(statuses))}、照合の回数: {len(calls)}、ロック期限: "
        f"{attempt.locked_until if attempt else None}"
    )
    assert statuses == [401] * CONCURRENT_REQUESTS
    assert len(calls) == settings.login_max_failed_attempts
    assert attempt is not None and attempt.locked_until is not None


def test_correct_password_rejected_after_concurrent_lock(
    real_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """同時の失敗でロックされたあとは、正しいパスワードでもログインできないこと。"""
    send_concurrently(EMAIL, "WrongPassword1")

    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 401


def test_db_connection_is_released_during_password_check(
    real_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """パスワードを照合している間は、DB の接続をプールに返していること。

    照合の順番待ち（最大 5 秒）の間も接続を持ち続けると、ログインを大量に送られたときに
    接続を使い切り、/auth/me などほかの API が DB を使えなくなるため。
    """
    checked_out_during_check: list[int] = []
    original = auth_service.verify_and_update_password

    def verify_and_update(password: str, hashed: str) -> tuple[bool, str | None]:
        checked_out_during_check.append(test_engine.pool.checkedout())
        return original(password, hashed)

    monkeypatch.setattr(auth_service, "verify_and_update_password", verify_and_update)

    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})

    print(f"\n照合中に使われていた DB の接続の数: {checked_out_during_check}")
    assert response.status_code == 200
    assert checked_out_during_check == [0]
