# Backend の Linter / Formatter（Ruff）を実行するコマンド
# 使い方: helpdesk-be で `make lint` などを実行する（事前に `poetry install` が必要）

# 別の仮想環境が有効になっていても、このプロジェクトの仮想環境（helpdesk-be/.venv）を使う
unexport VIRTUAL_ENV

RUFF := poetry run ruff

.PHONY: help lint lint-fix format-check format-fix

help: ## コマンドの一覧を表示する
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-14s %s\n", $$1, $$2}'

lint: ## 問題を検出する（問題があればエラー終了）
	$(RUFF) check .

lint-fix: ## 自動で直せる問題を直す
	$(RUFF) check --fix .

format-check: ## 書式がそろっているか確認する（ずれがあればエラー終了）
	$(RUFF) format --check .

format-fix: ## 書式を自動でそろえる
	$(RUFF) format .
