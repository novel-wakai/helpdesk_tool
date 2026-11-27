import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpError, networkError } from '../test/axiosError'
import { fetchCurrentUser, logout, type User } from './auth'
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

describe('logout', () => {
  it('ログアウトの API を、本文なしで呼ぶ', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValue({ data: undefined })

    await expect(logout()).resolves.toBeUndefined()
    expect(apiClient.post).toHaveBeenCalledWith('/auth/logout')
  })

  it('すでにログインが切れている（401）ときは、ログアウトできたものとして扱う', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(httpError(401))

    await expect(logout()).resolves.toBeUndefined()
  })

  it.each([
    ['500', httpError(500)],
    ['接続できない', networkError()],
  ])('%s のときはエラーにする（ログアウトできたと決めつけない）', async (_, error) => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(error)

    await expect(logout()).rejects.toBe(error)
  })
})
