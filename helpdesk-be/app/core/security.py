"""パスワードのハッシュ化と、ログイン用トークン（JWT）の発行・検証。"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

JWT_ALGORITHM = "HS256"

# 推奨設定（Argon2）でハッシュ化する
password_hash = PasswordHash.recommended()

# 照合の順番待ちをする最大の秒数。これを超えたら「混み合っている」として断る
PASSWORD_HASH_WAIT_SECONDS = 5

# 同時に行うパスワードの照合の数を制限する（Argon2 は 1 回で約 64MB のメモリを使うため）
_password_hash_slots = threading.BoundedSemaphore(settings.password_hash_concurrency)


class PasswordHashBusyError(Exception):
    """パスワードの照合が混み合っていて、順番が回ってこなかった。"""


@contextmanager
def _password_hash_slot() -> Iterator[None]:
    if not _password_hash_slots.acquire(timeout=PASSWORD_HASH_WAIT_SECONDS):
        raise PasswordHashBusyError
    try:
        yield
    finally:
        _password_hash_slots.release()


def hash_password(password: str) -> str:
    with _password_hash_slot():
        return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    with _password_hash_slot():
        return password_hash.verify(password, hashed)


def verify_and_update_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """パスワードを照合する。ハッシュの設定が古ければ、新しい設定で作り直したハッシュも返す。"""
    with _password_hash_slot():
        return password_hash.verify_and_update(password, hashed)


# 登録されていないメールアドレスなどでも、パスワードの照合と同じだけ時間をかけるためのダミー。
# 照合を省くと応答が速くなり、その差から「登録されているメールアドレスか」を推測されてしまう
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: int
    # 発行したときのユーザーの世代番号（users.token_version）。
    # ログアウトなどで世代番号が上がると、それより前に発行したトークンは使えなくなる
    token_version: int


def create_access_token(user_id: int, token_version: int) -> str:
    """ユーザー ID と世代番号を入れた JWT を発行する。有効期限は settings.jwt_expire_minutes。"""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessTokenPayload | None:
    """JWT を検証して中身を返す。改ざん・期限切れ・形式の誤りのときは None。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "ver", "exp"]},
        )
        token_version = payload["ver"]
        # bool は int の一種として扱われるため、true / false も明示的に拒否する
        if isinstance(token_version, bool) or not isinstance(token_version, int):
            return None
        return AccessTokenPayload(user_id=int(payload["sub"]), token_version=token_version)
    except (jwt.InvalidTokenError, ValueError):
        return None
