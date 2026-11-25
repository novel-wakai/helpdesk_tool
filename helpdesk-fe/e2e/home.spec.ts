import { expect, test } from '@playwright/test'

test('トップページで API に接続できている', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Novel HELPDESK' })).toBeVisible()
  await expect(page.getByText('接続OK')).toBeVisible()
})
