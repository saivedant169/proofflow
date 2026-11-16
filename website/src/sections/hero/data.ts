/**
 * Real-model comparison: 48 Fable 5.2/high invocations, eight fresh cases, one sample per arm and case.
 * Correct counts: "affected recoverable reports refreshed"; input exposure and list cost: the
 * "Provider accounting" table. Both in docs/MODEL_COMPARISON_RESULTS.md. Do not edit without the source.
 */

export const STUDY_SOURCE = 'docs/MODEL_COMPARISON_RESULTS.md'

export type ArmId = 'graph' | 'exact' | 'hybrid' | 'bm25' | 'dense' | 'full'

export type Arm = {
  id: ArmId
  label: string
  /** Full name for the readout. */
  name: string
  correct: number
  inputTokens: number
  costUsd: number
}

export const OF = 32

export const ARMS: Arm[] = [
  { id: 'graph', label: 'ProofFlow', name: 'ProofFlow (HydraDB dependency path)', correct: 32, inputTokens: 77_071, costUsd: 1.377214 },
  { id: 'exact', label: 'Exact-flat ablation', name: 'Exact-flat dependency walk (ablation)', correct: 32, inputTokens: 77_095, costUsd: 0.5055334 },
  { id: 'hybrid', label: 'Iterative hybrid', name: 'Iterative hybrid retrieval', correct: 28, inputTokens: 76_174, costUsd: 1.448095 },
  { id: 'bm25', label: 'Keyword (BM25)', name: 'Keyword search (BM25)', correct: 25, inputTokens: 75_699, costUsd: 1.427535 },
  { id: 'dense', label: 'Vector RAG', name: 'Vector RAG (BGE dense)', correct: 5, inputTokens: 75_785, costUsd: 1.377631 },
  { id: 'full', label: 'Full context', name: 'Full context (re-read everything)', correct: 32, inputTokens: 219_145, costUsd: 3.742368 },
]

export const arm = (id: ArmId) => ARMS.find(a => a.id === id) as Arm

const graph = arm('graph')
const full = arm('full')
const dense = arm('dense')

/** Derived from the table above. */
export const derived = {
  /** 219,145 − 77,071 */
  tokensSaved: full.inputTokens - graph.inputTokens,
  /** The doc's headline ratio, excluding the no-op case. */
  exposurePct: 39.33,
  /** 1 − 1.377214 / 3.742368 ≈ 63.2% */
  costLowerPct: (1 - graph.costUsd / full.costUsd) * 100,
  /** 32 / 5 */
  vsVector: graph.correct / dense.correct,
  vectorMisses: OF - dense.correct,
}

export const usd2 = (v: number) => `$${v.toFixed(2)}`
export const int = (n: number) => Math.round(n).toLocaleString('en-US')
