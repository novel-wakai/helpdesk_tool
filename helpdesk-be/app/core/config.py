from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """環境変数から読み込む設定。

    docker compose で起動したときは compose が環境変数を渡す。
    ホストから直接実行するとき（alembic など）はリポジトリ直下の .env を読む。
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 動かす環境。開発用の操作（テストユーザーの作成など）は development のときだけ行う。
    # 設定し忘れても安全なよう、既定は production
    app_env: Literal["development", "production"] = "production"

    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_host: str = "localhost"
    mysql_port: int = 3307

    # テスト用 DB（pytest だけが使う）
    test_mysql_database: str = "helpdesk_test"
    test_mysql_host: str = "localhost"
    test_mysql_port: int = 3308

    # 画面（FE）の URL。この URL からのリクエストだけ、Cookie 付きで API を呼べる（CORS）。
    # .env では JSON の形で、全体を ' ' で囲んで書く（例：CORS_ORIGINS='["https://helpdesk.example.com"]'）
    cors_origins: list[str] = ["http://localhost:5173"]

    # ログイン用トークン（JWT）の署名に使う秘密の値。既定値は置かず、.env での設定を必須にする
    # （設定し忘れたまま、誰でも知っている値で動いてしまうのを防ぐ）。推測されないよう 32 文字以上
    jwt_secret_key: str = Field(min_length=32)
    # JWT の有効期限（分）。8 時間（1 日の勤務時間）
    # 0 や負の数だと、ログインしてもすぐに切れてしまうため、1 分以上にする
    jwt_expire_minutes: int = Field(default=480, ge=1)
    # ログインの Cookie を HTTPS の通信でだけ送るか。設定し忘れても安全なよう、既定は True。
    # 開発環境（http://localhost）だけ .env で COOKIE_SECURE=false にする
    cookie_secure: bool = True

    # 総当たり攻撃の対策：同じアカウントで続けてこの回数パスワードを間違えると、
    # 一時的にログインできなくする
    login_max_failed_attempts: int = Field(default=5, ge=1)
    # 一時的にログインできなくする時間（分）
    login_lock_minutes: int = Field(default=15, ge=1)
    # 同時に行うパスワードの照合（Argon2。1 回で約 64MB のメモリを使う）の上限。
    # 大量のログインを同時に送られても、メモリを使い切って BE が止まらないようにする
    password_hash_concurrency: int = Field(default=4, ge=1)

    # API の説明画面（/docs・/redoc・/openapi.json）を表示するか。
    # 本番で API の一覧を外部に見せないよう、既定は False。開発環境だけ .env で true にする
    enable_api_docs: bool = False

    # 長さの確認（min_length）より先に実行し、見本の値のときは原因が分かるメッセージを出す
    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def reject_example_secret(cls, value: object) -> object:
        # .env.example の見本の値（公開されている）のまま動かさない。
        # 見本の値を知っていれば、誰でも任意のユーザー（管理者を含む）の JWT を作れてしまうため
        if isinstance(value, str) and value.startswith("change-me"):
            raise ValueError(
                "JWT_SECRET_KEY が .env.example の見本の値のままです。"
                "openssl rand -hex 32 などで作った値に変更してください"
            )
        return value

    def _build_url(self, host: str, port: int, database: str) -> URL:
        # 文字列を組み立てず URL.create を使う。パスワードに @ や % などの記号が含まれていても、
        # SQLAlchemy が正しく扱う（文字列にするときは自動で URL エンコードされる）
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=host,
            port=port,
            database=database,
            query={"charset": "utf8mb4"},
        )

    @property
    def database_url(self) -> URL:
        return self._build_url(self.mysql_host, self.mysql_port, self.mysql_database)

    @property
    def test_database_url(self) -> URL:
        return self._build_url(self.test_mysql_host, self.test_mysql_port, self.test_mysql_database)


settings = Settings()
