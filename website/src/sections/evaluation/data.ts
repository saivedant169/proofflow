/**
 * Evaluation section content. Every statement is copied or condensed from the file named
 * in its `sources` field; numbers are written exactly as those files state them.
 */

export type PipelineStep = {
  id: string
  title: string
  summary: string
  /** Real repository paths shown as identifiers. */
  files?: { path: string; note: string }[]
  /** Real commands or messages, one per line. Lines starting with # are comments. */
  code?: string[]
  detail: string
  sources: string[]
}

export const PIPELINE: PipelineStep[] = [
  {
    id: 'freeze',
    title: 'Freeze the protocol',
    summary: 'Cases, budgets, prompts and hashes are committed before the first scored run.',
    files: [
      { path: 'docs/MODEL_COMPARISON_PROTOCOL.md', note: '48 planned cells, written before any test outcome' },
      { path: 'docs/RETAIL_V2_SPEC.md', note: 'Protocol retail-v2-1, prespecified gates' },
      { path: 'docs/BENCHMARK_MANIFEST.json', note: 'Pilot configuration and arms' },
      { path: 'docs/RETAIL_BENCHMARK_MANIFEST.json', note: 'Code file hashes for the retail run' },
    ],
    detail:
      'The model study fixed exactly 48 cells, eight cases × six arms, each with at most one harness invocation, no retry and no fallback model. Retail v2 commits its protocol, source hashes, cases, oracle, runner and configuration before the first scored held-out execution.',
    sources: ['docs/MODEL_COMPARISON_PROTOCOL.md', 'docs/RETAIL_V2_SPEC.md'],
  },
  {
    id: 'run',
    title: 'Run held-out cases once',
    summary: 'Runs refuse to overwrite earlier results and need a clean, committed tracked tree.',
    code: [
      'uv run python -m proofflow.eval.runner --split test --allow-test --output results/reproduction',
      '',
      '# proofflow/eval/runner.py stops with one of these instead of running:',
      '# Held-out execution refuses tracked or staged code changes; commit the reviewed harness first',
      '# Refusing to overwrite a prior benchmark run: <output>',
    ],
    detail:
      'Held-out cases run once with no feedback updates and no post-result tuning. A transport failure remains visible; a necessary repair gets a new revision and an explicit rerun disclosure, not silent replacement.',
    sources: ['README.md', 'proofflow/eval/runner.py', 'docs/RETAIL_V2_SPEC.md'],
  },
  {
    id: 'audit',
    title: 'Audit the saved results',
    summary: 'A standard-library audit re-traces the arithmetic and receipts without models or services.',
    code: ['python3 scripts/audit_model_comparison_v4.py .'],
    detail:
      'The audit independently implements the staged arithmetic and receipt tracing. It does not run the benchmark, replay refresh or contact the provider; it checks the exported evidence from the published snapshot boundary.',
    sources: ['scripts/audit_model_comparison_v4.py'],
  },
  {
    id: 'verify',
    title: 'Publish an offline verifier',
    summary: 'A public ZIP lets anyone re-check the model study with only the Python standard library.',
    code: [
      'sha256sum -c proofflow-model-evidence.zip.sha256',
      'unzip proofflow-model-evidence.zip -d proofflow-model-evidence',
      'cd proofflow-model-evidence',
      'python3 scripts/verify_public_evidence.py',
    ],
    detail:
      'It audits 48 saved case-and-method cells and 152 model-study payloads, reconstructs the 4,681 source rows, traces receipts through exact source and tool versions, and reconciles the provider counters. It also checks historical failures, offline, without repository access or model credentials.',
    sources: ['docs/PUBLIC_EVIDENCE.md', 'README.md'],
  },
  {
    id: 'ci',
    title: 'Re-verify on every push',
    summary: 'CI runs the tests and audit, then real pinned HydraDB, MCP, recovery and Chromium checks.',
    code: [
      'uv run pytest -q',
      'python3 scripts/audit_model_comparison_v4.py .',
      'python3 scripts/build_public_evidence.py --check',
      'python3 scripts/build_delivery_evidence.py --check',
      'uv run python scripts/hydra_smoke.py --restart --output evidence/ci_hydra_smoke.json',
      'uv run python scripts/core_smoke.py --output evidence/ci_core_smoke.json',
      'uv run --extra mcp python scripts/mcp_smoke.py --output evidence/ci_mcp',
      'uv run python scripts/recovery_probe.py --output evidence/ci_recovery',
      'npm run test:e2e',
      'npm run test:e2e:negative',
    ],
    detail:
      'Every push and pull request runs on Ubuntu 24.04 against the pinned HydraDB container. The negative control reruns the unchanged FX browser test against a server that adds one cent, and passes only if the test catches it.',
    sources: ['.github/workflows/ci.yml', 'docs/BROWSER_ACCEPTANCE_RESULTS.md'],
  },
]

export type RetainedFailure = { what: string; kept: string; source: string }

export const RETAINED_FAILURES: RetainedFailure[] = [
  {
    what: 'MCP agent, first attempt',
    kept: 'Its launch used --safe-mode, which suppressed MCP tool discovery: zero tool requests ran. The failed $0.037144 attempt stays in the reported total.',
    source: 'docs/MCP_AGENT_RESULTS.md',
  },
  {
    what: 'Retail development efficiency gate',
    kept: 'Graph/full evidence was 60.79%, above the unchanged 40% threshold. Retained and not pooled with the held-out test.',
    source: 'docs/RETAIL_V2_RESULTS.md',
  },
  {
    what: 'Browser suite, first draft run',
    kept: '5/6 passed: one FX assertion used the wrong capitalization and text for the visible label.',
    source: 'docs/BROWSER_ACCEPTANCE_RESULTS.md',
  },
  {
    what: 'Negative control, first run',
    kept: 'The expected mismatch appeared alongside a Playwright teardown timeout, so the control command rejected the attempt.',
    source: 'docs/BROWSER_ACCEPTANCE_RESULTS.md',
  },
  {
    what: 'First CI browser run',
    kept: 'ubuntu-latest resolved to Ubuntu 26.04, unsupported by pinned Playwright 1.56.1. The setup failure is preserved; pinning ubuntu-24.04 fixed it.',
    source: 'docs/BROWSER_ACCEPTANCE_RESULTS.md',
  },
  {
    what: 'Fixed-budget diagnostic wrapper',
    kept: 'The publication wrapper raised the same KeyError in all 88 cells after saving their scores. The recovered scores keep each original failure status.',
    source: 'docs/FIXED_BUDGET_DIAGNOSTIC_RESULTS.md',
  },
]

export type VerifiedFact = { figure: string; label: string; detail: string; sources: string[] }

export const VERIFIED: VerifiedFact[] = [
  {
    figure: '9',
    label: 'Chromium workflows against real HydraDB',
    detail:
      'The expanded local suite passed nine workflows; the original suite passed six. The deployed revision passed 488 Python tests and nine default Chromium workflows on its first Linux CI attempt.',
    sources: ['docs/REPORT_HANDOFF_ACCEPTANCE.md', 'docs/HOSTED_DELIVERY.md'],
  },
  {
    figure: '$0.01',
    label: 'Injected error caught',
    detail:
      'A disposable server added one cent to the conversion. Chromium rendered $317.01 and $117.01 against the expected $317.00 and $117.00, and the unchanged test failed exactly as intended.',
    sources: ['docs/BROWSER_ACCEPTANCE_RESULTS.md'],
  },
  {
    figure: '15/15',
    label: 'Recovery checks after a killed update',
    detail:
      'The API child was killed between two committed source updates. Affected values stayed withheld after reopen; full resubmission restored the uninterrupted control’s values and lineage. Passed locally and on the Linux CI runner.',
    sources: ['docs/RECOVERY_V1_RESULTS.md'],
  },
  {
    figure: '$9,052.58 → $9,414.68',
    label: 'Hosted Chrome on 642 UCI Online Retail lines',
    detail:
      'A staged GBP rate correction moved the company and UK figures, matching the independent oracle to the cent. The old tab’s download was refused and the corrected reports persisted on reload.',
    sources: ['docs/REAL_PARTITION_RESULTS.md', 'docs/SUBMISSION_DRAFT.md'],
  },
]

/** Compact thread labels: a short name and a single tag per pipeline step (same sources as PIPELINE). */
export const STEP_TAGS: Record<string, { name: string; tag: string; tagLabel: string }> = {
  freeze: { name: 'Freeze protocol', tag: '48', tagLabel: 'cells fixed first' },
  run: { name: 'Run held-out once', tag: '1', tagLabel: 'run per cell, no retry' },
  audit: { name: 'Audit offline', tag: '0', tagLabel: 'models called' },
  verify: { name: 'Public verifier', tag: '4,681', tagLabel: 'rows rebuilt' },
  ci: { name: 'Re-verify in CI', tag: 'Each', tagLabel: 'push and pull request' },
}

/** Big-number labels for the verified-product row (detail and sources stay in VERIFIED). */
export const VERIFIED_LABELS = ['browser workflows pass', 'injected error caught', 'recovery checks pass', 'real lines, oracle-matched'] as const
