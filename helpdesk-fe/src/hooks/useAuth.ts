import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchCurrentUser, login } from '../api/auth'
import { clearUserData, currentUserQueryKey } from '../api/queryClient'

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
