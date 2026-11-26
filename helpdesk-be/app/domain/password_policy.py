"""パスワードの決まり（前提資料：8 文字以上、数字と大文字を必ず含む。上限は 20 文字）。

アカウントを発行・変更するとき（今は make seed）に使う。
ログインでは長さの上限（20 文字）だけを確認し、それ以外は照合の結果（401）で判断する
（ログインの画面で、パスワードの決まりを明かさないため）。
"""

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 20


def password_policy_errors(password: str) -> list[str]:
    """パスワードが決まりに合っていない点を返す。合っていれば空のリスト。"""
    errors = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"{PASSWORD_MIN_LENGTH} 文字以上にしてください")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"{PASSWORD_MAX_LENGTH} 文字以下にしてください")
    # 数字と大文字は半角だけを数える（isdigit() は全角の「１」なども数字として扱うため使わない）
    if not any("0" <= char <= "9" for char in password):
        errors.append("数字（0〜9）を 1 文字以上含めてください")
    if not any("A" <= char <= "Z" for char in password):
        errors.append("大文字（A〜Z）を 1 文字以上含めてください")
    return errors
