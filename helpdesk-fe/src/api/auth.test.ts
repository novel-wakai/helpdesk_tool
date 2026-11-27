import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpError, networkError } from '../test/axiosError'
import { fetchCurrentUser, type User } from './auth'
import { apiClient } from './client'

const user: User = {
  id: 1,
  display_name: 'Test.Employee',
  email: 'aaa@example.com',
  role: 'employee',
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('fetchCurrentUser', () => {
  it('ログインしていれば、ログイン中のユーザーを返す', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: user })

    await expect(fetchCurrentUser()).resolves.toEqual(user)
    expect(apiClient.get).toHaveBeenCalledWith('/auth/me')
  })

  it('ログインしていない（401）ときは null を返す', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(httpError(401))

    await expect(fetchCurrentUser()).resolves.toBeNull()
  })

  it.each([
    ['500', httpError(500)],
    ['接続できない', networkError()],
  ])('%s のときはエラーにする（ログインしていないと決めつけない）', async (_, error) => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(error)

    await expect(fetchCurrentUser()).rejects.toBe(error)
  })
})
