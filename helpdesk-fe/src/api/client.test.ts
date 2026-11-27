import { describe, expect, it } from 'vitest'

import { apiClient } from './client'

describe('apiClient', () => {
  it('API の呼び出しに、ログインの Cookie を付ける（付けないとログインの状態が保たれない）', () => {
    expect(apiClient.defaults.withCredentials).toBe(true)
  })
})
