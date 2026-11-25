import { Badge, Container, Heading, HStack, Text } from '@chakra-ui/react'

export type ApiStatus = 'checking' | 'ok' | 'error'

type Props = {
  apiStatus: ApiStatus
}

const statusLabel: Record<ApiStatus, { text: string; color: string }> = {
  checking: { text: '確認中', color: 'gray' },
  ok: { text: '接続OK', color: 'green' },
  error: { text: '接続できません', color: 'red' },
}

export const Home = ({ apiStatus }: Props) => {
  const { text, color } = statusLabel[apiStatus]

  return (
    <Container py={10}>
      <Heading size="2xl" mb={4}>
        Novel HELPDESK
      </Heading>
      <HStack>
        <Text>API:</Text>
        <Badge colorPalette={color}>{text}</Badge>
      </HStack>
    </Container>
  )
}
