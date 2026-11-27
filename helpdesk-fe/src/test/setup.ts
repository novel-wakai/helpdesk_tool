import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { toaster } from '../components/toaster'
import { consumeLoggedOutNotice } from '../features/auth/logoutNotice'

// テストごとに、描画した画面を片付ける（Vitest の globals を使わない設定では、自動では片付かない）
afterEach(() => {
  cleanup()
  // トーストはアプリ全体で 1 つの入れ物を使うため、前のテストのトーストを消す
  toaster.remove()
  // ログアウトの目印も、前のテストのものを残さない
  consumeLoggedOutNotice()
})
