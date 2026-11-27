from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.networks import validate_email

from app.domain.password_policy import PASSWORD_MAX_LENGTH
from app.domain.user_role import UserRole


class LoginRequest(BaseModel):
    # メールアドレスは小文字にそろえて照合する（大文字・小文字を区別しない）
    email: str = Field(max_length=255)
    # パスワードの決まりの上限（20 文字）を超えるものは、照合せずに 422 にする
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def check_email_format(cls, value: str) -> str:
        # 形式が正しくなければ 422 にする
        _, normalized = validate_email(value)
        # validate_email は「名前 <アドレス>」の形や前後の空白も受け付けて、アドレスだけを取り出す。
        # 取り出したアドレスと入力が（大文字・小文字以外で）違うものは、メールアドレスとして扱わない
        if normalized.lower() != value.lower():
            raise ValueError("メールアドレスだけを入力してください")
        # 保存しているメールアドレスと同じく、小文字にそろえる
        return value.lower()


class UserResponse(BaseModel):
    """ログイン中のユーザーの情報（パスワードのハッシュなどは含めない）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    email: str
    role: UserRole
