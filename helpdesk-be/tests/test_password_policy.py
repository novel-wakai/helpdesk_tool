"""パスワードの決まり（8〜20 文字、数字と大文字を必ず含む）のテスト。"""

import pytest

from app.domain.password_policy import password_policy_errors
from scripts.seed_dev_users import DEV_PASSWORD


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("Password1", id="basic"),
        pytest.param("Abcdef12", id="8-chars"),
        pytest.param("Abcdefghij1234567890", id="20-chars"),
        pytest.param("Pass word!1", id="with-symbols-and-space"),
    ],
)
def test_valid_passwords(password: str) -> None:
    assert password_policy_errors(password) == []


@pytest.mark.parametrize(
    ("password", "message"),
    [
        pytest.param("Abcde12", "8 文字以上", id="7-chars"),
        pytest.param("Abcdefghij12345678901", "20 文字以下", id="21-chars"),
        pytest.param("Password", "数字", id="no-digit"),
        pytest.param("password1", "大文字", id="no-uppercase"),
        pytest.param("passwordＡ1", "大文字", id="fullwidth-uppercase-not-counted"),
        pytest.param("Password１", "数字", id="fullwidth-digit-not-counted"),
    ],
)
def test_invalid_passwords(password: str, message: str) -> None:
    errors = password_policy_errors(password)

    print(f"\n{password!r}: {errors}")
    assert any(message in error for error in errors)


def test_dev_password_follows_policy() -> None:
    """make seed のテストユーザーのパスワードも、決まりに合っていること。"""
    assert password_policy_errors(DEV_PASSWORD) == []
