from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import access_token_cookie_name, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import PasswordHashBusyError, create_access_token, decode_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, UserResponse
from app.services.auth import authenticate


def no_store(response: Response) -> None:
    """ログイン関係の応答（ユーザーの情報を含む）を、ブラウザや途中の経路に保存させない。"""
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(no_store)])

# どの理由で失敗しても同じ文言にする（登録済みのメールアドレスかを推測させないため）
LOGIN_FAILED_MESSAGE = "メールアドレスまたはパスワードが正しくありません"
LOGIN_BUSY_MESSAGE = "ログインが混み合っています。しばらくしてからもう一度お試しください"

# ログインの Cookie の属性（保存するときと消すときで同じにする。違うとブラウザが消さないことがある）
COOKIE_OPTIONS = {
    # JavaScript から読めないようにする（画面に悪意のあるスクリプトが入っても盗まれない）
    "httponly": True,
    # 他のサイトからのリクエストには Cookie を付けない（なりすまし操作＝CSRF の対策）。
    # Lax は他のサイトのリンクから移動したときには付けるが、この Cookie は画面から API を
    # 呼ぶときにしか使わないため、より厳しい Strict にする
    "samesite": "strict",
    "path": "/",
}


@router.post(
    "/login",
    response_model=UserResponse,
    responses={
        401: {"description": LOGIN_FAILED_MESSAGE},
        503: {"description": LOGIN_BUSY_MESSAGE},
    },
)
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> User | JSONResponse:
    """メールアドレスとパスワードでログインし、JWT を Cookie に保存する。"""
    client_ip = request.client.host if request.client else None
    try:
        user = authenticate(db, body.email, body.password, client_ip)
    except PasswordHashBusyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=LOGIN_BUSY_MESSAGE,
            headers={"Retry-After": "5"},
        ) from None
    if user is None:
        # 失敗したときは、前にログインしていたユーザーの Cookie も消す
        # （別のユーザーでログインし直そうとして失敗したのに、前のユーザーのままになるのを防ぐ）
        failed = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": LOGIN_FAILED_MESSAGE},
            headers={"Cache-Control": "no-store"},
        )
        failed.delete_cookie(
            access_token_cookie_name(), secure=settings.cookie_secure, **COOKIE_OPTIONS
        )
        return failed

    response.set_cookie(
        key=access_token_cookie_name(),
        value=create_access_token(user.id, user.token_version),
        # True のときは HTTPS の通信でだけ Cookie を送る（既定は True）
        secure=settings.cookie_secure,
        # max_age / expires を付けない（ブラウザを閉じると Cookie が消え、ログインが切れる）。
        # ブラウザを開いたままでも、JWT 自体の有効期限（8 時間）が来ればログインが切れる
        **COOKIE_OPTIONS,
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """ログアウトする。Cookie を消し、そのユーザーに発行済みのトークンをすべて使えなくする。

    世代番号を上げるため、ほかの端末（ブラウザ）のログインも切れる。
    ログインしていない・トークンが無効なときも、Cookie を消して 204 を返す。
    """
    access_token = request.cookies.get(access_token_cookie_name())
    payload = decode_access_token(access_token) if access_token else None
    if payload is not None:
        user = db.get(User, payload.user_id)
        # 古いトークン（すでにログアウト済み）では、世代番号を上げない
        if user is not None and user.token_version == payload.token_version:
            user.token_version += 1
            db.commit()
    response.delete_cookie(
        access_token_cookie_name(), secure=settings.cookie_secure, **COOKIE_OPTIONS
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    """ログイン中のユーザーを返す。ログインしていなければ 401。"""
    return current_user
