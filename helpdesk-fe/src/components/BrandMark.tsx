import { Center } from '@chakra-ui/react'

type Props = {
  /** 背景が濃い色の上に置くとき（ログイン画面の左側）は true */
  onDark?: boolean
}

/** アプリのマーク（「N」の角丸の四角） */
export const BrandMark = ({ onDark = false }: Props) => (
  <Center
    boxSize="9"
    rounded="lg"
    fontWeight="bold"
    color="white"
    bg={onDark ? 'whiteAlpha.300' : 'teal.600'}
    aria-hidden
  >
    N
  </Center>
)
