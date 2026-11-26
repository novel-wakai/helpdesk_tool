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
        pytest.param("short-secret", "at least 32 characters", id="too-short"),
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
