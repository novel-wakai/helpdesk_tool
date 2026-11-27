from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """API が起動しているかの確認。

    ログイン不要：監視の仕組みや開発環境の確認から、ログインせずに呼べるようにするため。
    業務のデータは返さない。
    """
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """DB に接続できるかの確認。

    ログイン不要：監視の仕組みや開発環境の確認から、ログインせずに呼べるようにするため。
    業務のデータは返さない（接続できないときも、DB の内部の情報は応答に出さない）。
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
