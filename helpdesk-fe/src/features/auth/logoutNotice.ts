/**
 * 「ログアウトした」ことをログイン画面に伝える目印（ログイン画面で成功のトーストを出すため）。
 *
 * - 画面の履歴（location.state）に置かないのは、再読み込みしても履歴に残り、トーストを出し直してしまうため。
 *   この変数は再読み込みで消える
 * - ログイン画面に移す処理がどこで動いても（RequireAuth でも、ログアウトのボタンの処理でも）伝わる
 */
let loggedOut = false

/** ログアウトしたことを記録する */
export const markLoggedOut = () => {
  loggedOut = true
}

/** ログアウトした記録があれば true を返し、記録を消す（トーストを 1 回だけ出すため） */
export const consumeLoggedOutNotice = () => {
  const result = loggedOut
  loggedOut = false
  return result
}
