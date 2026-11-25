"""テスト共通の準備。

テストはすべてテスト用 DB（db-test コンテナ）に接続する。開発用 DB には触らない。
- テスト開始時にテーブルを作り直す
- 各テストはトランザクション内で実行し、終わったらロールバックする（テスト同士でデータが混ざらない）
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401  モデルを読み込んで metadata に登録する
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

if settings.test_mysql_database == settings.mysql_database:
    raise RuntimeError(
        "TEST_MYSQL_DATABASE が開発用 DB と同じ名前です。開発データを消さないよう、別の名前にしてください。"
    )

test_engine = create_engine(settings.test_database_url, pool_pre_ping=True)


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
