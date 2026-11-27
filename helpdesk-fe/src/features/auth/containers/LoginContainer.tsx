import { useNavigate } from 'react-router'

import type { LoginRequest } from '../../../api/auth'
import { useLogin } from '../../../hooks/useAuth'
import { getLoginErrorMessage } from '../loginErrorMessage'
import { LoginPage } from '../presentational/LoginPage'

export const LoginContainer = () => {
  const navigate = useNavigate()
  const loginMutation = useLogin()

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
