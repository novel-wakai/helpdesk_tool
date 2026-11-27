import { Box, Flex, HStack, Stack, Text } from '@chakra-ui/react'
import { NavLink, Outlet } from 'react-router'

import { BrandMark } from './BrandMark'

/** ログイン後の画面の共通の枠（左：サイドバー、右：各画面） */
export const AppLayout = () => (
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
    <Box as="main" flex="1" bg="gray.50">
      <Outlet />
    </Box>
  </Flex>
)
