import { expect, test, type Page } from '@playwright/test'

// BE（docker compose up）を起動し、make seed でテストユーザーを作った状態で実行する
const EMAIL = 'aaa@example.com'
const PASSWORD = 'Password123'
// エラーの表示の確認には、登録されていないアドレスを使う（テストユーザーに失敗を重ねてロックしないため。
// BE は登録の有無に関係なく、同じ 401 と同じメッセージを返す）
const UNKNOWN_EMAIL = 'nobody@example.com'

const fillLogin = async (page: Page, email: string, password: string) => {
  await page.getByLabel('メールアドレス').fill(email)
  await page.getByLabel('パスワード').fill(password)
  await page.getByRole('button', { name: 'ログイン' }).click()
}

const screenshot = (page: Page, name: string) =>
  page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true })

test('アプリを開くと、ログイン画面が表示される（受け入れ要件 1・2）', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('heading', { name: 'ログイン' })).toBeVisible()
  await expect(page.getByLabel('メールアドレス')).toBeVisible()
  await expect(page.getByLabel('パスワード')).toBeVisible()
  await expect(page.getByRole('button', { name: 'ログイン' })).toBeVisible()
  await screenshot(page, '01-login')
})

// ログインが必要なページと、存在しない URL（受け入れ要件：ログインしていなければ、すべてログイン画面へ）
for (const path of ['/tickets', '/not-found']) {
  test(`ログインしていないときに ${path} を開くと、ログイン画面に移る`, async ({ page }) => {
    await page.goto(path)

    await expect(page).toHaveURL('/login')
    await expect(page.getByRole('heading', { name: 'ログイン' })).toBeVisible()
  })
}

test('メールアドレスまたはパスワードが間違っていると、エラーメッセージが表示される（受け入れ要件 4）', async ({
  page,
}) => {
  await page.goto('/login')

  await fillLogin(page, UNKNOWN_EMAIL, 'WrongPassword1')

  await expect(page.getByRole('alert')).toHaveText(
    'メールアドレスまたはパスワードが正しくありません',
  )
  await expect(page).toHaveURL('/login')
  await screenshot(page, '02-login-error')
})

test('ログインするとチケット一覧が表示され、再読み込みや画面の移動でもログインが保たれる（受け入れ要件 3・5）', async ({
  page,
}) => {
  await page.goto('/login')

  await fillLogin(page, EMAIL, PASSWORD)

  await expect(page).toHaveURL('/tickets')
  await expect(page.getByRole('heading', { name: 'Ticket 一覧' })).toBeVisible()
  await screenshot(page, '03-tickets')

  // 再読み込みしても、ログインしたまま
  await page.reload()
  await expect(page).toHaveURL('/tickets')
  await expect(page.getByRole('heading', { name: 'Ticket 一覧' })).toBeVisible()

  // ログイン画面やトップを開いても、チケット一覧に戻る
  await page.goto('/login')
  await expect(page).toHaveURL('/tickets')
  await page.goto('/')
  await expect(page).toHaveURL('/tickets')
  await screenshot(page, '04-tickets-after-reload')
})
