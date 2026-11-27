import { Center, Spinner, VisuallyHidden } from '@chakra-ui/react'

/** 画面全体の読み込み中の表示（ログインの状態を確かめている間など） */
export const FullPageSpinner = () => (
  // role="status"：読み込み中であることを、読み上げソフトにも伝えられるようにする
  <Center minH="100vh" role="status">
    <Spinner size="lg" color="teal.600" />
    <VisuallyHidden>読み込み中</VisuallyHidden>
  </Center>
)
