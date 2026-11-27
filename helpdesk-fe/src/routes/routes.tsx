import { Navigate, type RouteObject } from 'react-router'

import { AppLayout } from '../components/AppLayout'
import { LoginContainer } from '../features/auth/containers/LoginContainer'
import { TicketListPage } from '../features/tickets/presentational/TicketListPage'
import { RedirectIfAuthenticated } from './RedirectIfAuthenticated'
import { RequireAuth } from './RequireAuth'

/**
 * 画面の一覧。
 * - /login：ログイン画面（ログイン済みならチケット一覧へ）
 * - /tickets：チケット一覧（ログインしていなければログイン画面へ）
 * - / やそのほかの URL：チケット一覧へ（ログインしていなければ、そこからログイン画面へ）
 */
export const routes: RouteObject[] = [
  {
    element: <RedirectIfAuthenticated />,
    children: [{ path: '/login', element: <LoginContainer /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [{ path: '/tickets', element: <TicketListPage /> }],
      },
    ],
  },
  { path: '*', element: <Navigate to="/tickets" replace /> },
]
