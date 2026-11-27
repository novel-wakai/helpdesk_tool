from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoginAttempt(Base):
    """ログインの試行の記録（総当たり攻撃の対策）。

    登録されていないメールアドレスも、登録済みのものと同じように記録する。
    片方だけ記録すると、応答にかかる時間の差やロックの有無から、
    「このメールアドレスは登録されている」と推測されてしまうため。
    ログインに成功すると、そのメールアドレスの行を消す（予約したときと同じ数え始めの行のとき）。
    """

    __tablename__ = "login_attempts"

    # 入力されたメールアドレス（小文字にそろえたもの）
    email: Mapped[str] = mapped_column(String(255), primary_key=True, comment="メールアドレス")
    # ロックの判定に使う。照合しなかった試行（ロック中・混み合いで断ったもの）は数えない
    failed_count: Mapped[int] = mapped_column(
        Integer, comment="数え始めてから、照合して失敗した回数"
    )
    # 照合の前に 1 足す（同時に来たリクエストが、失敗した数と照合中の数の合計で上限を確かめ、
    # 上限を超えて照合に進まないように）。照合して失敗したとき・照合できずに断ったとき（503 や
    # 照合中のエラー）に 1 引き、成功したときは行ごと消す。数え始めが変わっていれば何もしない
    pending_count: Mapped[int] = mapped_column(Integer, default=0, comment="照合中の試行の数")
    # 秒未満（マイクロ秒）まで保存する。照合のあとに記録するとき（失敗・成功・照合できずに
    # 断ったとき）、予約したときと同じ数え始めかどうかを、この値で見分けるため
    # （秒単位だと、同じ秒の中の数え直しを見分けられない）
    first_failed_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), comment="数え始めた日時（UTC）。ここから一定時間で回数を数え直す"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime, comment="この日時（UTC）まではログインできない"
    )
