import type { ReactNode } from 'react'
import { StateTag, type ClaimState as TagState } from '../../components/ui'
import type { AnyRecord, ArtifactRecord, DemoSession, ExecutionRecord, Json, JsonObject, SourceName, ToolRecord } from './engine'
import {
  SLOT_DEF, SOURCE_LABEL, STATE_TEXT, SYMBOL, TOOL_LABEL, lineagePath, money, recordName, shortId,
  type NodeView, type Slot,
} from './model'

const obj = (value: Json | undefined): JsonObject => (value && typeof value === 'object' && !Array.isArray(value) ? value : {})

function tagState(node: NodeView): TagState {
  if (node.badge === 'refreshed') return 'refreshed'
  if (node.badge === 'reused') return 'reused'
  if (node.state === 'changed') return 'stale'
  if (node.state === 'removed') return 'blocked'
  return node.state
}

function tagText(node: NodeView) {
  if (node.badge === 'refreshed') return 'Refreshed'
  if (node.badge === 'reused') return 'Reused'
  if (node.state === 'changed') return `Changed to v${node.version}`
  return STATE_TEXT[node.state]
}

/** Human-readable rows for a stored value. */
function valueRows(session: DemoSession, record: AnyRecord): [string, string][] {
  const value = record.value
  if (record.kind === 'source') {
    const ordersHead = session.runtime.getHead('source:orders')
    const orderCurrency = new Map(
      (Array.isArray(ordersHead?.value) ? ordersHead.value.map(obj) : []).map(row => [String(row.order_id), String(row.currency)]),
    )
    if (value === null) return [['Content', 'None (removed)']]
    if (record.name === 'fx') return Object.entries(obj(value)).map(([code, rate]) => [`${code} → USD`, String(rate)])
    const list = Array.isArray(value) ? value.map(obj) : []
    if (record.name === 'orders') return list.map(row => [String(row.order_id), `${row.region} ${money(Number(row.gross_cents), SYMBOL[String(row.currency)] ?? '')}`])
    if (record.name === 'refunds') return list.map(row => [`Refund on ${row.order_id}`, money(Number(row.refund_cents), SYMBOL[orderCurrency.get(String(row.order_id)) ?? ''] ?? '')])
    const counts = new Map<string, number>()
    for (const row of list) counts.set(String(row.region), (counts.get(String(row.region)) ?? 0) + 1)
    return [...counts.entries()].map(([region, count]) => [`${region} tickets`, String(count)])
  }
  if (record.kind !== 'artifact') return []
  if (record.tool === 'company_total') return [['Company total', money(Number(obj(value).usd_cents))]]
  if (record.tool === 'compose_report') {
    const sections = (obj(value).sections as Json[] | undefined ?? []).map(obj)
    return sections.map(section => [String(section.label), section.unit === 'USD cents' ? money(Number(section.value)) : String(section.value)])
  }
  return Object.entries(obj(obj(value).regions)).map(([region, raw]) => {
    const entry = obj(raw)
    if (typeof entry.usd_cents === 'number') return [region, money(entry.usd_cents)]
    if (typeof entry.tickets === 'number') return [region, `${entry.tickets} tickets`]
    return [region, money(Number(entry.amount_cents), SYMBOL[String(entry.currency)] ?? '')]
  })
}

function why(session: DemoSession, node: NodeView, record: AnyRecord): ReactNode {
  const runtime = session.runtime
  if (record.kind === 'source') {
    if (node.state === 'removed') return 'This source was removed. Anything that read it is blocked, and refresh cannot bring it back. Reset the sample to restore it.'
    if (node.state === 'changed') {
      const older = new Set<number>()
      for (const id of runtime.heads.values()) {
        const head = runtime.get(id)
        if (head.kind !== 'artifact') continue
        for (const inputId of Object.values(head.inputs)) {
          const input = runtime.records.get(inputId)
          if (input?.logicalId === record.logicalId && input.id !== record.id) older.add(input.version)
        }
      }
      return `Version ${record.version} is now current. Saved results that read version ${[...older].join(', ')} need refresh.`
    }
    return record.version > 1 ? `Version ${record.version}. Every saved result that reads this source reads this version.` : 'The authored fixture. Every saved result reads this version.'
  }
  if (node.state === 'blocked') {
    return `It read ${node.blockedBy.map(name => SOURCE_LABEL[name]).join(' and ')}, which was removed. Refresh cannot recompute it; the value stays withheld.`
  }
  if (node.state === 'stale' || node.state === 'unknown') {
    const reasons = runtime.currentness(record.id).reasons.filter(reason => reason.reason === 'version_changed')
    const lines = reasons.map(reason => {
      const old = runtime.records.get(reason.id)
      const now = reason.currentId ? runtime.records.get(reason.currentId) : undefined
      return old?.kind === 'source' ? `${SOURCE_LABEL[old.name as SourceName]} v${old.version} (current is v${now?.version ?? '?'})` : reason.logicalId
    })
    return `It was computed from ${lines.join(' and ')}. Its value is withheld until refresh.`
  }
  if (node.badge === 'refreshed') return 'Recomputed by the last refresh from current inputs.'
  if (node.badge === 'reused') return 'Still current, so the last refresh reused it without running its tool.'
  return 'Every input it read is still the current version.'
}

export default function Inspector({ session, slot, node }: { session: DemoSession; slot: Slot | null; node: NodeView | null }) {
  if (!slot || !node) {
    return (
      <div className="demo-inspector is-empty">
        <h3 className="demo-panel-title">Inspector</h3>
        <p className="soft">Select any step in the graph to see what it is, what it read and the receipt of the run that made it.</p>
      </div>
    )
  }
  const runtime = session.runtime
  const def = SLOT_DEF[slot]
  const record = runtime.get(node.recordId)
  const artifact = record.kind === 'artifact' ? (record as ArtifactRecord) : null
  const receipt = artifact ? (runtime.get(artifact.receiptId) as ExecutionRecord).receipt : null
  const withheld = node.state !== 'current'
  const rows = valueRows(session, record)

  // Dependency path from the change: from the version the saved work read, else from the corrected version.
  const change = session.change
  const oldRoots = [change?.previousSourceId, ...session.changedSourceIds].filter((id): id is string => !!id)
  let path = record.kind === 'artifact' ? lineagePath(session, [...new Set(oldRoots)], record.id) : null
  let fromCurrent = false
  if (!path && record.kind === 'artifact' && change?.changed) {
    path = lineagePath(session, [change.currentSourceId], record.id)
    fromCurrent = !!path
  }

  return (
    <div className="demo-inspector" aria-labelledby="demo-inspector-title">
      <div className="demo-inspector-head">
        <h3 className="demo-panel-title" id="demo-inspector-title">{def.label}</h3>
        <StateTag state={tagState(node)}>{tagText(node)}</StateTag>
      </div>
      <p className="demo-inspector-kind soft">
        {def.layer === 'source' ? `Source, version ${record.version}` : def.layer === 'report' ? `Saved report, made by ${TOOL_LABEL.compose_report}` : `Tool result, made by ${TOOL_LABEL[def.tool!]}`}
      </p>
      <p className="demo-inspector-plain">{def.plain}</p>
      <p className="demo-inspector-why">{why(session, node, record)}</p>

      <div className="demo-inspector-grid">
        {rows.length > 0 && (
          <div className="demo-inspector-block">
            <h4>{record.kind === 'source' ? 'Content' : withheld ? 'Saved value, withheld' : 'Value'}</h4>
            <dl className={`demo-values figure${withheld && record.kind !== 'source' ? ' is-withheld' : ''}`}>
              {rows.map(([label, value]) => (
                <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
              ))}
            </dl>
          </div>
        )}

        <div className="demo-inspector-block">
          <h4>{receipt ? 'Execution receipt' : 'Record'}</h4>
          <dl className="demo-receipt">
            {receipt && artifact ? (
              <>
                <div><dt>Tool</dt><dd><code>{receipt.tool}</code>, version {(runtime.get(receipt.tool_version_id) as ToolRecord).toolVersion}</dd></div>
                <div><dt>Run</dt><dd><code>{receipt.run_id}</code></dd></div>
                <div>
                  <dt>Inputs</dt>
                  <dd>
                    <ul className="demo-receipt-inputs">
                      {Object.entries(receipt.inputs).map(([name, id]) => {
                        const input = runtime.get(id)
                        const isHead = runtime.heads.get(input.logicalId) === id
                        return (
                          <li key={name}>
                            <code>{name}</code> <code className="demo-id">{shortId(id)}</code>{' '}
                            <span className="soft">{recordName(input)}{isHead ? '' : ', not the current version'}</span>
                          </li>
                        )
                      })}
                    </ul>
                  </dd>
                </div>
                <div><dt>Receipt</dt><dd><code className="demo-id">{shortId(artifact.receiptId)}</code></dd></div>
                <div><dt>Output</dt><dd><code className="demo-id">{shortId(receipt.output_id)}</code></dd></div>
                <div><dt>Output hash</dt><dd><code className="demo-id">{receipt.output_hash}</code></dd></div>
              </>
            ) : (
              <>
                <div><dt>Record</dt><dd><code className="demo-id">{shortId(record.id)}</code></dd></div>
                <div><dt>Content hash</dt><dd><code className="demo-id">{record.contentHash}</code></dd></div>
              </>
            )}
          </dl>
          <p className="demo-fine">IDs and hashes are generated in your browser for this replay (64-bit hash, not the server’s SHA-256).</p>
        </div>
      </div>

      {record.kind === 'artifact' && (
        <div className="demo-inspector-block">
          <h4>{fromCurrent ? 'Path from the corrected source' : 'Path from the change'}</h4>
          {path ? (
            <ol className="demo-path">
              {path.map(id => {
                const step = runtime.get(id)
                return <li key={id} className={`is-${step.kind}`}><span>{recordName(step)}</span></li>
              })}
            </ol>
          ) : (
            <p className="soft">{change ? 'Not downstream of the change. Nothing it read was corrected, so it stays as it is.' : 'No correction applied yet.'}</p>
          )}
        </div>
      )}
    </div>
  )
}
