from datetime import UTC, datetime

from pydantic import BaseModel, field_serializer

from app.domain.ticket_status import TicketStatus
from app.models.ticket import Ticket


class TicketListItem(BaseModel):
    """チケット一覧の 1 行。

    一覧に表示する項目だけを返す（詳細の本文やメールアドレスは含めない）。
    """

    id: int
    title: str
    is_public: bool
    status: TicketStatus
    # 質問日（作成日時）。UTC で返し、画面で日本時間に変える
    created_at: datetime
    requester_name: str
    # 担当者がいないときは null
    assignee_name: str | None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        # DB の日時はタイムゾーンを持たない（UTC で保存している）ため、
        # UTC であることを明示して返す。
        # 秒未満がちょうど 0 のときも、桁数をそろえる（いつも同じ形で返す）
        return value.replace(tzinfo=UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    @classmethod
    def from_ticket(cls, ticket: Ticket) -> "TicketListItem":
        return cls(
            id=ticket.id,
            title=ticket.title,
            is_public=ticket.is_public,
            status=ticket.status,
            created_at=ticket.created_at,
            requester_name=ticket.requester.display_name,
            assignee_name=ticket.assignee.display_name if ticket.assignee else None,
        )


class TicketListResponse(BaseModel):
    """チケット一覧。あとからページ分けや件数を足せるよう、配列をそのまま返さずに包む。"""

    items: list[TicketListItem]
