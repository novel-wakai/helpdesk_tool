import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from sqlalchemy import ColumnElement, and_, delete, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    PasswordHashBusyError,
    verify_and_update_password,
    verify_password,
)
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


class _ReservationStatus(Enum):
    ALLOWED = "allowed"  # 照合に進んでよい（照合中の数に 1 を足した）
    LOCKED = "locked"  # ロック中（照合しないで 401）
    IN_PROGRESS = "attempts in progress"  # 上限の回数分の照合が進んでいる（照合しないで 503）


@dataclass(frozen=True)
class _Reservation:
    """照合の前に行う「試行の予約」の結果。"""

    status: _ReservationStatus
    # 予約したときの数え始めの日時（first_failed_at）。照合が終わったときや 503 で戻すとき、
    # 同じ数え始めが続いているかを見分ける（ログインの成功で行が消えて作り直されたり、
    # 数え直したりしていたら、その行は別の数え始めのため、記録を加えない）
    window_started_at: datetime


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

    照合しないで断るとき（照合が混み合っている、またはこのメールアドレスで上限の回数分の
    照合がすでに進んでいる）は PasswordHashBusyError を投げる（503。少し待てば試せる）。

    login_attempts の行は、数え始め（first_failed_at）から 15 分の間の、2 つの数を持つ。
    - 照合して失敗した数（failed_count）：これが上限に達したらロックする
    - 照合中の数（pending_count）：照合に進む前に 1 足し、照合して失敗したとき・照合できずに
      断ったとき（503 や照合中のエラー）に 1 引く。成功したときは行ごと消す（どれも、
      予約したときと同じ数え始めの行のときだけ）。
      処理が途中で止まった（プロセスの停止や、記録するときの DB のエラー）ときは引かれずに残り、
      数え始めから 15 分たって数え直すまで、照合に進める回数が減る（安全な側）
    この 2 つの合計が上限に達していたら、新しい照合に進ませない。そのため、同時に送られても、
    1 つの数え始めの中で照合できるのは上限の回数までになる。照合しなかった試行（503）は
    照合して失敗した数に入らないため、ロックの判定に影響しない。

    処理は 3 段階に分ける。
    1. 予約：行に鍵をかけて照合中の数に 1 を足す。ユーザーもここで読み込み、DB の接続を手放す
    2. 照合：DB の接続を持たずに行う（照合の順番待ちの間、接続を使い切らないように）。
       混み合っていて照合できなければ、照合中の数から 1 引いて PasswordHashBusyError を投げる
    3. 記録：成功なら行を消す。失敗なら照合中の数から 1 引いて失敗した数に 1 足し、
       上限に達していればロックする（どちらも、予約したときと同じ数え始めの行だけ）

    未登録のメールアドレスも同じように数えてロックするため、処理の中身（DB への書き込み・
    照合の回数）が登録の有無で変わらず、応答の時間から登録済みかを推測されない。
    """
    reservation = _reserve_attempt(db, email, utc_now())
    if reservation.status is not _ReservationStatus.ALLOWED:
        # 照合しないで断る試行は、何も数えない（予約での変更を取り消す）
        db.rollback()
        logger.warning(
            "login rejected (%s): email=%s ip=%s", reservation.status.value, email, client_ip
        )
        if reservation.status is _ReservationStatus.IN_PROGRESS:
            # 照合中の試行が終われば、また試せる（パスワードの誤りとは限らないため 401 にしない）
            raise PasswordHashBusyError
        return None

    user = db.scalar(select(User).where(User.email == email))
    # 照合の前にトランザクションを終え、DB の接続をプールに返す
    db.commit()

    try:
        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)
        else:
            valid, updated_hash = verify_and_update_password(password, user.password_hash)
    except PasswordHashBusyError:
        # 照合が混み合っていて、照合しないまま断る（503）。照合中の数から 1 引く
        # （引かないと、照合していない試行で上限に達し、照合に進めなくなるため）
        logger.warning("login busy: email=%s ip=%s", email, client_ip)
        _cancel_reserved_attempt(db, email, reservation, client_ip)
        raise
    except Exception:
        # 照合の途中のエラー（保存されたハッシュの形式が壊れているなど）。照合の結果が出て
        # いないため、失敗としては数えず、照合中の数から 1 引いてからエラーにする（500）。
        # 引かないと、試すたびに照合中の数が残り、正しいパスワードでも 503 が続くため
        logger.exception("login check error: email=%s ip=%s", email, client_ip)
        _cancel_reserved_attempt(db, email, reservation, client_ip)
        raise

    if user is None:
        _finish_failed_attempt(db, email, reservation, client_ip, "unknown email")
        return None
    if not valid:
        _finish_failed_attempt(db, email, reservation, client_ip, "wrong password")
        return None
    if not user.is_active:
        _finish_failed_attempt(db, email, reservation, client_ip, "inactive user")
        return None

    # ログインに成功したら、試行の記録を消す。照合している間に数え始めが変わっていたら
    # （新しい数え始めで失敗やロックが記録されていたら）、その行は消さずに残す
    db.execute(delete(LoginAttempt).where(_same_window(email, reservation)))
    # ハッシュの設定が新しくなっていれば、新しい設定のハッシュに保存し直す
    if updated_hash is not None:
        db.execute(update(User).where(User.id == user.id).values(password_hash=updated_hash))
        user.password_hash = updated_hash
    db.commit()
    return user


def _reserve_attempt(db: Session, email: str, now: datetime) -> _Reservation:
    """照合に進んでよいかを決め、よければ照合中の数に 1 を足す（デッドロックならやり直す）。"""
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
        .values(email=email, failed_count=0, pending_count=0, first_failed_at=now)
        .on_duplicate_key_update(email=LoginAttempt.email)
    )
    # populate_existing：セッションが同じ行のオブジェクトをすでに持っていても、鍵をかけて
    # 読んだ最新の値で置き換える（古い値のまま数えて書き戻すと、ほかのリクエストの分が消える）
    attempt = db.execute(
        select(LoginAttempt)
        .where(LoginAttempt.email == email)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()

    if attempt.locked_until is not None and attempt.locked_until > now:
        return _Reservation(_ReservationStatus.LOCKED, attempt.first_failed_at)

    window_start = now - timedelta(minutes=settings.login_lock_minutes)
    lock_expired = attempt.locked_until is not None
    unused = attempt.failed_count == 0 and attempt.pending_count == 0
    if unused or attempt.first_failed_at < window_start or lock_expired:
        # 失敗も照合中もない、数え始めてから一定時間たった、またはロックが明けた：数え直す。
        # 数え始めの日時が変わるため、前の数え始めで照合中だった試行は、この行に記録を加えない
        # （一定時間たったのに照合中の数が残っているのは、照合中に処理が止まった試行の分）
        attempt.failed_count = 0
        attempt.pending_count = 0
        attempt.first_failed_at = now
        attempt.locked_until = None

    if attempt.failed_count + attempt.pending_count >= settings.login_max_failed_attempts:
        # 失敗した数と照合中の数で、上限に達している。ふつうは、失敗した数だけで上限に達すれば
        # ロックしているため、ここに来るのは照合中の試行があるとき（運用中に上限の回数を
        # 下げたときは、失敗した数だけで上限以上のこともある。そのときも照合には進ませない）
        return _Reservation(_ReservationStatus.IN_PROGRESS, attempt.first_failed_at)
    attempt.pending_count += 1
    return _Reservation(_ReservationStatus.ALLOWED, attempt.first_failed_at)


def _same_window(email: str, reservation: _Reservation) -> ColumnElement[bool]:
    """予約したときと同じ数え始めの行を選ぶ条件。"""
    return and_(
        LoginAttempt.email == email,
        LoginAttempt.first_failed_at == reservation.window_started_at,
    )


def _cancel_reserved_attempt(
    db: Session, email: str, reservation: _Reservation, client_ip: str | None
) -> None:
    """照合しなかった試行の分、照合中の数から 1 引く。

    予約したときと同じ数え始めの行だけを対象にする。照合を待っている間に、ほかのリクエストで
    ログインに成功して行が消えたり、数え直したりしていたら、何もしない（新しい数え始めの数を
    減らすと、その数え始めで照合できる回数が上限を超えてしまうため）。

    DB のエラーで引けなくても、例外は外に出さない（呼び出し元は、混み合いなら 503、
    照合中のエラーなら元のエラーで 500 を返す）。その場合、
    照合中の数が残り、数え始めから 15 分たつまでの間、照合に進める回数が 1 回減る（安全な側）。
    """
    try:
        db.execute(
            update(LoginAttempt)
            .where(_same_window(email, reservation), LoginAttempt.pending_count > 0)
            .values(pending_count=LoginAttempt.pending_count - 1)
        )
        db.commit()
    except SQLAlchemyError:
        logger.exception("login busy refund failed: email=%s ip=%s", email, client_ip)
        try:
            db.rollback()
        except SQLAlchemyError:
            # 接続が切れているなど。セッションは get_db の終わりに閉じられる
            pass


def _finish_failed_attempt(
    db: Session,
    email: str,
    reservation: _Reservation,
    client_ip: str | None,
    reason: str,
) -> None:
    """照合して失敗したことを記録する。失敗した数が上限に達したら、一時的にログインできなくする。

    予約したときと同じ数え始めの行だけに記録する。照合している間に、ほかのリクエストで
    ログインに成功して行が消えたり、数え直したりしていたら、記録しない（ログには残す）。
    """
    attempt = db.execute(
        select(LoginAttempt)
        .where(_same_window(email, reservation))
        .with_for_update()
        .execution_options(populate_existing=True)  # 理由は _reserve_attempt_once と同じ
    ).scalar_one_or_none()
    if attempt is None:
        db.commit()
        logger.warning(
            "login failed (%s, window changed): email=%s ip=%s", reason, email, client_ip
        )
        return

    attempt.pending_count = max(attempt.pending_count - 1, 0)
    attempt.failed_count += 1
    if attempt.failed_count >= settings.login_max_failed_attempts:
        attempt.locked_until = utc_now() + timedelta(minutes=settings.login_lock_minutes)
    locked_until = attempt.locked_until
    count = attempt.failed_count
    db.commit()
    if locked_until is not None:
        logger.warning(
            "login locked (%s): email=%s ip=%s until=%sZ", reason, email, client_ip, locked_until
        )
        return
    logger.warning("login failed (%s): email=%s ip=%s count=%d", reason, email, client_ip, count)
