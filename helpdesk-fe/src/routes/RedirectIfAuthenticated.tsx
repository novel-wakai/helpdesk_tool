import { Navigate, Outlet } from 'react-router'

import { FullPageSpinner } from '../components/FullPageSpinner'
import { useCurrentUser } from '../hooks/useAuth'

/** ログイン画面の入口。すでにログインしていれば、チケット一覧に移る */
export const RedirectIfAuthenticated = () => {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return <FullPageSpinner />
  }
  if (user) {
    return <Navigate to="/tickets" replace />
  }
  return <Outlet />
}
