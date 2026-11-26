from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.user_role import UserRole


class User(Base):
    """ログインする利用者（社員・サポート担当・管理者）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(100), comment="表示名")
    # 小文字にそろえて保存する（ログインでも小文字にそろえて照合し、大文字・小文字を区別しない）
    email: Mapped[str] = mapped_column(String(255), unique=True, comment="メールアドレス")
    # パスワードそのものは保存せず、ハッシュ（元に戻せない形に変換した値）だけを保存する
    password_hash: Mapped[str] = mapped_column(String(255), comment="パスワードのハッシュ")
    role: Mapped[UserRole] = mapped_column(
        # DB には Enum の名前（EMPLOYEE）ではなく値（employee）で保存する
        Enum(UserRole, values_callable=lambda roles: [role.value for role in roles]),
        comment="アカウントタイプ",
    )
    # False（利用停止）のユーザーはログインできない
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("1"), comment="利用中か（False は利用停止）"
    )
    # トークンの世代番号。ログアウトすると 1 つ上がり、それより前に発行したトークンは使えなくなる
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), comment="トークンの世代番号"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="作成日時"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新日時"
    )
