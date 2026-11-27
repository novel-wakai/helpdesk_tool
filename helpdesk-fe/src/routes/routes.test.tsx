import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentUser, login, type User } from '../api/auth'
import { currentUserQueryKey } from '../api/queryClient'
import {
  LOGIN_BUSY_MESSAGE,
  LOGIN_FAILED_MESSAGE,
  SERVER_UNREACHABLE_MESSAGE,
} from '../features/auth/loginErrorMessage'
import { httpError, networkError } from '../test/axiosError'
import { renderRoutes } from '../test/render'

// BE の API は呼ばず、応答を差し替える
vi.mock('../api/auth', () => ({
  login: vi.fn(),
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

const submitLogin = (email: string, password: string) => {
  fireEvent.change(screen.getByLabelText('メールアドレス'), { target: { value: email } })
  fireEvent.change(screen.getByLabelText('パスワード'), { target: { value: password } })
  fireEvent.click(screen.getByRole('button', { name: 'ログイン' }))
}

beforeEach(() => {
  vi.mocked(fetchCurrentUser).mockReset()
  vi.mocked(login).mockReset()
})

describe('ログインしていないとき', () => {
  beforeEach(() => {
    vi.mocked(fetchCurrentUser).mockResolvedValue(null)
  })

  it.each(['/', '/tickets', '/not-found'])('%s を開くと、ログイン画面を表示する', async (path) => {
    const { router } = renderRoutes(path)

    expect(await loginHeading()).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('ログインに成功すると、チケット一覧を表示する（受け入れ要件 3）', async () => {
    vi.mocked(login).mockResolvedValue(user)
    const { router } = renderRoutes('/login')
    await loginHeading()

    submitLogin('aaa@example.com', 'Password123')

    expect(await ticketHeading()).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/tickets')
    expect(vi.mocked(login).mock.calls[0][0]).toEqual({
      email: 'aaa@example.com',
      password: 'Password123',
    })
  })

  it('ログインの前に始まったログイン状態の確認が、あとから「ログインしていない」と返っても、ログインしたままになる', async () => {
    const { router, queryClient } = renderRoutes('/login')
    await loginHeading()
    // 画面に戻ったときなどの再取得が始まり、まだ返ってきていない
    let resolveStaleCheck: (value: User | null) => void = () => {}
    vi.mocked(fetchCurrentUser).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStaleCheck = resolve
      }),
    )
    void queryClient.refetchQueries({ queryKey: currentUserQueryKey })
    vi.mocked(fetchCurrentUser).mockResolvedValue(user)
    vi.mocked(login).mockResolvedValue(user)

    submitLogin('aaa@example.com', 'Password123')
    await ticketHeading()
    // ログインの前に始まった確認が、ログインしていない（Cookie なし）と返ってくる
    await act(async () => resolveStaleCheck(null))

    expect(router.state.location.pathname).toBe('/tickets')
    expect(queryClient.getQueryData(currentUserQueryKey)).toEqual(user)
  })

  it('ログインの応答を待つ間は、ボタンを押せない', async () => {
    vi.mocked(login).mockReturnValue(new Promise(() => {}))
    renderRoutes('/login')
    await loginHeading()

    submitLogin('aaa@example.com', 'Password123')

    await waitFor(() => expect(screen.getByRole('button', { name: /ログイン/ })).toBeDisabled())
    expect(login).toHaveBeenCalledTimes(1)
  })

  it('ログインすると、前に取得したデータを消す（前のユーザーのデータを表示しない）', async () => {
    vi.mocked(login).mockResolvedValue(user)
    const { queryClient } = renderRoutes('/login')
    await loginHeading()
    queryClient.setQueryData(['tickets'], ['前のユーザーのチケット'])

    submitLogin('aaa@example.com', 'Password123')
    await ticketHeading()

    expect(queryClient.getQueryData(['tickets'])).toBeUndefined()
  })

  it.each([
    [401, LOGIN_FAILED_MESSAGE],
    [422, LOGIN_FAILED_MESSAGE],
    [503, LOGIN_BUSY_MESSAGE],
  ])(
    'ログインが %i で失敗すると、エラーメッセージを表示し、ログイン画面のまま（受け入れ要件 4）',
    async (status, message) => {
      vi.mocked(login).mockRejectedValue(httpError(status))
      const { router, queryClient } = renderRoutes('/login')
      await loginHeading()
      queryClient.setQueryData(['tickets'], ['前のユーザーのチケット'])

      submitLogin('aaa@example.com', 'WrongPassword1')

      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(router.state.location.pathname).toBe('/login')
      // 401 なら、前のユーザーのデータも消える（ログインの API の 401 でも同じ）
      if (status === 401) {
        expect(queryClient.getQueryData(['tickets'])).toBeUndefined()
        expect(queryClient.getQueryData(currentUserQueryKey)).toBeNull()
      }
    },
  )

  it('BE に接続できないときは、「サーバーに接続できません」を表示する', async () => {
    vi.mocked(login).mockRejectedValue(networkError())
    renderRoutes('/login')
    await loginHeading()

    submitLogin('aaa@example.com', 'Password123')

    expect(await screen.findByRole('alert')).toHaveTextContent(SERVER_UNREACHABLE_MESSAGE)
  })
})

describe('ログインしているとき', () => {
  beforeEach(() => {
    vi.mocked(fetchCurrentUser).mockResolvedValue(user)
  })

  it('チケット一覧を開き直しても（再読み込み）、ログインしたまま表示する（受け入れ要件 5）', async () => {
    const { router } = renderRoutes('/tickets')

    expect(await ticketHeading()).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/tickets')
    expect(fetchCurrentUser).toHaveBeenCalled()
  })

  it.each(['/', '/login'])('%s を開くと、チケット一覧に移る', async (path) => {
    const { router } = renderRoutes(path)

    expect(await ticketHeading()).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/tickets')
  })

  it('画面を移っても、ログインしたまま表示する（受け入れ要件 5）', async () => {
    const { router } = renderRoutes('/tickets')
    await ticketHeading()

    await act(() => router.navigate('/'))

    await waitFor(() => expect(router.state.location.pathname).toBe('/tickets'))
    expect(await ticketHeading()).toBeInTheDocument()
  })

  it('どこかの API が 401（ログインが切れた）を返したら、ログイン画面に移る', async () => {
    const { router, queryClient } = renderRoutes('/tickets')
    await ticketHeading()
    queryClient.setQueryData(['tickets'], ['前のユーザーのチケット'])
    // ログインが切れたので、BE もログインしていない（401）と答える
    vi.mocked(fetchCurrentUser).mockResolvedValue(null)

    await queryClient
      .fetchQuery({ queryKey: ['other'], queryFn: () => Promise.reject(httpError(401)) })
      .catch(() => undefined)

    expect(await loginHeading()).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(queryClient.getQueryData(currentUserQueryKey)).toBeNull()
    // 前のユーザーのデータも消える
    expect(queryClient.getQueryData(['tickets'])).toBeUndefined()
  })
})

describe('ログインの状態を確かめている間', () => {
  it('読み込み中の表示を出し、ログイン画面もチケット一覧も表示しない', async () => {
    vi.mocked(fetchCurrentUser).mockReturnValue(new Promise(() => {}))
    const { router } = renderRoutes('/tickets')

    expect(await screen.findByRole('status')).toHaveTextContent('読み込み中')
    // 確かめ終わるまで、ログイン画面に移らない
    expect(router.state.location.pathname).toBe('/tickets')
    expect(screen.queryByRole('heading', { name: 'ログイン' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Ticket 一覧' })).not.toBeInTheDocument()
  })

  it('BE に接続できなければ、ログイン画面に移る', async () => {
    vi.mocked(fetchCurrentUser).mockRejectedValue(networkError())
    const { router } = renderRoutes('/tickets')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(await loginHeading()).toBeInTheDocument()
  })
})
