from pydantic_settings import BaseSettings, SettingsConfigDict


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

    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_host: str = "localhost"
    mysql_port: int = 3307

    # テスト用 DB（pytest だけが使う）
    test_mysql_database: str = "helpdesk_test"
    test_mysql_host: str = "localhost"
    test_mysql_port: int = 3308

    cors_origins: list[str] = ["http://localhost:5173"]

    def _build_url(self, host: str, port: int, database: str) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{host}:{port}/{database}?charset=utf8mb4"
        )

    @property
    def database_url(self) -> str:
        return self._build_url(self.mysql_host, self.mysql_port, self.mysql_database)

    @property
    def test_database_url(self) -> str:
        return self._build_url(
            self.test_mysql_host, self.test_mysql_port, self.test_mysql_database
        )


settings = Settings()
