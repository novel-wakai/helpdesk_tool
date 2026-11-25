# helpdesk-be

Novel HELPDESK のバックエンド（FastAPI + SQLAlchemy + MySQL）。

セットアップとコマンドはリポジトリ直下の [README.md](../README.md) を参照してください。

## ディレクトリ構成

```
app/
├── api/v1/     # エンドポイント（ルーター）
├── core/       # 設定（環境変数）と DB 接続
├── models/     # SQLAlchemy のモデル（テーブル定義）
├── schemas/    # Pydantic のスキーマ（リクエスト・レスポンスの型）
├── services/   # 業務ロジック
├── domain/     # ドメインの定義（ステータスなど）
└── main.py     # FastAPI アプリの起点
alembic/        # マイグレーション
tests/          # pytest のテスト
```
