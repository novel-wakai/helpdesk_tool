"""DB の接続 URL の組み立てのテスト。

パスワードに URL で特別な意味を持つ記号（@ % / # : など）が含まれていても、
接続先の情報（ユーザー名・パスワード・ホスト・ポート・DB 名）が正しく読み取れることを確認する。
"""

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings

PASSWORDS = [
    "simplepass",
    "p@ss",
    "p%41ss",
    "p/ss",
    "p#ss",
    "p:ss",
    "p@ss%/w#rd:1",
]


def make_settings(password: str, jwt_secret_key: str = "x" * 32) -> Settings:
    # .env や環境変数の値に左右されないよう、値をすべて直接渡す
    return Settings(
        _env_file=None,
        mysql_user="helpdesk",
        mysql_password=password,
        mysql_database="helpdesk",
        mysql_host="db.example",
        mysql_port=3307,
        test_mysql_database="helpdesk_test",
        test_mysql_host="db-test.example",
        test_mysql_port=3308,
        jwt_secret_key=jwt_secret_key,
    )


@pytest.mark.parametrize("password", PASSWORDS)
def test_database_url_keeps_password(password: str) -> None:
    """アプリ（create_engine）に渡す URL で、パスワードと接続先が崩れないこと。"""
    url = make_url(make_settings(password).database_url)

    assert url.username == "helpdesk"
    assert url.password == password
    assert url.host == "db.example"
    assert url.port == 3307
    assert url.database == "helpdesk"
    assert url.query == {"charset": "utf8mb4"}


@pytest.mark.parametrize("password", PASSWORDS)
def test_test_database_url_keeps_password(password: str) -> None:
    """テスト用 DB の URL でも、パスワードと接続先が崩れないこと。"""
    url = make_url(make_settings(password).test_database_url)

    assert url.password == password
    assert url.host == "db-test.example"
    assert url.port == 3308
    assert url.database == "helpdesk_test"


@pytest.mark.parametrize("password", PASSWORDS)
def test_database_url_for_alembic(password: str) -> None:
    """alembic に渡す文字列（alembic/env.py と同じ変換）から、元の接続先に戻せること。"""
    url_string = make_settings(password).database_url.render_as_string(hide_password=False)

    config = Config()
    config.set_main_option("sqlalchemy.url", url_string.replace("%", "%%"))
    restored = make_url(config.get_main_option("sqlalchemy.url"))

    assert restored.password == password
    assert restored.host == "db.example"
    assert restored.port == 3307
    assert restored.database == "helpdesk"


def test_cookie_secure_is_enabled_by_default() -> None:
    """COOKIE_SECURE を設定し忘れても、Cookie は HTTPS でだけ送る（安全な側が既定）こと。"""
    assert Settings.model_fields["cookie_secure"].default is True


@pytest.mark.parametrize(
    ("secret", "message"),
    [
        pytest.param("change-me", "見本の値のまま", id="example-value"),
        pytest.param(
            "change-me-to-a-random-value-of-32-chars", "見本の値のまま", id="example-like"
        ),
        pytest.param("short-secret", "32 文字以上", id="too-short"),
    ],
)
def test_jwt_secret_key_rejects_unsafe_values(secret: str, message: str) -> None:
    """JWT_SECRET_KEY が見本の値のまま、または短すぎるときは、設定の読み込みで失敗すること。"""
    with pytest.raises(ValidationError, match=message):
        make_settings("simplepass", jwt_secret_key=secret)


@pytest.mark.parametrize("minutes", [0, -1])
def test_jwt_expire_minutes_must_be_positive(minutes: int) -> None:
    """JWT の有効期限が 0 以下のときは、設定の読み込みで失敗すること。

    0 以下だと、ログインしてもすぐに切れてしまうため。
    """
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Settings(
            _env_file=None,
            mysql_user="helpdesk",
            mysql_password="simplepass",
            mysql_database="helpdesk",
            jwt_secret_key="x" * 32,
            jwt_expire_minutes=minutes,
        )


def test_cors_origins_from_env_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS_ORIGINS は、.env.example の書き方（JSON の形）で読み込めること。"""
    monkeypatch.setenv("CORS_ORIGINS", '["https://helpdesk.example.com", "https://b.example.com"]')

    loaded = Settings(
        _env_file=None,
        mysql_user="helpdesk",
        mysql_password="simplepass",
        mysql_database="helpdesk",
        jwt_secret_key="x" * 32,
    )

    assert loaded.cors_origins == ["https://helpdesk.example.com", "https://b.example.com"]


def test_secrets_are_hidden_when_settings_are_printed() -> None:
    """settings を表示（repr・str）しても、DB のパスワードと JWT の署名キーが出ないこと。

    テストが失敗したときの表示や、ログに settings を出してしまったときに、秘密の値が漏れないように。
    """
    password = "db-password-should-not-appear"
    jwt_secret_key = "jwt-secret-should-not-appear-0123456789"
    loaded = make_settings(password, jwt_secret_key=jwt_secret_key)

    shown = repr(loaded) + str(loaded) + repr(loaded.database_url)

    assert password not in shown
    assert jwt_secret_key not in shown
    # 値そのものは、明示的に取り出せば使える
    assert loaded.mysql_password.get_secret_value() == password
    assert loaded.jwt_secret_key.get_secret_value() == jwt_secret_key


@pytest.mark.parametrize(
    "secret", ["short-secret", "change-me-but-secret-looking-value-1234"], ids=["short", "example"]
)
def test_settings_error_does_not_show_secret(secret: str) -> None:
    """設定の値が誤っているときのエラーに、入力された秘密の値が出ないこと。"""
    with pytest.raises(ValidationError) as error:
        make_settings("simplepass", jwt_secret_key=secret)

    assert "jwt_secret_key" in str(error.value)
    assert secret not in str(error.value)


@pytest.mark.parametrize(("length", "ok"), [(31, False), (32, True)])
def test_jwt_secret_key_length_boundary(length: int, ok: bool) -> None:
    """JWT_SECRET_KEY は 32 文字以上なら読み込め、31 文字では失敗すること。"""
    secret = "k" * length
    if ok:
        assert make_settings("simplepass", jwt_secret_key=secret).jwt_secret_key.get_secret_value()
        return
    with pytest.raises(ValidationError, match="32 文字以上"):
        make_settings("simplepass", jwt_secret_key=secret)


def test_settings_error_from_env_does_not_show_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数から読んだ値が誤っているときも、エラーに値が出ないこと。"""
    monkeypatch.setenv("MYSQL_USER", "helpdesk")
    monkeypatch.setenv("MYSQL_PASSWORD", "env-password-should-not-appear")
    monkeypatch.setenv("MYSQL_DATABASE", "helpdesk")
    monkeypatch.setenv("JWT_SECRET_KEY", "env-short-secret-xyz")
    monkeypatch.setenv("MYSQL_PORT", "not-a-port-xyz")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    message = str(error.value)
    assert "jwt_secret_key" in message and "mysql_port" in message
    for value in ["env-password-should-not-appear", "env-short-secret-xyz", "not-a-port-xyz"]:
        assert value not in message
