"""開発用テストチケットの作成（make seed）のテスト。"""

from contextlib import nullcontext

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.ticket_status import TicketStatus
from app.domain.user_role import UserRole
from app.models.ticket import TICKET_DETAIL_MAX_LENGTH, TICKET_TITLE_MAX_LENGTH, Ticket
from app.models.user import User
from scripts import seed_dev_tickets
from scripts.seed_dev_tickets import DEV_TICKETS
from scripts.seed_dev_users import DEV_USERS

ROLES = {user["email"]: user["role"] for user in DEV_USERS}


def test_seed_stops_unless_development(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """APP_ENV が development でなければ、DB に接続せずに止まること。"""
    monkeypatch.setattr(settings, "app_env", "production")

    def fail_if_called() -> None:
        raise AssertionError("DB に接続してはいけない")

    monkeypatch.setattr(seed_dev_tickets, "SessionLocal", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        seed_dev_tickets.main()

    print(capsys.readouterr().err)
    assert exc_info.value.code == 1


def test_dev_tickets_cover_all_cases() -> None:
    """一覧を確かめるのに必要な組み合わせを含むこと。

    5 つのステータス、公開・非公開、担当者あり・なし。
    """
    assert {t.status for t in DEV_TICKETS} == set(TicketStatus)
    assert {t.is_public for t in DEV_TICKETS} == {True, False}
    assert {t.assignee is None for t in DEV_TICKETS} == {True, False}
    # 社員それぞれに非公開のチケットがある（もう 1 人の社員から見えないことを確かめられる）
    private_requesters = {t.requester for t in DEV_TICKETS if not t.is_public}
    employees = {email for email, role in ROLES.items() if role == UserRole.EMPLOYEE}
    assert private_requesters == employees


def test_dev_tickets_follow_business_rules() -> None:
    """質問者は社員、担当者はサポート担当で、新規質問のときだけ担当者がいないこと。長さは上限以内。"""
    for ticket in DEV_TICKETS:
        assert ROLES[ticket.requester] == UserRole.EMPLOYEE, ticket.title
        if ticket.status == TicketStatus.NEW:
            assert ticket.assignee is None, ticket.title
        else:
            assert ticket.assignee is not None, ticket.title
            assert ROLES[ticket.assignee] == UserRole.SUPPORT, ticket.title
        assert 0 < len(ticket.title) <= TICKET_TITLE_MAX_LENGTH
        assert 0 < len(ticket.detail) <= TICKET_DETAIL_MAX_LENGTH


def test_dev_tickets_have_unique_titles_per_requester() -> None:
    """同じ質問者・同じタイトルのチケットがないこと（作成済みかどうかを、この組で見分けるため）。"""
    keys = [(t.requester, t.title) for t in DEV_TICKETS]

    assert len(keys) == len(set(keys))


@pytest.fixture
def seed_db(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> Session:
    """シードを、開発用 DB ではなくテスト用 DB（テストの終わりに元に戻る）に向ける。"""
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(seed_dev_tickets, "SessionLocal", lambda: nullcontext(db_session))
    for user in DEV_USERS:
        db_session.add(
            User(
                display_name=user["display_name"],
                email=user["email"],
                password_hash="not-used",
                role=user["role"],
            )
        )
    db_session.flush()
    return db_session


def test_seed_creates_tickets_once(seed_db: Session) -> None:
    """テストチケットを作り、2 回目は増やさないこと（何度実行してもよい）。"""
    seed_dev_tickets.main()
    seed_dev_tickets.main()

    count = seed_db.scalar(select(func.count()).select_from(Ticket))
    assert count == len(DEV_TICKETS)


def test_seed_stops_when_user_role_is_unexpected(
    seed_db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    """テストユーザーのロールが想定と違えば、チケットを作らずに止まること。"""
    support = seed_db.scalar(select(User).where(User.email == "bbb@example.com"))
    assert support is not None
    support.role = UserRole.EMPLOYEE
    seed_db.flush()

    with pytest.raises(SystemExit) as exc_info:
        seed_dev_tickets.main()

    print(capsys.readouterr().err)
    assert exc_info.value.code == 1
    assert seed_db.scalar(select(func.count()).select_from(Ticket)) == 0
