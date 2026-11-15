import { expect, test } from '@playwright/test'
import type { Download, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import type { ImportedWorkspaceState, ImportExport, ImportExportRequest } from '../../src/lib/types'

const csv = readFileSync(new URL('../../../fixtures/browser_csv_v1/valid_non_eu.csv', import.meta.url), 'utf8')
const origin = process.env.PROOFFLOW_E2E_BASE_URL!
const exportPath = '/api/import/export'
const statePath = '/api/import/state'

function downloadButton(page: Page) {
  return page.getByRole('button', { name: 'Download current reports', exact: true })
}

function observe(page: Page, expectedFailures: string[] = []) {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (message.type() !== 'error' && message.type() !== 'warning') return
    const location = message.location().url
    if (location && new URL(location).origin !== origin) return
    if (location && expectedFailures.includes(new URL(location).pathname)
      && message.text().startsWith('Failed to load resource:')) return
    errors.push(message.text())
  })
  return errors
}

async function checkPage(page: Page, errors: string[]) {
  await expect(page).toHaveTitle(/ProofFlow/)
  expect(new URL(page.url()).origin).toBe(origin)
  await expect(page.getByRole('heading', { name: 'A change should travel.' })).toBeVisible()
  await expect(page.locator('vite-error-overlay, nextjs-portal')).toHaveCount(0)
  expect(errors).toEqual([])
}

function waitForPost(page: Page, pathname: string) {
  return page.waitForResponse(response => new URL(response.url()).pathname === pathname && response.request().method() === 'POST')
}

async function publish(page: Page, correction: boolean) {
  await page.getByRole('button', { name: correction ? 'Update CSV' : 'Use your data', exact: true }).click()
  await page.getByLabel('1. Supply one CSV', { exact: true }).fill(csv)
  await page.getByLabel('EUR → USD', { exact: true }).fill(correction ? '1.30' : '1.20')
  if (!correction) await page.getByLabel('Region for the second report', { exact: true }).fill('NORTH')
  await page.getByRole('button', { name: 'Validate CSV', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Validated CSV preview' })).toBeVisible()
  const pending = waitForPost(page, correction ? '/api/import/update' : '/api/import/create')
  await page.getByRole('button', { name: correction ? 'Publish correction' : 'Create reports', exact: true }).click()
  const response = await pending
  expect(response.status()).toBe(200)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  return await response.json() as ImportedWorkspaceState
}

function requestFor(state: ImportedWorkspaceState): ImportExportRequest {
  return {
    generation: state.generation,
    report_ids: {
      company: state.reports.find(report => report.key === 'company')!.id,
      region: state.reports.find(report => report.key === 'region')!.id,
    },
  }
}

async function expectDownload(page: Page, state: ImportedWorkspaceState, company: string, region: string) {
  const pendingResponse = waitForPost(page, exportPath)
  const pendingDownload = page.waitForEvent('download')
  await downloadButton(page).click()
  const [response, download] = await Promise.all([pendingResponse, pendingDownload])
  expect(response.status()).toBe(200)
  expect(response.headers()['cache-control']).toBe('no-store')
  expect(response.request().postDataJSON()).toEqual(requestFor(state))
  const file = await response.json() as ImportExport
  expect(file).toMatchObject({ filename: 'proofflow-current-reports.txt', media_type: 'text/plain;charset=utf-8' })
  expect(download.suggestedFilename()).toBe(file.filename)
  const text = await readFile(await download.path(), 'utf8')
  expect(text).toBe(file.content)
  expect(text).toContain(`Checked at (UTC): ${file.checked_at}`)
  expect(text).toContain(`Company net revenue: ${company} USD`)
  expect(text).toContain(`Regional net revenue ('NORTH'): ${region} USD`)
  for (const report of state.reports) {
    expect(text).toContain(report.id)
    expect(text).toContain(report.claims[0].artifact_id)
  }
  for (const line of csv.trim().split('\n')) expect(text).not.toContain(line)
  expect(text.includes(state.session_id)).toBe(false)
  const tokenPath = process.env.PROOFFLOW_HYDRA_TOKEN_FILE
  const token = tokenPath ? readFileSync(tokenPath, 'utf8').trim() : process.env.PROOFFLOW_HYDRA_TOKEN?.trim()
  if (token) expect(text.includes(token)).toBe(false)
  const note = page.getByRole('status').filter({ hasText: 'Snapshot checked at' })
  await expect(note.locator('time')).toHaveAttribute('datetime', file.checked_at)
  await expect(note.locator('time')).toContainText('UTC')
  await expect(note).toContainText('This file does not update automatically.')
}

test('download checks the visible imported report heads and refuses a concurrent CSV correction', async ({ page }, info) => {
  const errors = observe(page, [exportPath])
  const downloads: Download[] = []
  page.on('download', download => downloads.push(download))
  await page.goto('/')
  await expect(downloadButton(page)).toHaveCount(0)
  const initial = await publish(page, false)
  expect(initial.backend).toMatchObject({ engine: 'HydraDB OSS', fallback: false })
  expect(initial.backend.native_queries).toBeGreaterThan(0)
  const metrics = page.locator('.report-panel .metric strong')
  await expect(metrics).toHaveText(['$308.00', '$108.00'])
  await expectDownload(page, initial, '$308.00', '$108.00')
  expect(downloads).toHaveLength(1)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: info.outputPath('initial-download.png') })

  // An opener gives the new tab the same initial workspace preference and session cookie.
  const popup = page.waitForEvent('popup')
  await page.evaluate(() => { window.open(location.href, '_blank') })
  const otherTab = await popup
  const otherErrors = observe(otherTab)
  try {
    const stale = await publish(otherTab, true)
    expect(stale.session_id).toBe(initial.session_id)
    expect(stale.generation).toBe(initial.generation)
    await checkPage(otherTab, otherErrors)
    await expect(downloadButton(otherTab)).toBeDisabled()
    await expect(metrics).toHaveText(['$308.00', '$108.00'])
    await expect(downloadButton(page)).toBeEnabled()
    const refused = waitForPost(page, exportPath)
    const reconciliation = page.waitForResponse(response => new URL(response.url()).pathname === statePath)
    await downloadButton(page).click()
    const response = await refused
    expect(response.status()).toBe(409)
    expect(response.request().postDataJSON()).toEqual(requestFor(initial))
    expect((await reconciliation).status()).toBe(200)
    await expect(page.getByRole('alert')).toContainText('No report file was downloaded.')
    await expect(metrics).toHaveText(['Awaiting refresh', 'Awaiting refresh'])
    await expect(downloadButton(page)).toBeDisabled()
    await expect(page.getByText('Snapshot checked at', { exact: false })).toHaveCount(0)
    expect(downloads).toHaveLength(1)
    await page.screenshot({ path: info.outputPath('download-refused.png') })

    const refreshed = waitForPost(page, '/api/import/refresh')
    await page.getByRole('button', { name: 'Refresh affected', exact: true }).click()
    const refreshResponse = await refreshed
    expect(refreshResponse.status()).toBe(200)
    const next = await refreshResponse.json() as ImportedWorkspaceState
    expect(requestFor(next).report_ids.company).not.toBe(requestFor(initial).report_ids.company)
    expect(requestFor(next).report_ids.region).not.toBe(requestFor(initial).report_ids.region)
    await expect(metrics).toHaveText(['$317.00', '$117.00'])
    await expectDownload(page, next, '$317.00', '$117.00')
    expect(downloads).toHaveLength(2)

    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 })
      await page.evaluate(() => window.scrollTo(0, 0))
      await expect(downloadButton(page)).toBeInViewport({ ratio: 1 })
      await expect(page.getByRole('status').filter({ hasText: 'Snapshot checked at' })).toBeInViewport({ ratio: 1 })
      expect(await page.locator('.report-export').evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true)
      await page.screenshot({ path: info.outputPath(`refreshed-${width}px.png`) })
    }

    await page.getByRole('button', { name: 'Guided demo', exact: true }).click()
    await expect(downloadButton(page)).toHaveCount(0)
    await page.getByRole('button', { name: 'Open your CSV', exact: true }).click()
    await expect(downloadButton(page)).toBeEnabled()
    await expect(page.getByText('Snapshot checked at', { exact: false })).toHaveCount(0)
    await checkPage(page, errors)
  } finally {
    await otherTab.close()
  }
})

test('export unavailable and a failed reconciliation keep reports withheld until reload', async ({ page }, info) => {
  const errors = observe(page, [exportPath, statePath])
  const downloads: Download[] = []
  page.on('download', download => downloads.push(download))
  await page.goto('/')
  await publish(page, false)
  // Inject delivery failures while leaving the real HydraDB-backed import intact.
  await page.route(`**${exportPath}`, route => route.fulfill({
    status: 503,
    json: { error: { code: 'backend_unavailable', message: 'HydraDB evidence is unavailable.' } },
  }), { times: 1 })
  await page.route(`**${statePath}`, route => route.abort('failed'), { times: 1 })
  const unavailable = waitForPost(page, exportPath)
  await downloadButton(page).click()
  expect((await unavailable).status()).toBe(503)
  await expect(page.getByRole('alert')).toContainText('No report file was downloaded. HydraDB evidence is unavailable.')
  await expect(page.getByRole('heading', { name: 'Current evidence is unavailable.' })).toBeVisible()
  await expect(downloadButton(page)).toBeDisabled()
  await expect(page.locator('.report-panel')).toHaveCount(0)
  expect(downloads).toHaveLength(0)
  await page.screenshot({ path: info.outputPath('export-unavailable.png') })
  await page.getByRole('button', { name: 'Reload state', exact: true }).click()
  await expect(downloadButton(page)).toBeEnabled()
  await expect(page.locator('.report-panel .metric strong')).toHaveText(['$308.00', '$108.00'])
  await checkPage(page, errors)
})
