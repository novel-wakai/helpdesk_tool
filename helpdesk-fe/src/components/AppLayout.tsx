import { Box, Flex, HStack, Stack, Text } from '@chakra-ui/react'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { LOGOUT_FAILED_MESSAGE, LOGOUT_FAILED_TOAST_ID } from '../features/auth/logoutMessage'
import { useCurrentUser, useLogout } from '../hooks/useAuth'
import { AppHeader } from './AppHeader'
import { BrandMark } from './BrandMark'
import { toaster } from './toaster'

/**
 * ログイン後の画面の共通の枠（左：サイドバー、右：上部のヘッダーと各画面）。
 * ログインの確認（RequireAuth）の中で使うため、ログイン中のユーザーがいる前提で表示する。
 */
export const AppLayout = () => {
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const logoutMutation = useLogout()

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      // ログイン画面へ移すのは、ログインの確認（RequireAuth）が確実に行う（ログイン中のユーザーが消えるため）。
      // ここでの移動は念のためで、どちらも履歴を置き換える（戻るボタンでログアウト前の画面に戻らない）
      onSuccess: () => navigate('/login', { replace: true }),
      onError: () =>
        toaster.create({
          id: LOGOUT_FAILED_TOAST_ID,
          type: 'error',
          title: LOGOUT_FAILED_MESSAGE,
          duration: 6000,
        }),
    })
  }

  return (
    <Flex minH="100vh">
      <Box as="nav" aria-label="メニュー" w="56" flexShrink={0} borderRightWidth="1px" p="4">
        <HStack gap="3" mb="8" px="2">
          <BrandMark />
          <Stack gap="0" lineHeight="short">
            <Text fontWeight="bold">Novel</Text>
            <Text fontSize="xs" color="fg.muted" letterSpacing="wider">
              HELPDESK
            </Text>
          </Stack>
        </HStack>
        <NavLink to="/tickets">
          {({ isActive }) => (
            <Box
              px="3"
              py="2"
              rounded="md"
              fontSize="sm"
              fontWeight="medium"
              bg={isActive ? 'teal.50' : undefined}
              color={isActive ? 'teal.800' : undefined}
            >
              Ticket
            </Box>
          )}
        </NavLink>
      </Box>
      <Flex direction="column" flex="1" minW="0">
        <AppHeader
          displayName={user?.display_name ?? ''}
          onLogout={handleLogout}
          isLoggingOut={logoutMutation.isPending}
        />
        <Box as="main" flex="1" bg="gray.50">
          <Outlet />
        </Box>
      </Flex>
    </Flex>
  )
}
