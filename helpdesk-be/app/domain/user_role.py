from enum import StrEnum


class UserRole(StrEnum):
    """アカウントタイプ（ロール）。DB と API にはこの値（英字）で保存・返却する。"""

    EMPLOYEE = "employee"  # 社員
    SUPPORT = "support"  # サポート担当
    ADMIN = "admin"  # 管理者
