from enum import StrEnum


class TicketStatus(StrEnum):
    """チケットのステータス。

    DB と API にはこの値（英字）で保存・返却し、画面で日本語の表記に変える。
    """

    NEW = "new"  # 新規質問
    ASSIGNED = "assigned"  # 担当者割り当て済み
    IN_PROGRESS = "in_progress"  # 対応中
    RESOLVED = "resolved"  # 解決済み
    CLOSED = "closed"  # クローズ
