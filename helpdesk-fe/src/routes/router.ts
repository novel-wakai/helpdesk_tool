import { createBrowserRouter } from 'react-router'

import { routes } from './routes'

// 画面の一覧は routes.tsx だけに書く。ここで route を足すと、
// すべてのページがログインの確認を通ることを確かめるテスト（routeGuard.test.tsx）の対象から外れる
export const router = createBrowserRouter(routes)
