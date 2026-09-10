import { test, expect } from '@playwright/test'

const longName = 'A long task name to check that small screens wrap text without hiding the controls'
const calendar = { date: '2026-09-10', today: '2026-09-10', timezone: 'Asia/Colombo',
  tasks: [{ id: 'test-task', name: longName, completed: false }],
  history: Array.from({ length: 7 }, (_, i) => ({ date: `2026-09-${String(i + 4).padStart(2, '0')}`, total: 100, completed_ids: Array.from({ length: 100 }, (_, n) => `id-${n}`) })) }

test.beforeEach(async ({ page }) => {
  // Test-browser interception only. Production code has no fake-auth switch.
  await page.route('**/src/supabase.ts', route => route.fulfill({ contentType: 'application/javascript', body: `
    export const supabase = { auth: {
      onAuthStateChange(callback) { let active = true; queueMicrotask(() => { if (active) callback('SIGNED_IN', { user: { id: 'test-user' }, access_token: 'test-only' }) }); return {data:{subscription:{unsubscribe(){active=false}}}} },
      signOut: async () => ({error:null}), signInWithOAuth: async () => ({error:null})
    } };
  ` }))
  await page.route('**/api/**', route => route.fulfill({ json: calendar }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: longName })).toBeVisible()
})

for (const width of [320, 390, 768, 1280]) {
  test(`layout fits ${width}px including large progress counts`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 850 })
    await expect(page.getByRole('button', { name: `Edit ${longName}` })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.getByRole('heading', { name: 'Your last 7 days' }).scrollIntoViewIfNeeded()
    const bars = page.locator('.week-day')
    await expect(bars).toHaveCount(7)
    for (const bar of await bars.all()) {
      expect(await bar.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
    }
    await page.screenshot({ path: testInfo.outputPath(`layout-${width}.png`), fullPage: true })
  })
}

test('keyboard opens and cancels editing, and modal Escape returns focus', async ({ page }) => {
  const edit = page.getByRole('button', { name: `Edit ${longName}` })
  await edit.focus()
  await page.keyboard.press('Enter')
  const input = page.getByRole('textbox', { name: 'Edit task' })
  await expect(input).toBeFocused()
  await input.fill('Unsaved keyboard draft')
  await page.keyboard.press('Escape')
  await expect(edit).toBeFocused()
  await page.getByRole('button', { name: `Delete ${longName}` }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(page.getByRole('button', { name: 'Delete task', exact: true })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: `Delete ${longName}` })).toBeFocused()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('failed save preserves the edit and offers recovery', async ({ page }) => {
  await page.route('**/api/days/**', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.getByRole('button', { name: `Edit ${longName}` }).click()
  const input = page.getByRole('textbox', { name: 'Edit task' })
  await input.fill('Draft retained after failure')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('alert')).toContainText('Could not save')
  await expect(input).toHaveValue('Draft retained after failure')
  await expect(page.getByRole('button', { name: 'Save changes' })).toBeEnabled()
})


test('slow reload announces loading and completes without clearing the current list', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/calendar?**', async route => { await gate; await route.fulfill({ json: calendar }) })
  await page.getByRole('button', { name: 'Reload tasks' }).click()
  await expect(page.getByRole('status')).toHaveText('Loading your day…')
  await expect(page.getByRole('heading', { name: longName })).toBeVisible()
  release()
  await expect(page.getByRole('status')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reload tasks' })).toBeEnabled()
})


test('deletion removes the row immediately and restores it if saving fails', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/days/**', async route => { await gate; await route.fulfill({ status: 503, json: { detail: 'Unavailable' } }) })
  await page.getByRole('button', { name: `Delete ${longName}` }).click()
  await page.getByRole('button', { name: 'Delete task', exact: true }).click()
  await expect(page.getByRole('heading', { name: longName })).toHaveCount(0)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  release()
  await expect(page.getByRole('alert')).toContainText('Could not save')
  await expect(page.getByRole('heading', { name: longName })).toBeVisible()
})
