/**
 * Verified data for the results section. Every value is copied from the file named in
 * `source` (repository-relative). Percentages are kept as the source writes them.
 */

export type BarRow = {
  label: string
  value: number
  /** Brand emphasis (ProofFlow). */
  highlight?: boolean
  /** Uncapped reference row, drawn apart from the compared methods. */
  reference?: boolean
}

/** Actual-model study: 48 Fable 5.2/high invocations, eight fresh cases. */
export const modelStudy = {
  of: 32,
  invocations: 48,
  cases: 8,
  rows: [
    { label: 'ProofFlow graph', value: 32, correction: '6/6', highlight: true },
    { label: 'Exact-flat traversal', value: 32, correction: '6/6' },
    { label: 'Iterative hybrid', value: 28, correction: '3/6' },
    { label: 'BM25', value: 25, correction: '3/6' },
    { label: 'BGE vector retrieval', value: 5, correction: '0/6' },
    { label: 'Full context (uncapped)', value: 32, correction: '6/6', reference: true },
  ],
  exposure: {
    graph: 75_422,
    full: 191_774,
    pct: '39.33%',
    pctValue: 39.33,
    pctWithNoop: '35.17%',
  },
  unavailableBlocked: '4/4',
  source: 'docs/MODEL_COMPARISON_RESULTS.md',
  sourceSummary: 'evidence/model_comparison_v4_summary.json',
} as const

/** Retail v2: deterministic benchmark, 640 UCI Online Retail lines, no LLM. */
export const retail = {
  of: 38,
  lines: 640,
  refreshed: '38/38',
  blocked: '4/4',
  fewerPct: '69.41%',
  ratioPct: '30.59%',
  ratioValue: 30.59,
  graphTokens: 39_375,
  fullTokens: 128_729,
  allowanceMax: '9,611',
  /** Same per-case evidence allowance as the graph closure. */
  rows: [
    { label: 'ProofFlow graph', value: 38, recall: '100.00%', endstates: '10/10', highlight: true },
    { label: 'Exact-flat traversal', value: 38, recall: '100.00%', endstates: '10/10' },
    { label: 'Iterative hybrid', value: 33, recall: '92.91%', endstates: '6/10' },
    { label: 'BM25', value: 19, recall: '53.78%', endstates: '3/10' },
    { label: 'BGE vector retrieval', value: 8, recall: '43.77%', endstates: '2/10' },
  ],
  source: 'docs/RETAIL_V2_RESULTS.md',
  sourceSummary: 'evidence/retail_v2_summary.json',
} as const

/** Fixed evidence-budget diagnostic: same eight March cases, deterministic reader. */
export const fixedBudget = {
  of: 32,
  low: '4,096',
  high: '8,192',
  uncapped: 32,
  rows: [
    { label: 'ProofFlow graph and exact-flat', low: 15, high: 27, highlight: true },
    { label: 'Iterative hybrid', low: 15, high: 28 },
    { label: 'BM25', low: 5, high: 25 },
    { label: 'BGE vector retrieval', low: 2, high: 10 },
  ],
  cells: 88,
  source: 'docs/FIXED_BUDGET_DIAGNOSTIC_RESULTS.md',
} as const

/** Limits, each stated in the cited file. */
export const limits = [
  {
    text: 'Exact-flat traversal, a plain recursive walk over the same recorded dependencies, ties ProofFlow on every test endstate. The result supports explicit dependencies, not a unique storage-engine advantage.',
    source: 'README.md',
  },
  {
    text: 'The actual-model study is eight fresh cases with one sample per method and case. It does not establish general model reliability.',
    source: 'docs/MODEL_COMPARISON_RESULTS.md',
  },
  {
    text: 'Every method shares the same Hydra-assisted refresh executor, so blocking unavailable reports is a shared property, not a graph-only win.',
    source: 'README.md',
  },
  {
    text: 'The retail development efficiency gate failed: graph used 60.79% of full-context evidence, above the unchanged 40% threshold. It is kept and not pooled with the held-out test.',
    source: 'docs/RETAIL_V2_RESULTS.md',
  },
  {
    text: 'Input exposure counts tokens. It does not establish a latency or cost benefit.',
    source: 'docs/MODEL_COMPARISON_RESULTS.md',
  },
  {
    text: 'FX, refund and correction interventions are staged assumptions over a bounded sample, not observed incidents or customer validation.',
    source: 'README.md',
  },
  {
    text: 'The fixed-budget run’s original wrapper failed in all 88 cells. Scores were recovered by a separate read-only parser, and the failures are kept.',
    source: 'docs/FIXED_BUDGET_DIAGNOSTIC_RESULTS.md',
  },
  {
    text: 'Customer demand and time savings have not yet been measured.',
    source: 'docs/SUBMISSION_DRAFT.md',
  },
] as const

/** Earlier and smaller studies, reported separately and not pooled. */
export const onRecord = [
  {
    text: 'Earlier fixed 2,048-token pilots were weaker: ProofFlow refreshed 16/29 affected reports in the authored pilot and 5/9 in a 16-call model pilot.',
    sources: ['docs/BENCHMARK_RESULTS.md', 'docs/AGENT_RESULTS.md'],
  },
  {
    text: 'On a nine-row CSV close, full recalculation with a version check matched every output too. ProofFlow added retained receipts and dependency paths, not speed.',
    sources: ['docs/WORKFLOW_COMPARISON_RESULTS.md'],
  },
] as const

export const verifier = {
  text: 'Download the evidence ZIP and run one standard-library Python script. It rebuilds the 4,681 source rows, recalculates every report and traces each saved receipt offline, with no model account.',
  source: 'docs/PUBLIC_EVIDENCE.md',
} as const
