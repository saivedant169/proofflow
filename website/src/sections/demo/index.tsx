import { useCallback, useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { Ban, CircleAlert, CircleCheck, Info } from 'lucide-react'
import { ButtonLink, Source, StateTag } from '../../components/ui'
import { links } from '../../content/facts'
import {
  DemoSession, selfCheck,
  type ChangePayload, type SourceName, type ToolCall,
  type Verification,
} from './engine'
import {
  SLOTS, SLOT_DEF, SOURCE_LABEL, TOOL_LABEL, buildView, depthFrom, money, nodeChanged,
  type NodeView, type ReportView, type Slot, type View,
} from './model'
import Graph, { type Wave } from './Graph'
import Inspector from './Inspector'
import Reports from './Reports'
import Activity, { type LogEntry, type LogLine } from './Activity'
import Console, { type FieldError, type FormId } from './Console'
import './styles.css'

if (import.meta.env.DEV) {
  const failed = selfCheck().filter(row => !row.pass)
  console.assert(failed.length === 0, 'Demo engine self-check failed', failed)
}

const STEP_MS = 280
const SOURCE_SLOTS: Slot[] = ['source:orders', 'source:refunds', 'source:fx', 'source:tickets']

type StatusTone = 'info' | 'stale' | 'blocked' | 'pass' | 'fail'
interface Status { tone: StatusTone; text: string }

const plural = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`

function listText(items: string[]) {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

function changeTitle(payload: ChangePayload): string {
  const signed = (cents: number) => `${cents < 0 ? '−' : '+'}${money(Math.abs(cents), '€')}`
  switch (payload.kind) {
    case 'fx': return `EUR → USD set to ${payload.value}`
    case 'order': return `First EU order adjusted by ${signed(payload.delta_cents)}`
    case 'refund': return `Its refund adjusted by ${signed(payload.delta_cents)}`
    case 'support': return `Added ${plural(payload.count, 'EU support ticket')}`
    case 'remove': return `Removed the ${SOURCE_LABEL[payload.source].toLowerCase()} source`
  }
}

function callLine(session: DemoSession, call: ToolCall): LogLine {
  if (call.status !== 'success') return { kind: 'fail', text: `${TOOL_LABEL[call.tool]} failed` }
  const output = call.outputId ? session.runtime.records.get(call.outputId) : undefined
  const suffix = call.tool === 'compose_report' && output ? `: ${session.label(output)}` : ''
  return { kind: 'ran', text: `${TOOL_LABEL[call.tool]} ran${suffix}` }
}

function reusedLine(session: DemoSession, id: string): LogLine {
  const record = session.runtime.get(id)
  const tool = record.kind === 'artifact' ? TOOL_LABEL[record.tool] : record.logicalId
  return { kind: 'reused', text: `${tool} reused: ${session.label(record)} was still current` }
}

const labelOf = (logicalId: string) => SLOT_DEF[logicalId as Slot]?.label ?? logicalId

export default function Demo() {
  const reduce = useReducedMotion()
  const [session, setSession] = useState(() => new DemoSession(1))
  const [view, setView] = useState<View>(() => buildView(session))
  const [wave, setWave] = useState<Wave | null>(null)
  const [selected, setSelected] = useState<Slot | null>(null)
  const [verification, setVerification] = useState<Verification | null>(null)
  const [previous, setPrevious] = useState<Record<string, number>>({})
  const [fieldError, setFieldError] = useState<FieldError | null>(null)
  const [status, setStatus] = useState<Status>({
    tone: 'info', text: 'All eight saved results are current. Apply a correction to see what it touches.',
  })
  const logId = useRef(1)
  const waveId = useRef(0)
  const [log, setLog] = useState<LogEntry[]>(() => [{
    id: 0, tone: 'seed', title: 'Guided sample executed: runs A and B',
    lines: session.runtime.calls.map(call => callLine(session, call)),
  }])

  // Advance the travelling signal one dependency level at a time.
  useEffect(() => {
    if (!wave) return
    const timer = window.setTimeout(() => {
      setWave(current => (!current || current.id !== wave.id ? current
        : current.step >= current.max ? null : { ...current, step: current.step + 1 }))
    }, STEP_MS)
    return () => window.clearTimeout(timer)
  }, [wave])

  const display = useCallback((slot: Slot): NodeView => (
    wave && wave.changed.has(slot) && (wave.depth[slot] ?? 0) > wave.step ? wave.prev[slot] : view.nodes[slot]
  ), [wave, view])

  const displayedReports: ReportView[] = view.reports.map(report => {
    const pending = wave && wave.changed.has(report.slot) && (wave.depth[report.slot] ?? 0) > wave.step
    return pending ? wave.prevReports.find(item => item.key === report.key) ?? report : report
  })

  const snapshot = () => ({
    nodes: Object.fromEntries(SLOTS.map(def => [def.slot, display(def.slot)])) as Record<Slot, NodeView>,
    reports: displayedReports,
  })

  const startWave = (prev: ReturnType<typeof snapshot>, next: View, roots: Slot[], origin: Slot | null) => {
    const changed = new Set(SLOTS.map(def => def.slot).filter(slot => nodeChanged(prev.nodes[slot], next.nodes[slot])))
    if (reduce || !changed.size) {
      setWave(null)
      return
    }
    const depth = depthFrom(roots)
    const max = Math.max(...[...changed].map(slot => depth[slot] ?? 0))
    setWave({ id: ++waveId.current, origin, prev: prev.nodes, prevReports: prev.reports, depth, changed, step: 0, max })
  }

  const push = (entry: Omit<LogEntry, 'id'>) => setLog(current => [{ ...entry, id: logId.current++ }, ...current].slice(0, 40))

  const applyChange = (payload: ChangePayload, form: FormId) => {
    const prev = snapshot()
    let info
    try {
      info = session.applyChange(payload)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setFieldError({ form, message: `${message}.`.replace(/\.\.$/, '.') })
      setStatus({ tone: 'fail', text: `Correction refused: ${message}.`.replace(/\.\.$/, '.') })
      return
    }
    const next = buildView(session)
    setFieldError(null)
    setVerification(null)
    setPrevious({})
    setView(next)
    const title = changeTitle(payload)
    const root = `source:${info.source}` as Slot
    if (!info.changed) {
      setStatus({ tone: 'info', text: `${title}. That matches the saved version, so nothing new needs refresh.` })
      push({ tone: 'change', title, lines: [{ kind: 'note', text: 'Same content as the current version: no new version published' }] })
      return
    }
    // Saved results that read any earlier version of this source (changes accumulate until reset).
    const own = session.runtime.affected(session.changedSourceIds.filter(id => session.runtime.get(id).logicalId === root))
    const names = own.map(record => labelOf(record.logicalId))
    const version = session.runtime.get(info.currentSourceId).version
    if (payload.kind === 'remove') {
      setStatus({
        tone: 'blocked',
        text: `${title}. ${plural(own.length, 'saved result')} read it and ${own.length === 1 ? 'is' : 'are'} now blocked: ${listText(names)}. Refresh cannot recover them; reset restores the source.`,
      })
    } else {
      setStatus({
        tone: 'stale',
        text: own.length
          ? `${title}. ${plural(own.length, 'saved result')} read the old version and ${own.length === 1 ? 'is' : 'are'} withheld until refresh: ${listText(names)}. Everything else stays current.`
          : `${title}. No current saved result reads the old version.`,
      })
    }
    push({
      tone: 'change', title,
      lines: [
        { kind: 'note', text: payload.kind === 'remove' ? `${SOURCE_LABEL[info.source]} marked removed` : `${SOURCE_LABEL[info.source]} v${version} published` },
        ...names.map(name => ({ kind: 'note' as const, text: `${name}: ${payload.kind === 'remove' ? 'blocked' : 'needs refresh'}` })),
      ],
    })
    startWave(prev, next, [root], root)
  }

  const refresh = () => {
    const prev = snapshot()
    const before: Record<string, number> = {}
    for (const report of view.reports) {
      for (const claim of report.claims) before[`${report.key}:${claim.key}`] = claim.value ?? claim.savedValue
    }
    const outcome = session.refresh()
    const next = buildView(session)
    setView(next)
    setVerification(null)
    setFieldError(null)
    const calls = outcome.ok ? outcome.lastRefresh.toolCalls : outcome.toolCalls
    const lines = calls.map(call => callLine(session, call))
    if (outcome.ok) {
      const result = outcome.lastRefresh
      setPrevious(before)
      lines.push(...result.reusedArtifactIds.map(id => reusedLine(session, id)))
      if (result.executedCount === 0) {
        setStatus({ tone: 'info', text: 'Nothing needed refresh. Both reports were already current, so no tools ran.' })
      } else {
        setStatus({
          tone: 'pass',
          text: `Refresh ran ${plural(result.executedCount, 'tool')} and reused ${plural(result.reusedCount, 'saved result')}. ${result.unchangedSupport ? 'The support count kept the same artifact. ' : ''}${result.numericParity ? 'Both reports match a fresh recomputation.' : 'The reports do not match a fresh recomputation.'}`,
        })
      }
      push({
        tone: 'refresh',
        title: result.executedCount ? `Refresh: ${result.executedCount} ran, ${result.reusedCount} reused` : 'Refresh: nothing to do',
        lines,
      })
    } else {
      const source = outcome.source as SourceName | null
      const what = source ? `${SOURCE_LABEL[source]} was removed` : 'evidence is missing'
      setStatus({
        tone: 'blocked',
        text: `Refresh stopped: ${what}, so the work that needs it cannot be recomputed.${calls.length ? ` ${plural(calls.length, 'tool')} ran before the stop.` : ''} Reset the sample to restore it.`,
      })
      push({ tone: 'error', title: 'Refresh stopped', lines: [...lines, { kind: 'fail', text: outcome.error }] })
    }
    startWave(prev, next, SOURCE_SLOTS, null)
  }

  const verify = () => {
    const result = session.verify()
    setVerification(result)
    setStatus(result.passed
      ? { tone: 'pass', text: 'Check passed: both saved reports are current and match a fresh recomputation.' }
      : { tone: 'fail', text: `Check failed: ${listText(result.reports.filter(row => !(row.numericMatch && row.state === 'current')).map(row => row.title))} ${result.reports.filter(row => !(row.numericMatch && row.state === 'current')).length === 1 ? 'is' : 'are'} not both current and matching.` })
    push({
      tone: 'verify', title: result.passed ? 'Check values: passed' : 'Check values: failed',
      lines: result.reports.map(row => ({
        kind: row.numericMatch && row.state === 'current' ? 'pass' : 'fail',
        text: `${row.title}: ${row.error ? 'cannot recompute' : row.numericMatch ? 'values match' : 'values differ'}, ${row.state === 'current' ? 'current' : 'not current'}`,
      })),
    })
  }

  const reset = () => {
    const fresh = new DemoSession(session.generation + 1)
    setSession(fresh)
    setView(buildView(fresh))
    setWave(null)
    setVerification(null)
    setPrevious({})
    setFieldError(null)
    setStatus({ tone: 'info', text: 'Sample reset to the authored data. A new generation ran the eight initial tools; every saved result is current.' })
    push({ tone: 'reset', title: 'Sample reset: new generation', lines: fresh.runtime.calls.map(call => callLine(fresh, call)) })
  }

  const removed = new Set(SLOTS.filter(def => view.nodes[def.slot].state === 'removed').map(def => def.slot.replace('source:', '') as SourceName))
  const shown = SLOTS.filter(def => def.layer !== 'source').map(def => display(def.slot))
  const staleCount = shown.filter(node => node.state === 'stale' || node.state === 'unknown').length
  const blockedCount = shown.filter(node => node.state === 'blocked').length
  const StatusIcon = status.tone === 'pass' ? CircleCheck : status.tone === 'blocked' ? Ban : status.tone === 'info' ? Info : CircleAlert

  return (
    <section id="demo" className="section demo-section" aria-labelledby="demo-title">
      <div className="wrap">
        <header className="section-head demo-head">
          <h2 id="demo-title" className="section-title">Change a source. Watch only the affected work move.</h2>
          <p className="section-lede">Each correction flags only the work that read that source. Refresh reruns those steps and reuses everything else.</p>
        </header>

        <div className="demo-replay">
          <p>Replay of the guided sample in your browser. The live app runs the same corrections on SQLite and native HydraDB traversal.</p>
          <div className="demo-replay-actions">
            <ButtonLink href={links.liveApp} external variant="secondary">Try it on the live app</ButtonLink>
            <span className="demo-replay-sources">
              <Source path="docs/API_CONTRACT.md" />
              <Source path="proofflow/analytics.py" />
            </span>
          </div>
        </div>

        <div className="demo-bench panel">
          <Console view={view} removed={removed} error={fieldError} verification={verification}
            onChange={applyChange} onFieldError={setFieldError} onRefresh={refresh} onVerify={verify} onReset={reset} />

          <div className="demo-stage">
            <div className="demo-stage-head">
              <h3 className="demo-panel-title">Lineage</h3>
              <div className="demo-counts">
                {staleCount === 0 && blockedCount === 0 && <StateTag state="current">All current</StateTag>}
                {staleCount > 0 && <StateTag state="withheld">{staleCount} need refresh</StateTag>}
                {blockedCount > 0 && <StateTag state="blocked">{blockedCount} blocked</StateTag>}
              </div>
            </div>
            <p className={`demo-status is-${status.tone}`} role="status" aria-live="polite">
              <StatusIcon size={18} strokeWidth={2} aria-hidden />
              <span>{status.text}</span>
            </p>
            <Graph display={display} next={view.nodes} selected={selected} wave={wave}
              origin={wave?.origin ?? null} onSelect={slot => setSelected(current => (current === slot ? null : slot))} />
            <Inspector session={session} slot={selected} node={selected ? display(selected) : null} />
          </div>
        </div>

        <div className="demo-lower">
          <Reports reports={displayedReports} previous={previous} refresh={session.lastRefresh} />
          <Activity entries={log} />
        </div>

        <p className="demo-verified soft">
          The verified run: company revenue $5,565 to $5,755 and EU revenue $2,090 to $2,280 after EUR 1.10 to 1.20,
          EU support tickets 2 with the same artifact, and four tools on refresh. This replay reproduces each figure.{' '}
          <Source path="README.md" />
        </p>

        <div className="demo-shots">
          <figure>
            <img src="./shots/workspace-stale-final.jpg" width={1536} height={1146} loading="lazy"
              alt="The live ProofFlow app after correcting EUR to USD to 1.20: company revenue shows Awaiting refresh with the previous $5,565.00 labelled, the evidence graph highlights the affected path, and a banner says 4 saved artifacts require revalidation." />
            <figcaption>The live app after the EUR correction: affected values wait for refresh.</figcaption>
          </figure>
          <figure>
            <img src="./shots/workspace-refreshed-final.jpg" width={1536} height={1096} loading="lazy"
              alt="The live ProofFlow app after refresh: company revenue $5,755.00, EU revenue $2,280.00, EU support tickets 2, and a banner reporting 4 tool calls, unchanged support and matching recomputation." />
            <figcaption>The live app after refresh: four tool calls, support unchanged.</figcaption>
          </figure>
        </div>
      </div>
    </section>
  )
}
