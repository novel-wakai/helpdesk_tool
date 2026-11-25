"""DB の接続 URL の組み立てのテスト。

パスワードに URL で特別な意味を持つ記号（@ % / # : など）が含まれていても、
接続先の情報（ユーザー名・パスワード・ホスト・ポート・DB 名）が正しく読み取れることを確認する。
"""

import pytest
from alembic.config import Config
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


def make_settings(password: str) -> Settings:
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
