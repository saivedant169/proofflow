import { test, expect } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'
import { appendFileSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Evidence, ImportedWorkspaceState, SourceName } from '../src/lib/types'

// Workflow mutations use browser controls. Direct HTTP inspects server state
// and probes one expected refresh refusal when the browser disables its button.
// No success response, calculation, graph, or report value is mocked.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const fixtures = path.join(root, 'fixtures/browser_csv_v1')
const manifest = JSON.parse(readFileSync(path.join(fixtures, 'acceptance_manifest.json'), 'utf8'))
const normalURL = process.env.PROOFFLOW_E2E_BASE_URL!
const faultURL = process.env.PROOFFLOW_E2E_FAULT_URL!
const runOutput = process.env.PROOFFLOW_E2E_RUN_DIR!
const csv = (name: string) => readFileSync(path.join(fixtures, name), 'utf8')
const normalCSV = csv('valid_non_eu.csv')
const correctedCSV = normalCSV.replace('10000,1000,3', '12000,1500,3')
const errors = new WeakMap<Page, string[]>()
const expectedNetworkErrors = new WeakMap<Page, Set<string>>()
const pendingEvidence = new WeakMap<TestInfo, Record<string, unknown>>()

function watch(page: Page) {
  if (errors.has(page)) return
  errors.set(page, [])
  expectedNetworkErrors.set(page, new Set())
  page.on('pageerror', error => errors.get(page)!.push(error.message))
  page.on('console', message => {
    if (message.type() !== 'error' && message.type() !== 'warning') return
    const location = message.location().url
    if (location && !location.startsWith(normalURL) && !location.startsWith(faultURL)) return
    const pathname = location ? new URL(location).pathname : ''
    if (expectedNetworkErrors.get(page)!.has(pathname) && message.text().startsWith('Failed to load resource:')) return
    errors.get(page)!.push(message.text())
  })
}
function expectedFailure(page: Page, pathname: string) { expectedNetworkErrors.get(page)!.add(pathname) }
async function appHealthy(page: Page) {
  await expect(page).toHaveTitle(/ProofFlow/)
  await expect(page.getByRole('heading', { name: 'Keep revenue reports current', exact: true })).toBeVisible()
  await expect(page.locator('vite-error-overlay, nextjs-portal')).toHaveCount(0)
  expect(errors.get(page), 'Unexplained application console/runtime errors').toEqual([])
}
async function open(page: Page, url = normalURL) {
  watch(page)
  await page.goto(url)
  await expect(page.getByRole('button', { name: 'Change a source', exact: true })).toBeEnabled()
  expect(new URL(page.url()).origin).toBe(url)
  await appHealthy(page)
}
async function postThroughUI(page: Page, endpoint: string, action: () => Promise<unknown>, status = 200) {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === endpoint && response.request().method() === 'POST')
  await action()
  const response = await pending
  expect(response.status(), `${endpoint} status`).toBe(status)
  return response.json()
}
async function snapshot(page: Page): Promise<ImportedWorkspaceState> {
  const response = await page.request.get(`${new URL(page.url()).origin}/api/import/state`)
  expect(response.status()).toBe(200)
  const state = await response.json() as ImportedWorkspaceState
  expect(state.mode).toBe('guided_csv_import')
  expect(state.backend.fallback).toBe(false)
  expect(state.backend.engine).toBe('HydraDB OSS')
  expect(state.backend.native_queries).toBeGreaterThan(0)
  return state
}
function artifact(state: ImportedWorkspaceState, logicalID: string) {
  const node = state.graph.nodes.find(item => item.logical_id === logicalID && item.current_head)
  expect(node, `Current artifact ${logicalID}`).toBeTruthy()
  return node!
}
function sourceIDs(state: ImportedWorkspaceState) {
  return state.dataset.sources.map(source => [source.name, source.id]).sort()
}
function source(state: ImportedWorkspaceState, name: SourceName) {
  const entry = state.dataset.sources.find(item => item.name === name)
  expect(entry?.id, `Current ${name} source`).toBeTruthy()
  return entry!
}
function artifactIDs(state: ImportedWorkspaceState) {
  return state.graph.nodes.filter(node => node.kind === 'artifact' && node.current_head).map(node => node.id).sort()
}
function account(state: ImportedWorkspaceState, preflight: number, recorded: number, verification: number) {
  expect(state.last_operation).toMatchObject({
    preflight_calculation_count: preflight, recorded_tool_call_count: recorded,
    verification_calculation_count: verification, total_calculation_count: preflight + recorded + verification,
  })
}
function currentValues(state: ImportedWorkspaceState, company: number, regional: number) {
  expect(state.reports.map(report => [report.key, report.state, report.claims.length, report.claims[0].value])).toEqual([
    ['company', 'current', 1, company], ['region', 'current', 1, regional],
  ])
}
async function money(page: Page, company: string, regional: string, region = 'NORTH') {
  const companyValue = page.getByRole('button', { name: 'Inspect evidence for Company net revenue', exact: true }).locator('strong')
  const regionalValue = page.getByRole('button', { name: `Inspect evidence for ${region} net revenue`, exact: true }).locator('strong')
  await expect(companyValue.or(regionalValue), 'Rendered company and regional revenue').toHaveText([company, regional])
}
async function withheld(page: Page, label = 'Awaiting refresh') {
  const metrics = page.locator('.report-panel .metric')
  await expect(metrics).toHaveCount(2)
  await expect(metrics.locator('strong')).toHaveText([label, label])
  await expect(metrics.locator('.historical')).toHaveCount(2)
  await expect(metrics.locator('.metric-current')).toHaveCount(0)
}
async function drawer(page: Page, update = false) {
  await page.getByRole('button', { name: update ? 'Update CSV' : 'Use your data', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
}
async function supply(page: Page, { file = 'valid_non_eu.csv', text, rate = '1.20', currency = 'EUR', region = 'NORTH', update = false }: {
  file?: string; text?: string; rate?: string; currency?: string; region?: string; update?: boolean
} = {}) {
  if (text !== undefined) await page.getByLabel('1. Supply one CSV', { exact: true }).fill(text)
  else await page.getByLabel('Upload UTF-8 CSV', { exact: true }).setInputFiles(path.join(fixtures, file))
  await page.getByLabel(`${currency} → USD`, { exact: true }).fill(rate)
  if (!update) await page.getByLabel('Region for the second report', { exact: true }).fill(region)
}
async function preview(page: Page) {
  const result = await postThroughUI(page, '/api/import/preview', () => page.getByRole('button', { name: 'Validate CSV', exact: true }).click())
  expect(result).toMatchObject({ valid: true, persisted: false, row_count: 2, recorded_tool_calls: 0,
    accounting: { preflight_calculation_count: 8, recorded_tool_call_count: 0, verification_calculation_count: 0, total_calculation_count: 8 } })
  await expect(page.getByRole('region', { name: 'Validated CSV preview' })).toContainText('8 validation calculations · 0 recorded tool calls')
  return result
}
async function create(page: Page, fixture = 'valid_non_eu.csv', region = 'NORTH', currency = 'EUR', rate = '1.20') {
  await drawer(page)
  await expect(page.getByLabel('EUR → USD', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('GBP → USD', { exact: true })).toHaveValue('')
  await supply(page, { file: fixture, region, currency, rate })
  await preview(page)
  const created = await postThroughUI(page, '/api/import/create', () => page.getByRole('button', { name: 'Create reports', exact: true }).click()) as ImportedWorkspaceState
  await expect(page.getByRole('dialog')).toHaveCount(0)
  account(created, 8, 8, 11)
  return created
}
async function update(page: Page, rate = '1.30', text = normalCSV, status = 200) {
  await drawer(page, true)
  await supply(page, { text, rate, update: true })
  await preview(page)
  if (status !== 200) expectedFailure(page, '/api/import/update')
  const result = await postThroughUI(page, '/api/import/update', () => page.getByRole('button', { name: 'Publish correction', exact: true }).click(), status)
  if (status === 200) await expect(page.getByRole('dialog')).toHaveCount(0)
  return result as ImportedWorkspaceState
}
async function refresh(page: Page) {
  return await postThroughUI(page, '/api/import/refresh', () => page.getByRole('button', { name: 'Refresh affected', exact: true }).click()) as ImportedWorkspaceState
}
function record(info: TestInfo, evidence: Record<string, unknown>) {
  pendingEvidence.set(info, evidence)
}

test.beforeAll(() => {
  for (const [name, frozen] of Object.entries(manifest.files) as [string, { bytes: number; sha256: string }][]) {
    const contents = readFileSync(path.join(fixtures, name))
    expect(contents.length, name).toBe(frozen.bytes)
    expect(createHash('sha256').update(contents).digest('hex'), name).toBe(frozen.sha256)
  }
})
test.afterEach(async ({ page }, info) => {
  if (info.status === 'passed' && !page.isClosed()) {
    await page.screenshot({ path: info.outputPath('final.png'), fullPage: false })
    await appHealthy(page)
    const evidence = pendingEvidence.get(info)
    if (evidence) appendFileSync(path.join(runOutput, 'assertions.jsonl'), JSON.stringify({ test: info.title, ...evidence }) + '\n', { mode: 0o600 })
  }
})

test('CSV upload, preview and create persist real current reports across reload', async ({ page }, info) => {
  await open(page)
  await drawer(page)
  await expect(page.getByLabel('EUR → USD', { exact: true })).toHaveValue('')
  await supply(page)
  const validated = await preview(page)
  expect(validated.content_sha256).toBe(manifest.files['valid_non_eu.csv'].sha256)
  expect((await page.request.get(`${normalURL}/api/import/state`)).status()).toBe(404)
  const initial = await postThroughUI(page, '/api/import/create', () => page.getByRole('button', { name: 'Create reports', exact: true }).click()) as ImportedWorkspaceState
  await expect(page.getByRole('dialog')).toHaveCount(0)
  account(initial, 8, 8, 11)
  currentValues(initial, 30800, 10800)
  await money(page, '$308.00', '$108.00')
  await expect(page.locator('.import-accounting')).toContainText('8 validation calculations + 8 recorded tool calls + 11 check calculations = 27')
  await page.reload()
  await money(page, '$308.00', '$108.00')
  const restored = await snapshot(page)
  expect(restored.generation).toBe(initial.generation)
  expect(artifactIDs(restored)).toEqual(artifactIDs(initial))
  await drawer(page, true)
  await expect(page.getByLabel('1. Supply one CSV', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('EUR → USD', { exact: true })).toHaveValue('1.2')
  await page.getByRole('dialog').getByRole('button', { name: 'Close panel', exact: true }).click()
  record(info, { values_cents: [30800, 10800], preview_calculations: 8, create_accounting: [8, 8, 11], reload_preserved_generation: true })
})

test('FX correction withholds values, survives reload, refreshes four tools and preserves a reorder', async ({ page }, info) => {
  await open(page)
  const initial = await create(page)
  const support = artifact(initial, 'import:metric:support')
  const fxBefore = source(initial, 'fx').id
  const stale = await update(page)
  account(stale, 8, 0, 0)
  expect(source(stale, 'fx').id).not.toBe(fxBefore)
  for (const name of ['orders', 'refunds', 'tickets'] as const) {
    expect(source(stale, name).id).toBe(source(initial, name).id)
  }
  expect(stale.impact.changed_source_ids).toEqual([fxBefore])
  expect(stale.impact.affected_artifacts.map(item => item.logical_id).sort()).toEqual([
    'import:metric:company', 'import:metric:regional', 'import:report:company', 'import:report:region',
  ])
  expect(stale.reports.every(report => report.claims[0].value === null)).toBe(true)
  await withheld(page)
  await expect(page.locator('.metric-main .historical')).toHaveText('Previously $308.00')
  const evidenceResponse = page.waitForResponse(response => new URL(response.url()).pathname.startsWith('/api/import/evidence/'))
  await page.getByRole('button', { name: 'Inspect evidence for NORTH net revenue', exact: true }).click()
  const response = await evidenceResponse
  expect(response.status()).toBe(200)
  const evidence = await response.json() as Evidence
  const regionalBefore = initial.reports[1].claims[0].artifact_id
  const lineage = evidence.paths.find(item => item.source_id === fxBefore && item.target_id === regionalBefore)
  expect(lineage, 'Native path from the prior FX source to the withheld regional artifact').toBeDefined()
  expect(lineage!.nodes[0]).toMatchObject({ id: fxBefore, label: 'Explicit exchange rates', kind: 'source' })
  expect(lineage!.nodes.at(-1)).toMatchObject({ id: regionalBefore, kind: 'artifact' })
  expect(lineage!.nodes.some(node => node.kind === 'execution')).toBe(true)
  expect(lineage!.edges.map(edge => [edge.source, edge.target])).toEqual(
    lineage!.nodes.slice(1).map((node, index) => [lineage!.nodes[index].id, node.id]),
  )
  await expect(page.getByRole('dialog').getByText('Explicit exchange rates', { exact: true })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: 'Close panel', exact: true }).click()
  await page.reload()
  await withheld(page)
  expect((await snapshot(page)).generation).toBe(initial.generation)
  const fresh = await refresh(page)
  account(fresh, 0, 4, 11)
  await money(page, '$317.00', '$117.00')
  currentValues(fresh, 31700, 11700)
  expect(artifact(fresh, 'import:metric:support').id).toBe(support.id)
  const reordered = await update(page, '1.30', csv('reordered_non_eu.csv'))
  account(reordered, 8, 0, 0)
  expect(reordered.last_operation.noop).toBe(true)
  expect(reordered.dataset.source_csv_sha256).not.toBe(fresh.dataset.source_csv_sha256)
  expect(sourceIDs(reordered)).toEqual(sourceIDs(fresh))
  expect(artifactIDs(reordered)).toEqual(artifactIDs(fresh))
  expect(reordered.executions.map(execution => execution.id)).toEqual(fresh.executions.map(execution => execution.id))
  await expect(page.getByRole('button', { name: 'Refresh affected', exact: true })).toBeDisabled()
  await expect(page.locator('.import-accounting')).toContainText('Canonical sources unchanged.')
  await page.reload()
  await money(page, '$317.00', '$117.00')
  record(info, { stale_values_withheld: true, native_evidence_path: true, refresh_recorded_calls: 4, unchanged_support_id: true, reordered_recorded_calls: 0, reorder_validation_calls: 8 })
})

test('Malformed and oversized CSV invalidate readiness without replacing the current workspace', async ({ page }, info) => {
  await open(page)
  const initial = await create(page)
  await drawer(page, true)
  await supply(page, { text: normalCSV, update: true })
  await preview(page)
  await supply(page, { text: csv('malformed.csv'), update: true })
  await expect(page.getByRole('region', { name: 'Validated CSV preview' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Publish correction', exact: true })).toHaveCount(0)
  expectedFailure(page, '/api/import/preview')
  await postThroughUI(page, '/api/import/preview', () => page.getByRole('button', { name: 'Validate CSV', exact: true }).click(), 400)
  await expect(page.getByRole('alert')).toContainText('gross_cents')
  await expect(page.getByRole('button', { name: 'Publish correction', exact: true })).toHaveCount(0)
  await supply(page, { text: normalCSV, update: true })
  await preview(page)
  let publicationRequests = 0
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/import/update') publicationRequests++ })
  await page.getByLabel('Upload UTF-8 CSV', { exact: true }).setInputFiles(path.join(fixtures, 'oversized.csv'))
  await expect(page.getByRole('alert')).toContainText('exceeds 1 MiB')
  await expect(page.getByRole('region', { name: 'Validated CSV preview' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Publish correction', exact: true })).toHaveCount(0)
  expect(publicationRequests).toBe(0)
  await page.getByRole('dialog').getByRole('button', { name: 'Close panel', exact: true }).click()
  await page.reload()
  await money(page, '$308.00', '$108.00')
  const preserved = await snapshot(page)
  expect(sourceIDs(preserved)).toEqual(sourceIDs(initial))
  expect(artifactIDs(preserved)).toEqual(artifactIDs(initial))
  record(info, { malformed_http_status: 400, oversized_rejected_by_browser: true, oversized_server_status_claimed: false, publication_requests: 0, existing_artifacts_preserved: true })
})

test('Isolated browsers retain separate reports and zero-support mobile data without leakage', async ({ page, browser }, info) => {
  await open(page)
  const first = await create(page)
  const other = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' })
  const mobile = await other.newPage()
  try {
    await open(mobile)
    const second = await create(mobile, 'valid_zero_support.csv', 'APAC', 'GBP', '1.25')
    expect(first.session_id).not.toBe(second.session_id)
    currentValues(second, 16375, 9375)
    await money(mobile, '$163.75', '$93.75', 'APAC')
    await expect(mobile.locator('.report-panel .metric')).toHaveCount(2)
    await expect(mobile.getByRole('button', { name: /Inspect evidence for .*support/i })).toHaveCount(0)
    const privateEvidence = `${normalURL}/api/import/evidence/${encodeURIComponent(first.reports[0].claims[0].artifact_id)}`
    expect((await page.request.get(privateEvidence)).status()).toBe(200)
    const foreign = await other.request.get(privateEvidence)
    expect(foreign.status()).toBe(404)
    await update(page)
    await mobile.reload()
    await money(mobile, '$163.75', '$93.75', 'APAC')
    const unchanged = await snapshot(mobile)
    expect(unchanged.generation).toBe(second.generation)
    expect(artifactIDs(unchanged)).toEqual(artifactIDs(second))
    const dimensions = await mobile.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth }))
    expect(dimensions.page).toBeLessThanOrEqual(dimensions.viewport)
    await mobile.screenshot({ path: info.outputPath('mobile.png'), fullPage: false })
    await appHealthy(mobile)
    record(info, { isolated_contexts: 2, foreign_evidence_status: 404, zero_support_claim_omitted: true, mobile_viewport: [390, 844], page_width: dimensions.page, independent_reload_preserved: true })
  } finally { await other.close() }
})

test('Lost mutation and reconciliation responses fail closed, then reload recovers actual stale state', async ({ page }, info) => {
  await open(page)
  await create(page)
  let committed: ImportedWorkspaceState | null = null
  let failedRead = false
  expectedFailure(page, '/api/import/update')
  expectedFailure(page, '/api/import/state')
  await page.route('**/api/import/update', async route => {
    const actual = await route.fetch()
    expect(actual.status()).toBe(200)
    committed = await actual.json()
    await route.abort('failed') // A real completed mutation; only its browser response is lost.
  }, { times: 1 })
  await page.route('**/api/import/state', async route => {
    if (committed && !failedRead) { failedRead = true; await route.abort('failed') }
    else await route.continue()
  })
  await drawer(page, true)
  await supply(page, { text: normalCSV, rate: '1.30', update: true })
  await preview(page)
  await page.getByRole('button', { name: 'Publish correction', exact: true }).click()
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Could not reach ProofFlow')
  expect(committed).not.toBeNull()
  expect(failedRead).toBe(true)
  await page.getByRole('dialog').getByRole('button', { name: 'Close panel', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Current evidence is unavailable.' })).toBeVisible()
  await expect(page.locator('.report-panel')).toHaveCount(0)
  await page.unroute('**/api/import/state')
  await page.reload()
  await withheld(page)
  const restored = await snapshot(page)
  expect(restored.impact.affected_artifacts).toHaveLength(4)
  const recovered = await refresh(page)
  account(recovered, 0, 4, 11)
  await money(page, '$317.00', '$117.00')
  record(info, { mutation_executed_on_real_backend: true, dropped_update_response: true, dropped_reconciliation_response: true, old_current_panel_removed: true, reload_recovered_stale_state: true })
})

test('Real partial source publication stays blocked across reload and recovers through full CSV resubmission', async ({ page }, info) => {
  await open(page, faultURL)
  const initial = await create(page)
  const support = artifact(initial, 'import:metric:support')
  await update(page)
  await refresh(page)
  await expect(page.locator('.refresh-banner')).toContainText('Fresh recomputation matches.')
  const beforeFault = await snapshot(page)
  expect(beforeFault.incomplete_update).toBe(false)
  currentValues(beforeFault, 31700, 11700)
  await update(page, '1.30', correctedCSV, 503)
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: 'Close panel', exact: true }).click()
  await expect(page.getByText('Source publication is incomplete.', { exact: false })).toBeVisible()
  await withheld(page, 'Unavailable')
  await expect(page.locator('.refresh-banner')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Refresh affected', exact: true })).toBeDisabled()
  const partial = await snapshot(page)
  expect(partial.incomplete_update).toBe(true)
  expect(partial.dataset.source_csv_sha256).toBe(beforeFault.dataset.source_csv_sha256)
  expect(source(partial, 'orders').id).not.toBe(source(beforeFault, 'orders').id)
  for (const name of ['refunds', 'fx', 'tickets'] as const) {
    expect(source(partial, name).id).toBe(source(beforeFault, name).id)
  }
  const faultEvents = readFileSync(process.env.PROOFFLOW_E2E_FAULT_LOG!, 'utf8').trim().split('\n').map(line => JSON.parse(line))
  expect(faultEvents).toHaveLength(1)
  expect(faultEvents[0]).toMatchObject({
    event: 'injected_failure_after_committed_csv_orders',
    logical_id: 'source:csv:orders',
    previous_source_id: source(beforeFault, 'orders').id,
    committed_source_id: source(partial, 'orders').id,
    committed_content_hash: source(partial, 'orders').content_hash,
    source_head_verified: true,
    original_set_source_returned: true,
    graph_adapter: 'HydraGraph',
    fault_scope: 'test_process_only',
  })
  await page.reload()
  await withheld(page, 'Unavailable')
  await expect(page.locator('.refresh-banner')).toHaveCount(0)
  const reloaded = await snapshot(page)
  expect(reloaded.incomplete_update).toBe(true)
  expect(sourceIDs(reloaded)).toEqual(sourceIDs(partial))
  await page.getByRole('button', { name: 'Inspect evidence for NORTH net revenue', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('prior artifact evidence, not a repaired report')
  await expect(page.getByRole('dialog')).toContainText('Historical stored value')
  await page.getByRole('dialog').getByRole('button', { name: 'Close panel', exact: true }).click()
  const refused = await page.request.post(`${faultURL}/api/import/refresh`, { data: {} })
  expect(refused.status()).toBe(409)
  const resubmitted = await update(page, '1.30', correctedCSV)
  expect(resubmitted.incomplete_update).toBe(false)
  expect(source(resubmitted, 'orders').id).toBe(source(partial, 'orders').id)
  expect(source(resubmitted, 'refunds').id).not.toBe(source(partial, 'refunds').id)
  await withheld(page)
  const recovered = await refresh(page)
  account(recovered, 0, 7, 11)
  currentValues(recovered, 33650, 13650)
  expect(artifact(recovered, 'import:metric:support').id).toBe(support.id)
  await money(page, '$336.50', '$136.50')
  record(info, { real_hydra_fault_events: faultEvents.length, fault_injection: 'test-only exception after committed changed orders source', orders_commit_matches_fault_event: true, refunds_unchanged_until_resubmission: true, update_http_status: 503, refresh_refusal_status: 409, incomplete_persisted_after_reload: true, recovered_values_cents: [33650, 13650], recorded_refresh_calls: 7, unchanged_support_id: true })
})
