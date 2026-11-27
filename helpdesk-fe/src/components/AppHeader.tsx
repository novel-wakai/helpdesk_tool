import { Button, Flex, HStack, Text } from '@chakra-ui/react'

type Props = {
  /** ログイン中のユーザーの表示名 */
  displayName: string
  onLogout: () => void
  isLoggingOut: boolean
}

/** ログイン後の画面の上部（右端：ログイン中のユーザーとログアウトのボタン） */
export const AppHeader = ({ displayName, onLogout, isLoggingOut }: Props) => (
  <Flex
    as="header"
    justify="flex-end"
    align="center"
    h="14"
    px="8"
    borderBottomWidth="1px"
    bg="white"
  >
    <HStack gap="4">
      <Text fontSize="sm" color="fg.muted">
        {displayName}
      </Text>
      <Button
        size="sm"
        variant="outline"
        onClick={onLogout}
        // 送信中は押せない（二重に送らない）
        loading={isLoggingOut}
        loadingText="ログアウト中"
      >
        ログアウト
      </Button>
    </HStack>
  </Flex>
)
