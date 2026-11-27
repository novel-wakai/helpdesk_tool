from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


def access_token_cookie_name() -> str:
    """ログインの Cookie の名前。

    HTTPS（Secure）のときは __Host- を付ける。__Host- の付いた Cookie は、ブラウザが
    「Secure・Path=/・Domain なし」のときだけ保存するため、同じドメインの別のサブドメインなどから
    上書きされない（攻撃者のアカウントでログインした状態にされる攻撃の対策）。
    開発環境（http）では __Host- の Cookie を保存できないため、付けない。
    """
    return "__Host-access_token" if settings.cookie_secure else "access_token"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Cookie の JWT から、ログイン中のユーザーを取り出す。

    次のときは 401 にする。
    - ログインしていない、トークンが無効（改ざん・期限切れ）
    - ユーザーが見つからない、利用停止中
    - ログアウトなどで世代番号が上がり、トークンが古くなった
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="ログインしてください"
    )
    access_token = request.cookies.get(access_token_cookie_name())
    if access_token is None:
        raise unauthorized
    payload = decode_access_token(access_token)
    if payload is None:
        raise unauthorized
    user = db.get(User, payload.user_id)
    # ログイン後に利用停止になったユーザーも、ここで締め出す
    if user is None or not user.is_active:
        raise unauthorized
    if payload.token_version != user.token_version:
        raise unauthorized
    return user
