/**
 * Client-side replay of the ProofFlow guided sample.
 *
 * A faithful, small port of three files in the repository:
 *   - proofflow/analytics.py  the seven registered tools and DEMO_SOURCES (same arithmetic:
 *                             integer cents, Decimal exchange rates, ROUND_HALF_EVEN)
 *   - proofflow/runtime.py    immutable records, execution receipts, lineage edges,
 *                             currentness, affected, refresh (prerequisites first, rebind to
 *                             current heads, reuse current artifacts), full_recompute, report_claims
 *   - proofflow/demo.py       how the guided sample wires runs A and B, the five bounded
 *                             corrections, refresh bookkeeping and verify
 *
 * Differences from the server, on purpose and visible in the UI:
 *   - Record IDs and content hashes are generated in the browser with a 64-bit non-cryptographic
 *     hash (cyrb53) over canonical JSON. The server uses SHA-256 and HydraDB for traversal.
 *   - The lineage graph is an in-memory adjacency map, not HydraDB native traversal.
 *   - Exchange rates accept plain decimal notation only (no exponent form).
 *
 * Derivation of the verified table (README.md, "Run the application"):
 *   EU net    = 120000 + 80000 - 10000 = 190000 EUR cents
 *   US net    = 180000 + 60000 -  5000 = 235000 USD cents
 *   UK net    =  90000                 =  90000 GBP cents
 *   at EUR 1.10: EU 209000 + US 235000 + UK 112500 (90000 x 1.25) = 556500 cents  -> $5,565 / EU $2,090
 *   at EUR 1.20: EU 228000 + US 235000 + UK 112500                = 575500 cents  -> $5,755 / EU $2,280
 *   Refresh executes convert_to_usd, company_total and two compose_report calls = 4 tools;
 *   net_by_region and support_by_region are reused, so the support claim keeps the same artifact.
 * `selfCheck()` below replays that scenario and returns each comparison.
 */

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
export type JsonObject = { [key: string]: Json }

export class AnalyticsError extends Error { name = 'AnalyticsError' }
export class InvalidInputError extends Error { name = 'InvalidInputError' }
export class MissingEvidenceError extends Error { name = 'MissingEvidenceError' }
export class DependencyCycleError extends Error { name = 'DependencyCycleError' }

/* ------------------------------------------------------------------ hashing */

export function canonicalJson(value: Json | undefined): string {
  if (value === undefined) return 'null'
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`
}

/** cyrb53-style 64-bit hash as 16 hex characters. Not cryptographic; labelled as such in the UI. */
function hash64(text: string): string {
  let h1 = 0xdeadbeef
  let h2 = 0x41c6ce57
  for (let i = 0; i < text.length; i++) {
    const ch = text.charCodeAt(i)
    h1 = Math.imul(h1 ^ ch, 2654435761)
    h2 = Math.imul(h2 ^ ch, 1597334677)
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507)
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507)
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909)
  return (h2 >>> 0).toString(16).padStart(8, '0') + (h1 >>> 0).toString(16).padStart(8, '0')
}

export const digest = (value: Json | undefined) => hash64(canonicalJson(value))

const clone = <T extends Json>(value: T): T => JSON.parse(JSON.stringify(value)) as T

/* ------------------------------------------------------------ exact decimal */

export interface DecimalValue { negative: boolean; mantissa: bigint; scale: number; text: string }

/** Parse a plain decimal string the way Python's Decimal(str) does, keeping its canonical str(). */
export function parseDecimal(raw: string): DecimalValue | null {
  const match = /^\s*([+-])?(\d*)(?:\.(\d*))?\s*$/.exec(raw)
  if (!match) return null
  const [, sign, whole = '', frac = ''] = match
  if (!whole && !frac) return null
  const negative = sign === '-'
  const intPart = whole.replace(/^0+(?=\d)/, '') || '0'
  const hasPoint = raw.includes('.') && frac.length > 0
  const text = `${negative ? '-' : ''}${intPart}${hasPoint ? `.${frac}` : ''}`
  const mantissa = BigInt(`${intPart}${frac}`) * (negative ? -1n : 1n)
  return { negative, mantissa, scale: frac.length, text }
}

function compareDecimal(a: DecimalValue, b: DecimalValue): number {
  const scale = Math.max(a.scale, b.scale)
  const x = a.mantissa * 10n ** BigInt(scale - a.scale)
  const y = b.mantissa * 10n ** BigInt(scale - b.scale)
  return x === y ? 0 : x < y ? -1 : 1
}

/** Integer division with ROUND_HALF_EVEN, matching Decimal.quantize(Decimal('1'), ROUND_HALF_EVEN). */
function divideHalfEven(numerator: bigint, denominator: bigint): bigint {
  let quotient = numerator / denominator
  const remainder = numerator % denominator
  if (remainder === 0n) return quotient
  const negative = (numerator < 0n) !== (denominator < 0n)
  const twice = (remainder < 0n ? -remainder : remainder) * 2n
  const absDen = denominator < 0n ? -denominator : denominator
  if (twice > absDen || (twice === absDen && quotient % 2n !== 0n)) quotient += negative ? -1n : 1n
  return quotient
}

/* ----------------------------------------------------------------- tools */

export const TOOL_SPECS = {
  gross_by_region: { version: '1', description: 'Sum order amounts by region and currency.', inputs: ['orders'] },
  refunds_by_region: { version: '1', description: 'Join refunds to orders and sum refunded amounts by region.', inputs: ['orders', 'refunds'] },
  net_by_region: { version: '1', description: 'Subtract regional refunds from gross revenue.', inputs: ['gross', 'refunds'] },
  convert_to_usd: { version: '1', description: 'Convert net regional amounts to USD cents using explicit rates.', inputs: ['net', 'fx'] },
  company_total: { version: '1', description: 'Sum USD regional revenue into company revenue.', inputs: ['regional'] },
  support_by_region: { version: '1', description: 'Count support tickets by region.', inputs: ['tickets'] },
  compose_report: { version: '1', description: 'Compose structured numeric claims from explicit artifact inputs.', inputs: [] },
} as const satisfies Record<string, { version: string; description: string; inputs: readonly string[] }>

export type ToolName = keyof typeof TOOL_SPECS
export const TOOL_NAMES = Object.keys(TOOL_SPECS) as ToolName[]

const INT64_MIN = -(2n ** 63n)
const INT64_MAX = 2n ** 63n

function mapping(value: Json | undefined, where: string): JsonObject {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new AnalyticsError(`${where} must be an object with string keys`)
  return value
}

function rows(value: Json | undefined, where: string): JsonObject[] {
  if (!Array.isArray(value)) throw new AnalyticsError(`${where} must be a list of records`)
  return value.map((row, index) => mapping(row, `${where}[${index}]`))
}

function text(value: Json | undefined, where: string, limit = 200): string {
  if (typeof value !== 'string' || !value.trim() || value.length > limit || value.includes('\u0000')) {
    throw new AnalyticsError(`${where} must be a nonempty string of at most ${limit} characters`)
  }
  return value
}

function integer(value: Json | undefined, where: string, nonnegative = false): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value)) throw new AnalyticsError(`${where} must be a signed 64-bit integer`)
  if (nonnegative && value < 0) throw new AnalyticsError(`${where} must be nonnegative`)
  return value
}

function currency(value: Json | undefined, where: string): string {
  const code = text(value, where, 3)
  if (!/^[A-Z]{3}$/.test(code)) throw new AnalyticsError(`${where} must be a three-letter uppercase currency`)
  return code
}

const byKey = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0)

interface Order { order_id: string; region: string; currency: string; gross_cents: number }

function loadOrders(value: Json | undefined): Order[] {
  const orders = rows(value, 'orders').map((row, index) => ({
    order_id: text(row.order_id, `orders[${index}].order_id`),
    region: text(row.region, `orders[${index}].region`, 64),
    currency: currency(row.currency, `orders[${index}].currency`),
    gross_cents: integer(row.gross_cents, `orders[${index}].gross_cents`, true),
  }))
  const ids = new Set<string>()
  for (const order of orders) {
    if (ids.has(order.order_id)) throw new AnalyticsError('Analytics query failed: UNIQUE constraint failed: orders.order_id')
    ids.add(order.order_id)
  }
  const currencies = new Map<string, Set<string>>()
  for (const order of orders) {
    const set = currencies.get(order.region) ?? new Set<string>()
    set.add(order.currency)
    currencies.set(order.region, set)
  }
  const mixed = [...currencies.keys()].sort(byKey).find(region => (currencies.get(region)?.size ?? 0) > 1)
  if (mixed) throw new AnalyticsError(`Region '${mixed}' contains more than one currency`)
  return orders
}

function groupedRows(groups: Map<string, { currency: string; amount: number }>): JsonObject {
  const regions: JsonObject = {}
  for (const region of [...groups.keys()].sort(byKey)) {
    const group = groups.get(region)!
    regions[region] = { currency: group.currency, amount_cents: group.amount }
  }
  return { regions }
}

function grossByRegion(inputs: JsonObject): JsonObject {
  const groups = new Map<string, { currency: string; amount: number }>()
  for (const order of loadOrders(inputs.orders)) {
    const group = groups.get(order.region) ?? { currency: order.currency, amount: 0 }
    group.amount += order.gross_cents
    groups.set(order.region, group)
  }
  return groupedRows(groups)
}

function refundsByRegion(inputs: JsonObject): JsonObject {
  const orders = new Map(loadOrders(inputs.orders).map(order => [order.order_id, order]))
  const refunds = rows(inputs.refunds, 'refunds').map((row, index) => ({
    order_id: text(row.order_id, `refunds[${index}].order_id`),
    refund_cents: integer(row.refund_cents, `refunds[${index}].refund_cents`, true),
  }))
  const unmatched = refunds.find(refund => !orders.has(refund.order_id))
  if (unmatched) throw new AnalyticsError(`Refund references unknown order '${unmatched.order_id}'`)
  const groups = new Map<string, { currency: string; amount: number }>()
  for (const refund of refunds) {
    const order = orders.get(refund.order_id)!
    const group = groups.get(order.region) ?? { currency: order.currency, amount: 0 }
    group.amount += refund.refund_cents
    groups.set(order.region, group)
  }
  return groupedRows(groups)
}

function moneyRegions(value: Json | undefined, where: string) {
  const raw = mapping(mapping(value, where).regions, `${where}.regions`)
  const regions = new Map<string, { currency: string; amount_cents: number }>()
  for (const region of Object.keys(raw)) {
    text(region, `${where} region`, 64)
    const row = mapping(raw[region], `${where}.${region}`)
    regions.set(region, {
      currency: currency(row.currency, `${where}.${region}.currency`),
      amount_cents: integer(row.amount_cents, `${where}.${region}.amount_cents`),
    })
  }
  return regions
}

function netByRegion(inputs: JsonObject): JsonObject {
  const gross = moneyRegions(inputs.gross, 'gross')
  const refunds = moneyRegions(inputs.refunds, 'refunds')
  const unknown = [...refunds.keys()].filter(region => !gross.has(region)).sort(byKey)
  if (unknown.length) throw new AnalyticsError(`Refund totals refer to unknown gross regions: ${unknown.join(', ')}`)
  const result: JsonObject = {}
  for (const region of [...gross.keys()].sort(byKey)) {
    const amount = gross.get(region)!
    const refund = refunds.get(region) ?? { currency: amount.currency, amount_cents: 0 }
    if (refund.currency !== amount.currency) throw new AnalyticsError(`Gross/refund currency mismatch for region '${region}'`)
    result[region] = { currency: amount.currency, amount_cents: integer(amount.amount_cents - refund.amount_cents, `net.${region}`) }
  }
  return { regions: result }
}

function convertToUsd(inputs: JsonObject): JsonObject {
  const net = moneyRegions(inputs.net, 'net')
  const fx = mapping(inputs.fx, 'fx')
  const result: JsonObject = {}
  for (const region of [...net.keys()].sort(byKey)) {
    const amount = net.get(region)!
    const value = fx[amount.currency]
    if (typeof value !== 'string' && typeof value !== 'number') throw new AnalyticsError(`Missing or invalid exchange rate for ${amount.currency}`)
    const rate = parseDecimal(String(value))
    if (!rate) throw new AnalyticsError(`Invalid exchange rate for ${amount.currency}`)
    if (rate.mantissa <= 0n) throw new AnalyticsError(`Exchange rate for ${amount.currency} must be finite and positive`)
    // Decimal(amount_cents) * rate, quantized to whole cents with ROUND_HALF_EVEN.
    const converted = divideHalfEven(BigInt(amount.amount_cents) * rate.mantissa, 10n ** BigInt(rate.scale))
    if (converted < INT64_MIN || converted >= INT64_MAX || converted > BigInt(Number.MAX_SAFE_INTEGER) || converted < BigInt(Number.MIN_SAFE_INTEGER)) {
      throw new AnalyticsError(`converted.${region} must be a signed 64-bit integer`)
    }
    result[region] = { usd_cents: Number(converted) }
  }
  return { regions: result }
}

function companyTotal(inputs: JsonObject): JsonObject {
  const raw = mapping(mapping(inputs.regional, 'regional').regions, 'regional.regions')
  let total = 0
  for (const region of Object.keys(raw).sort(byKey)) {
    total += integer(mapping(raw[region], `regional.${region}`).usd_cents, `regional.${region}.usd_cents`)
  }
  return { usd_cents: integer(total, 'company_total') }
}

function supportByRegion(inputs: JsonObject): JsonObject {
  const tickets = rows(inputs.tickets, 'tickets').map((row, index) => ({
    ticket_id: text(row.ticket_id, `tickets[${index}].ticket_id`),
    region: text(row.region, `tickets[${index}].region`, 64),
    status: text(row.status, `tickets[${index}].status`, 64),
  }))
  const ids = new Set<string>()
  const counts = new Map<string, number>()
  for (const ticket of tickets) {
    if (ids.has(ticket.ticket_id)) throw new AnalyticsError('Analytics query failed: UNIQUE constraint failed: tickets.ticket_id')
    ids.add(ticket.ticket_id)
    counts.set(ticket.region, (counts.get(ticket.region) ?? 0) + 1)
  }
  const regions: JsonObject = {}
  for (const region of [...counts.keys()].sort(byKey)) regions[region] = { tickets: counts.get(region)! }
  return { regions }
}

function composeReport(inputs: JsonObject, params: JsonObject): JsonObject {
  const title = text(params.title, 'report title', 300)
  const sections = rows(params.sections, 'sections')
  if (!sections.length) throw new AnalyticsError('A report requires at least one section')
  const keys = new Set<string>()
  const output: Json[] = []
  sections.forEach((section, index) => {
    const key = text(section.key, `sections[${index}].key`, 80)
    if (keys.has(key)) throw new AnalyticsError(`Duplicate report section key '${key}'`)
    keys.add(key)
    const label = text(section.label, `sections[${index}].label`, 300)
    const unit = text(section.unit, `sections[${index}].unit`, 80)
    const inputName = text(section.input, `sections[${index}].input`, 100)
    if (!(inputName in inputs)) throw new AnalyticsError(`Unknown report input '${inputName}'`)
    const path = section.path
    if (!Array.isArray(path) || !path.length || path.length > 16) throw new AnalyticsError(`sections[${index}].path must contain 1–16 object keys`)
    let value: Json = inputs[inputName]
    for (const part of path) {
      if (typeof part !== 'string' || !part || part.startsWith('__') || part.includes('\u0000')) throw new AnalyticsError(`Invalid report path key ${JSON.stringify(part)}`)
      if (value === null || typeof value !== 'object' || Array.isArray(value) || !(part in value)) {
        throw new AnalyticsError(`Report path ${JSON.stringify(path)} does not exist in '${inputName}'`)
      }
      value = value[part]
    }
    if (typeof value !== 'number' || !Number.isFinite(value)) throw new AnalyticsError('Report claims must select a numeric value')
    output.push({ key, label, value, unit })
  })
  return { title, sections: output }
}

const IMPLEMENTATIONS: Record<ToolName, (inputs: JsonObject, params: JsonObject) => JsonObject> = {
  gross_by_region: grossByRegion,
  refunds_by_region: refundsByRegion,
  net_by_region: netByRegion,
  convert_to_usd: convertToUsd,
  company_total: companyTotal,
  support_by_region: supportByRegion,
  compose_report: composeReport,
}

/** analytics.execute_tool: all data and dependencies are explicit; extra inputs are refused. */
export function executeTool(name: ToolName, inputs: JsonObject, params: JsonObject = {}): JsonObject {
  if (!(name in TOOL_SPECS)) throw new AnalyticsError(`Unknown tool '${name}'`)
  if (name !== 'compose_report') {
    const expected = [...TOOL_SPECS[name].inputs].sort(byKey)
    const got = Object.keys(inputs).sort(byKey)
    if (expected.join('\u0000') !== got.join('\u0000')) throw new AnalyticsError(`${name} requires exactly inputs [${expected.join(', ')}], got [${got.join(', ')}]`)
    if (Object.keys(params).length) throw new AnalyticsError(`${name} does not accept parameters`)
  } else if (Object.keys(params).sort(byKey).join(',') !== 'sections,title') {
    throw new AnalyticsError('compose_report requires exactly title and sections parameters')
  }
  return IMPLEMENTATIONS[name](inputs, params)
}

export type SourceName = 'orders' | 'refunds' | 'fx' | 'tickets'
export const SOURCE_NAMES: readonly SourceName[] = ['orders', 'refunds', 'fx', 'tickets']

/** analytics.DEMO_SOURCES, copied verbatim. */
export const DEMO_SOURCES: Record<SourceName, Json> = {
  orders: [
    { order_id: 'eu-101', region: 'EU', currency: 'EUR', gross_cents: 120000 },
    { order_id: 'eu-102', region: 'EU', currency: 'EUR', gross_cents: 80000 },
    { order_id: 'us-201', region: 'US', currency: 'USD', gross_cents: 180000 },
    { order_id: 'us-202', region: 'US', currency: 'USD', gross_cents: 60000 },
    { order_id: 'uk-301', region: 'UK', currency: 'GBP', gross_cents: 90000 },
  ],
  refunds: [
    { order_id: 'eu-101', refund_cents: 10000 },
    { order_id: 'us-202', refund_cents: 5000 },
  ],
  fx: { EUR: '1.10', USD: '1.00', GBP: '1.25' },
  tickets: [
    { ticket_id: 't-1', region: 'EU', status: 'open' },
    { ticket_id: 't-2', region: 'EU', status: 'closed' },
    { ticket_id: 't-3', region: 'US', status: 'open' },
    { ticket_id: 't-4', region: 'UK', status: 'closed' },
  ],
}

/* --------------------------------------------------------------- records */

export type RecordKind = 'source' | 'tool' | 'execution' | 'artifact'

interface RecordBase {
  id: string
  logicalId: string
  contentHash: string
  /** Order of first publication in this session. */
  seq: number
  /** 1-based version number of this logical record (content-addressed records keep theirs). */
  version: number
  value: Json
}
export interface SourceRecord extends RecordBase { kind: 'source'; name: string; deleted: boolean }
export interface ToolRecord extends RecordBase { kind: 'tool'; name: ToolName; toolVersion: string }
export interface Receipt {
  tool: ToolName
  tool_version_id: string
  inputs: Record<string, string>
  params: JsonObject
  run_id: string
  output_id: string
  output_hash: string
  status: 'success'
  elapsed_ms: number
}
export interface ExecutionRecord extends RecordBase { kind: 'execution'; tool: ToolName; runId: string; receipt: Receipt }
export interface ArtifactRecord extends RecordBase {
  kind: 'artifact'
  tool: ToolName
  toolVersionId: string
  inputs: Record<string, string>
  params: JsonObject
  runId: string
  receiptId: string
  title: string
}
export type AnyRecord = SourceRecord | ToolRecord | ExecutionRecord | ArtifactRecord

export type EdgeKind = 'CONSUMED' | 'USED_TOOL' | 'PRODUCED'
export interface Edge { source: string; target: string; kind: EdgeKind }

export type ValidityState = 'current' | 'stale' | 'unknown'
export interface Reason {
  id: string
  reason: 'version_changed' | 'source_removed' | 'missing_manifest_record' | 'incomplete_graph_lineage'
  logicalId?: string
  currentId?: string | null
  missing?: string[]
}
export interface Currentness { id: string; state: ValidityState; reasons: Reason[] }

export interface ToolCall {
  tool: ToolName
  inputs: Record<string, string>
  params: JsonObject
  runId: string
  invocationId: string
  status: 'running' | 'success' | 'failed'
  outputId?: string
  error?: string
  elapsedMs?: number
}

export interface RefreshResult { replacements: Map<string, string>; executed: string[]; reused: string[] }
export interface SourceChange { logicalId: string; previousId: string | null; currentId: string; changed: boolean }

const MAX_DEPTH = 15
const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())

/** Store + graph + runtime in one object (ArtifactStore, HydraGraph and ProofFlowRuntime on the server). */
export class ProofFlowRuntime {
  readonly records = new Map<string, AnyRecord>()
  readonly heads = new Map<string, string>()
  readonly edges: Edge[] = []
  readonly calls: ToolCall[] = []
  private readonly parents = new Map<string, Set<string>>()
  private readonly children = new Map<string, Set<string>>()
  private readonly versions = new Map<string, number>()
  private seq = 0
  private invocations = 0
  readonly salt: string

  constructor(salt: string) {
    this.salt = salt
  }

  /* store */

  private prepareId(kind: RecordKind, logicalId: string, value: Json, identity: Json = null) {
    const contentHash = digest(value)
    const id = `${kind}:${digest({ logical_id: logicalId, content_hash: contentHash, identity })}`
    return { id, contentHash, existing: this.records.get(id) }
  }

  private commit(record: AnyRecord, head: boolean) {
    if (digest(record.value) !== record.contentHash) throw new MissingEvidenceError('Record content does not match its immutable hash')
    if (!this.records.has(record.id)) this.records.set(record.id, record)
    if (head) this.heads.set(record.logicalId, record.id)
  }

  private nextVersion(logicalId: string) {
    const version = (this.versions.get(logicalId) ?? 0) + 1
    this.versions.set(logicalId, version)
    return version
  }

  get(id: string): AnyRecord {
    const record = this.records.get(id)
    if (!record) throw new MissingEvidenceError(`Unknown record ${id}`)
    return record
  }

  getHead(logicalId: string): AnyRecord | undefined {
    const id = this.heads.get(logicalId)
    return id ? this.records.get(id) : undefined
  }

  read(id: string): Json {
    return clone(this.get(id).value)
  }

  /* graph */

  private putEdge(source: string, target: string, kind: EdgeKind) {
    const set = this.children.get(source) ?? new Set<string>()
    if (set.has(target)) return
    set.add(target)
    this.children.set(source, set)
    const up = this.parents.get(target) ?? new Set<string>()
    up.add(source)
    this.parents.set(target, up)
    this.edges.push({ source, target, kind })
  }

  private walk(starts: string[], next: Map<string, Set<string>>): string[] {
    const seen = new Set<string>()
    let frontier = [...starts]
    for (let depth = 0; depth < MAX_DEPTH && frontier.length; depth++) {
      const following: string[] = []
      for (const id of frontier) {
        for (const other of next.get(id) ?? []) {
          if (!seen.has(other)) {
            seen.add(other)
            following.push(other)
          }
        }
      }
      frontier = following
    }
    return [...seen]
  }

  ancestors(ids: string[]) { return this.walk(ids, this.parents) }
  descendants(ids: string[]) { return this.walk(ids, this.children) }
  parentsOf(id: string) { return [...(this.parents.get(id) ?? [])] }
  childrenOf(id: string) { return [...(this.children.get(id) ?? [])] }

  /* runtime */

  setSource(name: string, value: Json): SourceChange {
    const logicalId = `source:${name}`
    const previous = this.getHead(logicalId)
    const { id, contentHash, existing } = this.prepareId('source', logicalId, value)
    const record: AnyRecord = existing ?? {
      kind: 'source', id, logicalId, contentHash, value: clone(value), name, deleted: false,
      seq: ++this.seq, version: this.nextVersion(logicalId),
    }
    this.commit(record, true)
    return { logicalId, previousId: previous?.id ?? null, currentId: record.id, changed: !previous || previous.id !== record.id }
  }

  removeSource(name: string): SourceChange {
    const logicalId = `source:${name}`
    const previous = this.getHead(logicalId)
    if (!previous) throw new MissingEvidenceError(`Unknown source ${name}`)
    const { id, contentHash, existing } = this.prepareId('source', logicalId, null, { deleted: true })
    const record: AnyRecord = existing ?? {
      kind: 'source', id, logicalId, contentHash, value: null, name, deleted: true,
      seq: ++this.seq, version: this.nextVersion(logicalId),
    }
    this.commit(record, true)
    return { logicalId, previousId: previous.id, currentId: record.id, changed: previous.id !== record.id }
  }

  private tool(name: ToolName): ToolRecord {
    if (!(name in TOOL_SPECS)) throw new InvalidInputError(`Unknown tool '${name}'`)
    const head = this.getHead(`tool:${name}`)
    if (head && head.kind === 'tool') return head
    const logicalId = `tool:${name}`
    const value: Json = { name, version: TOOL_SPECS[name].version, implementation: 'proofflow/analytics.py' }
    const { id, contentHash, existing } = this.prepareId('tool', logicalId, value)
    const record: ToolRecord = existing?.kind === 'tool' ? existing : {
      kind: 'tool', id, logicalId, contentHash, value, name, toolVersion: TOOL_SPECS[name].version,
      seq: ++this.seq, version: this.nextVersion(logicalId),
    }
    this.commit(record, true)
    return record
  }

  /** runtime.currentness: validate graph-discovered dependencies. */
  currentness(id: string): Currentness {
    const record = this.get(id)
    const ancestors = record.kind === 'artifact' ? this.ancestors([id]) : []
    const discovered = new Set([...ancestors, id])
    const stale: Reason[] = []
    const unknown: Reason[] = []
    for (const nodeId of [...discovered].sort(byKey)) {
      const node = this.records.get(nodeId)
      if (!node) {
        unknown.push({ id: nodeId, reason: 'missing_manifest_record' })
        continue
      }
      if (node.kind === 'source' || node.kind === 'tool') {
        const head = this.getHead(node.logicalId)
        if (!head || head.id !== node.id) stale.push({ id: node.id, logicalId: node.logicalId, currentId: head?.id ?? null, reason: 'version_changed' })
        if (node.kind === 'source' && node.deleted) unknown.push({ id: node.id, reason: 'source_removed' })
      }
      if (node.kind === 'artifact') {
        const expected = [...Object.values(node.inputs), node.receiptId, node.toolVersionId]
        const missing = expected.filter(item => !discovered.has(item)).sort(byKey)
        if (missing.length) unknown.push({ id: node.id, reason: 'incomplete_graph_lineage', missing })
      }
    }
    const state: ValidityState = unknown.length ? 'unknown' : stale.length ? 'stale' : 'current'
    return { id, state, reasons: [...unknown, ...stale] }
  }

  private inputValue(id: string): Json {
    const record = this.get(id)
    if (record.kind !== 'source' && record.kind !== 'artifact') throw new InvalidInputError(`A tool input must be a source or artifact, got ${record.kind}`)
    const status = this.currentness(id)
    if (status.state !== 'current') throw new MissingEvidenceError(`Input is ${status.state}, refresh it first: ${id}`)
    return this.read(id)
  }

  execute(tool: ToolName, inputs: Record<string, string>, params: JsonObject = {},
    options: { logicalId?: string; runId?: string; reuse?: boolean } = {}): ArtifactRecord {
    const reuse = options.reuse ?? true
    const toolRecord = this.tool(tool)
    const signature: JsonObject = { tool_version_id: toolRecord.id, inputs, params }
    const logicalId = options.logicalId ?? `artifact:${tool}:${digest(signature).slice(0, 20)}`
    if (/^(source|tool|execution):/.test(logicalId)) throw new InvalidInputError('Artifact logical IDs must not use source, tool, or execution namespaces')
    const head = this.getHead(logicalId)
    if (head && head.kind !== 'artifact') throw new InvalidInputError('Artifact publication would replace a different kind of record')
    if (reuse && head && head.toolVersionId === toolRecord.id && canonicalJson(head.inputs) === canonicalJson(inputs)
      && canonicalJson(head.params) === canonicalJson(params)) {
      if (this.currentness(head.id).state === 'current') return head
    }
    const values: JsonObject = {}
    for (const [name, nodeId] of Object.entries(inputs)) values[name] = this.inputValue(nodeId)
    const invocationId = `${this.salt}-${(++this.invocations).toString().padStart(4, '0')}`
    const runId = options.runId ?? `run-${invocationId}`
    const call: ToolCall = { tool, inputs: { ...inputs }, params, runId, invocationId, status: 'running' }
    this.calls.push(call)
    const started = now()
    let result: JsonObject
    try {
      result = executeTool(tool, values, params)
    } catch (error) {
      call.status = 'failed'
      call.error = error instanceof Error ? error.message : String(error)
      call.elapsedMs = now() - started
      throw error
    }
    const elapsedMs = now() - started
    const out = this.prepareId('artifact', logicalId, result, invocationId)
    const receiptValue: Receipt = {
      tool, tool_version_id: toolRecord.id, inputs: { ...inputs }, params, run_id: runId,
      output_id: out.id, output_hash: out.contentHash, status: 'success', elapsed_ms: elapsedMs,
    }
    const receiptLogical = `execution:${invocationId}`
    const rec = this.prepareId('execution', receiptLogical, receiptValue as unknown as Json)
    const receipt: ExecutionRecord = {
      kind: 'execution', id: rec.id, logicalId: receiptLogical, contentHash: rec.contentHash,
      value: receiptValue as unknown as Json, tool, runId, receipt: receiptValue,
      seq: ++this.seq, version: this.nextVersion(receiptLogical),
    }
    const output: ArtifactRecord = {
      kind: 'artifact', id: out.id, logicalId, contentHash: out.contentHash, value: result,
      tool, toolVersionId: toolRecord.id, inputs: { ...inputs }, params, runId, receiptId: receipt.id,
      title: typeof params.title === 'string' ? params.title : logicalId,
      seq: ++this.seq, version: this.nextVersion(logicalId),
    }
    for (const nodeId of [...new Set(Object.values(inputs))].sort(byKey)) this.putEdge(nodeId, receipt.id, 'CONSUMED')
    this.putEdge(toolRecord.id, receipt.id, 'USED_TOOL')
    this.putEdge(receipt.id, output.id, 'PRODUCED')
    this.commit(receipt, false)
    this.commit(output, true)
    call.status = 'success'
    call.outputId = output.id
    call.elapsedMs = elapsedMs
    return output
  }

  /** runtime.affected: current artifact heads that descend from the changed versions. */
  affected(changedVersionIds: string[]): ArtifactRecord[] {
    const descendants = new Set(this.descendants(changedVersionIds))
    const result: ArtifactRecord[] = []
    for (const id of this.heads.values()) {
      const record = this.records.get(id)
      if (record?.kind === 'artifact' && descendants.has(id)) result.push(record)
    }
    return result.sort((a, b) => byKey(a.logicalId, b.logicalId))
  }

  /** runtime.refresh: topological refresh with old→new input rebinding and shared-work deduplication. */
  refresh(targetIds: string[], runId = `refresh-${this.salt}-${this.invocations + 1}`): RefreshResult {
    const replacements = new Map<string, string>()
    const executed: string[] = []
    const reused: string[] = []
    const visiting = new Set<string>()
    const visit = (nodeId: string): string => {
      const known = replacements.get(nodeId)
      if (known) return known
      if (visiting.has(nodeId)) throw new DependencyCycleError(`Dependency cycle at ${nodeId}`)
      visiting.add(nodeId)
      const record = this.get(nodeId)
      if (record.kind === 'source') {
        const head = this.getHead(record.logicalId)
        if (!head || (head.kind === 'source' && head.deleted)) throw new MissingEvidenceError(`Source no longer available: ${record.logicalId}`)
        this.read(head.id)
        replacements.set(nodeId, head.id)
      } else if (record.kind === 'artifact') {
        const status = this.currentness(nodeId)
        if (status.state === 'unknown') throw new MissingEvidenceError(`Cannot refresh incomplete evidence for ${nodeId}`)
        if (status.state === 'current') {
          replacements.set(nodeId, nodeId)
          reused.push(nodeId)
        } else {
          const receipt = (this.get(record.receiptId) as ExecutionRecord).receipt
          const rebound: Record<string, string> = {}
          for (const [name, inputId] of Object.entries(receipt.inputs)) rebound[name] = visit(inputId)
          const before = this.calls.length
          const output = this.execute(receipt.tool, rebound, receipt.params, { logicalId: record.logicalId, runId, reuse: true })
          replacements.set(nodeId, output.id)
          // An old handle may resolve to an already-current head without a tool call: count reuse.
          if (this.calls.length > before) executed.push(output.id)
          else reused.push(output.id)
        }
      } else {
        throw new InvalidInputError(`Cannot refresh a ${record.kind} record`)
      }
      visiting.delete(nodeId)
      return replacements.get(nodeId)!
    }
    for (const target of targetIds) visit(target)
    return { replacements, executed, reused }
  }

  /** runtime.full_recompute: fresh recipe evaluation with no graph query and no cached intermediates. */
  fullRecompute(targetId: string): Json {
    const visiting = new Set<string>()
    const compute = (nodeId: string): Json => {
      if (visiting.has(nodeId)) throw new DependencyCycleError(`Dependency cycle at ${nodeId}`)
      visiting.add(nodeId)
      const record = this.get(nodeId)
      let result: Json
      if (record.kind === 'source') {
        const head = this.getHead(record.logicalId)
        if (!head || (head.kind === 'source' && head.deleted)) throw new MissingEvidenceError(`Source no longer available: ${record.logicalId}`)
        result = this.read(head.id)
      } else if (record.kind === 'artifact') {
        const receipt = (this.get(record.receiptId) as ExecutionRecord).receipt
        const values: JsonObject = {}
        for (const [name, child] of Object.entries(receipt.inputs)) values[name] = compute(child)
        result = executeTool(receipt.tool, values, receipt.params)
      } else {
        throw new InvalidInputError(`Cannot recompute a ${record.kind} record`)
      }
      visiting.delete(nodeId)
      return result
    }
    return compute(targetId)
  }

  /** runtime.report_claims: inspect numeric slots separately, never serving a stale slot as current. */
  reportClaims(reportId: string): Claim[] {
    const record = this.get(reportId)
    if (record.kind !== 'artifact' || record.tool !== 'compose_report') throw new InvalidInputError('Expected a structured report artifact')
    const saved = record.value as { sections: { key: string; label: string; value: number; unit: string }[] }
    const sectionsByKey = new Map(saved.sections.map(section => [section.key, section]))
    const reportValidation = this.currentness(reportId)
    const formatting = this.currentness(record.toolVersionId)
    const definitions = record.params.sections as { key: string; input: string; path: string[] }[]
    return definitions.map(definition => {
      const inputId = record.inputs[definition.input]
      const evidence = this.currentness(inputId)
      const states = new Set<ValidityState>([evidence.state, formatting.state])
      if (reportValidation.state === 'unknown') states.add('unknown')
      const state: ValidityState = states.has('unknown') ? 'unknown' : states.has('stale') ? 'stale' : 'current'
      const section = sectionsByKey.get(definition.key)!
      return {
        key: section.key, label: section.label, unit: section.unit,
        savedValue: section.value,
        value: state === 'current' ? section.value : null,
        state, artifactId: inputId, path: definition.path,
        reasons: [...evidence.reasons, ...formatting.reasons, ...(reportValidation.state === 'unknown' ? reportValidation.reasons : [])],
      }
    })
  }
}

export interface Claim {
  key: string
  label: string
  unit: string
  /** Historical display only; never shown as current when state is not current. */
  savedValue: number
  value: number | null
  state: ValidityState
  artifactId: string
  path: string[]
  reasons: Reason[]
}

/* ------------------------------------------------------------ guided demo */

export const LABELS: Record<string, string> = {
  'metric:gross': 'Gross regional revenue',
  'metric:refunds': 'Regional refunds',
  'metric:net': 'Net regional revenue',
  'metric:regional': 'Regional USD revenue',
  'metric:company': 'Company revenue',
  'metric:support': 'Support tickets',
  'report:company': 'Company weekly report',
  'report:eu': 'EU operations brief',
}

export type ReportKey = 'company' | 'eu'

export type ChangePayload =
  | { kind: 'fx'; value: string }
  | { kind: 'order'; delta_cents: number }
  | { kind: 'refund'; delta_cents: number }
  | { kind: 'support'; count: number }
  | { kind: 'remove'; source: SourceName }

export interface ChangeInfo {
  kind: ChangePayload['kind']
  label: string
  source: SourceName
  previousSourceId: string | null
  currentSourceId: string
  changed: boolean
}

export interface LastRefresh {
  executedCount: number
  reusedCount: number
  executedArtifactIds: string[]
  reusedArtifactIds: string[]
  toolCalls: ToolCall[]
  numericParity: boolean
  unchangedSupport: boolean
}

export type RefreshOutcome =
  | { ok: true; lastRefresh: LastRefresh }
  | { ok: false; error: string; source: SourceName | null; toolCalls: ToolCall[] }

export interface VerifyRow { id: string; key: ReportKey; title: string; state: ValidityState; numericMatch: boolean; error: string | null }
export interface Verification { passed: boolean; reports: VerifyRow[] }

const SUPPORT_SECTION: JsonObject = { key: 'eu_support', label: 'EU support tickets', input: 'support', path: ['regions', 'EU', 'tickets'], unit: 'tickets' }

/** DemoSession from proofflow/demo.py: one isolated generation of the guided sample. */
export class DemoSession {
  readonly runtime: ProofFlowRuntime
  readonly generation: number
  change: ChangeInfo | null = null
  changedSourceIds: string[] = []
  affectedArtifacts: ArtifactRecord[] = []
  lastRefresh: LastRefresh | null = null
  private tickets = 0

  constructor(generation = 1) {
    this.generation = generation
    this.runtime = new ProofFlowRuntime(`g${generation}`)
    this.seed()
  }

  private seed() {
    const runtime = this.runtime
    const src = {} as Record<SourceName, string>
    for (const name of SOURCE_NAMES) src[name] = runtime.setSource(name, clone(DEMO_SOURCES[name])).currentId
    const gross = runtime.execute('gross_by_region', { orders: src.orders }, {}, { logicalId: 'metric:gross', runId: 'run-A' })
    const refunds = runtime.execute('refunds_by_region', { orders: src.orders, refunds: src.refunds }, {}, { logicalId: 'metric:refunds', runId: 'run-A' })
    const net = runtime.execute('net_by_region', { gross: gross.id, refunds: refunds.id }, {}, { logicalId: 'metric:net', runId: 'run-A' })
    const regional = runtime.execute('convert_to_usd', { net: net.id, fx: src.fx }, {}, { logicalId: 'metric:regional', runId: 'run-A' })
    const company = runtime.execute('company_total', { regional: regional.id }, {}, { logicalId: 'metric:company', runId: 'run-A' })
    const support = runtime.execute('support_by_region', { tickets: src.tickets }, {}, { logicalId: 'metric:support', runId: 'run-A' })
    runtime.execute('compose_report', { revenue: company.id, support: support.id }, {
      title: 'Company weekly report',
      sections: [{ key: 'company_revenue', label: 'Company revenue', input: 'revenue', path: ['usd_cents'], unit: 'USD cents' }, SUPPORT_SECTION],
    }, { logicalId: 'report:company', runId: 'run-A' })
    runtime.execute('compose_report', { revenue: regional.id, support: support.id }, {
      title: 'EU operations brief',
      sections: [{ key: 'eu_revenue', label: 'EU revenue', input: 'revenue', path: ['regions', 'EU', 'usd_cents'], unit: 'USD cents' }, SUPPORT_SECTION],
    }, { logicalId: 'report:eu', runId: 'run-B' })
  }

  reports(): { key: ReportKey; record: ArtifactRecord }[] {
    return (['company', 'eu'] as const).map(key => ({ key, record: this.runtime.getHead(`report:${key}`) as ArtifactRecord }))
  }

  label(record: AnyRecord): string {
    if (record.kind === 'source') return record.name
    if (record.kind === 'execution') return record.tool
    return LABELS[record.logicalId] ?? (record.kind === 'artifact' ? record.title : record.logicalId)
  }

  private source(name: SourceName): Json {
    const record = this.runtime.getHead(`source:${name}`)
    if (!record || (record.kind === 'source' && record.deleted)) throw new MissingEvidenceError('This source is unavailable; reset the demo to restore it')
    return this.runtime.read(record.id)
  }

  /** DemoSession.change: one bounded staged correction. Throws InvalidInputError / MissingEvidenceError. */
  applyChange(payload: ChangePayload): ChangeInfo {
    let source: SourceName
    let value: Json = null
    let label: string
    if (payload.kind === 'fx') {
      const rate = parseDecimal(payload.value)
      if (!rate) throw new InvalidInputError('Exchange rate must be a decimal between 0.10 and 5.00')
      if (compareDecimal(rate, parseDecimal('0.10')!) < 0 || compareDecimal(rate, parseDecimal('5.00')!) > 0) {
        throw new InvalidInputError('Exchange rate must be between 0.10 and 5.00')
      }
      source = 'fx'
      value = this.source(source) as JsonObject
      value.EUR = rate.text
      label = `EUR → USD corrected to ${rate.text}`
    } else if (payload.kind === 'order' || payload.kind === 'refund') {
      if (!Number.isInteger(payload.delta_cents) || payload.delta_cents < -50000 || payload.delta_cents > 50000) {
        throw new InvalidInputError('A correction needs integer delta_cents between -50000 and 50000')
      }
      source = payload.kind === 'order' ? 'orders' : 'refunds'
      const list = this.source(source) as JsonObject[]
      const field = payload.kind === 'order' ? 'gross_cents' : 'refund_cents'
      const next = (list[0][field] as number) + payload.delta_cents
      list[0][field] = next
      if (next < 0) throw new InvalidInputError('Correction would make the source amount negative')
      value = list
      label = `EU ${payload.kind} corrected by ${payload.delta_cents} cents`
    } else if (payload.kind === 'support') {
      if (!Number.isInteger(payload.count) || payload.count < 1 || payload.count > 5) throw new InvalidInputError('Support correction needs an integer count from 1 to 5')
      source = 'tickets'
      const list = this.source(source) as JsonObject[]
      for (let i = 0; i < payload.count; i++) list.push({ ticket_id: `demo-${this.runtime.salt}-${++this.tickets}`, region: 'EU', status: 'open' })
      value = list
      label = `Added ${payload.count} EU support tickets`
    } else if (payload.kind === 'remove') {
      if (!SOURCE_NAMES.includes(payload.source)) throw new InvalidInputError('Only orders, refunds, fx or tickets can be removed')
      source = payload.source
      label = `Removed ${source} source`
    } else {
      throw new InvalidInputError('Unknown staged correction')
    }
    const change = payload.kind === 'remove' ? this.runtime.removeSource(source) : this.runtime.setSource(source, value)
    const roots = [...this.changedSourceIds]
    if (change.changed && change.previousId && !roots.includes(change.previousId)) roots.push(change.previousId)
    this.changedSourceIds = roots
    this.affectedArtifacts = roots.length ? this.runtime.affected(roots) : []
    this.change = { kind: payload.kind, label, source, previousSourceId: change.previousId, currentSourceId: change.currentId, changed: change.changed }
    this.lastRefresh = null
    return this.change
  }

  /** DemoSession.refresh: refresh both report heads; a removed source stops it (HTTP 409 on the server). */
  refresh(): RefreshOutcome {
    const targets = this.reports().map(report => report.record.id)
    const supportBefore = this.runtime.getHead('metric:support')
    const before = this.runtime.calls.length
    let result: RefreshResult
    try {
      result = this.runtime.refresh(targets)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      const match = /source:(orders|refunds|fx|tickets)/.exec(message)
      return { ok: false, error: message, source: match ? (match[1] as SourceName) : null, toolCalls: this.runtime.calls.slice(before) }
    }
    const calls = this.runtime.calls.slice(before)
    const supportAfter = this.runtime.getHead('metric:support')
    const verification = this.verify()
    this.lastRefresh = {
      executedCount: calls.length,
      reusedCount: new Set(result.reused).size,
      executedArtifactIds: [...result.executed],
      reusedArtifactIds: [...new Set(result.reused)],
      toolCalls: calls,
      numericParity: verification.passed,
      unchangedSupport: !!supportBefore && !!supportAfter && supportBefore.id === supportAfter.id && supportBefore.contentHash === supportAfter.contentHash,
    }
    return { ok: true, lastRefresh: this.lastRefresh }
  }

  /** DemoSession.verify: compare saved report values with a fresh recipe evaluation. */
  verify(): Verification {
    const rows: VerifyRow[] = this.reports().map(({ key, record }) => {
      const status = this.runtime.currentness(record.id)
      let numericMatch = false
      let error: string | null = null
      try {
        numericMatch = canonicalJson(record.value) === canonicalJson(this.runtime.fullRecompute(record.id))
      } catch (cause) {
        error = cause instanceof Error ? cause.message : String(cause)
      }
      return { id: record.id, key, title: this.label(record), state: status.state, numericMatch, error }
    })
    return { passed: rows.every(row => row.numericMatch && row.state === 'current'), reports: rows }
  }

  /** Removed sources whose deletion makes this artifact unrecoverable by refresh. */
  blockedBy(id: string): SourceName[] {
    const record = this.runtime.records.get(id)
    if (!record || record.kind !== 'artifact') return []
    const names = new Set<SourceName>()
    for (const ancestor of this.runtime.ancestors([id])) {
      const node = this.runtime.records.get(ancestor)
      if (node?.kind !== 'source') continue
      const head = this.runtime.getHead(node.logicalId)
      if (head?.kind === 'source' && head.deleted) names.add(node.name as SourceName)
    }
    return [...names]
  }
}

/* -------------------------------------------------------------- self-check */

export interface CheckRow { name: string; expected: string; actual: string; pass: boolean }

const claimValue = (session: DemoSession, report: ReportKey, key: string) => {
  const record = session.reports().find(item => item.key === report)!.record
  return session.runtime.reportClaims(record.id).find(claim => claim.key === key)!
}

/** Replays the README scenario and the API test expectations (tests/test_api.py). */
export function selfCheck(): CheckRow[] {
  const out: CheckRow[] = []
  const check = (name: string, expected: unknown, actual: unknown) =>
    out.push({ name, expected: String(expected), actual: String(actual), pass: String(expected) === String(actual) })

  const s = new DemoSession(1)
  check('initial tool executions', 8, s.runtime.calls.length)
  check('company revenue before (cents)', 556500, claimValue(s, 'company', 'company_revenue').value)
  check('EU revenue before (cents)', 209000, claimValue(s, 'eu', 'eu_revenue').value)
  check('EU support before', 2, claimValue(s, 'eu', 'eu_support').value)
  const supportBefore = claimValue(s, 'eu', 'eu_support').artifactId

  s.applyChange({ kind: 'fx', value: '1.20' })
  check('affected after FX', 4, s.affectedArtifacts.length)
  check('EU revenue state after FX', 'stale', claimValue(s, 'eu', 'eu_revenue').state)
  check('EU revenue value withheld', 'null', claimValue(s, 'eu', 'eu_revenue').value)
  check('EU revenue saved value', 209000, claimValue(s, 'eu', 'eu_revenue').savedValue)
  check('EU support stays current', 'current', claimValue(s, 'eu', 'eu_support').state)
  check('verify fails while stale', false, s.verify().passed)

  const refreshed = s.refresh()
  check('refresh succeeded', true, refreshed.ok)
  if (refreshed.ok) {
    check('tools executed during refresh', 4, refreshed.lastRefresh.executedCount)
    check('artifacts reused during refresh', 2, refreshed.lastRefresh.reusedCount)
    check('support_by_region not re-run', true, refreshed.lastRefresh.toolCalls.every(call => call.tool !== 'support_by_region'))
    check('numeric parity', true, refreshed.lastRefresh.numericParity)
    check('unchanged support', true, refreshed.lastRefresh.unchangedSupport)
  }
  check('company revenue after (cents)', 575500, claimValue(s, 'company', 'company_revenue').value)
  check('EU revenue after (cents)', 228000, claimValue(s, 'eu', 'eu_revenue').value)
  check('EU support same artifact', supportBefore, claimValue(s, 'eu', 'eu_support').artifactId)
  const again = s.refresh()
  check('second refresh executes nothing', 0, again.ok ? again.lastRefresh.executedCount : -1)
  check('verify passes after refresh', true, s.verify().passed)

  const r = new DemoSession(2)
  r.applyChange({ kind: 'remove', source: 'fx' })
  check('EU revenue not current after removing fx', true, claimValue(r, 'eu', 'eu_revenue').state !== 'current')
  check('EU support still current after removing fx', 'current', claimValue(r, 'eu', 'eu_support').state)
  check('refresh blocked by removed fx', false, r.refresh().ok)
  check('verify fails with removed fx', false, r.verify().passed)

  // ROUND_HALF_EVEN: 190000 x 1.000005 = 190000.95 -> 190001; 5 x 1.5 = 7.5 -> 8; 5 x 0.5 = 2.5 -> 2
  check('half-even 7.5', 8, (convertToUsd({ net: { regions: { X: { currency: 'EUR', amount_cents: 5 } } }, fx: { EUR: '1.5' } }).regions as Record<string, { usd_cents: number }>).X.usd_cents)
  check('half-even 2.5', 2, (convertToUsd({ net: { regions: { X: { currency: 'EUR', amount_cents: 5 } } }, fx: { EUR: '0.5' } }).regions as Record<string, { usd_cents: number }>).X.usd_cents)
  check('half-even -2.5', -2, (convertToUsd({ net: { regions: { X: { currency: 'EUR', amount_cents: -5 } } }, fx: { EUR: '0.5' } }).regions as Record<string, { usd_cents: number }>).X.usd_cents)
  return out
}
