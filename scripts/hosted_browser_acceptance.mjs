import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { lookup } from 'node:dns/promises'
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium, devices, expect as playwrightExpect } from '../frontend/node_modules/@playwright/test/index.mjs'

const origin = new URL('https://proofflow.arnavbule.in')
const root = new URL('../', import.meta.url)
const dist = new URL('frontend/dist/', root)
const fixtures = new URL('fixtures/browser_csv_v1/', root)
const statePath = '/api/import/state'
const exportPath = '/api/import/export'
const videoPath = '/walkthrough.mp4'
const timeout = 30_000
const expect = playwrightExpect.configure({ timeout: 15_000 })
const utcNow = () => new Date().toISOString()
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const url = path => new URL(path, origin).href
const button = (page, name) => page.getByRole('button', { name, exact: true })
const downloadButton = page => button(page, 'Download current reports')
const copyButton = page => button(page, 'Copy checked report')
const metrics = page => page.locator('.report-panel .metric strong')
const snapshotNote = page => page.getByRole('status').filter({ hasText: 'Snapshot checked at' })
const get = (page, path) => page.request.get(url(path), { maxRedirects: 0, timeout })
const hostedClipboard = process.platform === 'linux' && process.env.GITHUB_ACTIONS === 'true'
  && process.env.RUNNER_ENVIRONMENT === 'github-hosted'
const clipboardSentinel = 'ProofFlow hosted acceptance clipboard sentinel'

class CheckFailure extends Error {}

function check(condition, label) {
  if (!condition) throw new CheckFailure(label)
}

function same(left, right) {
  return JSON.stringify(left) === JSON.stringify(right)
}

process.umask(0o077)
const outputParent = process.env.PROOFFLOW_HOSTED_OUTPUT_DIR ?? tmpdir()
await mkdir(outputParent, { recursive: true, mode: 0o700 })
const output = await mkdtemp(join(outputParent, 'hosted-browser-'))
const receipt = {
  schema_version: 1,
  origin: origin.origin,
  started_at_utc: utcNow(),
  steps: {},
  screenshots: [],
  cleanup: {
    browser_contexts_opened: 0,
    browser_contexts_closed: 0,
    csv_creates_observed: 0,
    server_sessions: 'Fresh QA sessions expire under the service idle TTL.',
  },
}

function failure(error) {
  const line = error?.stack?.match(/hosted_browser_acceptance\.mjs:(\d+):\d+/)?.[1]
  return {
    cause: error instanceof CheckFailure ? error.message : error?.name === 'TimeoutError' ? 'Timed out' : 'Browser assertion or request failed',
    ...(line ? { script_line: Number(line) } : {}),
  }
}

async function step(name, action, dependencyPassed = true) {
  if (!dependencyPassed) {
    receipt.steps[name] = { status: 'skipped', cause: 'Earlier required check failed' }
    return false
  }
  try {
    receipt.steps[name] = { status: 'pass', ...await action() }
    console.log(`${name}: pass`)
    return true
  } catch (error) {
    const details = failure(error)
    receipt.steps[name] = { status: 'fail', ...details }
    console.error(`${name}: fail (${details.cause}, line ${details.script_line ?? 'unknown'})`)
    return false
  }
}

async function screenshot(page, name) {
  const filename = `${name}.png`
  const image = await page.screenshot({ path: join(output, filename), animations: 'disabled' })
  receipt.screenshots.push({ filename, sha256: sha256(image), bytes: image.length, viewport: page.viewportSize() })
}

async function withContext(browser, options, action) {
  const context = await browser.newContext({ serviceWorkers: 'block', ...options })
  receipt.cleanup.browser_contexts_opened++
  context.setDefaultTimeout(timeout)
  try {
    return await action(context)
  } finally {
    // Playwright removes downloaded files and its temporary profile on close.
    await context.close()
    receipt.cleanup.browser_contexts_closed++
  }
}

function provenance() {
  const env = process.env
  const sourceSha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
  const sourceWorktreeClean = execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).length === 0
  const hosted = env.GITHUB_ACTIONS === 'true'
  receipt.source_sha = sourceSha
  receipt.source_worktree_clean = sourceWorktreeClean
  receipt.runner = hosted ? {
    provider: 'GitHub Actions', environment: env.RUNNER_ENVIRONMENT, image_os: env.ImageOS,
    image_version: env.ImageVersion, operating_system: env.RUNNER_OS, architecture: env.RUNNER_ARCH,
    event: env.GITHUB_EVENT_NAME, repository: env.GITHUB_REPOSITORY, run_id: env.GITHUB_RUN_ID,
    run_attempt: env.GITHUB_RUN_ATTEMPT, workflow_ref: env.GITHUB_WORKFLOW_REF,
    run_url: `${env.GITHUB_SERVER_URL}/${env.GITHUB_REPOSITORY}/actions/runs/${env.GITHUB_RUN_ID}`,
  } : { provider: 'Local verification', operating_system: process.platform, architecture: process.arch }
  if (hosted) {
    check(env.RUNNER_ENVIRONMENT === 'github-hosted' && env.RUNNER_OS === 'Linux' && env.ImageOS === 'ubuntu24', 'Expected a GitHub-hosted Ubuntu 24.04 runner')
    check(sourceSha === env.GITHUB_SHA && sourceWorktreeClean && env.GITHUB_SERVER_URL === 'https://github.com', 'Clean source checkout matches the workflow SHA on GitHub')
  }
  check(env.NODE_TLS_REJECT_UNAUTHORIZED !== '0', 'Node TLS verification is enabled')
}

async function fetchPublic(path, headers) {
  return fetch(url(path), { headers, redirect: 'error', signal: AbortSignal.timeout(timeout) })
}

function buildAssetPaths(index) {
  const paths = [...new Set(index.toString('utf8').match(/\/assets\/[\w.-]+\.(?:js|css)(?=["'])/g))].sort()
  check(paths.some(path => path.endsWith('.js')) && paths.some(path => path.endsWith('.css')), 'Built HTML references a script and stylesheet')
  return paths
}

async function readBuildFile(path) {
  try {
    return await readFile(new URL(path, dist))
  } catch (error) {
    if (error.code === 'ENOENT') throw new CheckFailure('Required checked-out build file is absent. Run npm run build in frontend.')
    throw error
  }
}

async function publicDelivery() {
  const builtIndex = await readBuildFile('index.html')
  const builtAssets = new Map(await Promise.all(buildAssetPaths(builtIndex).map(async path => [path, await readBuildFile(path.slice(1))])))
  receipt.checked_out_build = {
    index_sha256: sha256(builtIndex),
    assets: [...builtAssets].map(([path, bytes]) => ({ path, bytes: bytes.length, sha256: sha256(bytes) })),
  }
  const hosts = await readFile('/etc/hosts', 'utf8')
  check(!hosts.split('\n').some(line => line.split('#')[0].trim().split(/\s+/).slice(1)
    .some(host => host.toLowerCase().replace(/\.$/, '') === origin.hostname)), 'Canonical hostname has no hosts-file override')
  const addresses = await lookup(origin.hostname, { all: true })
  check(addresses.length > 0, 'Canonical hostname resolves through the system resolver')

  const health = await fetchPublic('/health')
  const healthBody = await health.json()
  check(health.status === 200 && healthBody.status === 'ok' && healthBody.backend === 'HydraDB OSS', 'Health is 200 with a real HydraDB backend')
  const index = await fetchPublic('/')
  const servedIndex = Buffer.from(await index.arrayBuffer())
  check(index.status === 200 && index.headers.get('content-type')?.includes('text/html') && servedIndex.includes('ProofFlow'), 'Built ProofFlow HTML is served')
  const paths = buildAssetPaths(servedIndex)
  const servedAssets = await Promise.all(paths.map(async path => {
    const response = await fetchPublic(path)
    const bytes = Buffer.from(await response.arrayBuffer())
    const type = response.headers.get('content-type') ?? ''
    check(response.status === 200 && bytes.length > 0 && (path.endsWith('.css') ? type.includes('text/css') : type.includes('javascript')),
      'Referenced build asset is served with the expected content type')
    return { path, bytes, status: response.status }
  }))
  receipt.served_build = {
    index_sha256: sha256(servedIndex),
    assets: servedAssets.map(({ path, bytes, status }) => ({ path, bytes: bytes.length, sha256: sha256(bytes), status })),
  }
  check(servedIndex.equals(builtIndex), 'Hosted index HTML must match the checked-out build byte for byte')
  check(same(paths, [...builtAssets.keys()]) && servedAssets.every(({ path, bytes }) => bytes.equals(builtAssets.get(path))),
    'Hosted frontend asset paths and bytes must match the checked-out build')
  return {
    resolver: 'System DNS', address_families: [...new Set(addresses.map(address => address.family))],
    hosts_file_override: false, browser_resolver_override: false, tls_validation: 'Enabled',
    health: { status: health.status, backend: healthBody.backend }, byte_match_to_checked_out_build: true,
  }
}

async function mediaBytes() {
  const [full, range, poster, expectedVideo, expectedPoster] = await Promise.all([
    fetchPublic(videoPath), fetchPublic(videoPath, { Range: 'bytes=0-1023' }), fetchPublic('/walkthrough-poster.jpg'),
    readFile(new URL('video/proofflow-walkthrough.mp4', root)), readFile(new URL('video/poster.jpg', root)),
  ])
  const [video, prefix, image] = await Promise.all([full, range, poster].map(async response => Buffer.from(await response.arrayBuffer())))
  const contentRange = range.headers.get('content-range')
  check(full.status === 200 && full.headers.get('content-type') === 'video/mp4' && video.equals(expectedVideo), 'Hosted MP4 matches the checked-in video bytes')
  check(range.status === 206 && contentRange === `bytes 0-1023/${video.length}` && prefix.equals(video.subarray(0, 1024)), 'MP4 range has the expected headers and bytes')
  check(poster.status === 200 && poster.headers.get('content-type') === 'image/jpeg' && image.equals(expectedPoster), 'Hosted poster matches the checked-in image bytes')
  return {
    video: { status: full.status, bytes: video.length, sha256: sha256(video), range_status: range.status, content_range: contentRange, prefix_matches: true },
    poster: { status: poster.status, bytes: image.length, sha256: sha256(image) },
  }
}

async function playAndSeek(browser) {
  return withContext(browser, { viewport: { width: 1280, height: 800 } }, async context => {
    const page = await context.newPage()
    const response = await page.goto(url(videoPath), { waitUntil: 'domcontentloaded' })
    check(response?.ok() && page.url() === url(videoPath) && !response.request().redirectedFrom(), 'Browser opens the exact canonical MP4 URL')
    const video = page.locator('video')
    await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2)
    await video.evaluate(element => {
      element.muted = true
      void element.play().catch(() => {})
    })
    await page.waitForFunction(() => {
      const element = document.querySelector('video')
      return element && !element.paused && !element.error && element.currentTime >= 0.3
    })
    const before = await video.evaluate(element => ({ time: element.currentTime, duration: element.duration, width: element.videoWidth, height: element.videoHeight }))
    check(Math.abs(before.duration - 120) < 0.5 && before.width === 1920 && before.height === 1080, 'Expected walkthrough duration and resolution')
    await video.evaluate(element => { element.currentTime = 75 })
    await page.waitForFunction(() => {
      const element = document.querySelector('video')
      return element && !element.seeking && !element.paused && !element.error && element.currentTime >= 75.3
    })
    const after = await video.evaluate(element => {
      element.pause()
      return element.currentTime
    })
    await screenshot(page, 'walkthrough-seek')
    return { played_seconds: Number(before.time.toFixed(2)), seek_target_seconds: 75, continued_to_seconds: Number(after.toFixed(2)), duration_seconds: before.duration, dimensions: [before.width, before.height] }
  })
}

function watchErrors(page, expectedStaleExport = false) {
  const entries = []
  page.on('pageerror', () => entries.push('pageerror'))
  page.on('console', message => {
    if (!['warning', 'error'].includes(message.type())) return
    const location = message.location().url
    if (location && !location.startsWith(`${origin.origin}/`)) return
    if (expectedStaleExport && location === url(exportPath) && /^Failed to load resource:.*\b409\b/.test(message.text())) return
    entries.push(message.type())
  })
  return entries
}

async function openApp(page) {
  const response = await page.goto(url('/'), { waitUntil: 'domcontentloaded' })
  check(response?.status() === 200 && page.url() === url('/') && !response.request().redirectedFrom(), 'Browser opens the canonical app without redirection')
  await expect(page).toHaveTitle(/ProofFlow/)
  await expect(button(page, 'Change a source')).toBeEnabled()
  await expect(button(page, 'Use your data')).toBeEnabled()
  const assets = await page.locator('script[src^="/assets/"], link[href^="/assets/"]').evaluateAll(nodes =>
    [...new Set(nodes.map(node => node.getAttribute('src') ?? node.getAttribute('href')))].sort())
  check(same(assets, receipt.served_build.assets.map(asset => asset.path)), 'Browser application uses the recorded public build assets')
  const security = await response.securityDetails()
  check(/^TLS/.test(security?.protocol ?? ''), 'Browser reports a validated TLS connection')
  return security.protocol
}

function responseFor(page, path, method) {
  return page.waitForResponse(response => response.url() === url(path) && response.request().method() === method)
}

async function postFromUI(page, path, name) {
  const [response] = await Promise.all([responseFor(page, path, 'POST'), button(page, name).click()])
  check(response.status() === 200, `${path} expected 200, got ${response.status()}`)
  return response.json()
}

function reports(state) {
  return ['company', 'region'].map(key => state.reports.find(report => report.key === key))
}

function reportState(state, expectedStatus, expectedValues) {
  const selected = reports(state)
  check(state.reports.length === 2 && selected.every(report => report?.claims.length === 1), 'Workspace has one revenue claim per company and region report')
  const observed = selected.map(report => [report.state, report.claims[0].state, report.claims[0].value])
  check(same(observed, expectedValues.map(value => [expectedStatus, expectedStatus, value])), 'Expected API report and claim states and values')
  return observed.map(report => report[2])
}

function accounting(state, expected) {
  const op = state.last_operation
  const observed = [op.preflight_calculation_count, op.recorded_tool_call_count, op.verification_calculation_count, op.total_calculation_count]
  check(same(observed, [...expected, expected.reduce((total, count) => total + count, 0)]), 'Expected preflight, recorded call and verification counts')
  return { preflight: observed[0], recorded_calls: observed[1], verification: observed[2], total: observed[3] }
}

const source = (state, name) => state.dataset.sources.find(item => item.name === name)?.id
const support = state => state.graph.nodes.find(node => node.logical_id === 'import:metric:support' && node.current_head)?.id
const heads = state => state.graph.nodes.filter(node => node.kind === 'artifact' && node.current_head).map(node => node.id).sort()

function exportSelection(state) {
  const [company, region] = reports(state)
  return { generation: state.generation, report_ids: { company: company.id, region: region.id } }
}

async function importState(page) {
  const response = await get(page, statePath)
  check(response.status() === 200, 'Current imported workspace state is readable')
  const state = await response.json()
  check(state.mode === 'guided_csv_import' && state.backend.engine === 'HydraDB OSS' && !state.backend.fallback && state.backend.native_queries > 0,
    'Imported workspace uses native HydraDB queries')
  return state
}

async function preview(page, fixture, currency, rate, region) {
  const creating = Boolean(region)
  await button(page, creating ? 'Use your data' : 'Update CSV').click()
  await page.getByLabel('Upload UTF-8 CSV', { exact: true }).setInputFiles({ name: fixture.name, mimeType: 'text/csv', buffer: fixture.bytes })
  await page.getByLabel(`${currency} → USD`, { exact: true }).fill(rate)
  if (creating) await page.getByLabel('Region for the second report', { exact: true }).fill(region)
  const result = await postFromUI(page, '/api/import/preview', 'Validate CSV')
  check(result.valid && result.persisted === false && result.row_count === 2 && result.recorded_tool_calls === 0 &&
    result.accounting.preflight_calculation_count === 8 && result.content_sha256 === fixture.sha, 'Preview validates the frozen CSV without writing')
  await expect(page.getByRole('region', { name: 'Validated CSV preview' })).toContainText('8 validation calculations · 0 recorded tool calls')
}

async function publish(page, updating = false) {
  const state = await postFromUI(page, `/api/import/${updating ? 'update' : 'create'}`, updating ? 'Publish correction' : 'Create reports')
  if (!updating) receipt.cleanup.csv_creates_observed++
  await expect(page.getByRole('dialog')).toHaveCount(0)
  check(state.backend.engine === 'HydraDB OSS' && state.backend.fallback === false && state.backend.native_queries > 0, 'Write response reports native HydraDB queries')
  return state
}

function checkExportHeaders(response) {
  const headers = response.headers()
  check(headers['cache-control'] === 'no-store' && headers['content-type']?.startsWith('application/json') && !headers['set-cookie'], 'Export is JSON, uncachable and issues no session cookie')
}

async function checkedDownload(page, state, amounts, fixture) {
  const started = Date.now()
  const [response, download] = await Promise.all([
    responseFor(page, exportPath, 'POST'), page.waitForEvent('download'), downloadButton(page).click(),
  ])
  check(response.status() === 200 && same(response.request().postDataJSON(), exportSelection(state)), 'Successful export checks the visible report heads')
  checkExportHeaders(response)
  const serverFile = await response.json()
  const filename = 'proofflow-current-reports.txt'
  const path = await download.path()
  const bytes = await readFile(path)
  const content = bytes.toString('utf8')
  const checkedAt = serverFile.checked_at
  check(typeof checkedAt === 'string' && /(?:\+00:00|Z)$/.test(checkedAt) && Math.abs(Date.parse(checkedAt) - started) < 120_000, 'Export check time is recent UTC')
  check(serverFile.filename === filename && download.suggestedFilename() === filename && serverFile.media_type === 'text/plain;charset=utf-8', 'Browser download has expected filename and type')
  check(bytes.equals(Buffer.from(serverFile.content, 'utf8')) && content.includes(`Checked at (UTC): ${checkedAt}`), 'Downloaded UTF-8 bytes match the server checked snapshot')
  check(content.includes(`Company net revenue: ${amounts[0]} USD`) && content.includes(`Regional net revenue ('NORTH'): ${amounts[1]} USD`), 'Download contains the expected current company and NORTH amounts')
  check(reports(state).every(report => content.includes(report.id) && content.includes(report.claims[0].artifact_id)), 'Download includes both report and claim artifact IDs')
  const cookie = (await page.context().cookies(origin.origin)).find(item => item.name === 'proofflow_session')
  const excluded = [cookie?.value, state.session_id, state.generation, ...fixture.bytes.toString('utf8').trim().split('\n')]
  check(excluded.every(value => value && !content.includes(value)), 'Download excludes session secrets and raw CSV rows')
  await expect(snapshotNote(page).locator('time')).toHaveAttribute('datetime', checkedAt)
  await expect(snapshotNote(page).locator('time')).toContainText('UTC')
  await expect(snapshotNote(page)).toContainText('This file does not update automatically.')
  return { path, observation: { status: response.status(), filename, checked_at_utc: checkedAt, sha256: sha256(bytes), bytes: bytes.length, matches_server_bytes: true, matching_report_and_claim_ids: true, no_store: true } }
}

async function setClipboardSentinel(page) {
  await page.bringToFront()
  await page.evaluate(text => navigator.clipboard.writeText(text), clipboardSentinel)
  check(await page.evaluate(() => navigator.clipboard.readText()) === clipboardSentinel, 'Disposable browser clipboard contains its sentinel')
}

async function checkedCopy(page, state, amounts) {
  await setClipboardSentinel(page)
  const [response] = await Promise.all([responseFor(page, exportPath, 'POST'), copyButton(page).press('Enter')])
  check(response.status() === 200 && same(response.request().postDataJSON(), exportSelection(state)), 'Copy checks the visible report heads')
  checkExportHeaders(response)
  const snapshot = await response.json()
  await expect(snapshotNote(page)).toContainText('Report copied.')
  await expect(snapshotNote(page).locator('time')).toHaveAttribute('datetime', snapshot.checked_at)
  const content = await page.evaluate(() => navigator.clipboard.readText())
  check(content === snapshot.content && content.includes(`Checked at (UTC): ${snapshot.checked_at}`), 'Real clipboard contains the exact checked snapshot and UTC time')
  check(content.includes(`Company net revenue: ${amounts[0]} USD`) && content.includes(`Regional net revenue ('NORTH'): ${amounts[1]} USD`), 'Copied snapshot has the expected current amounts')
  check(reports(state).every(report => content.includes(report.id) && content.includes(report.claims[0].artifact_id)), 'Copied snapshot includes both report and claim artifact IDs')
  return { status: response.status(), exact_server_text: true, checked_at_utc: snapshot.checked_at, sha256: sha256(content) }
}

async function staleCopy(page, initial) {
  await setClipboardSentinel(page)
  await expect(metrics(page)).toHaveText(['$308.00', '$108.00'])
  await expect(copyButton(page)).toBeEnabled()
  const [rejected, reconciled] = await Promise.all([
    responseFor(page, exportPath, 'POST'), responseFor(page, statePath, 'GET'), copyButton(page).press('Enter'),
  ])
  check(rejected.status() === 409 && reconciled.status() === 200, 'Stale copy is refused and reconciles with the saved workspace')
  checkExportHeaders(rejected)
  const rejection = await rejected.json()
  check(same(rejected.request().postDataJSON(), exportSelection(initial)) && same(Object.keys(rejection), ['error']) && rejection.error.code === 'evidence_unavailable', 'Stale copy checks the original report heads and returns no snapshot')
  await expect(page.getByRole('alert')).toContainText('No report was copied to the clipboard.')
  await expect(metrics(page)).toHaveText(['Awaiting refresh', 'Awaiting refresh'])
  await expect(copyButton(page)).toBeDisabled()
  await expect(snapshotNote(page)).toHaveCount(0)
  check(await page.evaluate(() => navigator.clipboard.readText()) === clipboardSentinel, 'The refused copy preserved the real clipboard sentinel')
  return { status: rejected.status(), reconciliation_status: reconciled.status(), clipboard_sentinel_unchanged: true }
}

async function openSameWorkspace(page) {
  // An opener copies the selected workspace preference into the new tab.
  await page.bringToFront()
  const [popup] = await Promise.all([page.waitForEvent('popup'), page.evaluate(() => { window.open(location.href, '_blank') })])
  return popup
}

async function loadFixture(name) {
  const manifest = JSON.parse(await readFile(new URL('acceptance_manifest.json', fixtures), 'utf8'))
  const bytes = await readFile(new URL(name, fixtures))
  const sha = sha256(bytes)
  check(sha === manifest.files[name].sha256 && bytes.length === manifest.files[name].bytes, 'Frozen CSV matches the acceptance manifest')
  return { name, bytes, sha }
}

async function browserWorkspaces(browser) {
  const north = await loadFixture('valid_non_eu.csv')
  const apac = await loadFixture('valid_zero_support.csv')
  const desktopOptions = { viewport: { width: 1536, height: 1024 }, acceptDownloads: true }
  const mobileOptions = { ...devices['Pixel 7'], viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 }
  return withContext(browser, desktopOptions, desktop => withContext(browser, mobileOptions, async mobile => {
    const page = await desktop.newPage()
    const mobilePage = await mobile.newPage()
    const desktopErrors = watchErrors(page, true)
    const mobileErrors = watchErrors(mobilePage)
    let initial, mobileInitial, firstFile, downloads = 0
    page.on('download', () => downloads++)

    const created = await step('csv_initial_create_reload_and_download', async () => {
      check((await desktop.cookies()).length === 0, 'Desktop starts with a fresh cookie jar')
      const tls = await openApp(page)
      const cookie = (await desktop.cookies(origin.origin)).find(item => item.name === 'proofflow_session')
      check(cookie?.secure && cookie.httpOnly && cookie.sameSite === 'Strict' && cookie.path === '/', 'Browser session cookie is Secure, HttpOnly and SameSite Strict')
      await expect(downloadButton(page)).toHaveCount(0)
      await preview(page, north, 'EUR', '1.20', 'NORTH')
      check((await get(page, statePath)).status() === 404, 'Desktop preview left import state empty')
      initial = await publish(page)
      const values = reportState(initial, 'current', [30800, 10800])
      await expect(metrics(page)).toHaveText(['$308.00', '$108.00'])
      await page.reload({ waitUntil: 'domcontentloaded' })
      await expect(metrics(page)).toHaveText(['$308.00', '$108.00'])
      const restored = await importState(page)
      check(restored.session_id === initial.session_id && restored.generation === initial.generation && same(heads(restored), heads(initial)), 'Reload preserves session, generation and current artifacts')
      firstFile = await checkedDownload(page, initial, ['$308.00', '$108.00'], north)
      let clipboard = { status: 'skipped', cause: 'Real clipboard check is limited to the disposable GitHub-hosted Linux browser' }
      if (hostedClipboard) {
        await desktop.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: origin.origin })
        clipboard = await checkedCopy(page, initial, ['$308.00', '$108.00'])
      }
      check(downloads === 1, 'Initial report produced one download event')
      await screenshot(page, 'north-initial-desktop')
      return { tls_protocol: tls, cookie: { secure: true, http_only: true, same_site: 'Strict' }, fixture_sha256: north.sha, fx: '1.20', revenue_usd_cents: values, accounting: accounting(initial, [8, 8, 11]), native_queries: initial.backend.native_queries, reload_preserved_artifacts: true, export: firstFile.observation, clipboard }
    })

    const isolated = await step('mobile_session_and_evidence_isolation', async () => {
      check((await mobile.cookies()).length === 0, 'Mobile starts with an independent cookie jar')
      await openApp(mobilePage)
      check((await get(mobilePage, statePath)).status() === 404, 'Independent browser cannot see the desktop import workspace')
      await preview(mobilePage, apac, 'GBP', '1.25', 'APAC')
      mobileInitial = await publish(mobilePage)
      const values = reportState(mobileInitial, 'current', [16375, 9375])
      check(mobileInitial.session_id !== initial.session_id && mobileInitial.generation !== initial.generation, 'Desktop and mobile have distinct sessions and workspaces')
      await expect(metrics(mobilePage)).toHaveText(['$163.75', '$93.75'])
      const evidencePath = `/api/import/evidence/${encodeURIComponent(reports(initial)[0].claims[0].artifact_id)}`
      const [owner, other] = await Promise.all([get(page, evidencePath), get(mobilePage, evidencePath)])
      check(owner.status() === 200 && other.status() === 404, 'Only its owner can read the isolated test artifact')
      return { different_sessions: true, fixture_sha256: apac.sha, revenue_usd_cents: values, owner_evidence_status: owner.status(), other_context_evidence_status: other.status() }
    }, created)

    const corrected = await step('second_tab_correction_and_stale_export', async () => {
      const second = await openSameWorkspace(page)
      const copyTab = hostedClipboard ? await openSameWorkspace(page) : null
      const secondErrors = watchErrors(second)
      const copyErrors = copyTab ? watchErrors(copyTab, true) : []
      try {
        await expect(metrics(second)).toHaveText(['$308.00', '$108.00'])
        if (copyTab) await expect(metrics(copyTab)).toHaveText(['$308.00', '$108.00'])
        await preview(second, north, 'EUR', '1.30')
        const stale = await publish(second, true)
        check(stale.session_id === initial.session_id && same(exportSelection(stale), exportSelection(initial)), 'Second tab corrects the same session, generation and pending report heads')
        check(source(stale, 'fx') !== source(initial, 'fx') && ['orders', 'refunds', 'tickets'].every(name => source(stale, name) === source(initial, name)), 'Only the FX source version changes')
        check(stale.impact.affected_artifacts.length === 4, 'Four artifacts depend on the corrected source')
        const values = reportState(stale, 'stale', [null, null])
        await expect(metrics(second)).toHaveText(['Awaiting refresh', 'Awaiting refresh'])
        await expect(downloadButton(second)).toBeDisabled()
        const clipboard = copyTab ? await staleCopy(copyTab, initial) : null
        await page.bringToFront()
        await expect(metrics(page)).toHaveText(['$308.00', '$108.00'])
        await expect(downloadButton(page)).toBeEnabled()
        const before = downloads
        const [rejected, reconciled] = await Promise.all([
          responseFor(page, exportPath, 'POST'), responseFor(page, statePath, 'GET'), downloadButton(page).click(),
        ])
        check(rejected.status() === 409 && reconciled.status() === 200, `Stale export expected 409 and reconciliation 200, got ${rejected.status()} and ${reconciled.status()}`)
        checkExportHeaders(rejected)
        const rejection = await rejected.json()
        check(same(rejected.request().postDataJSON(), exportSelection(initial)) && same(Object.keys(rejection), ['error']) && rejection.error.code === 'evidence_unavailable', 'Server refused the stale report heads without returning a snapshot')
        await expect(page.getByRole('alert')).toContainText('No report file was downloaded.')
        await expect(metrics(page)).toHaveText(['Awaiting refresh', 'Awaiting refresh'])
        await expect(page.locator('.report-panel .historical')).toHaveText(['Previously $308.00', 'Previously $108.00'])
        await expect(downloadButton(page)).toBeDisabled()
        await expect(snapshotNote(page)).toHaveCount(0)
        await screenshot(page, 'north-stale-export-refused')
        check(downloads === before && secondErrors.length === 0 && copyErrors.length === 0, 'Stale attempt emitted no download or unexpected popup errors')
        return { fx: '1.30', affected_artifacts: stale.impact.affected_artifacts.length, accounting: accounting(stale, [8, 0, 0]), same_session_and_pending_heads: true, current_values_withheld: values, stale_export_status: rejected.status(), reconciliation_status: reconciled.status(), download_events: downloads - before, clipboard }
      } finally {
        if (copyTab) await copyTab.close()
        await second.close()
      }
    }, created)

    await step('fresh_refresh_download_and_narrow_viewports', async () => {
      const fresh = await postFromUI(page, '/api/import/refresh', 'Refresh affected')
      const values = reportState(fresh, 'current', [31700, 11700])
      check(fresh.last_refresh.numeric_parity === true && fresh.last_refresh.unchanged_support && support(fresh) && support(fresh) === support(initial), 'Independent check passes and support artifact is unchanged')
      check(fresh.generation === initial.generation && reports(fresh).every((report, index) => report.id !== reports(initial)[index].id), 'Both report heads changed within the original workspace generation')
      await expect(metrics(page)).toHaveText(['$317.00', '$117.00'])
      await expect(page.locator('.refresh-banner')).toContainText('Fresh recomputation matches.')
      const lastFile = await checkedDownload(page, fresh, ['$317.00', '$117.00'], north)
      const clipboard = hostedClipboard ? await checkedCopy(page, fresh, ['$317.00', '$117.00']) : null
      check(downloads === 2 && sha256(await readFile(firstFile.path)) === firstFile.observation.sha256, 'Only the two approved downloads occurred and the first snapshot stayed unchanged')
      await screenshot(page, 'north-refreshed-desktop')
      const viewports = []
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 844 })
        await page.evaluate(() => window.scrollTo(0, 0))
        await expect(downloadButton(page)).toBeInViewport({ ratio: 1 })
        await expect(copyButton(page)).toBeInViewport({ ratio: 1 })
        await expect(snapshotNote(page)).toBeInViewport({ ratio: 1 })
        const noOverflow = await downloadButton(page).evaluate(node => {
          const toolbar = node.closest('.workspace-workflow, .report-export')
          return Boolean(toolbar && document.documentElement.scrollWidth <= innerWidth && toolbar.scrollWidth <= toolbar.clientWidth)
        })
        check(noOverflow, 'Page and report export controls fit the narrow viewport')
        await screenshot(page, `north-refreshed-${width}px`)
        viewports.push({ width, height: 844, no_horizontal_overflow: noOverflow })
      }
      await page.reload({ waitUntil: 'domcontentloaded' })
      await expect(metrics(page)).toHaveText(['$317.00', '$117.00'])
      const restored = await importState(page)
      check(same(exportSelection(restored), exportSelection(fresh)) && same(heads(restored), heads(fresh)), 'Refreshed report heads and artifacts survive reload')
      check(desktopErrors.length === 0, 'Desktop has no unexpected console or runtime errors')
      return { revenue_usd_cents: values, accounting: accounting(fresh, [0, 4, 11]), numeric_parity: true, preserved_support_artifact: true, new_report_heads: true, reload_preserved_artifacts: true, previous_file_unchanged: true, export: lastFile.observation, clipboard, viewports }
    }, corrected)

    await step('mobile_session_after_desktop_correction', async () => {
      await mobilePage.reload({ waitUntil: 'domcontentloaded' })
      await expect(metrics(mobilePage)).toHaveText(['$163.75', '$93.75'])
      const restored = await importState(mobilePage)
      const values = reportState(restored, 'current', [16375, 9375])
      check(same(exportSelection(restored), exportSelection(mobileInitial)) && same(heads(restored), heads(mobileInitial)), 'Other browser retains its previous report and artifact identities')
      check(await mobilePage.evaluate(() => innerWidth === 390 && document.documentElement.scrollWidth <= innerWidth), 'Android-emulated viewport has no horizontal overflow')
      check(mobileErrors.length === 0, 'Mobile has no unexpected console or runtime errors')
      await screenshot(mobilePage, 'apac-mobile')
      return { revenue_usd_cents: values, reload_preserved_artifacts: true, viewport: mobilePage.viewportSize() }
    }, isolated && corrected)
  }))
}

let browser
try {
  const identified = await step('runner_provenance', provenance)
  const online = await step('public_https_health_and_build', publicDelivery, identified)
  await step('walkthrough_media_delivery', mediaBytes, online)
  const launched = await step('launch_browser', async () => {
    browser = await chromium.launch({ channel: 'chrome', headless: true, timeout })
    receipt.browser = { name: 'Google Chrome', version: browser.version(), playwright: 'frontend/package-lock.json' }
  }, online)
  await step('browser_walkthrough_play_and_seek', () => playAndSeek(browser), launched)
  if (launched) await browserWorkspaces(browser)
} catch (error) {
  receipt.runner_failure = failure(error)
} finally {
  if (browser) await step('close_browser', () => browser.close())
  receipt.finished_at_utc = utcNow()
  receipt.passed = !receipt.runner_failure && Object.values(receipt.steps).every(row => row.status === 'pass')
  await writeFile(join(output, 'receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`, { mode: 0o600 })
  console.log(`Hosted browser evidence: ${output}`)
  if (!receipt.passed) process.exitCode = 1
}
