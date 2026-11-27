import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import type { RouteObject } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentUser, login, logout, type User } from '../../api/auth'
import { currentUserQueryKey } from '../../api/queryClient'
import { AppLayout } from '../../components/AppLayout'
import { RequireAuth } from '../../routes/RequireAuth'
import { routes } from '../../routes/routes'
import { httpError, networkError } from '../../test/axiosError'
import { renderRoutes } from '../../test/render'
import { LOGOUT_FAILED_MESSAGE, LOGOUT_SUCCESS_MESSAGE } from './logoutMessage'
import { consumeLoggedOutNotice } from './logoutNotice'

// BE の API は呼ばず、応答を差し替える
vi.mock('../../api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

const user: User = {
  id: 1,
  display_name: 'Test.Employee',
  email: 'aaa@example.com',
  role: 'employee',
}

const loginHeading = () => screen.findByRole('heading', { name: 'ログイン' })
const ticketHeading = () => screen.findByRole('heading', { name: 'Ticket 一覧' })
const logoutButton = () => screen.getByRole('button', { name: /ログアウト/ })

/** 表示中のトーストのうち、text を含むもの */
const findToast = (text: string) =>
  screen.findByText(text, { selector: '[data-scope="toast"][data-part="title"]' })

beforeEach(() => {
  vi.mocked(fetchCurrentUser).mockReset()
  vi.mocked(login).mockReset()
  vi.mocked(logout).mockReset()
  vi.mocked(fetchCurrentUser).mockResolvedValue(user)
})

describe('ヘッダー', () => {
  it('ログイン後の画面の上部に、ログイン中のユーザーの表示名とログアウトのボタンを表示する', async () => {
    renderRoutes('/tickets')
    await ticketHeading()

    const header = screen.getByRole('banner')
    expect(within(header).getByText('Test.Employee')).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: 'ログアウト' })).toBeEnabled()
  })

  it('ログインの確認（RequireAuth）の中のページは、すべてヘッダーのある枠（AppLayout）の中にある', () => {
    // 今後ページを増やしても、すべてのページにログアウトのボタンが出ることを確かめる
    const elementType = (route: RouteObject) => (route.element as ReactElement | undefined)?.type
    const pagesOutsideLayout = (
      list: RouteObject[],
      inAuth: boolean,
      inLayout: boolean,
    ): string[] =>
      list.flatMap((route) => {
        const auth = inAuth || elementType(route) === RequireAuth
        const layout = inLayout || elementType(route) === AppLayout
        const self =
          auth && !layout && (route.path !== undefined || route.index)
            ? [route.path ?? '(index)']
            : []
        return [...self, ...pagesOutsideLayout(route.children ?? [], auth, layout)]
      })

    expect(pagesOutsideLayout(routes, false, false)).toEqual([])
  })

  it('ログイン画面には、ログアウトのボタンを表示しない', async () => {
    vi.mocked(fetchCurrentUser).mockResolvedValue(null)
    renderRoutes('/login')
    await loginHeading()

    expect(screen.queryByRole('button', { name: /ログアウト/ })).not.toBeInTheDocument()
  })
})

describe('ログアウトに成功したとき', () => {
  beforeEach(() => {
    // ログアウトしたら、BE もログインしていない（/auth/me が 401）と答える
    vi.mocked(logout).mockImplementation(async () => {
      vi.mocked(fetchCurrentUser).mockResolvedValue(null)
    })
  })

  it('ログアウトの API を呼び、ログイン画面に移ってから、成功のトーストを出す', async () => {
    const { router } = renderRoutes('/tickets')
    await ticketHeading()

    fireEvent.click(logoutButton())

    expect(await loginHeading()).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(logout).toHaveBeenCalledTimes(1)
    // トーストは、ログイン画面に移ったあとに出る
    expect(await findToast(LOGOUT_SUCCESS_MESSAGE)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('成功のトーストは、ログアウトの応答を待つ間（チケット一覧のまま）には出さず、ログイン画面に移ってから出す', async () => {
    let finishLogout: () => void = () => {}
    vi.mocked(logout).mockReturnValue(
      new Promise((resolve) => {
        finishLogout = () => {
          vi.mocked(fetchCurrentUser).mockResolvedValue(null)
          resolve()
        }
      }),
    )
    const { router } = renderRoutes('/tickets')
    await ticketHeading()

    fireEvent.click(logoutButton())
    await waitFor(() => expect(logoutButton()).toBeDisabled())
    expect(screen.queryByText(LOGOUT_SUCCESS_MESSAGE)).not.toBeInTheDocument()

    await act(async () => finishLogout())

    expect(await findToast(LOGOUT_SUCCESS_MESSAGE)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.getByRole('heading', { name: 'ログイン' })).toBeInTheDocument()
    // 成功のトーストは 1 つだけ（開発時に画面の処理が 2 回動いても、重ねて出さない）
    expect(screen.getAllByText(LOGOUT_SUCCESS_MESSAGE)).toHaveLength(1)
  })

  it('取得したデータとログイン中のユーザーを消す。トーストの目印も 1 回で消す（再読み込みで出し直さない）', async () => {
    const { queryClient } = renderRoutes('/tickets')
    await ticketHeading()
    queryClient.setQueryData(['tickets'], ['ログアウトしたユーザーのチケット'])

    fireEvent.click(logoutButton())
    await findToast(LOGOUT_SUCCESS_MESSAGE)

    expect(queryClient.getQueryData(['tickets'])).toBeUndefined()
    expect(queryClient.getQueryData(currentUserQueryKey)).toBeNull()
    expect(consumeLoggedOutNotice()).toBe(false)
  })

  it('ログアウトのあと、戻るボタンでログイン後の画面に戻ろうとしても、ログイン画面に移る', async () => {
    // チケット一覧を 2 回開いた履歴（戻るとチケット一覧になる）
    const { router } = renderRoutes(['/tickets', '/tickets'])
    await ticketHeading()

    fireEvent.click(logoutButton())
    await loginHeading()
    await act(() => router.navigate(-1))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(await loginHeading()).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Ticket 一覧' })).not.toBeInTheDocument()
  })

  it('ログアウトの前に始まったログイン状態の確認が、あとから「ログイン中」と返っても、ログアウトしたままになる', async () => {
    const { router, queryClient } = renderRoutes('/tickets')
    await ticketHeading()
    // 画面に戻ったときなどの再取得が始まり、まだ返ってきていない
    let resolveStaleCheck: (value: User | null) => void = () => {}
    vi.mocked(fetchCurrentUser).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStaleCheck = resolve
      }),
    )
    void queryClient.refetchQueries({ queryKey: currentUserQueryKey })
    vi.mocked(fetchCurrentUser).mockResolvedValue(null)

    fireEvent.click(logoutButton())
    await loginHeading()
    // ログアウトの前に始まった確認が、ログイン中と返ってくる
    await act(async () => resolveStaleCheck(user))

    expect(router.state.location.pathname).toBe('/login')
    expect(queryClient.getQueryData(currentUserQueryKey)).toBeNull()
  })

  it('ログアウトの応答を待つ間は、ボタンを押せず、もう一度送らない', async () => {
    vi.mocked(logout).mockReturnValue(new Promise(() => {}))
    renderRoutes('/tickets')
    await ticketHeading()

    fireEvent.click(logoutButton())

    await waitFor(() => expect(logoutButton()).toBeDisabled())
    fireEvent.click(logoutButton())
    expect(logout).toHaveBeenCalledTimes(1)
  })
})

describe('ログアウトに失敗したとき', () => {
  it.each([
    ['500', httpError(500)],
    ['接続できない', networkError()],
  ])('%s のときは、画面を移らず、ログインしたまま、エラーのトーストを出す', async (_, error) => {
    vi.mocked(logout).mockRejectedValue(error)
    const { router, queryClient } = renderRoutes('/tickets')
    await ticketHeading()
    queryClient.setQueryData(['tickets'], ['チケット'])

    fireEvent.click(logoutButton())

    // エラーは role="alert" で、読み上げソフトがすぐに読み上げる
    expect(await screen.findByRole('alert')).toHaveTextContent(LOGOUT_FAILED_MESSAGE)
    expect(router.state.location.pathname).toBe('/tickets')
    expect(queryClient.getQueryData(currentUserQueryKey)).toEqual(user)
    expect(queryClient.getQueryData(['tickets'])).toEqual(['チケット'])
    expect(screen.queryByText(LOGOUT_SUCCESS_MESSAGE)).not.toBeInTheDocument()
    // もう一度押せる
    await waitFor(() => expect(logoutButton()).toBeEnabled())
  })
})
