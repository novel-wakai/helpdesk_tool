import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchCurrentUser, login, logout } from '../api/auth'
import { clearUserData, currentUserQueryKey } from '../api/queryClient'
import { markLoggedOut } from '../features/auth/logoutNotice'

/**
 * ログイン中のユーザー（ログインしていなければ null）。
 *
 * ログインの状態は Cookie（JavaScript から読めない）で保たれるため、画面を開いたときや
 * 再読み込みしたときは、BE に問い合わせて確かめる。
 */
export const useCurrentUser = () =>
  useQuery({
    queryKey: currentUserQueryKey,
    queryFn: fetchCurrentUser,
    retry: false,
  })

/** ログインする。成功したら、ログイン中のユーザーとして保持する */
export const useLogin = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: login,
    onSuccess: async (user) => {
      // ログインの前に始まったログイン状態の確認（画面に戻ったときの再取得など）が、
      // あとから「ログインしていない」と返って、ログインしたユーザーを上書きしないよう止める
      await queryClient.cancelQueries({ queryKey: currentUserQueryKey })
      // 前にログインしていたユーザーのデータを残さない
      clearUserData(queryClient)
      queryClient.setQueryData(currentUserQueryKey, user)
    },
  })
}

/**
 * ログアウトする。成功したら、取得したデータとログイン中のユーザーを消す
 * （ログインが必要な画面は、それを見てログイン画面に移る）。
 * 失敗したとき（BE に接続できない、500 など）は、何も消さない。Cookie は JavaScript から消せないため、
 * 画面だけログアウトしたように見せると、実際にはログインが残ってしまう。
 */
export const useLogout = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      // ログアウトの前に始まったログイン状態の確認が、あとから「ログイン中」と返って、
      // ログアウトを上書きしないよう止める
      await queryClient.cancelQueries({ queryKey: currentUserQueryKey })
      clearUserData(queryClient)
      // ログイン画面で「ログアウトしました」を出すための目印
      markLoggedOut()
      queryClient.setQueryData(currentUserQueryKey, null)
    },
  })
}
