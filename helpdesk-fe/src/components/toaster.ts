import { createToaster } from '@chakra-ui/react'

/** アプリ全体で使うトースト（画面の右上に出る短い通知）。表示する場所は AppToaster.tsx */
export const toaster = createToaster({
  placement: 'top-end',
  // 画面を見ていない間は、自動で消える時間を止める
  pauseOnPageIdle: true,
})
