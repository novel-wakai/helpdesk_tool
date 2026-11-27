import { describe, expect, it } from 'vitest'

import { httpError, networkError } from '../../test/axiosError'
import {
  getLoginErrorMessage,
  LOGIN_BUSY_MESSAGE,
  LOGIN_FAILED_MESSAGE,
  LOGIN_UNEXPECTED_MESSAGE,
  SERVER_UNREACHABLE_MESSAGE,
} from './loginErrorMessage'

describe('getLoginErrorMessage', () => {
  it.each([401, 422])('%i は「メールアドレスまたはパスワードが正しくありません」', (status) => {
    expect(getLoginErrorMessage(httpError(status))).toBe(LOGIN_FAILED_MESSAGE)
  })

  it('503 は「混み合っています」', () => {
    expect(getLoginErrorMessage(httpError(503))).toBe(LOGIN_BUSY_MESSAGE)
  })

  it('BE に接続できないときは「サーバーに接続できません」', () => {
    expect(getLoginErrorMessage(networkError())).toBe(SERVER_UNREACHABLE_MESSAGE)
  })

  it.each([400, 500])('想定していない %i は、内部の情報を出さずに共通のメッセージ', (status) => {
    expect(getLoginErrorMessage(httpError(status))).toBe(LOGIN_UNEXPECTED_MESSAGE)
  })

  it('Axios 以外のエラーも、共通のメッセージ', () => {
    expect(getLoginErrorMessage(new Error('boom'))).toBe(LOGIN_UNEXPECTED_MESSAGE)
  })
})
