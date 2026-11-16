/**
 * The guided-sample lineage chain, as drawn in README.md ("How it works" mermaid diagram).
 * Record kinds and edge kinds mirror proofflow/runtime.py: an execution receipt CONSUMED its
 * inputs, USED_TOOL a tool version, and PRODUCED one immutable artifact.
 * Values: README.md "Run the application" table (EUR→USD 1.10 → 1.20; four tools re-run on refresh,
 * support reused).
 *
 * The story is driven by one number, scroll progress p in [0, 1]. Every timing below is a slice of p.
 */

import type { Box } from './geometry'

export type NodeId = 'fx' | 'net' | 'tool' | 'exec' | 'regional' | 'support' | 'company' | 'eu'
export type RecordKind = 'source' | 'tool' | 'execution' | 'artifact' | 'report'
export type NodeState = 'current' | 'stale' | 'refreshed' | 'reused'

export interface ChainNode {
  id: NodeId
  kind: RecordKind
  title: string
  sub: string
  claim?: string
  /** p at which the node has fully appeared (it fades in over APPEAR before this). */
  shown: number
  /** p at which the correction pulse reaches it (stale), and the refresh re-ink (refreshed or reused). */
  staleAt?: number
  freshAt?: number
  fresh?: 'refreshed' | 'reused'
}

export const APPEAR = 0.035

/** Six chapters of equal length. Labels stay at four words or fewer; the caption is one sentence. */
export const PHASES = [
  { key: 'source', label: 'Source version', caption: 'Every input is saved as an immutable version: here, EUR→USD at 1.10.' },
  { key: 'receipt', label: 'Execution receipt', caption: 'Each tool run records the tool version and exactly which inputs it consumed.' },
  { key: 'artifact', label: 'Immutable artifact', caption: 'The output is stored once, named by its content hash, and never edited.' },
  { key: 'claim', label: 'Report claim', caption: 'Every number in a saved report points at the artifact it came from.' },
  { key: 'change', label: 'Correction', caption: 'The rate becomes 1.20. HydraDB returns the exact dependency path, not look-alike text; those claims are withheld.' },
  { key: 'refresh', label: 'Refresh', caption: 'Only that path is recomputed, no full re-read: four tools re-run, and support is reused.' },
] as const

export const PHASE_LEN = 1 / PHASES.length
export const CHANGE_AT = 4 * PHASE_LEN + 0.012 // the rate is corrected
export const REFRESH_AT = 5 * PHASE_LEN + 0.008 // refresh begins

export const NODES: ChainNode[] = [
  { id: 'fx', kind: 'source', title: 'FX rate', sub: 'EUR→USD 1.10', shown: 0, staleAt: CHANGE_AT, freshAt: REFRESH_AT },
  { id: 'net', kind: 'artifact', title: 'Net revenue', sub: 'artifact', shown: 0.21, freshAt: REFRESH_AT + 0.02, fresh: 'reused' },
  { id: 'tool', kind: 'tool', title: 'convert_to_usd', sub: 'tool version', shown: 0.225 },
  { id: 'exec', kind: 'execution', title: 'Conversion', sub: 'execution receipt', shown: 0.295, staleAt: 0.735, freshAt: 0.895, fresh: 'refreshed' },
  { id: 'regional', kind: 'artifact', title: 'Regional result', sub: 'artifact, content-hashed', shown: 0.44, staleAt: 0.775, freshAt: 0.935, fresh: 'refreshed' },
  { id: 'support', kind: 'artifact', title: 'Support tickets', sub: 'artifact', shown: 0.54, freshAt: REFRESH_AT + 0.02, fresh: 'reused' },
  { id: 'company', kind: 'report', title: 'Company report', sub: '', claim: 'Revenue claim', shown: 0.62, staleAt: 0.815, freshAt: 0.975, fresh: 'refreshed' },
  { id: 'eu', kind: 'report', title: 'EU brief', sub: '', claim: 'Revenue claim', shown: 0.625, staleAt: 0.815, freshAt: 0.975, fresh: 'refreshed' },
]

export interface ChainEdge {
  id: string
  from: NodeId
  to: NodeId
  label?: 'CONSUMED' | 'USED_TOOL' | 'PRODUCED'
  /** The thread draws over this slice of p. */
  draw: [number, number]
  /** The orange correction pulse travels this edge (only the path from the changed source). */
  pulse?: [number, number]
  /** The mint refresh re-ink. */
  ink: [number, number]
}

export const EDGES: ChainEdge[] = [
  { id: 'fx-exec', from: 'fx', to: 'exec', label: 'CONSUMED', draw: [0.215, 0.27], pulse: [0.695, 0.735], ink: [0.855, 0.895] },
  { id: 'net-exec', from: 'net', to: 'exec', label: 'CONSUMED', draw: [0.225, 0.275], ink: [0.855, 0.895] },
  { id: 'tool-exec', from: 'tool', to: 'exec', label: 'USED_TOOL', draw: [0.235, 0.28], ink: [0.855, 0.895] },
  { id: 'exec-regional', from: 'exec', to: 'regional', label: 'PRODUCED', draw: [0.36, 0.41], pulse: [0.735, 0.775], ink: [0.895, 0.935] },
  { id: 'regional-company', from: 'regional', to: 'company', draw: [0.55, 0.6], pulse: [0.775, 0.815], ink: [0.935, 0.975] },
  { id: 'regional-eu', from: 'regional', to: 'eu', draw: [0.55, 0.6], pulse: [0.775, 0.815], ink: [0.935, 0.975] },
  { id: 'support-company', from: 'support', to: 'company', draw: [0.565, 0.61], ink: [0.935, 0.975] },
  { id: 'support-eu', from: 'support', to: 'eu', draw: [0.565, 0.61], ink: [0.935, 0.975] },
]

export interface Layout { width: number; height: number; axis: 'x' | 'y'; nodes: Record<NodeId, Box> }

/** Wide layout reads left to right, like the README diagram. */
export const WIDE: Layout = {
  width: 960,
  height: 410,
  axis: 'x',
  nodes: {
    fx: { x: 95, y: 92, w: 158, h: 62 },
    net: { x: 95, y: 250, w: 158, h: 62 },
    tool: { x: 330, y: 338, w: 168, h: 50 },
    exec: { x: 330, y: 171, w: 168, h: 62 },
    regional: { x: 560, y: 171, w: 176, h: 62 },
    support: { x: 560, y: 336, w: 176, h: 62 },
    company: { x: 820, y: 96, w: 196, h: 92 },
    eu: { x: 820, y: 262, w: 196, h: 92 },
  },
}

/** Phone layout reads top to bottom so labels stay legible. */
export const NARROW: Layout = {
  width: 330,
  height: 470,
  axis: 'y',
  nodes: {
    fx: { x: 84, y: 38, w: 150, h: 58 },
    net: { x: 248, y: 38, w: 150, h: 58 },
    exec: { x: 100, y: 160, w: 170, h: 58 },
    tool: { x: 262, y: 160, w: 120, h: 46 },
    regional: { x: 100, y: 282, w: 170, h: 58 },
    support: { x: 262, y: 282, w: 124, h: 58 },
    company: { x: 84, y: 414, w: 156, h: 92 },
    eu: { x: 248, y: 414, w: 156, h: 92 },
  },
}

/**
 * Report claims are shown by version, not by amount: the sample's dollar values are report content
 * (README.md: company $5,565 → $5,755, EU $2,090 → $2,280) and belong to the demo, not this diagram.
 */
export const VALUES: Record<'company' | 'eu', { before: string; after: string }> = {
  company: { before: 'v1', after: 'v2' },
  eu: { before: 'v1', after: 'v2' },
}

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v))
export const span = (p: number, [a, b]: [number, number]) => clamp01((p - a) / (b - a))

export function stateAt(node: ChainNode, p: number): NodeState {
  if (node.freshAt !== undefined && p >= node.freshAt) return node.fresh ?? 'current'
  if (node.staleAt !== undefined && p >= node.staleAt) return 'stale'
  return 'current'
}

export function subAt(node: ChainNode, p: number): string {
  const state = stateAt(node, p)
  if (node.id === 'fx') {
    if (p >= REFRESH_AT) return 'EUR→USD 1.20'
    if (p >= CHANGE_AT) return '1.10, replaced by 1.20'
  }
  if (state === 'refreshed') return node.kind === 'execution' ? 'new receipt' : 'new artifact'
  if (state === 'reused') return 'reused'
  return node.sub
}

/** Plain-language picture of the chain at p, for the SVG's accessible name. */
export function describe(p: number): string {
  const shown = NODES.filter(n => p >= n.shown - APPEAR)
  const states = shown.filter(n => stateAt(n, p) !== 'current')
    .map(n => `${n.title} ${stateAt(n, p) === 'stale' ? 'stale, withheld' : stateAt(n, p)}`)
  return `Lineage chain showing ${shown.map(n => n.title).join(', ')}.${states.length ? ` ${states.join('; ')}.` : ' All current.'}`
}
