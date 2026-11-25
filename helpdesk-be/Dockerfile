# マルチステージビルド
#   dev  : 開発用。本番用パッケージ＋開発用パッケージ（pytest など）。コード変更で自動再起動
#   prod : 本番用。本番用パッケージのみ。Poetry もテストも含めず、root 以外のユーザーで動かす
#
#   開発: docker compose up（docker-compose.yml で target: dev を指定済み）
#   本番: docker build --target prod -t helpdesk-be:prod ./helpdesk-be

# ---------- 共通の土台 ----------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---------- 本番用パッケージを仮想環境に入れる ----------
FROM base AS builder

ENV POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry>=2,<3"

# 仮想環境は /app の外に置く（開発時に /app をホストのフォルダで上書きしても消えないように）
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# ---------- 開発用 ----------
FROM builder AS dev

# 開発用パッケージ（pytest など）を追加する
RUN poetry install --no-root

COPY . .

EXPOSE 8000

# コード変更を検知して自動で再起動する（--reload）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- 本番用 ----------
FROM base AS prod

# builder で作った本番用パッケージだけの仮想環境をコピーする（Poetry 自体は持ち込まない）
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# アプリの実行に必要なものだけをコピーする（テストは含めない）
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# root 以外のユーザーで動かす
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
