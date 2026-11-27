import { ChakraProvider, defaultSystem } from '@chakra-ui/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'

import { createQueryClient } from './api/queryClient'
import { protectPageOnRestore } from './app/pageRestore'
import { AppToaster } from './components/AppToaster'
import { router } from './routes/router'

const queryClient = createQueryClient()
protectPageOnRestore()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <AppToaster />
      </QueryClientProvider>
    </ChakraProvider>
  </StrictMode>,
)
