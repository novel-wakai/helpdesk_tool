import { useEffect } from 'react'
import { useNavigate } from 'react-router'

import type { LoginRequest } from '../../../api/auth'
import { toaster } from '../../../components/toaster'
import { useLogin } from '../../../hooks/useAuth'
import { getLoginErrorMessage } from '../loginErrorMessage'
import { LOGOUT_SUCCESS_MESSAGE, LOGOUT_SUCCESS_TOAST_ID } from '../logoutMessage'
import { consumeLoggedOutNotice } from '../logoutNotice'
import { LoginPage } from '../presentational/LoginPage'

export const LoginContainer = () => {
  const navigate = useNavigate()
  const loginMutation = useLogin()

  // ログアウトしてログイン画面に移ってきたら、成功のトーストを出す（1 回だけ。目印はすぐに消す）
  useEffect(() => {
    if (consumeLoggedOutNotice()) {
      // 画面の表示の処理（useEffect）の中で直接トーストを作ると、React の描画と重なって警告が出るため、
      // 表示の処理が終わってから作る
      queueMicrotask(() =>
        toaster.create({
          id: LOGOUT_SUCCESS_TOAST_ID,
          type: 'success',
          title: LOGOUT_SUCCESS_MESSAGE,
          duration: 3000,
        }),
      )
    }
  }, [])

  const handleSubmit = (values: LoginRequest) => {
    loginMutation.mutate(values, {
      // ログインできたら、チケット一覧へ（戻るボタンでログイン画面に戻らないよう、履歴を置き換える）
      onSuccess: () => navigate('/tickets', { replace: true }),
    })
  }

  return (
    <LoginPage
      onSubmit={handleSubmit}
      isSubmitting={loginMutation.isPending}
      errorMessage={loginMutation.error ? getLoginErrorMessage(loginMutation.error) : undefined}
    />
  )
}
