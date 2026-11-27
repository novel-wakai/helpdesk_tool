"""ログイン（POST /api/v1/auth/login）とログイン状態の確認（GET /api/v1/auth/me）のテスト。"""

import logging
import threading
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.v1.auth import LOGIN_FAILED_MESSAGE
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    JWT_ALGORITHM,
    PasswordHashBusyError,
    create_access_token,
    hash_password,
)
from app.domain.user_role import UserRole
from app.main import app
from app.models.login_attempt import LoginAttempt
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services import auth as auth_service
from app.services.auth import utc_now

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"
PASSWORD = "Password123"


def assert_no_login_cookie(response: Response) -> None:
    """ログイン用の Cookie を発行していないこと（発行するのは、Cookie を消す指示だけ）。"""
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is None or ('access_token="";' in set_cookie and "Max-Age=0" in set_cookie)


@pytest.fixture(autouse=True)
def cookie_not_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    """テストの通信は http のため、Secure の Cookie はクライアントが送り返さない。

    .env の値に左右されないよう、テストでは Secure を外す（Secure のテストだけ個別に True にする）。
    """
    monkeypatch.setattr(settings, "cookie_secure", False)


@pytest.fixture
def user(db_session: Session) -> User:
    """利用中のユーザー（社員）。"""
    user = User(
        display_name="Test.Employee",
        email="aaa@example.com",
        password_hash=hash_password(PASSWORD),
        role=UserRole.EMPLOYEE,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def inactive_user(db_session: Session) -> User:
    """利用停止中のユーザー。"""
    user = User(
        display_name="Stopped.User",
        email="stopped@example.com",
        password_hash=hash_password(PASSWORD),
        role=UserRole.EMPLOYEE,
        is_active=False,
    )
    db_session.add(user)
    db_session.flush()
    return user


# ---------- ログイン：成功 ----------


def test_login_success(client: TestClient, user: User) -> None:
    """登録済みで利用中のメールアドレスと正しいパスワードで、ログインに成功すること。"""
    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "display_name": "Test.Employee",
        "email": "aaa@example.com",
        "role": "employee",
    }


@pytest.mark.parametrize(
    "email",
    [
        pytest.param("AAA@example.com", id="uppercase-local-part"),
        pytest.param("aaa@EXAMPLE.COM", id="uppercase-domain"),
        pytest.param("Aaa@Example.com", id="mixed-case"),
    ],
)
def test_login_ignores_email_case(client: TestClient, user: User, email: str) -> None:
    """メールアドレスに大文字が混ざっていても、小文字にそろえてログインできること。"""
    response = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["email"] == "aaa@example.com"


def test_login_sets_session_cookie(client: TestClient, user: User) -> None:
    """ログインに成功すると、JWT が安全な設定の Cookie で保存されること。"""
    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    set_cookie = response.headers["set-cookie"]
    print(f"\nSet-Cookie: {set_cookie}")
    assert set_cookie.startswith("access_token=")
    # JavaScript から読めない
    assert "HttpOnly" in set_cookie
    # 他のサイトからのリクエストには付かない
    assert "SameSite=strict" in set_cookie
    assert "Path=/" in set_cookie
    # 有効期限がない（ブラウザを閉じると消える）
    assert "Max-Age" not in set_cookie
    assert "expires" not in set_cookie.lower()


def test_login_cookie_is_secure_when_enabled(
    client: TestClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """COOKIE_SECURE が有効（既定）のときは、Cookie に Secure が付くこと（HTTPS でだけ送る）。"""
    monkeypatch.setattr(settings, "cookie_secure", True)

    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    set_cookie = response.headers["set-cookie"]
    print(f"\nSet-Cookie: {set_cookie}")
    # HTTPS のときは __Host- を付けた名前にする（サブドメインなどから上書きされないように）
    assert set_cookie.startswith("__Host-access_token=")
    assert "; Secure" in set_cookie
    assert "Path=/" in set_cookie
    assert "Domain" not in set_cookie


def test_secure_cookie_login_flow_over_https(user: User, db_session: Session) -> None:
    """HTTPS（COOKIE_SECURE=true）で、ログイン → /auth/me → ログアウトが一通り動くこと。"""

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, base_url="https://testserver") as https_client:
            settings_secure = pytest.MonkeyPatch()
            settings_secure.setattr(settings, "cookie_secure", True)
            try:
                login = https_client.post(
                    LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD}
                )
                assert login.status_code == 200
                assert https_client.get(ME_URL).status_code == 200
                assert https_client.post(LOGOUT_URL).status_code == 204
                assert https_client.get(ME_URL).status_code == 401
            finally:
                settings_secure.undo()
    finally:
        app.dependency_overrides.clear()


def test_login_token_expires_in_8_hours(client: TestClient, user: User) -> None:
    """発行される JWT の有効期限が 8 時間であること。"""
    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    token = response.cookies["access_token"]
    payload = jwt.decode(
        token, settings.jwt_secret_key.get_secret_value(), algorithms=[JWT_ALGORITHM]
    )
    assert payload["sub"] == str(user.id)
    assert payload["ver"] == user.token_version
    assert payload["exp"] - payload["iat"] == 8 * 60 * 60


# ---------- ログイン：失敗 ----------


@pytest.mark.parametrize(
    ("email", "password"),
    [
        pytest.param("aaa@example.com", "WrongPassword1", id="wrong-password"),
        pytest.param("unknown@example.com", PASSWORD, id="unknown-email"),
        pytest.param("stopped@example.com", PASSWORD, id="inactive-user"),
    ],
)
def test_login_failure_returns_same_message(
    client: TestClient, user: User, inactive_user: User, email: str, password: str
) -> None:
    """ログインできない場合は、理由に関係なく同じ 401 とメッセージを返すこと。

    Cookie も発行しないこと。
    """
    response = client.post(LOGIN_URL, json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json() == {"detail": LOGIN_FAILED_MESSAGE}
    assert_no_login_cookie(response)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"email": "not-an-email", "password": PASSWORD}, id="invalid-email-format"),
        pytest.param({"email": "aaa@example.com", "password": ""}, id="empty-password"),
        pytest.param({"password": PASSWORD}, id="missing-email"),
    ],
)
def test_login_invalid_input(client: TestClient, user: User, body: dict[str, str]) -> None:
    """入力の形式が正しくない場合は 422 になること。"""
    response = client.post(LOGIN_URL, json=body)

    assert response.status_code == 422


def test_validation_error_does_not_echo_password(client: TestClient) -> None:
    """422 の応答に、送ったパスワードが含まれないこと（通信の記録などに残らないように）。"""
    secret = "TopSecret1" + "x" * 200  # 長すぎて 422 になるパスワード

    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": secret})

    print(f"\n422 の応答: {response.text}")
    assert response.status_code == 422
    assert "TopSecret1" not in response.text
    # どの項目がなぜ誤りかは返す
    assert response.json()["detail"][0]["loc"] == ["body", "password"]


# ---------- ログイン状態の確認 ----------


def test_me_after_login(client: TestClient, user: User) -> None:
    """ログイン後は、Cookie でログイン中のユーザーを取得できること（ログイン状態が保たれる）。"""
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    response = client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["email"] == "aaa@example.com"


def test_auth_responses_are_not_cached(client: TestClient, user: User) -> None:
    """ログインと /auth/me の応答に Cache-Control: no-store が付くこと。

    ユーザーの情報を、ブラウザや途中の経路に保存させないため。
    """
    login = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})
    me = client.get(ME_URL)

    assert login.headers["cache-control"] == "no-store"
    assert me.headers["cache-control"] == "no-store"


def test_me_without_login(client: TestClient) -> None:
    """ログインしていない場合は 401 になること。"""
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_with_tampered_token(client: TestClient, user: User) -> None:
    """別の鍵で署名された（改ざんされた）トークンは 401 になること。"""
    forged = jwt.encode(
        {"sub": str(user.id), "ver": 0, "exp": datetime.now(UTC) + timedelta(hours=1)},
        "another-secret-key-that-is-32-chars-long",
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("access_token", forged)

    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_with_expired_token(client: TestClient, user: User) -> None:
    """有効期限が切れたトークンは 401 になること。"""
    expired = jwt.encode(
        {"sub": str(user.id), "ver": 0, "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("access_token", expired)

    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_after_user_deactivated(client: TestClient, user: User, db_session: Session) -> None:
    """ログイン後に利用停止になったユーザーは、以降 401 になること。"""
    client.cookies.set("access_token", create_access_token(user.id, user.token_version))
    user.is_active = False
    db_session.flush()

    response = client.get(ME_URL)

    assert response.status_code == 401


# ---------- パスワードの保存 ----------


def test_password_is_not_stored_as_plain_text(user: User) -> None:
    """パスワードはそのままではなく、ハッシュ（Argon2）で保存されること。"""
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")


# ---------- 総当たり攻撃の対策（一時ロック） ----------


def login_as(client: TestClient, email: str, password: str) -> int:
    return client.post(LOGIN_URL, json={"email": email, "password": password}).status_code


def get_attempt(db_session: Session, email: str) -> LoginAttempt | None:
    return db_session.get(LoginAttempt, email, populate_existing=True)


def test_login_locked_after_repeated_failures(
    client: TestClient, user: User, db_session: Session
) -> None:
    """続けて 5 回パスワードを間違えると、正しいパスワードでもログインできなくなること。"""
    for _ in range(settings.login_max_failed_attempts):
        assert login_as(client, "aaa@example.com", "WrongPassword1") == 401

    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None and attempt.locked_until is not None
    print(f"\nロック期限（UTC）: {attempt.locked_until}、今（UTC）: {utc_now()}")
    # ロック中も、ほかの失敗と同じ 401 とメッセージ（ロック中かどうかを見分けさせない）
    assert response.status_code == 401
    assert response.json() == {"detail": LOGIN_FAILED_MESSAGE}
    # ロックの期限は 15 分後（DB の DATETIME は秒未満を四捨五入して保存するため、1 秒の誤差を許す）
    remaining = attempt.locked_until - utc_now()
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15, seconds=1)


def test_unknown_email_is_recorded_and_locked_the_same_way(
    client: TestClient, db_session: Session
) -> None:
    """登録されていないメールアドレスも、同じように失敗が記録され、ロックされること。

    登録済みのときだけ記録すると、処理時間やロックの有無から登録の有無を推測されるため。
    """
    for count in range(1, settings.login_max_failed_attempts):
        login_as(client, "nobody@example.com", "WrongPassword1")
        attempt = get_attempt(db_session, "nobody@example.com")
        assert attempt is not None and attempt.failed_count == count

    login_as(client, "nobody@example.com", "WrongPassword1")

    attempt = get_attempt(db_session, "nobody@example.com")
    assert attempt is not None and attempt.locked_until is not None


def test_login_not_locked_before_limit(client: TestClient, user: User) -> None:
    """上限より 1 回少ない失敗なら、正しいパスワードでログインできること。"""
    for _ in range(settings.login_max_failed_attempts - 1):
        login_as(client, "aaa@example.com", "WrongPassword1")

    assert login_as(client, "aaa@example.com", PASSWORD) == 200


def test_login_success_clears_failed_attempts(
    client: TestClient, user: User, db_session: Session
) -> None:
    """ログインに成功すると、失敗の記録が消えること（あとの失敗は 1 回目から数える）。"""
    for _ in range(settings.login_max_failed_attempts - 1):
        login_as(client, "aaa@example.com", "WrongPassword1")

    assert login_as(client, "aaa@example.com", PASSWORD) == 200
    assert get_attempt(db_session, "aaa@example.com") is None
    # 成功のあとに 1 回間違えても、ロックされない
    login_as(client, "aaa@example.com", "WrongPassword1")
    assert login_as(client, "aaa@example.com", PASSWORD) == 200


def test_failed_count_restarts_after_window(
    client: TestClient, user: User, db_session: Session
) -> None:
    """数え始めてから 15 分たっていれば、回数は 1 から数え直すこと（15 分以内に 5 回でロック）。"""
    db_session.add(
        LoginAttempt(
            email="aaa@example.com",
            failed_count=settings.login_max_failed_attempts - 1,
            first_failed_at=utc_now() - timedelta(minutes=settings.login_lock_minutes, seconds=1),
        )
    )
    db_session.flush()

    login_as(client, "aaa@example.com", "WrongPassword1")

    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert attempt.failed_count == 1
    assert attempt.locked_until is None


def test_login_allowed_after_lock_expires(
    client: TestClient, user: User, db_session: Session
) -> None:
    """ロックの期限が過ぎたら、またログインできること。"""
    db_session.add(
        LoginAttempt(
            email="aaa@example.com",
            failed_count=settings.login_max_failed_attempts,
            first_failed_at=utc_now() - timedelta(minutes=16),
            locked_until=utc_now() - timedelta(seconds=1),
        )
    )
    db_session.flush()

    assert login_as(client, "aaa@example.com", PASSWORD) == 200
    assert get_attempt(db_session, "aaa@example.com") is None


def test_login_failures_are_logged_without_password(
    client: TestClient, user: User, caplog: pytest.LogCaptureFixture
) -> None:
    """ログインの失敗とロックがログに残り、パスワードは残らないこと。"""
    with caplog.at_level(logging.WARNING, logger="app.auth"):
        for _ in range(settings.login_max_failed_attempts):
            login_as(client, "aaa@example.com", "WrongPassword1")
        login_as(client, "aaa@example.com", PASSWORD)

    print("\n" + "\n".join(caplog.messages))
    assert "login failed (wrong password): email=aaa@example.com" in caplog.text
    assert "login locked (wrong password): email=aaa@example.com" in caplog.text
    assert "login rejected (locked): email=aaa@example.com" in caplog.text
    assert "WrongPassword1" not in caplog.text
    assert PASSWORD not in caplog.text


def test_login_returns_503_when_password_check_is_busy(
    client: TestClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """パスワードの照合が混み合っていて順番が回ってこないときは、503 を返すこと。"""

    def busy(password: str, hashed: str) -> tuple[bool, str | None]:
        raise PasswordHashBusyError

    monkeypatch.setattr(auth_service, "verify_and_update_password", busy)

    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert_no_login_cookie(response)


def raise_busy(password: str, hashed: str) -> tuple[bool, str | None]:
    raise PasswordHashBusyError


def add_attempt(
    db_session: Session,
    failed: int,
    pending: int,
    email: str = "aaa@example.com",
    started_minutes_ago: float = 0,
) -> LoginAttempt:
    """試行の記録を作る（数え始めは、今から started_minutes_ago 分前）。

    ログインの処理が照合しないで断るとき、セッションを rollback する。テストではアプリと
    セッションを共有しているため、確定（commit）しておかないと、作った記録まで消えてしまう
    （テストが終わればテスト全体のトランザクションごと巻き戻る）。
    """
    attempt = LoginAttempt(
        email=email,
        failed_count=failed,
        pending_count=pending,
        first_failed_at=utc_now() - timedelta(minutes=started_minutes_ago),
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_busy_login_does_not_count_toward_lock(
    client: TestClient,
    user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """照合が混み合って 503 になった試行は、回数に数えないこと。

    照合していない試行で上限に達し、正しいパスワードでもログインできなくなるのを防ぐ。
    混み合ったことはログに残し、パスワードは残さない。
    """
    original = auth_service.verify_and_update_password

    # 2 回失敗したあとに、上限の回数を超えて 503 になっても
    for _ in range(2):
        assert login_as(client, "aaa@example.com", "WrongPassword1") == 401
    monkeypatch.setattr(auth_service, "verify_and_update_password", raise_busy)
    with caplog.at_level(logging.WARNING, logger="app.auth"):
        for _ in range(settings.login_max_failed_attempts + 1):
            assert login_as(client, "aaa@example.com", PASSWORD) == 503

    # 失敗した数は 2 回のままで、照合中の数も残らない
    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (2, 0)
    assert attempt.locked_until is None
    assert "login busy: email=aaa@example.com" in caplog.text
    assert PASSWORD not in caplog.text

    # 混み合いが解消すれば、正しいパスワードでログインできる
    monkeypatch.setattr(auth_service, "verify_and_update_password", original)
    assert login_as(client, "aaa@example.com", PASSWORD) == 200


def test_busy_login_with_unknown_email_does_not_count(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未登録のメールアドレスでも、ダミーの照合が混み合って 503 になった試行は数えないこと。"""

    def busy(password: str, hashed: str) -> bool:
        raise PasswordHashBusyError

    monkeypatch.setattr(auth_service, "verify_password", busy)

    assert login_as(client, "nobody@example.com", PASSWORD) == 503

    attempt = get_attempt(db_session, "nobody@example.com")
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (0, 0)
    assert attempt.locked_until is None


def test_lock_depends_only_on_checked_failures(
    client: TestClient, user: User, db_session: Session
) -> None:
    """ロックは、照合して失敗した数だけで決まること（照合中の試行は含めない）。

    照合中の試行が 4 件あるときに 1 回間違えても、ロックしない。照合中の試行は、
    あとで混み合いのため照合しないまま 503 になるかもしれないため。
    """
    add_attempt(db_session, failed=0, pending=settings.login_max_failed_attempts - 1)

    assert login_as(client, "aaa@example.com", "WrongPassword1") == 401

    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert attempt.failed_count == 1
    assert attempt.pending_count == settings.login_max_failed_attempts - 1
    assert attempt.locked_until is None


@pytest.mark.parametrize("email", ["aaa@example.com", "nobody@example.com"])
def test_login_returns_503_while_limit_is_in_progress(
    client: TestClient, user: User, db_session: Session, email: str
) -> None:
    """失敗した数と照合中の数で上限に達しているときは、照合しないで 503 を返すこと。

    照合中の試行が終われば試せるため、パスワードの誤りを表す 401 にはしない。
    断った試行は数えない。未登録のメールアドレスでも同じ（登録の有無を推測させない）。
    """
    add_attempt(db_session, failed=settings.login_max_failed_attempts - 1, pending=1, email=email)

    response = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert_no_login_cookie(response)
    attempt = get_attempt(db_session, email)
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (
        settings.login_max_failed_attempts - 1,
        1,
    )


@pytest.mark.parametrize(("minutes_ago", "expected"), [(14, 503), (16, 200)])
def test_leftover_pending_count_is_reset_after_window(
    client: TestClient, user: User, db_session: Session, minutes_ago: int, expected: int
) -> None:
    """照合中の数が残ったまま（処理が途中で止まった）でも、数え始めから 15 分たてば数え直すこと。

    15 分たつまでは照合に進ませない（照合できる回数を増やさない、安全な側）。
    """
    add_attempt(
        db_session,
        failed=0,
        pending=settings.login_max_failed_attempts,
        started_minutes_ago=minutes_ago,
    )

    assert login_as(client, "aaa@example.com", PASSWORD) == expected


@pytest.mark.parametrize(
    ("email", "check"),
    [("aaa@example.com", "verify_and_update_password"), ("nobody@example.com", "verify_password")],
    ids=["registered", "unknown"],
)
def test_password_check_error_releases_pending_count(
    user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    email: str,
    check: str,
) -> None:
    """照合の途中でエラー（保存されたハッシュが壊れているなど）になったら、500 を返し、
    失敗として数えず、照合中の数も残さないこと（残ると、試すたびに照合に進める回数が減っていく）。
    """

    def broken_check(password: str, hashed: str) -> tuple[bool, str | None]:
        raise RuntimeError("broken hash")

    monkeypatch.setattr(auth_service, check, broken_check)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with (
            caplog.at_level(logging.WARNING, logger="app.auth"),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            status_code = login_as(client, email, PASSWORD)
    finally:
        app.dependency_overrides.clear()

    assert status_code == 500
    attempt = get_attempt(db_session, email)
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (0, 0)
    assert f"login check error: email={email}" in caplog.text
    assert PASSWORD not in caplog.text


def test_success_does_not_clear_new_window_lock(
    client: TestClient, user: User, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合している間に、新しい数え始めで失敗が続いてロックされていたら、
    前の数え始めの試行がログインに成功しても、そのロックを消さないこと。
    """
    original = auth_service.verify_and_update_password
    login_as(client, "aaa@example.com", "WrongPassword1")

    def new_window_locked_then_check(password: str, hashed: str) -> tuple[bool, str | None]:
        attempt = get_attempt(db_session, "aaa@example.com")
        assert attempt is not None
        attempt.failed_count = settings.login_max_failed_attempts
        attempt.pending_count = 0
        attempt.first_failed_at = utc_now()
        attempt.locked_until = utc_now() + timedelta(minutes=settings.login_lock_minutes)
        db_session.flush()
        return original(password, hashed)

    monkeypatch.setattr(auth_service, "verify_and_update_password", new_window_locked_then_check)

    assert login_as(client, "aaa@example.com", PASSWORD) == 200

    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert attempt.locked_until is not None


def start_new_window(db_session: Session, change: str) -> None:
    """照合している間に、ほかのリクエストで数え始めが変わった状態にする。

    recreated：ログインの成功で行が消え、別の試行で作り直された
    restarted：数え始めから 15 分たち、数え直された
    どちらも、新しい数え始めで 1 回失敗し、1 件が照合中とする。
    """
    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    if change == "recreated":
        db_session.delete(attempt)
        db_session.flush()
        add_attempt(db_session, failed=1, pending=1)
        return
    attempt.failed_count = 1
    attempt.pending_count = 1
    attempt.first_failed_at = utc_now()
    db_session.flush()


@pytest.mark.parametrize("change", ["recreated", "restarted"])
@pytest.mark.parametrize("outcome", ["busy", "wrong password"])
def test_old_window_attempt_does_not_touch_new_window(
    client: TestClient,
    user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    outcome: str,
) -> None:
    """照合している間に数え始めが変わったら、前の数え始めの試行は新しい行を変えないこと。

    503 で照合中の数を引いたり（busy）、失敗を足してロックしたり（wrong password）すると、
    新しい数え始めで照合できる回数が増えたり、関係のない失敗でロックしたりしてしまう。
    """
    for _ in range(settings.login_max_failed_attempts - 1):
        login_as(client, "aaa@example.com", "WrongPassword1")

    def change_window(password: str, hashed: str) -> tuple[bool, str | None]:
        start_new_window(db_session, change)
        if outcome == "busy":
            raise PasswordHashBusyError
        return False, None

    monkeypatch.setattr(auth_service, "verify_and_update_password", change_window)

    status_code = login_as(client, "aaa@example.com", "WrongPassword1")

    assert status_code == (503 if outcome == "busy" else 401)
    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (1, 1)
    assert attempt.locked_until is None


def test_attempt_rejected_during_busy_wait_does_not_block_login(
    client: TestClient, user: User, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合を待つ間に断られた試行があっても、503 のあとにログインできること。"""
    original = auth_service.verify_and_update_password
    for _ in range(settings.login_max_failed_attempts - 1):
        login_as(client, "aaa@example.com", "WrongPassword1")

    def rejected_retry_then_busy(password: str, hashed: str) -> tuple[bool, str | None]:
        # 上限の回目の試行が照合を待つ間に、利用者が再送した（照合せずに断られる）
        with pytest.raises(PasswordHashBusyError):
            auth_service.authenticate(db_session, "aaa@example.com", PASSWORD)
        raise PasswordHashBusyError

    monkeypatch.setattr(auth_service, "verify_and_update_password", rejected_retry_then_busy)
    assert login_as(client, "aaa@example.com", PASSWORD) == 503

    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (
        settings.login_max_failed_attempts - 1,
        0,
    )

    monkeypatch.setattr(auth_service, "verify_and_update_password", original)
    assert login_as(client, "aaa@example.com", PASSWORD) == 200


@pytest.mark.parametrize("rollback_fails", [False, True], ids=["update", "update+rollback"])
def test_busy_login_returns_503_when_refund_fails(
    client: TestClient,
    user: User,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    rollback_fails: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """照合中の数を引くときに DB でエラーが起きても、500 ではなく 503 を返し、ログに残すこと。

    引けなかった分は照合中の数に残る（照合に進める回数が減る、安全な側）。
    取り消し（rollback）まで失敗しても 503 を返す。
    """

    def broken_update(*args: object) -> None:
        raise OperationalError("UPDATE login_attempts", {}, Exception("lock wait timeout"))

    def broken_rollback() -> None:
        raise OperationalError("ROLLBACK", {}, Exception("connection lost"))

    monkeypatch.setattr(auth_service, "verify_and_update_password", raise_busy)
    monkeypatch.setattr(auth_service, "update", broken_update)
    if rollback_fails:
        monkeypatch.setattr(db_session, "rollback", broken_rollback)

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert "login busy refund failed: email=aaa@example.com" in caplog.text
    assert PASSWORD not in caplog.text
    monkeypatch.undo()
    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert (attempt.failed_count, attempt.pending_count) == (0, 1)


def test_busy_login_keeps_existing_lock(
    client: TestClient, user: User, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ロック中は照合に進まないため、503 にならず、ロックも解けないこと。"""
    for _ in range(settings.login_max_failed_attempts):
        login_as(client, "aaa@example.com", "WrongPassword1")

    calls: list[str] = []

    def busy(password: str, hashed: str) -> tuple[bool, str | None]:
        calls.append(hashed)
        raise PasswordHashBusyError

    monkeypatch.setattr(auth_service, "verify_and_update_password", busy)

    assert login_as(client, "aaa@example.com", PASSWORD) == 401
    assert calls == []
    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None and attempt.locked_until is not None


def test_password_check_waits_for_free_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """同時に照合できる数がいっぱいで、待っても空かなければ PasswordHashBusyError になること。"""
    full = threading.BoundedSemaphore(1)
    full.acquire()
    monkeypatch.setattr(security, "_password_hash_slots", full)
    monkeypatch.setattr(security, "PASSWORD_HASH_WAIT_SECONDS", 0.1)

    with pytest.raises(PasswordHashBusyError):
        security.verify_password(PASSWORD, security.DUMMY_PASSWORD_HASH)


# ---------- ログアウト ----------


def test_logout_clears_cookie_and_revokes_token(client: TestClient, user: User) -> None:
    """ログアウトすると Cookie が消え、それまでのトークンは使えなくなること。"""
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})
    old_token = client.cookies["access_token"]

    response = client.post(LOGOUT_URL)

    print(f"\nログアウトの Set-Cookie: {response.headers['set-cookie']}")
    assert response.status_code == 204
    assert response.headers["set-cookie"].startswith('access_token="";')
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert client.get(ME_URL).status_code == 401
    # 消す前のトークンを持ち出して使っても、401 になる
    client.cookies.set("access_token", old_token)
    assert client.get(ME_URL).status_code == 401


def test_logout_revokes_other_sessions(client: TestClient, user: User) -> None:
    """ログアウトすると、ほかの端末（別に発行したトークン）のログインも切れること。"""
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})
    other_device_token = client.cookies["access_token"]
    client.cookies.clear()
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    client.post(LOGOUT_URL)

    client.cookies.set("access_token", other_device_token)
    assert client.get(ME_URL).status_code == 401


def test_login_again_after_logout(client: TestClient, user: User) -> None:
    """ログアウトしたあとも、もう一度ログインできること。"""
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})
    client.post(LOGOUT_URL)

    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    assert client.get(ME_URL).status_code == 200


def test_logout_without_login(client: TestClient) -> None:
    """ログインしていなくても、ログアウトは 204 を返すこと（失敗させない）。"""
    response = client.post(LOGOUT_URL)

    assert response.status_code == 204


def test_token_without_version_is_rejected(client: TestClient, user: User) -> None:
    """世代番号（ver）を含まないトークンは 401 になること。"""
    token = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("access_token", token)

    assert client.get(ME_URL).status_code == 401


def test_token_with_boolean_version_is_rejected(client: TestClient, user: User) -> None:
    """世代番号（ver）が true / false のトークンは 401 になること（bool を数として扱わない）。"""
    token = jwt.encode(
        {"sub": str(user.id), "ver": False, "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    client.cookies.set("access_token", token)

    assert client.get(ME_URL).status_code == 401


def test_failed_login_clears_previous_cookie(client: TestClient, user: User) -> None:
    """ログインに失敗したら、前にログインしていたユーザーの Cookie も消えること。"""
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})

    response = client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": "Wrong1234"})

    assert response.status_code == 401
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    assert client.get(ME_URL).status_code == 401


def test_failures_spread_over_window_do_not_lock(
    client: TestClient, user: User, db_session: Session
) -> None:
    """数え始めてから 15 分を過ぎた失敗は、前の回数に足さないこと。

    14 分おきに失敗しても、ロックしない（「15 分以内に 5 回」でロックする）。
    """
    db_session.add(
        LoginAttempt(
            email="aaa@example.com",
            failed_count=settings.login_max_failed_attempts - 1,
            # 最後の失敗は 1 分前だが、数え始めたのは 16 分前
            first_failed_at=utc_now() - timedelta(minutes=16),
        )
    )
    db_session.flush()

    login_as(client, "aaa@example.com", "WrongPassword1")

    attempt = get_attempt(db_session, "aaa@example.com")
    assert attempt is not None
    assert attempt.failed_count == 1
    assert attempt.locked_until is None


def test_uppercase_attempts_count_toward_same_account(
    client: TestClient, user: User, db_session: Session
) -> None:
    """大文字を混ぜた入力（AAA@...）の失敗も、aaa@... への試行として数えてロックすること。"""
    variants = ["AAA@example.com", "aaa@EXAMPLE.COM", "Aaa@Example.com", "aAa@example.com"]
    for email in [*variants, "aaa@example.com"][: settings.login_max_failed_attempts]:
        login_as(client, email, "WrongPassword1")

    assert login_as(client, "aaa@example.com", PASSWORD) == 401


def test_unknown_email_runs_dummy_password_check(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """未登録のメールアドレスでも、ダミーのパスワードの照合を 1 回行うこと。

    登録済みのときと応答時間をそろえ、登録の有無を推測させないため。
    """
    calls: list[str] = []
    original = auth_service.verify_password

    def spy(password: str, hashed: str) -> bool:
        calls.append(hashed)
        return original(password, hashed)

    monkeypatch.setattr(auth_service, "verify_password", spy)

    login_as(client, "nobody@example.com", PASSWORD)

    assert calls == [security.DUMMY_PASSWORD_HASH]


def test_password_hash_is_upgraded_on_login(client: TestClient, db_session: Session) -> None:
    """古い設定のハッシュで保存されたパスワードは、ログイン時に今の設定で作り直されること。"""
    from pwdlib import PasswordHash
    from pwdlib.hashers.argon2 import Argon2Hasher

    weak_hash = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash(PASSWORD)
    old = User(
        display_name="Old.Hash",
        email="old@example.com",
        password_hash=weak_hash,
        role=UserRole.EMPLOYEE,
    )
    db_session.add(old)
    db_session.flush()

    assert login_as(client, "old@example.com", PASSWORD) == 200

    db_session.refresh(old)
    print(f"\n作り直す前: {weak_hash.split('$')[3]} → 後: {old.password_hash.split('$')[3]}")
    assert old.password_hash != weak_hash
    assert "m=65536" in old.password_hash
    assert login_as(client, "old@example.com", PASSWORD) == 200


def test_logout_with_old_token_does_not_revoke_new_login(client: TestClient, user: User) -> None:
    """ログアウト済みの古いトークンでログアウトしても、新しいログインは切れないこと。"""
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})
    old_token = client.cookies["access_token"]
    client.post(LOGOUT_URL)
    client.post(LOGIN_URL, json={"email": "aaa@example.com", "password": PASSWORD})
    new_token = client.cookies["access_token"]

    client.cookies.clear()
    client.cookies.set("access_token", old_token)
    client.post(LOGOUT_URL)

    client.cookies.clear()
    client.cookies.set("access_token", new_token)
    assert client.get(ME_URL).status_code == 200


@pytest.mark.parametrize(
    "email",
    [
        pytest.param("x <aaa@example.com>", id="display-name"),
        pytest.param(" aaa@example.com", id="leading-space"),
        pytest.param("aaa@example.com ", id="trailing-space"),
    ],
)
def test_login_rejects_non_plain_email(client: TestClient, db_session: Session, email: str) -> None:
    """名前付きの形や前後の空白があるものは、メールアドレスとして受け付けない（422）こと。"""
    response = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})

    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(LoginAttempt)) == 0


def test_login_rejects_password_longer_than_limit(client: TestClient, user: User) -> None:
    """パスワードが 20 文字を超えると、照合せずに 422 になること。"""
    response = client.post(
        LOGIN_URL, json={"email": "aaa@example.com", "password": "A1" * 10 + "x"}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]


def test_login_with_20_char_password(client: TestClient, db_session: Session) -> None:
    """ちょうど 20 文字のパスワードでは、ログインできること。"""
    password = "Abcdefghij1234567890"
    db_session.add(
        User(
            display_name="Long.Password",
            email="long@example.com",
            password_hash=hash_password(password),
            role=UserRole.EMPLOYEE,
        )
    )
    db_session.flush()

    assert login_as(client, "long@example.com", password) == 200


def test_login_request_lowercases_email() -> None:
    """ログインの入力のメールアドレスは、小文字にそろえてから照合に使うこと。

    DB の照合順序（大文字・小文字を区別しない）に頼らず、ログや試行の記録もそろえるため。
    """
    assert LoginRequest(email="AAA@Example.COM", password=PASSWORD).email == "aaa@example.com"


def test_uppercase_login_is_logged_in_lowercase(
    client: TestClient, user: User, caplog: pytest.LogCaptureFixture
) -> None:
    """大文字を混ぜて失敗しても、ログには小文字のメールアドレスで残ること。"""
    with caplog.at_level(logging.WARNING, logger="app.auth"):
        login_as(client, "AAA@Example.COM", "WrongPassword1")

    assert "email=aaa@example.com" in caplog.text
    assert "AAA@Example.COM" not in caplog.text
