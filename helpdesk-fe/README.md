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
- BE の API は、ログインしていないとき、ログイン画面に移す（リダイレクトする）のではなく 401 を返します。ログイン画面に移すのは FE の役目です
- ログインなしで使える BE の API（今の時点）は、`/api/v1/health`・`/api/v1/health/db`（動作確認用）と `/api/v1/auth/login`・`/api/v1/auth/logout` です。API の説明画面（`/docs` など）は、`ENABLE_API_DOCS=true` のときだけ表示されます。最新の状態は BE のコードで確かめてください

### ページを追加するとき

- ページは `src/routes/routes.tsx` の `RequireAuth` の中（`children`）に追加してください。外に置くと、ログインしていなくても開けてしまいます
- route は `element` で書いてください（`Component`・`lazy` は使わない）。`loader`・`action`・`errorElement` なども使わないでください（ログインの確認より先に動いたり、確認の外で表示されたりするため）
- 画面の一覧は `routes.tsx` だけに書き、`router.ts` で route を足さないでください
- 存在しない URL（`*`）は、ほかのページに移すか、`RequireAuth` の中に置いてください
- `src/routes/routeGuard.test.tsx` が、`/login` 以外のすべてのページがログインの確認を通ることを確かめます。ログインなしで開けるページを増やすときは、理由を添えてテストの `PUBLIC_PATHS` に追加してください

### 本番で画面を配信するときの注意

- 画面を配信するサーバー（nginx など）は、どの URL を開いても `index.html` を返すように設定してください。設定しないと、`/tickets` などを直接開いたときに、ログイン画面ではなくサーバーの 404 が表示されます（開発サーバーの `yarn dev` は、この設定をしなくても動きます）
- 画面のプログラム（`dist/` の JS ファイル）は、ログインしていなくても読み込めます。秘密の情報（API キーなど）を FE のコードや `VITE_` で始まる環境変数に入れないでください
