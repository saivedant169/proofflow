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

/**
 * Provider accounting, actual-model study: all eight cases, one sample per arm, Fable 5.2.
 * Copied from docs/MODEL_COMPARISON_RESULTS.md, section "Provider accounting". Input exposure
 * includes cache creation and cache reads; list costs depend on cache treatment.
 */
export const accounting = {
  cases: 8,
  of: 32,
  rows: [
    { key: 'full', label: 'Full context', sub: 'Re-read everything', correct: 32, tokens: 219_145, cost: 3.742368 },
    { key: 'bge', label: 'Vector RAG', sub: 'BGE dense', correct: 5, tokens: 75_785, cost: 1.377631 },
    { key: 'bm25', label: 'Keyword search', sub: 'BM25', correct: 25, tokens: 75_699, cost: 1.427535 },
    { key: 'hybrid', label: 'Hybrid retrieval', sub: 'Iterative', correct: 28, tokens: 76_174, cost: 1.448095 },
    { key: 'pf', label: 'ProofFlow', sub: 'HydraDB graph', correct: 32, tokens: 77_071, cost: 1.377214, highlight: true },
    { key: 'flat', label: 'Exact-flat walk', sub: 'Ablation', correct: 32, tokens: 77_095, cost: 0.5055334, ablation: true },
  ],
  /** Derived from the rows above (stated as derived on the page). */
  derived: {
    tokensSaved: 142_074,          // 219,145 - 77,071
    costLowerPct: 63,              // 1 - 1.3772140 / 3.7423680 = 63.2%
    vsVector: '6.4×',              // 32 / 5
    perCaseCostPf: 0.1722,         // 1.3772140 / 8
    perCaseCostFull: 0.4678,       // 3.7423680 / 8
    perCaseCostSaved: 0.2956,      // (3.7423680 - 1.3772140) / 8
    perCaseTokensSaved: 17_759,    // 142,074 / 8
    vectorMissed: 27,              // 32 - 5 affected reports
  },
  source: 'docs/MODEL_COMPARISON_RESULTS.md',
} as const

/** "What we don't claim" chips: short label, one sentence, and the files that state it. */
export const notClaimed = [
  {
    chip: 'List prices, cache-dependent',
    text: 'Costs are list prices from this one study and depend on cache treatment: exact-flat sent the same ordered prompts as ProofFlow yet cost $0.51, mostly cache reads.',
    sources: ['docs/MODEL_COMPARISON_RESULTS.md'],
  },
  {
    chip: 'One sample per case',
    text: 'One frozen sample per case and method, across eight fresh cases, all sharing one refresh executor. Run-to-run variance is not measured.',
    sources: ['docs/MODEL_COMPARISON_RESULTS.md'],
  },
  {
    chip: 'Exact-flat ties',
    text: 'A plain walk over the same recorded dependencies ties ProofFlow on correctness. The win is explicit dependencies, which HydraDB holds and traverses.',
    sources: ['docs/MODEL_COMPARISON_RESULTS.md', 'docs/RETAIL_V2_RESULTS.md'],
  },
  {
    chip: 'No latency claim',
    text: 'Timings describe one sequential, cached local run. Input exposure cannot establish a latency benefit, and time savings are not yet measured.',
    sources: ['docs/MODEL_COMPARISON_RESULTS.md', 'docs/SUBMISSION_DRAFT.md'],
  },
  {
    chip: 'Fixed caps: all miss',
    text: 'Under hard caps of 4,096 and 8,192 tokens every method missed reports; ProofFlow reached 15 and 27 of 32, hybrid 28 at 8,192.',
    sources: ['docs/FIXED_BUDGET_DIAGNOSTIC_RESULTS.md'],
  },
  {
    chip: 'Dev efficiency gate failed',
    text: 'On the retail development cases graph used 60.79% of full-context evidence, above the unchanged 40% gate. Kept, never pooled with test.',
    sources: ['docs/RETAIL_V2_RESULTS.md'],
  },
] as const
