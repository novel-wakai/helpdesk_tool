# Novel HELPDESK

社内からの問い合わせをひとつの窓口にまとめる、チケット管理システムです。

- **社員**が困りごとや依頼を「チケット」として起票する
- **サポート担当**がチケットを引き受け、やり取りしながら解決まで進める
- **管理者**がアカウントを管理し、問い合わせ全体の状況をグラフで確認する

質問から解決までのやり取りと対応の経緯がチケットに残るため、誰が何をどこまで対応したかを追えます。

> 業務ルールの詳細は `helpdesk_overview.md`（開発の前提資料）に、画面のイメージは `Novel HELPDESK - Sample.pdf`（画面サンプル）にまとめています。
> これらの資料は**リポジトリには含めていません**。開発に参加する方は担当者から別途受け取り、`private/` フォルダに置いてください（フォルダごと `.gitignore` で除外済みのため、コミットされません）。

## 目次

1. [システム構成](#システム構成)
2. [使用技術](#使用技術)
3. [セットアップ](#セットアップ)
4. [よく使うコマンド](#よく使うコマンド)
5. [参考資料](#参考資料)

## システム構成

| 名前 | 役割 | URL（ローカル） |
|---|---|---|
| helpdesk-be | API サーバー | http://localhost:8000/api/v1 |
| helpdesk-fe | Web 画面 | http://localhost:5173 |
| db | MySQL・開発用（Docker） | localhost:3307 |
| db-test | MySQL・テスト用（Docker）。pytest だけが使い、止めるとデータは消える | localhost:3308 |

- 認証は JWT（トークン）で行います
- フロントエンドはバックエンドが起動している前提で動きます

```
helpdesk_tool/
├── README.md
├── docker-compose.yml   # MySQL と BE をまとめて起動
├── .env.example         # 環境変数の見本
├── private/             # 非公開資料（Git 管理外。各自で用意する）
├── helpdesk-be/         # バックエンド（FastAPI）
└── helpdesk-fe/         # フロントエンド（React）
```

## 使用技術

### Backend（helpdesk-be）

| 用途 | 採用技術 |
|---|---|
| 言語 | Python 3.13 |
| フレームワーク | FastAPI |
| ORM | SQLAlchemy v2 |
| マイグレーション | Alembic |
| DB | MySQL 8.0 |
| パッケージ管理 | Poetry |
| 実行環境 | Docker / docker compose |
| テスト | pytest（テスト用 DB は Docker で起動） |

### Frontend（helpdesk-fe）

| 用途 | 採用技術 |
|---|---|
| 言語 | TypeScript |
| フレームワーク | React 19 + Vite |
| UI ライブラリ | Chakra UI v3 |
| サーバー状態管理 | TanStack React Query v5 |
| HTTP クライアント | Axios |
| ルーティング | React Router v7 |
| グラフ描画 | Recharts |
| テスト | Vitest + React Testing Library、E2E は Playwright |
| パッケージ管理 | yarn |

画面は **Container**（データ取得・ロジック）と **Presentational**（表示のみ）に分けて実装します。

## セットアップ

### 開発に必要なもの

- Docker / Docker Compose
- Python 3.13、Poetry
- Node.js 26、yarn（Node.js のバージョンは `helpdesk-fe/.nvmrc` で指定。22.22.2 以上の 22 系・24.15 以上の 24 系でも動作しますが、23・25 系やそれより古いバージョンでは `yarn install` が失敗します）

### 1. 前提資料を受け取る

担当者から次の資料を受け取り、`private/` フォルダ（なければ作成）に置きます。このフォルダは Git の管理外です。

- `helpdesk_overview.md`（開発の前提資料）
- `Novel HELPDESK - Sample.pdf`（画面サンプル）

### 2. 環境変数を用意する

```bash
cp .env.example .env
# .env のパスワードを任意の値に変更する
```

### 3. Backend を起動する（DB と API を Docker で起動）

```bash
docker compose up -d --build
```

- 動作確認：http://localhost:8000/api/v1/health
- API ドキュメント（Swagger UI）：http://localhost:8000/docs
- MySQL はホストの **3307** 番（開発用）と **3308** 番（テスト用）で公開しています（ローカルの MySQL との衝突を避けるため）
- 起動するコンテナは `db`（開発用 DB）、`db-test`（テスト用 DB）、`be`（API）の 3 つです

エディタの補完用に、ホストにも仮想環境を作っておきます。

```bash
cd helpdesk-be
poetry config virtualenvs.in-project true   # 初回のみ。helpdesk-be/.venv に作られる
poetry env use python3.13
poetry install
```

### 4. Frontend を起動する

```bash
cd helpdesk-fe
yarn install
yarn dev
```

http://localhost:5173 を開き、「API: 接続OK」と表示されればセットアップ完了です。

## よく使うコマンド

| 用途 | コマンド | 実行場所 |
|---|---|---|
| BE・DB の起動 / 停止 | `docker compose up -d` / `docker compose down` | リポジトリ直下 |
| BE のテスト（テスト用 DB を使用） | `docker compose exec be pytest` | リポジトリ直下 |
| BE の本番用イメージ作成（本番用パッケージのみ） | `docker build --target prod -t helpdesk-be:prod ./helpdesk-be` | リポジトリ直下 |
| マイグレーション作成 | `poetry run alembic revision --autogenerate -m "内容"` | helpdesk-be |
| マイグレーション適用 | `poetry run alembic upgrade head` | helpdesk-be |
| FE の開発サーバー | `yarn dev` | helpdesk-fe |
| FE のビルド（型チェック含む） | `yarn build` | helpdesk-fe |
| FE のテスト | `yarn test` | helpdesk-fe |
| E2E テスト | `yarn test:e2e`（初回のみ `yarn playwright install chromium`） | helpdesk-fe |

## 参考資料

- `helpdesk_overview.md`：開発の前提と業務ルール（非公開。担当者から別途受領）
- `Novel HELPDESK - Sample.pdf`：画面のイメージ（非公開。担当者から別途受領）
