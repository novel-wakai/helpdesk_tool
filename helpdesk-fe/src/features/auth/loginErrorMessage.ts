import { isAxiosError } from 'axios'

// どの理由で失敗しても同じ文言にする（登録済みのメールアドレスかを推測させないため。BE と同じ文言）
export const LOGIN_FAILED_MESSAGE = 'メールアドレスまたはパスワードが正しくありません'
export const LOGIN_BUSY_MESSAGE = '混み合っています。しばらくしてからもう一度お試しください'
export const SERVER_UNREACHABLE_MESSAGE = 'サーバーに接続できません'
export const LOGIN_UNEXPECTED_MESSAGE =
  'ログインできませんでした。しばらくしてからもう一度お試しください'

/** ログインの失敗を、利用者に見せるメッセージにする（BE の内部の情報は表示しない） */
export const getLoginErrorMessage = (error: unknown): string => {
  if (!isAxiosError(error)) {
    return LOGIN_UNEXPECTED_MESSAGE
  }
  if (!error.response) {
    return SERVER_UNREACHABLE_MESSAGE
  }
  switch (error.response.status) {
    // 401：メールアドレスまたはパスワードが違う、ロック中など
    // 422：形式の誤り（パスワードが長すぎるなど）。パスワードの決まりを明かさないよう、401 と同じにする
    case 401:
    case 422:
      return LOGIN_FAILED_MESSAGE
    // 503：ログインが混み合っている
    case 503:
      return LOGIN_BUSY_MESSAGE
    default:
      return LOGIN_UNEXPECTED_MESSAGE
  }
}
