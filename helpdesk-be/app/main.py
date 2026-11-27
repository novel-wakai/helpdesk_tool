from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings

# すべての応答に付ける、ブラウザ向けの安全のためのヘッダー
SECURITY_HEADERS = {
    # 応答の種類（Content-Type）をブラウザに推測させない（JSON を HTML として実行させない）
    "X-Content-Type-Options": "nosniff",
    # 他のサイトの画面の中に埋め込ませない（クリックジャッキングの対策）
    "X-Frame-Options": "DENY",
    # 他のサイトへ移動するときに、URL を相手に送らない
    "Referrer-Policy": "no-referrer",
}


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """入力の形式エラー（422）の応答から、送られてきた値（input）を取り除く。

    FastAPI の既定では送られた値をそのまま返すため、パスワードが応答に含まれ、
    通信の記録やエラー収集ツールに残ってしまう。どの項目がなぜ誤りかだけを返す。
    """
    errors = [
        {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def create_app() -> FastAPI:
    # API の説明画面は、設定で有効にしたときだけ表示する（既定は表示しない）。
    # 説明画面はログインなしで見られる（API の一覧を開発中に確かめるため）。
    # 有効にするのは開発環境だけにする
    docs_enabled = settings.enable_api_docs
    app = FastAPI(
        title="Novel HELPDESK API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        # 画面から使うメソッドとヘッダーだけを許可する（必要になったら追加する）
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.middleware("http")(add_security_headers)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
