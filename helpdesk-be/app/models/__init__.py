# モデルをここで読み込み、Base.metadata に登録する
# （alembic と pytest がテーブルを見つけられるように）
from app.models.login_attempt import LoginAttempt
from app.models.user import User

__all__ = ["LoginAttempt", "User"]
