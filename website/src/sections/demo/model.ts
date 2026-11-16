/** View model for the walkthrough: fixed graph slots, display states and plain-language copy. */
import type { AnyRecord, ArtifactRecord, DemoSession, Json, JsonObject, ReportKey, SourceName, ToolName } from './engine'

export type Slot =
  | 'source:orders' | 'source:refunds' | 'source:fx' | 'source:tickets'
  | 'metric:gross' | 'metric:refunds' | 'metric:net' | 'metric:regional' | 'metric:company' | 'metric:support'
  | 'report:company' | 'report:eu'

export type Layer = 'source' | 'metric' | 'report'

export interface SlotDef {
  slot: Slot
  label: string
  layer: Layer
  /** Static recipe parents, used for layout and the order of the animated signal. */
  parents: Slot[]
  tool?: ToolName
  /** Node centre in the 880 x 660 graph coordinate system (top-down: sources at the top). */
  cx: number
  cy: number
  plain: string
}

export const GRAPH_W = 880
export const GRAPH_H = 660
const ROW = (i: number) => 40 + 116 * i

/** Listed in dependency (topological) order. */
export const SLOTS: SlotDef[] = [
  { slot: 'source:orders', label: 'Orders', layer: 'source', parents: [], cx: 105, cy: ROW(0),
    plain: 'Five authored orders across the EU, US and UK. The first EU order, eu-101, is the one you can correct.' },
  { slot: 'source:refunds', label: 'Refunds', layer: 'source', parents: [], cx: 325, cy: ROW(0),
    plain: 'Two refunds matched to orders, including the refund on eu-101.' },
  { slot: 'source:fx', label: 'Exchange rates', layer: 'source', parents: [], cx: 545, cy: ROW(0),
    plain: 'USD exchange rates for EUR, USD and GBP. Only the EUR rate can be corrected here.' },
  { slot: 'source:tickets', label: 'Tickets', layer: 'source', parents: [], cx: 785, cy: ROW(0),
    plain: 'Support tickets with a region and status. Corrections add new open EU tickets.' },
  { slot: 'metric:gross', label: 'Gross regional revenue', layer: 'metric', parents: ['source:orders'], tool: 'gross_by_region', cx: 105, cy: ROW(1),
    plain: 'Sums each region’s orders in that region’s own currency.' },
  { slot: 'metric:refunds', label: 'Regional refunds', layer: 'metric', parents: ['source:orders', 'source:refunds'], tool: 'refunds_by_region', cx: 325, cy: ROW(1),
    plain: 'Joins each refund to its order and sums refunds by region.' },
  { slot: 'metric:support', label: 'Support tickets', layer: 'metric', parents: ['source:tickets'], tool: 'support_by_region', cx: 785, cy: ROW(1),
    plain: 'Counts support tickets per region. No money calculation touches it.' },
  { slot: 'metric:net', label: 'Net regional revenue', layer: 'metric', parents: ['metric:gross', 'metric:refunds'], tool: 'net_by_region', cx: 215, cy: ROW(2),
    plain: 'Subtracts each region’s refunds from its gross revenue.' },
  { slot: 'metric:regional', label: 'Regional USD revenue', layer: 'metric', parents: ['metric:net', 'source:fx'], tool: 'convert_to_usd', cx: 415, cy: ROW(3),
    plain: 'Converts each region’s net revenue to USD cents with the recorded rates, rounding half to even.' },
  { slot: 'metric:company', label: 'Company revenue', layer: 'metric', parents: ['metric:regional'], tool: 'company_total', cx: 605, cy: ROW(4),
    plain: 'Adds the regional USD amounts into one company figure.' },
  { slot: 'report:company', label: 'Company weekly report', layer: 'report', parents: ['metric:company', 'metric:support'], tool: 'compose_report', cx: 785, cy: ROW(5),
    plain: 'Saved by run A. Claims company revenue and EU support tickets.' },
  { slot: 'report:eu', label: 'EU operations brief', layer: 'report', parents: ['metric:regional', 'metric:support'], tool: 'compose_report', cx: 385, cy: ROW(5),
    plain: 'Saved by a separate run B. Claims EU revenue and EU support tickets.' },
]

export const SLOT_DEF = Object.fromEntries(SLOTS.map(def => [def.slot, def])) as Record<Slot, SlotDef>

export const SOURCE_LABEL: Record<SourceName, string> = {
  orders: 'Orders', refunds: 'Refunds', fx: 'Exchange rates', tickets: 'Tickets',
}

export const TOOL_LABEL: Record<ToolName, string> = {
  gross_by_region: 'Gross by region',
  refunds_by_region: 'Refunds by region',
  net_by_region: 'Net by region',
  convert_to_usd: 'Convert to USD',
  company_total: 'Company total',
  support_by_region: 'Support by region',
  compose_report: 'Compose report',
}

/* ---------------------------------------------------------------- format */

/** Exact money formatting from integer cents: integer quotient and remainder, no float division. */
export function money(cents: number, symbol = '$'): string {
  const negative = cents < 0
  const abs = Math.abs(cents)
  const remainder = abs % 100
  const whole = (abs - remainder) / 100
  const grouped = whole.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negative ? '−' : ''}${symbol}${grouped}${remainder ? `.${remainder.toString().padStart(2, '0')}` : ''}`
}

export const SYMBOL: Record<string, string> = { USD: '$', EUR: '€', GBP: '£' }

export const shortId = (id: string) => {
  const [kind, hash = ''] = id.split(':')
  return `${kind}:${hash.slice(0, 10)}`
}

/* ------------------------------------------------------------------ view */

export type NodeState = 'current' | 'changed' | 'removed' | 'stale' | 'blocked' | 'unknown'
export type Badge = 'refreshed' | 'reused' | null

export interface NodeView {
  slot: Slot
  recordId: string
  version: number
  state: NodeState
  badge: Badge
  /** Short value shown on the node when it is current. */
  detail: string
  blockedBy: SourceName[]
}

export type ClaimState = 'current' | 'stale' | 'blocked' | 'unknown'

export interface ClaimView {
  key: string
  label: string
  unit: string
  state: ClaimState
  value: number | null
  savedValue: number
  artifactId: string
  blockedBy: SourceName[]
}

export interface ReportView {
  key: ReportKey
  slot: Slot
  title: string
  runId: string
  recordId: string
  state: NodeState
  badge: Badge
  claims: ClaimView[]
}

export interface View {
  nodes: Record<Slot, NodeView>
  reports: ReportView[]
  counts: { stale: number; blocked: number; current: number }
}

const asObject = (value: Json): JsonObject => (value && typeof value === 'object' && !Array.isArray(value) ? value : {})

function regionMoney(value: Json, region = 'EU'): string {
  const entry = asObject(asObject(asObject(value).regions)[region] ?? null)
  if (typeof entry.usd_cents === 'number') return `${region} ${money(entry.usd_cents)}`
  if (typeof entry.amount_cents === 'number') return `${region} ${money(entry.amount_cents, SYMBOL[String(entry.currency)] ?? '')}`
  if (typeof entry.tickets === 'number') return `${region} ${entry.tickets} tickets`
  return ''
}

export function sourceDetail(name: SourceName, value: Json): string {
  if (value === null) return 'Removed'
  if (name === 'fx') return `EUR ${String(asObject(value).EUR)}`
  const list = Array.isArray(value) ? value.map(asObject) : []
  if (name === 'orders') return `eu-101 ${money(Number(list[0]?.gross_cents ?? 0), '€')}`
  if (name === 'refunds') return `eu-101 ${money(Number(list[0]?.refund_cents ?? 0), '€')}`
  return `EU ${list.filter(row => row.region === 'EU').length} tickets`
}

function artifactDetail(record: ArtifactRecord): string {
  if (record.tool === 'company_total') return money(Number(asObject(record.value).usd_cents))
  if (record.tool === 'compose_report') return `${(asObject(record.value).sections as Json[] | undefined)?.length ?? 0} claims`
  return regionMoney(record.value)
}

/** Build the display state of every slot from the engine. */
export function buildView(session: DemoSession): View {
  const runtime = session.runtime
  const heads = [...runtime.heads.values()].map(id => runtime.get(id))
  const artifactHeads = heads.filter((record): record is ArtifactRecord => record.kind === 'artifact')
  const refresh = session.lastRefresh
  const nodes = {} as Record<Slot, NodeView>

  for (const def of SLOTS) {
    const head = runtime.getHead(def.slot) as AnyRecord
    let state: NodeState = 'current'
    let detail = ''
    let blockedBy: SourceName[] = []
    let badge: Badge = null
    if (head.kind === 'source') {
      const name = head.name as SourceName
      detail = sourceDetail(name, head.value)
      if (head.deleted) state = 'removed'
      else {
        const consumersReadOther = artifactHeads.some(artifact => Object.values(artifact.inputs).some(inputId => {
          const input = runtime.records.get(inputId)
          return input?.logicalId === def.slot && input.id !== head.id
        }))
        if (consumersReadOther) state = 'changed'
      }
    } else if (head.kind === 'artifact') {
      const validity = runtime.currentness(head.id).state
      blockedBy = validity === 'current' ? [] : session.blockedBy(head.id)
      state = validity === 'current' ? 'current' : blockedBy.length ? 'blocked' : validity
      detail = artifactDetail(head)
      if (refresh?.executedArtifactIds.includes(head.id)) badge = 'refreshed'
      else if (refresh?.reusedArtifactIds.includes(head.id)) badge = 'reused'
    }
    nodes[def.slot] = { slot: def.slot, recordId: head.id, version: head.version, state, badge, detail, blockedBy }
  }

  const reports: ReportView[] = session.reports().map(({ key, record }) => {
    const slot = `report:${key}` as Slot
    const claims: ClaimView[] = runtime.reportClaims(record.id).map(claim => {
      const blockedBy = claim.state === 'current' ? [] : session.blockedBy(claim.artifactId)
      return {
        key: claim.key, label: claim.label, unit: claim.unit,
        state: claim.state === 'current' ? 'current' : blockedBy.length ? 'blocked' : claim.state,
        value: claim.value, savedValue: claim.savedValue, artifactId: claim.artifactId, blockedBy,
      }
    })
    return {
      key, slot, title: session.label(record), runId: record.runId, recordId: record.id,
      state: nodes[slot].state, badge: nodes[slot].badge, claims,
    }
  })

  const all = Object.values(nodes).filter(node => SLOT_DEF[node.slot].layer !== 'source')
  return {
    nodes,
    reports,
    counts: {
      stale: all.filter(node => node.state === 'stale' || node.state === 'unknown').length,
      blocked: all.filter(node => node.state === 'blocked').length,
      current: all.filter(node => node.state === 'current').length,
    },
  }
}

/** Longest-path depth from the given roots over the static recipe graph (dependency order). */
export function depthFrom(roots: Slot[]): Partial<Record<Slot, number>> {
  const depth: Partial<Record<Slot, number>> = {}
  for (const root of roots) depth[root] = 0
  for (const def of SLOTS) {
    const parentDepths = def.parents.map(parent => depth[parent]).filter((d): d is number => d !== undefined)
    if (parentDepths.length && depth[def.slot] === undefined) depth[def.slot] = Math.max(...parentDepths) + 1
  }
  return depth
}

export const nodeChanged = (a: NodeView, b: NodeView) => a.state !== b.state || a.badge !== b.badge || a.recordId !== b.recordId

/** Shortest recorded lineage path (record IDs) from any root to the target, or null. */
export function lineagePath(session: DemoSession, roots: string[], target: string): string[] | null {
  const runtime = session.runtime
  for (const root of roots) {
    const previous = new Map<string, string | null>([[root, null]])
    const queue = [root]
    while (queue.length) {
      const id = queue.shift()!
      if (id === target) {
        const path: string[] = []
        for (let at: string | null = id; at; at = previous.get(at) ?? null) path.unshift(at)
        return path
      }
      for (const child of runtime.childrenOf(id)) {
        if (!previous.has(child)) {
          previous.set(child, id)
          queue.push(child)
        }
      }
    }
  }
  return null
}

/** Plain name of any record, e.g. "Exchange rates v2", "Convert to USD", "Regional USD revenue v1". */
export function recordName(record: AnyRecord): string {
  if (record.kind === 'source') return `${SOURCE_LABEL[record.name as SourceName] ?? record.name} v${record.version}`
  if (record.kind === 'execution') return `${TOOL_LABEL[record.tool]} ran`
  if (record.kind === 'tool') return `${TOOL_LABEL[record.name]} tool`
  return `${SLOT_DEF[record.logicalId as Slot]?.label ?? record.title} v${record.version}`
}

export const STATE_TEXT: Record<NodeState, string> = {
  current: 'Current',
  changed: 'Changed',
  removed: 'Removed',
  stale: 'Needs refresh',
  blocked: 'Blocked',
  unknown: 'Unknown',
}
