# helpdesk-fe

Novel HELPDESK のフロントエンド（React 19 + Vite + TypeScript）。

セットアップとコマンドはリポジトリ直下の [README.md](../README.md) を参照してください。

## ディレクトリ構成

```
src/
├── api/        # Axios の設定と API 呼び出し、React Query の設定
├── hooks/      # React Query のフック
├── routes/     # ルーティングと、ログインの確認（ログインしていなければログイン画面へ）
├── components/ # 画面をまたいで使う部品（ログイン後の共通の枠など）
├── features/   # 機能ごとのまとまり（containers / presentational）
└── test/       # テスト用のセットアップとヘルパー
e2e/            # Playwright の E2E テスト
```

## 画面とログイン

| URL                  | 画面          | ログインしていないとき                     |
| -------------------- | ------------- | ------------------------------------------ |
| `/login`             | ログイン      | 表示する（ログイン済みなら `/tickets` へ） |
| `/tickets`           | チケット一覧  | `/login` へ                                |
| `/` とそのほかの URL | `/tickets` へ | `/login` へ                                |

- ログインの状態は、BE が保存する Cookie（HttpOnly。JavaScript からは読めない）で保たれます。画面を開いたときは `GET /auth/me` でログイン中かを確かめます
- どの API でも 401 が返ったら（ログインが切れたなど）、ログイン画面に移ります
- 画面を隠すのは使いやすさのためで、データを守るのは BE の権限の確認です
