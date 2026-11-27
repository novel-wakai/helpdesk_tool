from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ticket import TicketListItem, TicketListResponse
from app.services.ticket import list_visible_tickets


def no_store(response: Response) -> None:
    """チケットの情報を含む応答を、ブラウザや途中の経路に保存させない。"""
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(no_store)])


@router.get("", response_model=TicketListResponse)
def list_tickets(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TicketListResponse:
    """チケットの一覧を、質問日の新しい順に返す。ログインが必要。

    社員には、自分が起票したチケットと公開のチケットだけを返す（サポート担当・管理者にはすべて）。
    """
    tickets = list_visible_tickets(db, current_user)
    return TicketListResponse(items=[TicketListItem.from_ticket(ticket) for ticket in tickets])
