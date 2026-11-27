import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../../../test/render'
import { EMAIL_REQUIRED_MESSAGE, LoginPage, PASSWORD_REQUIRED_MESSAGE } from './LoginPage'

const setup = (props: Partial<Parameters<typeof LoginPage>[0]> = {}) => {
  const onSubmit = vi.fn()
  renderWithProviders(<LoginPage onSubmit={onSubmit} isSubmitting={false} {...props} />)
  return {
    onSubmit,
    email: screen.getByLabelText('メールアドレス'),
    password: screen.getByLabelText('パスワード'),
    submit: screen.getByRole('button', { name: 'ログイン' }),
  }
}

describe('LoginPage', () => {
  it('メールアドレスとパスワードの入力欄があるフォームを表示する（受け入れ要件 1）', () => {
    const { email, password } = setup()

    expect(screen.getByRole('heading', { name: 'ログイン' })).toBeInTheDocument()
    expect(email).toHaveAttribute('type', 'email')
    expect(password).toHaveAttribute('type', 'password')
  })

  it('フォームの送信ボタンがある（受け入れ要件 2）', () => {
    const { submit } = setup()

    expect(submit).toHaveAttribute('type', 'submit')
  })

  it('入力したメールアドレス（前後の空白を除く）とパスワードを送信する', () => {
    const { onSubmit, email, password, submit } = setup()

    fireEvent.change(email, { target: { value: '  aaa@example.com ' } })
    fireEvent.change(password, { target: { value: ' Password123 ' } })
    fireEvent.click(submit)

    // パスワードの空白は、パスワードの一部として扱う（除かない）
    expect(onSubmit).toHaveBeenCalledWith({ email: 'aaa@example.com', password: ' Password123 ' })
  })

  it('空欄のまま送信すると、入力を促すメッセージを出し、送信しない', () => {
    const { onSubmit, email, submit } = setup()
    // 入力欄に移った時点で、誤りの状態になっているか
    let invalidWhenFocused: string | null = null
    email.addEventListener('focus', () => {
      invalidWhenFocused = email.getAttribute('aria-invalid')
    })

    fireEvent.change(email, { target: { value: '   ' } })
    fireEvent.click(submit)

    expect(screen.getByText(EMAIL_REQUIRED_MESSAGE)).toBeInTheDocument()
    expect(screen.getByText(PASSWORD_REQUIRED_MESSAGE)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
    // 最初の誤りの欄（メールアドレス）に移り、その時点で誤りの状態になっている
    expect(email).toHaveFocus()
    expect(invalidWhenFocused).toBe('true')
    // 誤りの文言が、入力欄と結びついている（入力欄に移ったときに読み上げられる）
    expect(email).toHaveAccessibleDescription(EMAIL_REQUIRED_MESSAGE)
  })

  it('パスワードだけが空欄のときは、パスワードの欄に移る', () => {
    const { onSubmit, email, password, submit } = setup()

    fireEvent.change(email, { target: { value: 'aaa@example.com' } })
    fireEvent.click(submit)

    expect(screen.queryByText(EMAIL_REQUIRED_MESSAGE)).not.toBeInTheDocument()
    expect(screen.getByText(PASSWORD_REQUIRED_MESSAGE)).toBeInTheDocument()
    expect(password).toHaveFocus()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('ログインに失敗したときのメッセージを表示する', () => {
    setup({ errorMessage: 'メールアドレスまたはパスワードが正しくありません' })

    expect(screen.getByRole('alert')).toHaveTextContent(
      'メールアドレスまたはパスワードが正しくありません',
    )
  })

  it('送信中はボタンを押せず、もう一度送信しない（二重送信の防止）', () => {
    const onSubmit = vi.fn()
    renderWithProviders(<LoginPage onSubmit={onSubmit} isSubmitting />)

    fireEvent.change(screen.getByLabelText('メールアドレス'), {
      target: { value: 'aaa@example.com' },
    })
    fireEvent.change(screen.getByLabelText('パスワード'), { target: { value: 'Password123' } })
    const submit = screen.getByRole('button', { name: /ログイン/ })
    fireEvent.submit(submit.closest('form')!)

    expect(submit).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('メールアドレスの欄は、自動で大文字にしない', () => {
    const { email } = setup()

    expect(email).toHaveAttribute('autocapitalize', 'none')
    expect(email).toHaveAttribute('autocomplete', 'username')
  })
})
