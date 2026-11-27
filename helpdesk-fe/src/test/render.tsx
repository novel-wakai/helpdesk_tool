import { ChakraProvider, defaultSystem } from '@chakra-ui/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { StrictMode, type ReactElement } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { createQueryClient } from '../api/queryClient'
import { AppToaster } from '../components/AppToaster'
import { routes } from '../routes/routes'

/** Chakra UI のプロバイダーで包んで描画するテスト用ヘルパー */
export const renderWithProviders = (ui: ReactElement) =>
  render(<ChakraProvider value={defaultSystem}>{ui}</ChakraProvider>)

/**
 * アプリの画面一覧（routes）を、指定した URL から表示するテスト用ヘルパー。
 * テストごとに新しい QueryClient を使う（前のテストのログイン状態を持ち越さない）。
 */
export const renderRoutes = (initialPath: string | string[]) => {
  const queryClient = createQueryClient()
  // 配列を渡すと、その順に開いた履歴を作る（最後の URL を表示する。戻るボタンの確認用）
  const initialEntries = Array.isArray(initialPath) ? initialPath : [initialPath]
  const router = createMemoryRouter(routes, { initialEntries })
  // 本番の画面（main.tsx）と同じく StrictMode で包む（開発時に画面の処理が 2 回動いても正しく動くかを確かめる）
  const result = render(
    <StrictMode>
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          <AppToaster />
        </QueryClientProvider>
      </ChakraProvider>
    </StrictMode>,
  )
  return { ...result, router, queryClient }
}
