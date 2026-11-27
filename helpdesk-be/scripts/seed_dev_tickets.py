"""開発用のテストチケットを作る（開発環境専用）。

使い方: helpdesk-be で `make seed`（テストユーザーを作ったあとに、続けて実行される）

- 架空のチケットを 10 件作る。公開・非公開、担当者あり・なし、5 つのステータスをすべて含める
- 質問者は社員のテストユーザー（2 人）、担当者はサポート担当のテストユーザー
- 質問日（作成日時）は、実行した日時から日数をさかのぼった日時にする（一覧の並び順を確かめるため）
- 同じ質問者・同じタイトルのチケットがすでにあれば、作らずに飛ばす（何度実行してもよい）
- .env の APP_ENV が development でなければ、何もせずに止まる
"""

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import SessionLocal
from app.domain.ticket_status import TicketStatus
from app.domain.user_role import UserRole
from app.models.ticket import Ticket
from app.models.user import User
from scripts.seed_dev_users import require_development

EMPLOYEE = "aaa@example.com"
EMPLOYEE2 = "ddd@example.com"
SUPPORT = "bbb@example.com"


@dataclass(frozen=True)
class DevTicket:
    title: str
    detail: str
    requester: str
    is_public: bool
    status: TicketStatus
    # 担当者（サポート担当）のメールアドレス。新規質問のときは None
    assignee: str | None
    # 何日前に作られたことにするか
    days_ago: int


DEV_TICKETS = [
    DevTicket(
        "社内ポータルにログインできない",
        "今朝から社内ポータルを開くと、ログインの画面に戻されてしまいます。",
        EMPLOYEE,
        True,
        TicketStatus.NEW,
        None,
        0,
    ),
    DevTicket(
        "共有フォルダの容量を増やしたい",
        "チームの共有フォルダの空きが少なくなってきたため、容量を増やしてほしいです。",
        EMPLOYEE,
        False,
        TicketStatus.ASSIGNED,
        SUPPORT,
        1,
    ),
    DevTicket(
        "メールの署名を変更したい",
        "部署が変わったので、メールの署名を変更する方法を教えてください。",
        EMPLOYEE2,
        True,
        TicketStatus.IN_PROGRESS,
        SUPPORT,
        2,
    ),
    DevTicket(
        "経費精算システムの操作方法を知りたい",
        "交通費の申請で、経路を入力する欄が見つかりません。",
        EMPLOYEE2,
        False,
        TicketStatus.NEW,
        None,
        3,
    ),
    DevTicket(
        "モニターをもう 1 台借りたい",
        "作業の効率を上げるため、モニターをもう 1 台貸し出してほしいです。",
        EMPLOYEE,
        True,
        TicketStatus.RESOLVED,
        SUPPORT,
        5,
    ),
    DevTicket(
        "勤怠システムの打刻が反映されない",
        "昨日の退勤の打刻が、勤怠の一覧に表示されていません。",
        EMPLOYEE2,
        True,
        TicketStatus.CLOSED,
        SUPPORT,
        7,
    ),
    DevTicket(
        "キーボードの一部のキーが反応しない",
        "貸与されたノートPCで、いくつかのキーを押しても入力されません。",
        EMPLOYEE,
        False,
        TicketStatus.IN_PROGRESS,
        SUPPORT,
        9,
    ),
    DevTicket(
        "社内チャットの通知音を消したい",
        "会議中に通知音が鳴ってしまうので、消す方法を知りたいです。",
        EMPLOYEE2,
        False,
        TicketStatus.ASSIGNED,
        SUPPORT,
        12,
    ),
    DevTicket(
        "ノートPCのバッテリーの減りが早い",
        "フル充電しても 2 時間ほどで残りが少なくなります。",
        EMPLOYEE,
        True,
        TicketStatus.CLOSED,
        SUPPORT,
        15,
    ),
    DevTicket(
        "新しいソフトのインストールを申請したい",
        "業務で使う画像編集ソフトをインストールしたいので、申請の方法を教えてください。",
        EMPLOYEE2,
        True,
        TicketStatus.NEW,
        None,
        20,
    ),
]


def main() -> None:
    require_development()
    now = datetime.now(UTC).replace(tzinfo=None)
    with SessionLocal() as db:
        users = {user.email: user for user in db.scalars(select(User))}
        missing = {EMPLOYEE, EMPLOYEE2, SUPPORT} - users.keys()
        if missing:
            print(
                f"中止しました：テストユーザーがいません（{'、'.join(sorted(missing))}）。"
                "先にテストユーザーを作ってください",
                file=sys.stderr,
            )
            sys.exit(1)
        # 質問者は社員、担当者はサポート担当（DB のロールが手で変えられていたら、業務の決まりに
        # 合わないチケットを作ってしまうため止める）
        expected_roles = {
            EMPLOYEE: UserRole.EMPLOYEE,
            EMPLOYEE2: UserRole.EMPLOYEE,
            SUPPORT: UserRole.SUPPORT,
        }
        wrong = [email for email, role in expected_roles.items() if users[email].role != role]
        if wrong:
            print(
                f"中止しました：テストユーザーのロールが想定と違います（{'、'.join(sorted(wrong))}）",
                file=sys.stderr,
            )
            sys.exit(1)
        for data in DEV_TICKETS:
            requester = users[data.requester]
            exists = db.scalar(
                select(Ticket.id).where(
                    Ticket.requester_id == requester.id, Ticket.title == data.title
                )
            )
            if exists is not None:
                print(f"skip   : {data.title}（作成済み）")
                continue
            db.add(
                Ticket(
                    title=data.title,
                    detail=data.detail,
                    is_public=data.is_public,
                    status=data.status,
                    requester_id=requester.id,
                    assignee_id=users[data.assignee].id if data.assignee else None,
                    created_at=now - timedelta(days=data.days_ago),
                )
            )
            print(f"created: {data.title}（{data.status.value}）")
        db.commit()


if __name__ == "__main__":
    main()
