from sqlalchemy import ColumnElement, or_, select, true
from sqlalchemy.orm import Session, joinedload

from app.domain.user_role import UserRole
from app.models.ticket import Ticket
from app.models.user import User

# 非公開を含めて、すべてのチケットを見られるロール
ROLES_THAT_SEE_ALL_TICKETS = frozenset({UserRole.SUPPORT, UserRole.ADMIN})


def visible_ticket_condition(user: User) -> ColumnElement[bool]:
    """ユーザーが見てよいチケットの条件（SQL の WHERE）。

    - サポート担当・管理者：すべてのチケット
    - それ以外（社員）：自分が起票したチケットと、公開のチケット
      （他人の非公開チケットは、一覧にも出さない）
    ロールが増えたときに見えすぎないよう、すべてを見せるロールを列挙し、それ以外は社員と同じにする。
    """
    if user.role in ROLES_THAT_SEE_ALL_TICKETS:
        return true()
    return or_(Ticket.requester_id == user.id, Ticket.is_public.is_(True))


def list_visible_tickets(db: Session, user: User) -> list[Ticket]:
    """ユーザーが見てよいチケットを、質問日（作成日時）の新しい順に返す。

    同じ日時のチケットは、あとから作ったもの（ID の大きいもの）を先にする
    （並びを毎回同じにするため）。
    質問者と担当者は、まとめて読み込む（チケットごとに SQL を発行しない）。
    """
    statement = (
        select(Ticket)
        .where(visible_ticket_condition(user))
        .options(joinedload(Ticket.requester), joinedload(Ticket.assignee))
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
    )
    return list(db.scalars(statement))
