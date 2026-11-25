import { ChakraProvider, defaultSystem } from '@chakra-ui/react'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'

/** Chakra UI のプロバイダーで包んで描画するテスト用ヘルパー */
export const renderWithProviders = (ui: ReactElement) =>
  render(<ChakraProvider value={defaultSystem}>{ui}</ChakraProvider>)
