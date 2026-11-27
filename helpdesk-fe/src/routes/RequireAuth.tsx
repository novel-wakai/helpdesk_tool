import { Navigate, Outlet } from 'react-router'

import { FullPageSpinner } from '../components/FullPageSpinner'
import { useCurrentUser } from '../hooks/useAuth'

/**
 * ログインが必要な画面の入口。ログインしていなければ、ログイン画面に移る。
 *
 * BE に接続できないときもログイン画面に移る（ログインを試すと、接続できないことを表示する）。
 * 画面の表示を隠すだけで、データを守るのは BE の権限の確認であることに注意する。
 */
export const RequireAuth = () => {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return <FullPageSpinner />
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
