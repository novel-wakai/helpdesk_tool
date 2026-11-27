import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import { httpError, networkError } from '../test/axiosError'
import { clearUserData, currentUserQueryKey, shouldRetry } from './queryClient'

describe('shouldRetry', () => {
  it.each([400, 401, 403, 404, 422])('BE が %i を返したときは、やり直さない', (status) => {
    expect(shouldRetry(0, httpError(status))).toBe(false)
  })

  it.each([
    ['500', httpError(500)],
    ['接続できない', networkError()],
  ])('%s のときは、3 回までやり直す', (_, error) => {
    expect(shouldRetry(0, error)).toBe(true)
    expect(shouldRetry(2, error)).toBe(true)
    expect(shouldRetry(3, error)).toBe(false)
  })
})

describe('clearUserData', () => {
  it('ログイン中のユーザー以外のデータを、auth で始まるものも含めてすべて消す', () => {
    const queryClient = new QueryClient()
    queryClient.setQueryData(currentUserQueryKey, { id: 1 })
    queryClient.setQueryData(['auth', 'sessions'], ['前のユーザーの端末'])
    queryClient.setQueryData(['tickets'], ['前のユーザーのチケット'])

    clearUserData(queryClient)

    expect(queryClient.getQueryData(currentUserQueryKey)).toEqual({ id: 1 })
    expect(queryClient.getQueryData(['auth', 'sessions'])).toBeUndefined()
    expect(queryClient.getQueryData(['tickets'])).toBeUndefined()
  })
})
