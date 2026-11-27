import { expect, test, type Page } from '@playwright/test'

// BE（docker compose up）を起動し、make seed でテストユーザーを作った状態で実行する。
// ログアウトすると、このユーザーのほかのログインもすべて切れるため、login.spec.ts とは別のユーザーを使う
const EMAIL = 'bbb@example.com'
const PASSWORD = 'Password123'

const screenshot = (page: Page, name: string) =>
  page.screenshot({ path: test.info().outputPath(`${name}.png`), fullPage: true })

test('ヘッダーのボタンでログアウトすると、ログイン画面に移り、成功のトーストが出る。戻るボタンでもログイン後の画面は表示されない', async ({
  page,
}) => {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill(EMAIL)
  await page.getByLabel('パスワード').fill(PASSWORD)
  await page.getByRole('button', { name: 'ログイン' }).click()
  await expect(page).toHaveURL('/tickets')
  // 戻るボタンでチケット一覧に戻れる履歴を作る（同じ URL を開くと、ブラウザが履歴を置き換えるため、
  // クエリを付けて別の URL にする）
  await page.goto('/tickets?e2e=history')
  await expect(page.getByRole('heading', { name: 'Ticket 一覧' })).toBeVisible()

  // すべてのページのヘッダーに、ログアウトのボタンがある（受け入れ要件 1）
  const header = page.getByRole('banner')
  await expect(header.getByRole('button', { name: 'ログアウト' })).toBeVisible()
  await screenshot(page, '01-header')

  // ログアウトすると、ログイン画面に移る（受け入れ要件 2・3）
  await header.getByRole('button', { name: 'ログアウト' }).click()
  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('heading', { name: 'ログイン' })).toBeVisible()
  // ログイン画面に移ってから、成功のトーストが出る（受け入れ要件 4）
  await expect(page.getByText('ログアウトしました')).toBeVisible()
  await screenshot(page, '02-logged-out')

  // 戻るボタンでチケット一覧を開こうとしても、ログイン画面に移る（受け入れ要件 5）。
  // 戻る先はログイン直後の別のページの読み込みで、ブラウザがメモリから復元する（bfcache）か、
  // 読み込み直すかは、ブラウザの判断による。どちらでもログイン画面に移ることを確かめる
  await page.goBack()
  await expect(page).toHaveURL('/login')
  await expect(page.getByRole('heading', { name: 'ログイン' })).toBeVisible()

  // URL を直接開いても（再読み込みと同じ）、ログイン画面に移る。BE でもログインが切れている
  await page.goto('/tickets')
  await expect(page).toHaveURL('/login')
  // 再読み込みでは、成功のトーストを出し直さない
  await expect(page.getByText('ログアウトしました')).toHaveCount(0)
})
