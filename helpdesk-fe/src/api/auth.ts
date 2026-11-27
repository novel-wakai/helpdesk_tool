import { isAxiosError } from 'axios'

import { apiClient } from './client'

/** アカウントタイプ（社員 / サポート担当 / 管理者） */
export type UserRole = 'employee' | 'support' | 'admin'

/** ログイン中のユーザー */
export type User = {
  id: number
  display_name: string
  email: string
  role: UserRole
}

export type LoginRequest = {
  email: string
  password: string
}

/** ログインする。成功すると、BE がログインの Cookie を保存する */
export const login = async (body: LoginRequest): Promise<User> => {
  const { data } = await apiClient.post<User>('/auth/login', body)
  return data
}

/** ログイン中のユーザーを取得する。ログインしていない（401）ときは null を返す */
export const fetchCurrentUser = async (): Promise<User | null> => {
  try {
    const { data } = await apiClient.get<User>('/auth/me')
    return data
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 401) {
      return null
    }
    throw error
  }
}

/**
 * ログアウトする。BE が Cookie を消し、このユーザーに発行済みのトークンをすべて使えなくする
 * （ほかのタブ・端末のログインも切れる）。
 * すでにログインが切れている（401）ときは、ログアウトできたものとして扱う。
 */
export const logout = async (): Promise<void> => {
  try {
    await apiClient.post('/auth/logout')
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 401) {
      return
    }
    throw error
  }
}
