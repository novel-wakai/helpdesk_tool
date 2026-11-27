from collections.abc import Generator

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def create_db_engine(url: URL) -> Engine:
    """DB への接続を作る。

    接続ごとにタイムゾーンを UTC にする。MySQL の既定は DB サーバーの時刻（日本時間）のため、
    NOW() で入る created_at（日本時間）と、アプリで作る日時（UTC）が同じ DB の中で混ざってしまう。
    日時はすべて UTC で保存し、画面に出すときに日本時間に変える。
    """
    return create_engine(
        url, pool_pre_ping=True, connect_args={"init_command": "SET time_zone = '+00:00'"}
    )


engine = create_db_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """すべてのモデルの基底クラス。"""


def get_db() -> Generator[Session]:
    """リクエストごとに DB セッションを渡す FastAPI の依存関数。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
