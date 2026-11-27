"""チケット一覧の API（GET /api/v1/tickets）のテスト。"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.deps import access_token_cookie_name
from app.core.security import create_access_token
from app.domain.ticket_status import TicketStatus
from app.domain.user_role import UserRole
from app.models.ticket import Ticket
from app.models.user import User

TICKETS_URL = "/api/v1/tickets"
BASE_TIME = datetime(2026, 3, 2, 9, 0, 0)


def add_user(db: Session, name: str, email: str, role: UserRole, *, active: bool = True) -> User:
    user = User(
        display_name=name,
        email=email,
        # このテストではパスワードでログインしない（トークンを直接作る）
        password_hash="not-used",
        role=role,
        is_active=active,
    )
    db.add(user)
    db.flush()
    return user


def add_ticket(
    db: Session,
    title: str,
    requester: User,
    *,
    is_public: bool = True,
    status: TicketStatus = TicketStatus.NEW,
    assignee: User | None = None,
    created_at: datetime = BASE_TIME,
) -> Ticket:
    ticket = Ticket(
        title=title,
        detail=f"{title}の詳細",
        is_public=is_public,
        status=status,
        requester_id=requester.id,
        assignee_id=assignee.id if assignee else None,
        created_at=created_at,
    )
    db.add(ticket)
    db.flush()
    return ticket


def login_as(client: TestClient, user: User) -> None:
    """パスワードの照合を飛ばし、ログインの Cookie を直接付ける。"""
    client.cookies.set(access_token_cookie_name(), create_access_token(user.id, user.token_version))


def titles(client: TestClient) -> list[str]:
    response = client.get(TICKETS_URL)
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


@pytest.fixture
def employee(db_session: Session) -> User:
    return add_user(db_session, "Test.Employee", "aaa@example.com", UserRole.EMPLOYEE)


@pytest.fixture
def other_employee(db_session: Session) -> User:
    return add_user(db_session, "Test.Employee2", "ddd@example.com", UserRole.EMPLOYEE)


@pytest.fixture
def support(db_session: Session) -> User:
    return add_user(db_session, "Test.Support", "bbb@example.com", UserRole.SUPPORT)


@pytest.fixture
def admin(db_session: Session) -> User:
    return add_user(db_session, "Test.Admin", "ccc@example.com", UserRole.ADMIN)


@pytest.fixture
def tickets(db_session: Session, employee: User, other_employee: User) -> None:
    """自分（employee）と他人（other_employee）の、公開・非公開のチケット。"""
    add_ticket(db_session, "自分の公開", employee, is_public=True, created_at=BASE_TIME)
    add_ticket(
        db_session,
        "自分の非公開",
        employee,
        is_public=False,
        created_at=BASE_TIME + timedelta(hours=1),
    )
    add_ticket(
        db_session,
        "他人の公開",
        other_employee,
        is_public=True,
        created_at=BASE_TIME + timedelta(hours=2),
    )
    add_ticket(
        db_session,
        "他人の非公開",
        other_employee,
        is_public=False,
        created_at=BASE_TIME + timedelta(hours=3),
    )


def test_list_requires_login(client: TestClient, tickets: None) -> None:
    """ログインしていなければ 401 を返し、チケットを返さないこと。"""
    response = client.get(TICKETS_URL)

    assert response.status_code == 401
    assert "items" not in response.json()


def test_employee_sees_own_and_public_tickets_only(
    client: TestClient, employee: User, tickets: None
) -> None:
    """社員には、自分のチケット（公開・非公開）と、他人の公開チケットだけを返すこと。

    自分が質問者でない かつ 非公開 のチケットは返さない。
    """
    login_as(client, employee)

    assert titles(client) == ["他人の公開", "自分の非公開", "自分の公開"]


def test_other_employee_cannot_see_my_private_ticket(
    client: TestClient, other_employee: User, tickets: None
) -> None:
    """別の社員から見ると、こちらの非公開チケットは返らないこと（立場を入れ替えても同じ）。"""
    login_as(client, other_employee)

    assert titles(client) == ["他人の非公開", "他人の公開", "自分の公開"]


@pytest.mark.parametrize("role_fixture", ["support", "admin"])
def test_support_and_admin_see_all_tickets(
    client: TestClient, request: pytest.FixtureRequest, role_fixture: str, tickets: None
) -> None:
    """サポート担当と管理者には、非公開を含めてすべてのチケットを返すこと。"""
    login_as(client, request.getfixturevalue(role_fixture))

    assert titles(client) == ["他人の非公開", "他人の公開", "自分の非公開", "自分の公開"]


def test_tickets_are_sorted_newest_first(
    client: TestClient, db_session: Session, employee: User
) -> None:
    """質問日（作成日時）の新しい順に返すこと。同じ日時なら、あとから作ったものを先にすること。"""
    add_ticket(db_session, "3 日前", employee, created_at=BASE_TIME - timedelta(days=3))
    add_ticket(db_session, "同じ日時（先に作成）", employee, created_at=BASE_TIME)
    add_ticket(db_session, "1 日後", employee, created_at=BASE_TIME + timedelta(days=1))
    add_ticket(db_session, "同じ日時（あとに作成）", employee, created_at=BASE_TIME)
    # 秒未満まで比べる（同じ秒の中でも、新しいものを先にする）
    add_ticket(
        db_session, "0.5 秒後", employee, created_at=BASE_TIME + timedelta(microseconds=500_000)
    )
    login_as(client, employee)

    assert titles(client) == [
        "1 日後",
        "0.5 秒後",
        "同じ日時（あとに作成）",
        "同じ日時（先に作成）",
        "3 日前",
    ]


def test_list_item_contains_only_list_fields(
    client: TestClient, db_session: Session, employee: User, support: User
) -> None:
    """一覧の項目（質問日・タイトル・公開状況・ステータス・質問者名・担当者名）を返すこと。

    詳細の本文やメールアドレスなど、一覧に不要な情報は返さない。質問日は UTC であることを明示する。
    """
    ticket = add_ticket(
        db_session,
        "一覧の項目",
        employee,
        is_public=False,
        status=TicketStatus.IN_PROGRESS,
        assignee=support,
        created_at=datetime(2026, 3, 2, 15, 30, 0, 123456),
    )
    login_as(client, employee)

    response = client.get(TICKETS_URL)

    print(f"\n一覧の応答: {response.json()}")
    assert response.json() == {
        "items": [
            {
                "id": ticket.id,
                "title": "一覧の項目",
                "is_public": False,
                "status": "in_progress",
                "created_at": "2026-03-02T15:30:00.123456Z",
                "requester_name": "Test.Employee",
                "assignee_name": "Test.Support",
            }
        ]
    }
    assert "aaa@example.com" not in response.text
    assert "の詳細" not in response.text


def test_unassigned_ticket_has_null_assignee(
    client: TestClient, db_session: Session, employee: User
) -> None:
    """担当者がいないチケットは、担当者名を null で返すこと。"""
    add_ticket(db_session, "未割当", employee, status=TicketStatus.NEW)
    login_as(client, employee)

    item = client.get(TICKETS_URL).json()["items"][0]

    assert item["assignee_name"] is None
    assert item["status"] == "new"


@pytest.mark.parametrize("status", list(TicketStatus))
def test_all_statuses_are_returned(
    client: TestClient, db_session: Session, employee: User, status: TicketStatus
) -> None:
    """5 つのステータスを、それぞれ英字の値で返すこと。"""
    add_ticket(db_session, "ステータス", employee, status=status)
    login_as(client, employee)

    assert client.get(TICKETS_URL).json()["items"][0]["status"] == status.value


def test_tickets_of_inactive_users_are_listed(
    client: TestClient, db_session: Session, admin: User
) -> None:
    """質問者や担当者が利用停止になっても、チケットと表示名はそのまま返すこと。"""
    inactive_employee = add_user(
        db_session, "Test.Retired", "eee@example.com", UserRole.EMPLOYEE, active=False
    )
    inactive_support = add_user(
        db_session, "Test.RetiredSupport", "fff@example.com", UserRole.SUPPORT, active=False
    )
    add_ticket(
        db_session,
        "利用停止のユーザー",
        inactive_employee,
        status=TicketStatus.ASSIGNED,
        assignee=inactive_support,
    )
    login_as(client, admin)

    item = client.get(TICKETS_URL).json()["items"][0]

    assert item["requester_name"] == "Test.Retired"
    assert item["assignee_name"] == "Test.RetiredSupport"


def test_empty_list(client: TestClient, employee: User) -> None:
    """チケットがなければ、空の一覧を返すこと。"""
    login_as(client, employee)

    assert client.get(TICKETS_URL).json() == {"items": []}


def test_list_response_is_not_cached(client: TestClient, employee: User) -> None:
    """チケットの情報を含む応答を、ブラウザなどに保存させないこと。"""
    login_as(client, employee)

    response = client.get(TICKETS_URL)

    assert response.headers["Cache-Control"] == "no-store"


def test_list_query_count_does_not_grow_with_tickets(
    client: TestClient, db_session: Session, employee: User, support: User
) -> None:
    """チケットの数が増えても、SQL の数が増えないこと。

    チケットごとに質問者・担当者を読み込まない（N+1 にならない）。
    """
    statements: list[str] = []

    def count(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    login_as(client, employee)
    add_ticket(db_session, "1 件目", employee, assignee=support, status=TicketStatus.ASSIGNED)
    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        client.get(TICKETS_URL)
        with_one = len(statements)
        for i in range(5):
            add_ticket(
                db_session, f"追加 {i}", employee, assignee=support, status=TicketStatus.ASSIGNED
            )
        statements.clear()
        client.get(TICKETS_URL)
        with_six = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count)

    print(f"\nSELECT の数: 1 件のとき {with_one}、6 件のとき {with_six}")
    assert with_six == with_one


def test_created_at_always_has_microseconds(
    client: TestClient, db_session: Session, employee: User
) -> None:
    """秒未満がちょうど 0 の質問日も、桁数をそろえて UTC で返すこと（いつも同じ形にする）。"""
    add_ticket(db_session, "秒未満が 0", employee, created_at=datetime(2026, 3, 2, 9, 0, 0))
    login_as(client, employee)

    returned = client.get(TICKETS_URL).json()["items"][0]["created_at"]

    assert returned == "2026-03-02T09:00:00.000000Z"
