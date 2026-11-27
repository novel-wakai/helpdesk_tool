import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// テストごとに、描画した画面を片付ける（Vitest の globals を使わない設定では、自動では片付かない）
afterEach(() => {
  cleanup()
})
