from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoginAttempt(Base):
    """ログインの試行の記録（総当たり攻撃の対策）。

    登録されていないメールアドレスも、登録済みのものと同じように記録する。
    片方だけ記録すると、応答にかかる時間の差やロックの有無から、
    「このメールアドレスは登録されている」と推測されてしまうため。
    ログインに成功すると、そのメールアドレスの行を消す。
    """

    __tablename__ = "login_attempts"

    # 入力されたメールアドレス（小文字にそろえたもの）
    email: Mapped[str] = mapped_column(String(255), primary_key=True, comment="メールアドレス")
    # 照合の前に数える（同時に来たリクエストが、ロックの確認をすり抜けないように）
    failed_count: Mapped[int] = mapped_column(Integer, comment="数え始めてからの試行の回数")
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime, comment="数え始めた日時（UTC）。ここから一定時間で回数を数え直す"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime, comment="この日時（UTC）まではログインできない"
    )
