/**
 * Verified facts used across the site. Every value here is copied from a file in this
 * repository; `source` is the repository path that states it. Do not add a number
 * without a source. Section-specific tables live next to their section and follow the same rule.
 */

export const REPO_URL = 'https://github.com/saivedant169/proofflow'
export const REPO_BLOB = `${REPO_URL}/blob/main`
export const repoFile = (path: string) => `${REPO_BLOB}/${path}`

export const links = {
  liveApp: 'https://proofflow.arnavbule.in/app/',
  walkthrough: 'https://proofflow.arnavbule.in/walkthrough.mp4',
  publicEvidence: 'https://proofflow.arnavbule.in/evidence/',
  evidenceZip: 'https://proofflow.arnavbule.in/evidence/proofflow-model-evidence.zip',
  connector: 'https://proofflow.arnavbule.in/agent/',
  connectorScript: 'https://proofflow.arnavbule.in/agent/proofflow_csv_mcp.py',
  repo: REPO_URL,
} as const

export const project = {
  name: 'ProofFlow',
  promise: 'Keep saved agent reports current when an input changes.',
  track: 'HydraDB hackathon, Track 2: agent context layer',
  license: 'MIT',
  source: 'README.md, docs/SUBMISSION_DRAFT.md',
} as const

/** Guided sample (authored commerce fixture). Source: README.md table, proofflow/analytics.py DEMO_SOURCES. */
export const guidedSample = {
  fxBefore: '1.10',
  fxAfter: '1.20',
  companyBeforeCents: 556_500,
  companyAfterCents: 575_500,
  euBeforeCents: 209_000,
  euAfterCents: 228_000,
  euSupportTickets: 2,
  refreshToolCalls: 4,
  source: 'README.md (Run the application), proofflow/analytics.py',
} as const

/** Headline results. Each entry: value, what it means, and the file that reports it. */
export const headline = {
  modelStudy: {
    invocations: 48,
    refreshed: '32/32',
    inputExposurePct: 39.33,
    note: 'Affected reports refreshed in a frozen 48-invocation actual-model comparison, at 39.33% of full context’s provider input exposure (excluding the no-op case). Eight fresh cases, one sample per method and case.',
    comparators: [
      { method: 'ProofFlow graph', refreshed: 32 },
      { method: 'Exact-flat traversal', refreshed: 32 },
      { method: 'Iterative hybrid', refreshed: 28 },
      { method: 'BM25', refreshed: 25 },
      { method: 'BGE vector retrieval', refreshed: 5 },
    ],
    of: 32,
    source: 'docs/MODEL_COMPARISON_RESULTS.md',
  },
  retail: {
    refreshed: '38/38',
    blocked: '4/4',
    fewerTokensPct: 69.41,
    graphTokens: 39_375,
    fullTokens: 128_729,
    lines: 640,
    note: 'Recoverable affected reports refreshed and unavailable reports correctly blocked, with 69.41% fewer evidence tokens than full context.',
    comparators: [
      { method: 'ProofFlow / HydraDB', refreshed: 38, recallPct: 100.0, endstates: 10 },
      { method: 'Exact flat dependency traversal', refreshed: 38, recallPct: 100.0, endstates: 10 },
      { method: 'Iterative hybrid', refreshed: 33, recallPct: 92.91, endstates: 6 },
      { method: 'BM25', refreshed: 19, recallPct: 53.78, endstates: 3 },
      { method: 'Dense BGE', refreshed: 8, recallPct: 43.77, endstates: 2 },
    ],
    of: 38,
    source: 'docs/RETAIL_V2_RESULTS.md, evidence/retail_v2_summary.json',
  },
  fixedBudget: {
    budgets: [4096, 8192],
    rows: [
      { method: 'Graph and exact-flat', at4096: 15, at8192: 27 },
      { method: 'Iterative hybrid', at4096: 15, at8192: 28 },
      { method: 'BM25', at4096: 5, at8192: 25 },
      { method: 'BGE', at4096: 2, at8192: 10 },
    ],
    uncapped: 32,
    of: 32,
    note: 'Every capped method missed reports at both limits; the uncapped reference refreshed 32/32.',
    source: 'docs/FIXED_BUDGET_DIAGNOSTIC_RESULTS.md',
  },
  mcpAgent: {
    checks: 32,
    recordedCalls: 12,
    note: 'A real Fable 5.2/high Claude Code client completed one corrected MCP trajectory with 32 recorded checks passed. Its first launch-configuration failure is retained.',
    source: 'docs/MCP_AGENT_RESULTS.md',
  },
  composition: {
    checks: 17,
    note: 'A model chose a seven-tool workflow from typed contracts, composed a new EU brief from earlier artifacts, and both reports refreshed correctly after an FX correction: 17 execution checks passed.',
    source: 'docs/COMPOSITION.md',
  },
} as const

/** Limits the project states about itself. Shown as prominently as the wins. */
export const limits = [
  { text: 'Exact flat dependency traversal ties ProofFlow on every test endstate. The result supports explicit dependencies, not a unique storage-engine advantage.', source: 'README.md' },
  { text: 'The retail development efficiency gate failed: graph/full evidence was 60.79%, above the unchanged 40% threshold. It is retained and not pooled with the held-out test.', source: 'docs/RETAIL_V2_RESULTS.md' },
  { text: 'The actual-model study is eight fresh cases with one sample per method and case. It does not establish general model reliability.', source: 'docs/MODEL_COMPARISON_RESULTS.md' },
  { text: 'FX, refund and correction interventions are staged assumptions over a bounded sample, not observed incidents or customer validation.', source: 'README.md' },
  { text: 'Customer demand and time savings have not yet been measured.', source: 'docs/SUBMISSION_DRAFT.md' },
] as const
