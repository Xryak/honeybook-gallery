import { DatabaseSync } from 'node:sqlite'
import { expect, test } from '@playwright/test'
import { E2E_DB } from '../../playwright.config'

/**
 * Read the most recent OTP code for a gallery straight from the backend's
 * SQLite DB — this stands in for "a human reading the code from the backend
 * terminal", with zero test-only code paths in the app itself.
 */
function latestOtp(gallery: string): string {
  const db = new DatabaseSync(E2E_DB, { readOnly: true })
  // Wait out (rather than throw on) a transient writer lock from the backend.
  db.exec('PRAGMA busy_timeout = 2000')
  try {
    const row = db
      .prepare('SELECT code FROM otp_codes WHERE gallery_id = ? ORDER BY id DESC LIMIT 1')
      .get(gallery) as { code: string } | undefined
    if (!row) throw new Error(`no OTP issued for ${gallery}`)
    return row.code
  } finally {
    db.close()
  }
}

/** Trigger an OTP the way the upstream system / CLI would, then read it back. */
async function getCode(request: import('@playwright/test').APIRequestContext, gallery: string) {
  const res = await request.post(`http://localhost:8000/api/galleries/${gallery}/otp`)
  expect(res.ok()).toBeTruthy()
  return latestOtp(gallery)
}

test('full flow: OTP entry → gallery → favorite persists across reload', async ({
  page,
  request,
}) => {
  await page.goto('/galleries/g_001')
  await expect(page.getByRole('heading', { name: 'Enter your code' })).toBeVisible()

  const code = await getCode(request, 'g_001')
  await page.getByLabel('Six digit verification code').fill(code)
  await page.getByRole('button', { name: 'Verify' }).click()

  // Gallery view: title + 10 thumbnails.
  await expect(page.getByRole('heading', { name: "Anna's Wedding" })).toBeVisible()
  const tiles = page.locator('.tile')
  await expect(tiles).toHaveCount(10)

  // Favorite the first photo.
  const first = tiles.first()
  await expect(first).toHaveAttribute('aria-pressed', 'false')
  await first.click()
  await expect(first).toHaveAttribute('aria-pressed', 'true')
  await expect(first).toHaveClass(/is-favorite/)

  // Reload: the session (localStorage token) and favorite both survive.
  await page.reload()
  await expect(page.getByRole('heading', { name: "Anna's Wedding" })).toBeVisible()
  await expect(page.locator('.tile').first()).toHaveAttribute('aria-pressed', 'true')

  // Toggle back off.
  await page.locator('.tile').first().click()
  await expect(page.locator('.tile').first()).toHaveAttribute('aria-pressed', 'false')
})

test('a wrong code shows the generic retry message', async ({ page, request }) => {
  await getCode(request, 'g_001') // ensure a (different) code exists
  await page.goto('/galleries/g_001')
  await page.getByLabel('Six digit verification code').fill('000000')
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByRole('alert')).toContainText("That code didn't work")
})

test('a token for g_001 does not unlock g_002', async ({ page, request }) => {
  // Authenticate g_001.
  await page.goto('/galleries/g_001')
  const code = await getCode(request, 'g_001')
  await page.getByLabel('Six digit verification code').fill(code)
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByRole('heading', { name: "Anna's Wedding" })).toBeVisible()

  // g_002 still demands its own code.
  await page.goto('/galleries/g_002')
  await expect(page.getByRole('heading', { name: 'Enter your code' })).toBeVisible()
})
