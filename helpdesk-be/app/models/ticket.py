from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.ticket_status import TicketStatus
from app.models.user import User

# タイトル（要件）と詳細の長さの上限。入力の確認は、チケットを作る API で行う
TICKET_TITLE_MAX_LENGTH = 100
TICKET_DETAIL_MAX_LENGTH = 5000


class Ticket(Base):
    """1 件の問い合わせ（チケット）。"""

    __tablename__ = "tickets"
    __table_args__ = (
        # 一覧は質問日（作成日時）の新しい順に並べる
        Index("ix_tickets_created_at_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(TICKET_TITLE_MAX_LENGTH), comment="要件（タイトル）")
    # 上限（TICKET_DETAIL_MAX_LENGTH 文字）は API で確かめる。TEXT は 65,535 バイトまで入る
    detail: Mapped[str] = mapped_column(Text, comment="詳細")
    # False（非公開）のチケットは、起票者以外の社員には見せない
    is_public: Mapped[bool] = mapped_column(Boolean, comment="公開か（False は非公開）")
    status: Mapped[TicketStatus] = mapped_column(
        # DB には Enum の名前（NEW）ではなく値（new）で保存する
        Enum(TicketStatus, values_callable=lambda statuses: [s.value for s in statuses]),
        default=TicketStatus.NEW,
        comment="ステータス",
    )
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, comment="起票者（質問者）"
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, comment="担当者（サポート担当）。未割当は NULL"
    )
    # 秒未満（マイクロ秒）まで保存する（同じ秒に作られたチケットも、作られた順に並べるため）
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), server_default=func.now(6), comment="作成日時（質問日。UTC）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        server_default=func.now(6),
        onupdate=func.now(6),
        comment="更新日時（UTC）",
    )

    # lazy="raise"：読み込みの指定を忘れて、チケットごとに SQL を発行する（N+1）のを防ぐ
    requester: Mapped[User] = relationship(foreign_keys=[requester_id], lazy="raise")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="raise")
