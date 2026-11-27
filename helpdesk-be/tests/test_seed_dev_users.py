"""開発用テストユーザーの作成（make seed）のテスト。"""

import pytest

from app.core.config import Settings, settings
from app.domain.user_role import UserRole
from scripts import seed_dev_users


def test_app_env_is_production_by_default() -> None:
    """APP_ENV を設定し忘れても、本番（production）として扱う（安全な側が既定）こと。"""
    assert Settings.model_fields["app_env"].default == "production"


def test_seed_stops_unless_development(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """APP_ENV が development でなければ、DB に接続せずに止まること。"""
    monkeypatch.setattr(settings, "app_env", "production")

    def fail_if_called() -> None:
        raise AssertionError("DB に接続してはいけない")

    monkeypatch.setattr(seed_dev_users, "SessionLocal", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        seed_dev_users.main()

    print(capsys.readouterr().err)
    assert exc_info.value.code == 1


def test_seed_users_include_two_employees() -> None:
    """社員のテストユーザーが 2 人いること（他人の非公開チケットが見えないことを確かめるため）。"""
    employees = [u for u in seed_dev_users.DEV_USERS if u["role"] == UserRole.EMPLOYEE]

    assert len(employees) == 2
