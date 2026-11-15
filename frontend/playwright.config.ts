import { defineConfig } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { existsSync, lstatSync, mkdirSync, mkdtempSync, realpathSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.dirname(fileURLToPath(import.meta.url))
const root = realpathSync.native(path.dirname(frontend))
const outputError = 'PROOFFLOW_E2E_OUTPUT_DIR must be an absolute path outside all ProofFlow worktrees.'
if (process.argv.some(arg => /^--(output|reporter)(=|$)/.test(arg))) {
  throw new Error('Use PROOFFLOW_E2E_OUTPUT_DIR to set the parent for ProofFlow E2E evidence.')
}

// Resolve existing symlink ancestors even if the requested directory does not
// exist. Always use the canonical result for writes, never the input spelling.
function canonicalize(candidate: string): string {
  try {
    lstatSync(candidate)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT' || path.dirname(candidate) === candidate) throw error
    return path.join(canonicalize(path.dirname(candidate)), path.basename(candidate))
  }
  return realpathSync.native(candidate)
}
const checkouts = [root]
if (existsSync(path.join(root, '.git'))) {
  const entries = execFileSync('git', ['worktree', 'list', '--porcelain', '-z'], { cwd: root, encoding: 'utf8' })
  for (const entry of entries.split('\0').filter(value => value.startsWith('worktree '))) {
    const worktree = entry.slice('worktree '.length)
    if (existsSync(worktree)) checkouts.push(realpathSync.native(worktree))
  }
}
const requested = process.env.PROOFFLOW_E2E_OUTPUT_DIR ?? tmpdir()
if (!path.isAbsolute(requested)) throw new Error(outputError)
const outputParent = canonicalize(path.resolve(requested))
if (checkouts.some(checkout => outputParent === checkout || outputParent.startsWith(`${checkout}${path.sep}`))) {
  throw new Error(outputError)
}

const python = process.env.PROOFFLOW_E2E_PYTHON ?? path.join(root, '.venv', 'bin', 'python')
if (!existsSync(python)) throw new Error('Set PROOFFLOW_E2E_PYTHON to the existing ProofFlow Python environment.')
if (!process.env.PROOFFLOW_HYDRA_TOKEN_FILE && !process.env.PROOFFLOW_HYDRA_TOKEN) {
  throw new Error('Supply existing local HydraDB credentials through PROOFFLOW_HYDRA_TOKEN_FILE or PROOFFLOW_HYDRA_TOKEN.')
}
const normalPort = Number(process.env.PROOFFLOW_E2E_PORT ?? '18780')
const faultPort = Number(process.env.PROOFFLOW_E2E_FAULT_PORT ?? '18781')
if (![normalPort, faultPort].every(port => Number.isInteger(port) && port >= 1024 && port <= 65535) || normalPort === faultPort) {
  throw new Error('E2E server ports must be distinct unprivileged integer ports.')
}

// Playwright reloads this config in its worker; it inherits the selected run
// directory. A new invocation otherwise always preserves previous artifacts.
const inheritedRun = process.env.TEST_WORKER_INDEX === undefined ? undefined : process.env.PROOFFLOW_E2E_RUN_DIR
let output: string
if (inheritedRun) {
  output = realpathSync.native(inheritedRun)
  const stat = lstatSync(output)
  if (path.dirname(output) !== outputParent || !/^proofflow-browser-e2e-[a-zA-Z0-9]{6}$/.test(path.basename(output))
      || !stat.isDirectory() || (stat.mode & 0o077) !== 0) {
    throw new Error('Invalid inherited ProofFlow E2E run directory.')
  }
  for (const name of ['results.json', 'assertions.jsonl', 'test-results']) {
    try {
      if (lstatSync(path.join(output, name)).isSymbolicLink()) throw new Error('E2E evidence paths cannot be symlinks.')
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error
    }
  }
} else {
  mkdirSync(outputParent, { recursive: true, mode: 0o700 })
  output = mkdtempSync(path.join(outputParent, 'proofflow-browser-e2e-'))
  console.log(`ProofFlow E2E evidence directory: ${output}`)
}
process.env.PROOFFLOW_E2E_RUN_DIR = output
// Playwright otherwise lets this ambient variable override reporter options.
process.env.PLAYWRIGHT_JSON_OUTPUT_FILE = path.join(output, 'results.json')
const normalURL = `http://127.0.0.1:${normalPort}`
const faultURL = `http://127.0.0.1:${faultPort}`
const negativeFX = process.env.PROOFFLOW_E2E_NEGATIVE_FX === '1'
process.env.PROOFFLOW_E2E_BASE_URL = normalURL
process.env.PROOFFLOW_E2E_FAULT_URL = faultURL
process.env.PROOFFLOW_E2E_FAULT_LOG = path.join(output, `fault-events-${faultPort}.jsonl`)
const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`
const server = (port: number, label: string, control?: '--fault-after-orders' | '--negative-fx-cent') => ({
  command: [quote(python), quote(path.join(frontend, 'e2e', 'serve.py')), '--port', String(port), '--state-dir', quote(path.join(output, label)), '--static-dir', quote(path.join(frontend, 'dist')), ...(control ? [control] : [])].join(' '),
  cwd: root,
  url: `http://127.0.0.1:${port}/health`,
  reuseExistingServer: false,
  timeout: 60_000,
  gracefulShutdown: { signal: 'SIGTERM' as const, timeout: 10_000 },
  stdout: 'pipe' as const,
  stderr: 'pipe' as const,
  env: {
    PYTHONPATH: root,
    PYTHONDONTWRITEBYTECODE: '1',
    PROOFFLOW_COOKIE_SECURE: 'false',
    PROOFFLOW_HYDRA_URL: process.env.PROOFFLOW_HYDRA_URL ?? 'http://127.0.0.1:18443',
  },
})

export default defineConfig({
  testDir: './e2e',
  testMatch: 'csv.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  outputDir: path.join(output, 'test-results'),
  reporter: [['line'], ['json', { outputFile: path.join(output, 'results.json') }]],
  use: {
    baseURL: normalURL,
    browserName: 'chromium',
    viewport: { width: 1536, height: 1024 },
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    serviceWorkers: 'block',
    screenshot: 'only-on-failure',
    trace: negativeFX ? 'off' : 'retain-on-failure',
  },
  webServer: negativeFX
    ? [server(normalPort, 'negative-fx-state', '--negative-fx-cent')]
    : [server(normalPort, 'normal-state'), server(faultPort, 'fault-state', '--fault-after-orders')],
})
