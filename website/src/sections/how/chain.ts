/**
 * The guided-sample lineage chain, as drawn in README.md ("How it works" mermaid diagram).
 * Record kinds and edge kinds mirror proofflow/runtime.py: an execution receipt CONSUMED its
 * inputs, USED_TOOL a tool version, and PRODUCED one immutable artifact.
 * Values: README.md "Run the application" table (EUR→USD 1.10 → 1.20).
 */

import type { Box } from './geometry'

export type NodeId = 'fx' | 'net' | 'tool' | 'exec' | 'regional' | 'support' | 'company' | 'eu'
export type RecordKind = 'source' | 'tool' | 'execution' | 'artifact' | 'report'
export type NodeState = 'current' | 'stale' | 'refreshed' | 'reused'

export interface ChainNode {
  id: NodeId
  kind: RecordKind
  title: string
  /** Default secondary line. Steps may override it. */
  sub: string
  /** Report nodes carry one claim. */
  claim?: string
}

export const NODES: ChainNode[] = [
  { id: 'fx', kind: 'source', title: 'FX rate', sub: 'EUR→USD 1.10' },
  { id: 'net', kind: 'artifact', title: 'Net revenue', sub: 'artifact' },
  { id: 'tool', kind: 'tool', title: 'convert_to_usd', sub: 'tool version' },
  { id: 'exec', kind: 'execution', title: 'Conversion', sub: 'execution receipt' },
  { id: 'regional', kind: 'artifact', title: 'Regional USD', sub: 'artifact, content-hashed' },
  { id: 'support', kind: 'artifact', title: 'Support tickets', sub: 'artifact' },
  { id: 'company', kind: 'report', title: 'Company report', sub: '', claim: 'Company revenue' },
  { id: 'eu', kind: 'report', title: 'EU brief', sub: '', claim: 'EU revenue' },
]

export interface ChainEdge {
  id: string
  from: NodeId
  to: NodeId
  /** Edge kind from proofflow/runtime.py; only shown where it teaches something. */
  label?: 'CONSUMED' | 'USED_TOOL' | 'PRODUCED'
  /** Steps of propagation from the changed source (for the stale pulse and refresh re-ink). */
  depth: number
}

export const EDGES: ChainEdge[] = [
  { id: 'fx-exec', from: 'fx', to: 'exec', label: 'CONSUMED', depth: 0 },
  { id: 'net-exec', from: 'net', to: 'exec', label: 'CONSUMED', depth: 0 },
  { id: 'tool-exec', from: 'tool', to: 'exec', label: 'USED_TOOL', depth: 0 },
  { id: 'exec-regional', from: 'exec', to: 'regional', label: 'PRODUCED', depth: 1 },
  { id: 'regional-company', from: 'regional', to: 'company', depth: 2 },
  { id: 'regional-eu', from: 'regional', to: 'eu', depth: 2 },
  { id: 'support-company', from: 'support', to: 'company', depth: 2 },
  { id: 'support-eu', from: 'support', to: 'eu', depth: 2 },
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
    support: { x: 264, y: 282, w: 112, h: 58 },
    company: { x: 84, y: 414, w: 156, h: 92 },
    eu: { x: 248, y: 414, w: 156, h: 92 },
  },
}

export interface NodeView { state: NodeState; sub?: string; value?: string }

export interface Step {
  key: string
  label: string
  title: string
  body: string
  /** Bullet points shown under the body (refresh only). */
  points?: string[]
  visible: NodeId[]
  view: Partial<Record<NodeId, NodeView>>
}

const all: NodeId[] = ['fx', 'net', 'tool', 'exec', 'regional', 'support', 'company', 'eu']
const before = { company: { state: 'current', value: '$5,565' }, eu: { state: 'current', value: '$2,090' } } as const

export const STEPS: Step[] = [
  {
    key: 'source',
    label: 'Source version',
    title: 'A source version',
    body: 'Every input is saved as an immutable version. Here, the EUR to USD exchange rate is 1.10.',
    visible: ['fx'],
    view: {},
  },
  {
    key: 'receipt',
    label: 'Execution receipt',
    title: 'An execution receipt',
    body: 'Running a registered tool writes a receipt: which tool version ran and exactly which inputs it consumed.',
    visible: ['fx', 'net', 'tool', 'exec'],
    view: {},
  },
  {
    key: 'artifact',
    label: 'Immutable artifact',
    title: 'An immutable artifact',
    body: 'The output is stored once, named by the hash of its content, and never edited. A new result is a new artifact.',
    visible: ['fx', 'net', 'tool', 'exec', 'regional'],
    view: {},
  },
  {
    key: 'claim',
    label: 'Report claim',
    title: 'A report claim',
    body: 'Each number in a saved report points at the artifact it came from. Both reports share the regional revenue; support is a separate artifact.',
    visible: all,
    view: { ...before },
  },
  {
    key: 'change',
    label: 'A source changes',
    title: 'Correct the rate to 1.20',
    body: 'HydraDB walks the descendants of the old version. Every claim on that path is withheld instead of served stale. Support is not on the path.',
    visible: all,
    view: {
      fx: { state: 'stale', sub: '1.10, replaced by 1.20' },
      exec: { state: 'stale' },
      regional: { state: 'stale' },
      company: { state: 'stale' },
      eu: { state: 'stale' },
    },
  },
  {
    key: 'refresh',
    label: 'Refresh',
    title: 'Refresh only what changed',
    body: 'Four tools ran. Revenue moved to the new rate; the support artifact kept its identity.',
    points: [
      'Walk prerequisites first',
      'Re-execute only stale work',
      'Rebind inputs to the current heads',
      'Reuse what is still current',
    ],
    visible: all,
    view: {
      fx: { state: 'current', sub: 'EUR→USD 1.20' },
      exec: { state: 'refreshed', sub: 'new receipt' },
      regional: { state: 'refreshed', sub: 'new artifact' },
      company: { state: 'refreshed', value: '$5,755' },
      eu: { state: 'refreshed', value: '$2,280' },
      support: { state: 'reused', sub: 'reused' },
      net: { state: 'reused', sub: 'reused' },
    },
  },
]

/** Plain-language description of a step's picture, used as the SVG's accessible name. */
export function describe(step: Step): string {
  const shown = step.visible.map(id => NODES.find(n => n.id === id)!.title)
  const states = step.visible
    .map(id => ({ id, v: step.view[id] }))
    .filter(x => x.v && x.v.state !== 'current')
    .map(x => `${NODES.find(n => n.id === x.id)!.title} ${x.v!.state === 'stale' ? 'stale, withheld' : x.v!.state}`)
  return `Lineage chain showing ${shown.join(', ')}.${states.length ? ` ${states.join('; ')}.` : ' All current.'}`
}
