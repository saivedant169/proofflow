import { expect, test } from '@playwright/test'
import type { Download, Page, TestInfo } from '@playwright/test'
import { appendFileSync, readFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import type { ImportedWorkspaceState, ImportExport, ImportExportRequest } from '../../src/lib/types'

const csv = readFileSync(new URL('../../../fixtures/browser_csv_v1/valid_non_eu.csv', import.meta.url), 'utf8')
const origin = process.env.PROOFFLOW_E2E_BASE_URL!
const exportPath = '/api/import/export'
const statePath = '/api/import/state'
const runOutput = process.env.PROOFFLOW_E2E_RUN_DIR!
const testEvidence = new WeakMap<TestInfo, Record<string, unknown>>()

test.afterEach(({}, info) => {
  const evidence = testEvidence.get(info)
  if (info.status === 'passed' && evidence) {
    appendFileSync(path.join(runOutput, 'assertions.jsonl'), JSON.stringify({ test: info.title, ...evidence }) + '\n', { mode: 0o600 })
  }
})

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

async function publish(page: Page, correction: boolean, {
  csvText = csv, eurRate = correction ? '1.30' : '1.20', gbpRate,
}: { csvText?: string; eurRate?: string; gbpRate?: string } = {}) {
  await page.getByRole('button', { name: correction ? 'Update CSV' : 'Use your data', exact: true }).click()
  await page.getByLabel('1. Supply one CSV', { exact: true }).fill(csvText)
  await page.getByLabel('EUR → USD', { exact: true }).fill(eurRate)
  if (gbpRate) await page.getByLabel('GBP → USD', { exact: true }).fill(gbpRate)
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

async function expectDownload(page: Page, state: ImportedWorkspaceState, company: string, region: string, sourceCSV = csv) {
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
  for (const line of sourceCSV.trim().split('\n')) expect(text).not.toContain(line)
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
    testEvidence.set(info, {
      initial_values_cents: [30800, 10800], refreshed_values_cents: [31700, 11700],
      second_tab_published_correction: true, stale_export_status: 409, refused_attempt_download_events: 0,
      stale_values_withheld: true, new_report_heads: true, downloaded_server_text: true,
      file_contains_check_time_and_artifact_ids: true, file_excludes_csv_and_credentials: true,
      snapshot_note_cleared_on_workspace_switch: true, mobile_viewports: [[390, 844], [320, 844]],
    })
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
  testEvidence.set(info, {
    browser_injected_export_status: 503, browser_injected_reconciliation_failure: true,
    download_events_before_reload: 0, reports_withheld_until_reload: true, restored_values_cents: [30800, 10800],
  })
})

test('large CSV revenues preserve exact cents in the reports, evidence, and download', async ({ page }, info) => {
  const errors = observe(page)
  // Nine maximum-size orders and one smaller order per region. NORTH rounds
  // to a safe integer cent amount whose dollar division used to round again.
  const csvText = [
    'order_id,region,currency,gross_cents',
    ...Array.from({ length: 9 }, (_, i) => `large-north-${i},NORTH,EUR,1000000000000`),
    'large-north-tail,NORTH,EUR,7199254741',
    ...Array.from({ length: 9 }, (_, i) => `large-south-${i},SOUTH,GBP,1000000000000`),
    'large-south-tail,SOUTH,GBP,928007452591',
  ].join('\n')
  const company = '$100,000,000,000,000.01'
  const region = '$90,071,992,547,409.01'
  await page.goto('/')
  const state = await publish(page, false, { csvText, eurRate: '999.999999999989', gbpRate: '100' })
  expect(state.backend).toMatchObject({ engine: 'HydraDB OSS', fallback: false })
  expect(state.backend.native_queries).toBeGreaterThan(0)
  const metrics = page.locator('.report-panel .metric strong')
  await expect(metrics).toHaveText([company, region])
  expect(state.reports[0].claims[0]).toMatchObject({ value: '10000000000000001', saved_value: '10000000000000001' })
  expect(state.reports[1].claims[0]).toMatchObject({ value: 9007199254740901, saved_value: 9007199254740901 })
  await expectDownload(page, state, company, region, csvText)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: info.outputPath('exact-current-cents.png') })

  await page.getByRole('button', { name: 'Inspect evidence for Company net revenue', exact: true }).click()
  const evidence = page.getByRole('dialog')
  await evidence.getByText('Historical stored value', { exact: true }).click()
  await expect(evidence.locator('pre').last()).toHaveText(/"usd_cents": "10000000000000001"/)
  await page.screenshot({ path: info.outputPath('exact-evidence-cents.png') })
  await evidence.getByRole('button', { name: 'Close panel', exact: true }).click()

  await page.setViewportSize({ width: 320, height: 844 })
  await metrics.first().scrollIntoViewIfNeeded()
  await expect(metrics).toHaveText([company, region])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('exact-current-cents-320px.png') })
  await page.setViewportSize({ width: 1536, height: 1024 })

  const stale = await publish(page, true, { csvText, eurRate: '999.999999999990', gbpRate: '100' })
  expect(stale.reports[0].claims[0]).toMatchObject({ value: null, saved_value: '10000000000000001' })
  await expect(metrics).toHaveText(['Awaiting refresh', 'Awaiting refresh'])
  await expect(page.locator('.report-panel .historical')).toHaveText([`Previously ${company}`, `Previously ${region}`])
  await expect(downloadButton(page)).toBeDisabled()
  await checkPage(page, errors)
  testEvidence.set(info, {
    company_cents_decimal_string: '10000000000000001', regional_safe_integer_cents: 9007199254740901,
    displayed_and_downloaded_usd: [company, region], exact_evidence_display: true,
    exact_historical_values_after_correction: true, stale_download_disabled: true, mobile_viewport: [320, 844],
  })
})
