"""開発用のテストユーザーを作る（開発環境専用）。

使い方: helpdesk-be で `make seed`
（事前に `poetry run alembic upgrade head` でテーブルを作っておく）

- 社員・サポート担当・管理者を 1 人ずつ作る。パスワードはすべて DEV_PASSWORD
- 同じメールアドレスのユーザーがすでにいれば、作らずに飛ばす（何度実行してもよい）
- 本番用の Docker イメージには、このフォルダ（scripts/）を含めていない
- .env の APP_ENV が development でなければ、何もせずに止まる
  （パスワードが公開されている管理者を、本番の DB に作ってしまわないため）
"""

import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.domain.password_policy import password_policy_errors
from app.domain.user_role import UserRole
from app.models.user import User
from app.services.auth import normalize_email

# 誰でも知っている値のため、開発環境以外では使わない
DEV_PASSWORD = "Password123"

DEV_USERS = [
    {"display_name": "Test.Employee", "email": "aaa@example.com", "role": UserRole.EMPLOYEE},
    {"display_name": "Test.Support", "email": "bbb@example.com", "role": UserRole.SUPPORT},
    {"display_name": "Test.Admin", "email": "ccc@example.com", "role": UserRole.ADMIN},
]


def main() -> None:
    # 接続先のホスト名では判断しない（本番でも DB のサービス名が db などになり得るため）。
    # .env で APP_ENV=development と明示したときだけ実行する
    if settings.app_env != "development":
        print(
            f"中止しました：APP_ENV が development ではありません（APP_ENV={settings.app_env}）。"
            "テストユーザーは開発環境でだけ作れます",
            file=sys.stderr,
        )
        sys.exit(1)
    # テストユーザーのパスワードも、パスワードの決まりに合わせる
    errors = password_policy_errors(DEV_PASSWORD)
    if errors:
        print(
            f"中止しました：DEV_PASSWORD が決まりに合っていません（{'、'.join(errors)}）",
            file=sys.stderr,
        )
        sys.exit(1)
    with SessionLocal() as db:
        for data in DEV_USERS:
            email = normalize_email(data["email"])
            if db.scalar(select(User).where(User.email == email)) is not None:
                print(f"skip   : {email}（作成済み）")
                continue
            db.add(
                User(
                    display_name=data["display_name"],
                    email=email,
                    password_hash=hash_password(DEV_PASSWORD),
                    role=data["role"],
                )
            )
            print(f"created: {email}（{data['role'].value}）")
        db.commit()
    print(f"パスワードはすべて {DEV_PASSWORD} です")


if __name__ == "__main__":
    main()
