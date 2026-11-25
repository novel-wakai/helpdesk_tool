import { createBrowserRouter } from 'react-router'

import { HomeContainer } from '../features/home/containers/HomeContainer'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <HomeContainer />,
  },
])
