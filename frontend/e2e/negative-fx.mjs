import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { stripVTControlCharacters } from 'node:util'

const frontend = fileURLToPath(new URL('..', import.meta.url))
const require = createRequire(import.meta.url)
const title = 'FX correction withholds values, survives reload, refreshes four tools and preserves a reorder'

// Ask the same config to validate the requested parent before we create any
// directories. The normal runner publishes its unique output path on stdout.
const env = { ...process.env, PROOFFLOW_E2E_NEGATIVE_FX: '1' }
delete env.TEST_WORKER_INDEX
delete env.PROOFFLOW_E2E_RUN_DIR
const runner = spawnSync(process.execPath, [require.resolve('@playwright/test/cli'), 'test', '--grep', title], {
  cwd: frontend, env, encoding: 'utf8', maxBuffer: 1024 * 1024,
})
process.stdout.write(runner.stdout ?? '')
process.stderr.write(runner.stderr ?? '')
if (runner.error) throw runner.error
const output = runner.stdout.match(/^ProofFlow E2E evidence directory: (.+)$/m)?.[1]
if (!output || runner.status !== 1) throw new Error('Expected exactly one failed Playwright run for the one-cent mutation.')

const report = JSON.parse(readFileSync(path.join(output, 'results.json'), 'utf8'))
const specs = report.suites.flatMap(suite => suite.specs ?? [])
const results = specs[0]?.tests.flatMap(test => test.results) ?? []
const failure = stripVTControlCharacters(results[0]?.error?.message ?? '')
const diffLines = failure.split('\n').map(line => line.trim().replace(/\s+/g, ' '))
if (report.errors.length || report.stats.unexpected !== 1 || report.stats.expected !== 0 || specs.length !== 1
    || specs[0].title !== title || results.length !== 1 || results[0].status !== 'failed'
    || results[0].errors.length !== 1 || !failure.includes('Rendered company and regional revenue')
    || !['- "$317.00"', '- "$117.00"', '+ "$317.01"', '+ "$117.01"'].every(amount => diffLines.some(line => line.startsWith(amount)))) {
  throw new Error('Mutation run did not fail on the expected rendered one-cent difference; inspect its raw report.')
}

writeFileSync(path.join(output, 'negative-control.json'), JSON.stringify({
  test: title,
  test_server_mutation: 'Add one cent to NORTH at EUR 1.30 in convert_to_usd',
  playwright_exit_status: runner.status,
  expected_rendered_amounts: ['$317.00', '$117.00'],
  observed_rendered_amounts: ['$317.01', '$117.01'],
  outcome: 'unchanged browser assertion detected the deliberate mutation',
}, null, 2) + '\n', { mode: 0o600 })
console.log('Negative control passed: unchanged browser assertions detected both one-cent differences.')
