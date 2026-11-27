import { ChakraProvider, defaultSystem } from '@chakra-ui/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { createQueryClient } from '../api/queryClient'
import { routes } from '../routes/routes'

/** Chakra UI のプロバイダーで包んで描画するテスト用ヘルパー */
export const renderWithProviders = (ui: ReactElement) =>
  render(<ChakraProvider value={defaultSystem}>{ui}</ChakraProvider>)

/**
 * アプリの画面一覧（routes）を、指定した URL から表示するテスト用ヘルパー。
 * テストごとに新しい QueryClient を使う（前のテストのログイン状態を持ち越さない）。
 */
export const renderRoutes = (initialPath: string) => {
  const queryClient = createQueryClient()
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })
  const result = render(
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ChakraProvider>,
  )
  return { ...result, router, queryClient }
}
