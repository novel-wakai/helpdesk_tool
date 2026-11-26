import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import DUMMY_PASSWORD_HASH, verify_and_update_password, verify_password
from app.models.login_attempt import LoginAttempt
from app.models.user import User

# ログインの失敗やロックを記録する（攻撃に気づけるように）。パスワードは記録しない
logger = logging.getLogger("app.auth")

# MySQL のデッドロック（ほかのリクエストと行の鍵を取り合った）のエラー番号
MYSQL_DEADLOCK = 1213
# デッドロックが起きたときに、やり直す回数
RESERVE_RETRIES = 3


def normalize_email(email: str) -> str:
    """保存するメールアドレスを、前後の空白を除いた小文字にそろえる。

    メールアドレスはすべて小文字で保存する。ログインでも入力を小文字にそろえて照合するため、
    大文字・小文字を区別しない（AAA@Example.COM でも aaa@example.com としてログインできる）。
    """
    return email.strip().lower()


def utc_now() -> datetime:
    """現在の日時（UTC）。DB の DATETIME はタイムゾーンを持たないため、タイムゾーンなしで扱う。"""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class _Reservation:
    """照合の前に行う「試行の予約」の結果。"""

    allowed: bool  # 照合してよいか（False はロック中、または試行の上限を使い切った）
    count: int  # この試行を含めた、数え始めてからの試行の回数
    reason: str  # 照合してはいけない理由（ログ用）


def authenticate(
    db: Session, email: str, password: str, client_ip: str | None = None
) -> User | None:
    """メールアドレスとパスワードを照合し、ログインしてよいユーザーを返す。

    email は小文字にそろえたもの（LoginRequest で変換済み）を受け取る。

    次の場合はすべて None を返す（呼び出し側で区別できないようにするため、理由は返さない）。
    - 続けて失敗したため、一時的にログインできない（ロック中）
    - メールアドレスが登録されていない
    - パスワードが間違っている
    - 利用停止中のユーザー

    処理は 3 段階に分ける。
    1. 予約：照合の前に、この試行を 1 回として数える（行に鍵をかけて数えるため、同時に来た
       リクエストも上限を超えて照合に進めない）。ユーザーもここで読み込み、DB の接続を手放す
    2. 照合：DB の接続を持たずに行う（照合の順番待ちの間、接続を使い切らないように）
    3. 記録：成功なら記録を消し、失敗で上限に達していればロックする

    未登録のメールアドレスも同じように数えてロックするため、処理の中身（DB への書き込み・
    照合の回数）が登録の有無で変わらず、応答の時間から登録済みかを推測されない。
    """
    now = utc_now()
    reservation = _reserve_attempt(db, email, now)
    if not reservation.allowed:
        db.commit()
        logger.warning("login rejected (%s): email=%s ip=%s", reservation.reason, email, client_ip)
        return None

    user = db.scalar(select(User).where(User.email == email))
    # 照合の前にトランザクションを終え、DB の接続をプールに返す
    db.commit()

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        _finish_failed_attempt(db, email, now, reservation, client_ip, "unknown email")
        return None

    valid, updated_hash = verify_and_update_password(password, user.password_hash)
    if not valid:
        _finish_failed_attempt(db, email, now, reservation, client_ip, "wrong password")
        return None
    if not user.is_active:
        _finish_failed_attempt(db, email, now, reservation, client_ip, "inactive user")
        return None

    # ログインに成功したら、試行の記録を消す
    db.execute(delete(LoginAttempt).where(LoginAttempt.email == email))
    # ハッシュの設定が新しくなっていれば、新しい設定のハッシュに保存し直す
    if updated_hash is not None:
        db.execute(update(User).where(User.id == user.id).values(password_hash=updated_hash))
        user.password_hash = updated_hash
    db.commit()
    return user


def _reserve_attempt(db: Session, email: str, now: datetime) -> _Reservation:
    """この試行を 1 回として数え、照合してよいかを決める（デッドロックならやり直す）。"""
    for retry in range(RESERVE_RETRIES):
        try:
            return _reserve_attempt_once(db, email, now)
        except OperationalError as error:
            db.rollback()
            if error.orig is None or error.orig.args[0] != MYSQL_DEADLOCK:
                raise
            if retry == RESERVE_RETRIES - 1:
                raise
            logger.info("login reserve deadlock, retrying: email=%s", email)
    raise AssertionError("unreachable")


def _reserve_attempt_once(db: Session, email: str, now: datetime) -> _Reservation:
    # 行がなければ作る。あれば何も変えないが、行に鍵（排他ロック）をかける。
    # 同じメールアドレスへの同時のリクエストは、ここで 1 つずつ順番に処理される
    db.execute(
        insert(LoginAttempt)
        .values(email=email, failed_count=0, first_failed_at=now)
        .on_duplicate_key_update(email=LoginAttempt.email)
    )
    attempt = db.execute(
        select(LoginAttempt).where(LoginAttempt.email == email).with_for_update()
    ).scalar_one()
    db.refresh(attempt)

    if attempt.locked_until is not None and attempt.locked_until > now:
        return _Reservation(allowed=False, count=attempt.failed_count, reason="locked")

    window_start = now - timedelta(minutes=settings.login_lock_minutes)
    lock_expired = attempt.locked_until is not None
    if attempt.failed_count == 0 or attempt.first_failed_at < window_start or lock_expired:
        # 最初の試行、数え始めてから一定時間たった、またはロックが明けた：1 から数え直す
        attempt.failed_count = 1
        attempt.first_failed_at = now
        attempt.locked_until = None
    else:
        attempt.failed_count += 1

    if attempt.failed_count > settings.login_max_failed_attempts:
        # 上限の回数分の照合が、すでにほかのリクエストで進んでいる
        return _Reservation(allowed=False, count=attempt.failed_count, reason="too many attempts")
    return _Reservation(allowed=True, count=attempt.failed_count, reason="")


def _finish_failed_attempt(
    db: Session,
    email: str,
    now: datetime,
    reservation: _Reservation,
    client_ip: str | None,
    reason: str,
) -> None:
    """失敗を記録する。上限の回数に達していれば、一時的にログインできなくする。"""
    if reservation.count >= settings.login_max_failed_attempts:
        locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        db.execute(
            update(LoginAttempt)
            .where(LoginAttempt.email == email)
            .values(locked_until=locked_until)
        )
        db.commit()
        logger.warning(
            "login locked (%s): email=%s ip=%s until=%sZ", reason, email, client_ip, locked_until
        )
        return
    logger.warning(
        "login failed (%s): email=%s ip=%s count=%d", reason, email, client_ip, reservation.count
    )
