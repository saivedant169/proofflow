import { useCallback, useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { Ban, CircleAlert, CircleCheck, Info, PanelRightOpen, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'
import { ButtonLink, Source } from '../../components/ui'
import { links } from '../../content/facts'
import {
  DemoSession, selfCheck,
  type ArtifactRecord, type ChangePayload, type SourceName, type ToolCall, type Verification,
} from './engine'
import {
  SLOTS, SLOT_DEF, SOURCE_LABEL, TOOL_LABEL, buildView, depthFrom, money, nodeChanged,
  type NodeView, type ReportView, type Slot, type View,
} from './model'
import Graph, { type Wave } from './Graph'
import Chips, { type FieldError, type FormId } from './Chips'
import { Counters, Reports, type MeterTone } from './Cards'
import Drawer, { type DrawerTab } from './Drawer'
import type { LogEntry, LogLine } from './Activity'
import './styles.css'

if (import.meta.env.DEV) {
  const failed = selfCheck().filter(row => !row.pass)
  console.assert(failed.length === 0, 'Demo engine self-check failed', failed)
}

const STEP_MS = 380
const SOURCE_SLOTS: Slot[] = ['source:orders', 'source:refunds', 'source:fx', 'source:tickets']
const RESULT_SLOTS = SLOTS.filter(def => def.layer !== 'source').map(def => def.slot)

type StatusTone = 'info' | 'stale' | 'blocked' | 'pass' | 'fail'
/** `short` is the visible event chip; `text` is the full sentence announced to screen readers. */
interface Status { tone: StatusTone; short: string; text: string }

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

/** Distinct saved records (by logical id) read through the given input maps. */
function distinctInputs(session: DemoSession, inputs: Record<string, string>[]) {
  const ids = new Set<string>()
  for (const map of inputs) for (const id of Object.values(map)) ids.add(session.runtime.records.get(id)?.logicalId ?? id)
  return ids.size
}

const labelOf = (logicalId: string) => SLOT_DEF[logicalId as Slot]?.label ?? logicalId
const INITIAL: Status = { tone: 'info', short: 'All 8 results current', text: 'All eight saved results are current. Apply a correction to see what it touches.' }

export default function Demo() {
  const reduce = useReducedMotion()
  const [session, setSession] = useState(() => new DemoSession(1))
  const [view, setView] = useState<View>(() => buildView(session))
  const [wave, setWave] = useState<Wave | null>(null)
  const [selected, setSelected] = useState<Slot | null>(null)
  const [preview, setPreview] = useState<Slot | null>(null)
  const [verification, setVerification] = useState<Verification | null>(null)
  const [previous, setPrevious] = useState<Record<string, number>>({})
  const [fieldError, setFieldError] = useState<FieldError | null>(null)
  const [status, setStatus] = useState<Status>(INITIAL)
  const [work, setWork] = useState<{ ran: number; reused: number; records: number; healed: boolean }>({ ran: 0, reused: 0, records: 0, healed: false })
  const [drawer, setDrawer] = useState<{ open: boolean; tab: DrawerTab }>({ open: false, tab: 'step' })
  const trigger = useRef<HTMLElement | null>(null)
  const sectionRef = useRef<HTMLElement>(null)
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

  const closeDrawer = useCallback(() => {
    setDrawer(current => ({ ...current, open: false }))
    const back = trigger.current
    trigger.current = null
    if (back && back.isConnected) back.focus({ preventScroll: true })
  }, [])

  // The drawer belongs to the playground: close it once the section scrolls away.
  useEffect(() => {
    const node = sectionRef.current
    if (!node || !drawer.open) return
    const onScroll = () => {
      const rect = node.getBoundingClientRect()
      if (rect.bottom < 0 || rect.top > window.innerHeight) setDrawer(current => ({ ...current, open: false }))
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [drawer.open])

  const openDrawer = (tab: DrawerTab) => {
    if (!drawer.open) trigger.current = document.activeElement as HTMLElement | null
    setDrawer({ open: true, tab })
  }

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
    setWave({ id: ++waveId.current, origin, prev: prev.nodes, prevReports: prev.reports, depth, changed, step: 0, max, stepMs: STEP_MS })
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
      setStatus({ tone: 'fail', short: 'Correction refused', text: `Correction refused: ${message}.`.replace(/\.\.$/, '.') })
      return
    }
    const next = buildView(session)
    setFieldError(null)
    setVerification(null)
    setPrevious({})
    setWork({ ran: 0, reused: 0, records: 0, healed: false })
    setView(next)
    const title = changeTitle(payload)
    const root = `source:${info.source}` as Slot
    if (!info.changed) {
      setStatus({ tone: 'info', short: 'No change', text: `${title}. That matches the saved version, so nothing new needs refresh.` })
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
        short: `${SOURCE_LABEL[info.source]} removed`,
        text: `${title}. ${plural(own.length, 'saved result')} read it and ${own.length === 1 ? 'is' : 'are'} now blocked: ${listText(names)}. Refresh cannot recover them; reset restores the source.`,
      })
    } else {
      setStatus({
        tone: 'stale',
        short: `${SOURCE_LABEL[info.source]} v${version}`,
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
      setWork({ ran: result.executedCount, reused: result.reusedCount, records: distinctInputs(session, calls.map(call => call.inputs)), healed: true })
      lines.push(...result.reusedArtifactIds.map(id => reusedLine(session, id)))
      if (result.executedCount === 0) {
        setStatus({ tone: 'info', short: 'Nothing to refresh', text: 'Nothing needed refresh. Both reports were already current, so no tools ran.' })
      } else {
        setStatus({
          tone: 'pass',
          short: result.numericParity ? 'Healed and verified' : 'Refreshed',
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
      setWork({ ran: calls.length, reused: 0, records: 0, healed: false })
      setStatus({
        tone: 'blocked',
        short: 'Refresh stopped',
        text: `Refresh stopped: ${what}, so the work that needs it cannot be recomputed.${calls.length ? ` ${plural(calls.length, 'tool')} ran before the stop.` : ''} Reset the sample to restore it.`,
      })
      push({ tone: 'error', title: 'Refresh stopped', lines: [...lines, { kind: 'fail', text: outcome.error }] })
    }
    startWave(prev, next, SOURCE_SLOTS, null)
  }

  const verify = () => {
    const result = session.verify()
    const failing = result.reports.filter(row => !(row.numericMatch && row.state === 'current'))
    setVerification(result)
    setStatus(result.passed
      ? { tone: 'pass', short: 'Check passed', text: 'Check passed: both saved reports are current and match a fresh recomputation.' }
      : { tone: 'fail', short: 'Check failed', text: `Check failed: ${listText(failing.map(row => row.title))} ${failing.length === 1 ? 'is' : 'are'} not both current and matching.` })
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
    setWork({ ran: 0, reused: 0, records: 0, healed: false })
    setStatus({ tone: 'info', short: 'Sample reset', text: 'Sample reset to the authored data. A new generation ran the eight initial tools; every saved result is current.' })
    push({ tone: 'reset', title: 'Sample reset: new generation', lines: fresh.runtime.calls.map(call => callLine(fresh, call)) })
  }

  const selectNode = (slot: Slot) => {
    if (drawer.open && drawer.tab === 'step' && selected === slot) {
      closeDrawer()
      return
    }
    setSelected(slot)
    openDrawer('step')
  }

  const removed = new Set(SLOTS.filter(def => view.nodes[def.slot].state === 'removed').map(def => def.slot.replace('source:', '') as SourceName))
  const shown = RESULT_SLOTS.map(slot => display(slot))
  const staleCount = shown.filter(node => node.state === 'stale' || node.state === 'unknown').length
  const blockedCount = shown.filter(node => node.state === 'blocked').length
  // Context-layer point, against the re-run-everything baseline: steps re-run and distinct records read.
  const pendingArtifacts = session.affectedArtifacts.filter(record => {
    const state = view.nodes[record.logicalId as Slot]?.state
    return state === 'stale' || state === 'unknown'
  })
  const pending = !work.healed && pendingArtifacts.length > 0
  const heads = RESULT_SLOTS.map(slot => session.runtime.getHead(slot)).filter((record): record is ArtifactRecord => record?.kind === 'artifact')
  const meterTone: MeterTone = staleCount ? 'stale' : blockedCount ? 'blocked' : work.healed && work.ran ? 'fresh' : 'idle'
  const meters = {
    steps: work.healed ? work.ran : pending ? pendingArtifacts.length : 0,
    stepsTotal: RESULT_SLOTS.length,
    records: work.healed ? work.records : pending ? distinctInputs(session, pendingArtifacts.map(record => record.inputs)) : 0,
    recordsTotal: distinctInputs(session, heads.map(record => record.inputs)),
    pending,
    tone: meterTone,
  }
  const rate = view.nodes['source:fx'].state === 'removed' ? '1.20' : view.nodes['source:fx'].detail.replace('EUR ', '')
  const StatusIcon = status.tone === 'pass' ? CircleCheck : status.tone === 'blocked' ? Ban : status.tone === 'info' ? Info : CircleAlert
  const checkTone = verification ? (verification.passed ? ' is-pass' : ' is-fail') : ''

  return (
    <section id="demo" ref={sectionRef} className="section demo-section stage" aria-labelledby="demo-title">
      <div className="demo-wash" aria-hidden />
      <div className="wrap">
        <header className="demo-head">
          <div className="demo-head-copy">
            <h2 id="demo-title" className="demo-title">Break it. Watch it heal.</h2>
            <p className="demo-lede">Correct a source: only the work that read it is withheld and re-run. Everything else is reused.</p>
          </div>
        </header>
        <Counters work={meters} reused={work.reused} withheld={staleCount} blocked={blockedCount} />

        <Chips rate={rate} removed={removed} error={fieldError} onChange={applyChange}
          onFieldError={setFieldError} onPreview={setPreview} />

        <div className="demo-frame">
          <div className="demo-frame-top">
            <span className="demo-example">Example: revenue reports an agent saved</span>
            <span className={`demo-event is-${status.tone}`} aria-hidden>
              <StatusIcon size={14} strokeWidth={2.4} />
              {status.short}
            </span>
            <button type="button" className="demo-info" onClick={() => openDrawer('activity')}
              aria-label={`Open activity log, ${log.length} entries`}>
              <PanelRightOpen size={17} strokeWidth={2} aria-hidden />
              <span className="demo-info-label">Activity</span>
            </button>
          </div>

          <Graph display={display} next={view.nodes} selected={drawer.open && drawer.tab === 'step' ? selected : null}
            wave={wave} preview={preview} onSelect={selectNode} />

          <div className="demo-dock" role="group" aria-label="Actions">
            <button type="button" className={`demo-act demo-act--refresh${staleCount ? ' is-due' : ''}`} onClick={refresh}>
              <RefreshCw size={18} strokeWidth={2.3} aria-hidden />
              Refresh
            </button>
            <button type="button" className={`demo-act demo-act--check${checkTone}`} onClick={verify}>
              {verification?.passed ? <CircleCheck size={18} strokeWidth={2.2} aria-hidden /> : <ShieldCheck size={18} strokeWidth={2.2} aria-hidden />}
              {verification ? (verification.passed ? 'Passed' : 'Failed') : 'Check'}
            </button>
            <button type="button" className="demo-act demo-act--reset" onClick={reset} aria-label="Reset sample">
              <RotateCcw size={17} strokeWidth={2.2} aria-hidden />
            </button>
          </div>
        </div>

        <Reports reports={displayedReports} previous={previous} refresh={session.lastRefresh}
          checks={verification?.reports ?? null} />

        <footer className="demo-foot">
          <p className="demo-honest">Browser replay of the guided sample; the live app runs SQLite and HydraDB.</p>
          <ButtonLink href={links.liveApp} external variant="secondary">Open the live app</ButtonLink>
          <span className="demo-sources">
            <Source path="README.md" />
            <Source path="proofflow/analytics.py" />
          </span>
        </footer>

        <div className="demo-real">
          <span className="demo-real-label">See the real app</span>
          <a className="demo-shot" href={import.meta.env.BASE_URL + 'shots/workspace-stale-final.jpg'} target="_blank" rel="noreferrer">
            <img src={import.meta.env.BASE_URL + 'shots/workspace-stale-final.jpg'} width={1536} height={1146} loading="lazy"
              alt="The live ProofFlow app after correcting EUR to USD to 1.20: company revenue shows Awaiting refresh with the previous $5,565.00 labelled, and 4 saved artifacts require revalidation." />
            <span>Withheld</span>
          </a>
          <a className="demo-shot" href={import.meta.env.BASE_URL + 'shots/workspace-refreshed-final.jpg'} target="_blank" rel="noreferrer">
            <img src={import.meta.env.BASE_URL + 'shots/workspace-refreshed-final.jpg'} width={1536} height={1096} loading="lazy"
              alt="The live ProofFlow app after refresh: company revenue $5,755.00, EU revenue $2,280.00, EU support tickets 2, 4 tool calls and matching recomputation." />
            <span>Refreshed</span>
          </a>
        </div>
      </div>

      <Drawer open={drawer.open} tab={drawer.tab} onTab={tab => setDrawer(current => ({ ...current, tab }))}
        onClose={closeDrawer} session={session} slot={selected} node={selected ? display(selected) : null} log={log} />
      <p className="sr-only" role="status" aria-live="polite">{status.text}</p>
    </section>
  )
}
