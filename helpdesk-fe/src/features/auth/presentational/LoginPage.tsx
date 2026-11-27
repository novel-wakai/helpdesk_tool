import {
  Alert,
  Button,
  chakra,
  Field,
  Flex,
  Heading,
  HStack,
  Input,
  Stack,
  Text,
} from '@chakra-ui/react'
import { useRef, useState, type FormEvent } from 'react'
import { flushSync } from 'react-dom'

import type { LoginRequest } from '../../../api/auth'
import { BrandMark } from '../../../components/BrandMark'

export const EMAIL_REQUIRED_MESSAGE = 'メールアドレスを入力してください'
export const PASSWORD_REQUIRED_MESSAGE = 'パスワードを入力してください'

const EMAIL_ERROR_ID = 'login-email-error'
const PASSWORD_ERROR_ID = 'login-password-error'

type Props = {
  onSubmit: (values: LoginRequest) => void
  isSubmitting: boolean
  /** ログインに失敗したときに表示するメッセージ */
  errorMessage?: string
}

type FieldErrors = {
  email?: string
  password?: string
}

/** ログイン画面（左：アプリの紹介、右：ログインのフォーム） */
export const LoginPage = ({ onSubmit, isSubmitting, errorMessage }: Props) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSubmitting) {
      return
    }

    // 送信前は空欄だけを確かめる（形式の確認は BE で行う）。
    // メールアドレスは前後の空白を除く（貼り付けたときに付きやすいため）。パスワードはそのまま送る
    const trimmedEmail = email.trim()
    const errors: FieldErrors = {
      email: trimmedEmail === '' ? EMAIL_REQUIRED_MESSAGE : undefined,
      password: password === '' ? PASSWORD_REQUIRED_MESSAGE : undefined,
    }
    // 誤りの表示を画面に反映してから、入力欄に移る（移った時点で「誤りがある」状態にするため）
    flushSync(() => setFieldErrors(errors))
    if (errors.email || errors.password) {
      // 最初の誤りの欄に移る（読み上げソフトの利用者にも、どこを直すかが伝わるように）
      const firstInvalid = errors.email ? emailRef.current : passwordRef.current
      firstInvalid?.focus()
      return
    }

    onSubmit({ email: trimmedEmail, password })
  }

  return (
    <Flex minH="100vh">
      <Flex
        display={{ base: 'none', md: 'flex' }}
        flex="1"
        direction="column"
        justify="space-between"
        p="14"
        color="white"
        bgGradient="to-br"
        gradientFrom="teal.900"
        gradientTo="teal.700"
      >
        <HStack gap="3">
          <BrandMark onDark />
          <Text fontWeight="semibold">Novel HELPDESK</Text>
        </HStack>
        <Stack gap="4" pb="24">
          <Heading as="p" size="3xl" lineHeight="short">
            困ったときの窓口は、
            <br />
            ここひとつ。
          </Heading>
          <Text color="whiteAlpha.800" maxW="md">
            チケットで問い合わせを受け付け、社員とサポート担当のやり取りや対応の状況を、まとめて確認できます。
          </Text>
        </Stack>
      </Flex>

      <Flex flex="1" align="center" justify="center" bg="gray.50" px="6" py="12">
        <chakra.form onSubmit={handleSubmit} noValidate w="full" maxW="md">
          <Stack gap="6">
            <Stack gap="2">
              <Heading as="h1" size="2xl">
                ログイン
              </Heading>
              <Text color="fg.muted" fontSize="sm">
                登録されているメールアドレスとパスワードを入力してください
              </Text>
            </Stack>

            {errorMessage && (
              // role="alert"：表示されたことを、読み上げソフトにも伝える
              <Alert.Root status="error" role="alert">
                <Alert.Indicator />
                <Alert.Title>{errorMessage}</Alert.Title>
              </Alert.Root>
            )}

            <Field.Root invalid={Boolean(fieldErrors.email)}>
              <Field.Label>メールアドレス</Field.Label>
              <Input
                ref={emailRef}
                // 誤りの文言と結びつけ、入力欄に移ったときに読み上げられるようにする
                aria-describedby={fieldErrors.email ? EMAIL_ERROR_ID : undefined}
                type="email"
                name="email"
                bg="white"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                // スマートフォンで先頭が大文字にならないようにする
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
              />
              <Field.ErrorText id={EMAIL_ERROR_ID}>{fieldErrors.email}</Field.ErrorText>
            </Field.Root>

            <Field.Root invalid={Boolean(fieldErrors.password)}>
              <Field.Label>パスワード</Field.Label>
              <Input
                ref={passwordRef}
                aria-describedby={fieldErrors.password ? PASSWORD_ERROR_ID : undefined}
                type="password"
                name="password"
                bg="white"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
              />
              <Field.ErrorText id={PASSWORD_ERROR_ID}>{fieldErrors.password}</Field.ErrorText>
            </Field.Root>

            <Button
              type="submit"
              colorPalette="teal"
              rounded="full"
              w="full"
              loading={isSubmitting}
              loadingText="ログイン中"
            >
              ログイン
            </Button>
          </Stack>
        </chakra.form>
      </Flex>
    </Flex>
  )
}
