import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { CircleCheck, CircleX } from 'lucide-react'
import { StateTag, type ClaimState as TagState } from '../../components/ui'
import type { LastRefresh, VerifyRow } from './engine'
import { SOURCE_LABEL, money, type ClaimView, type ReportView } from './model'

/** Animate a number from its last shown value to the new target. Integers only (cents, counts). */
export function useTicker(target: number, duration = 900): number {
  const reduce = useReducedMotion()
  const [value, setValue] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = from.current
    from.current = target
    if (reduce || start === target) {
      setValue(target)
      return
    }
    let frame = 0
    const began = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - began) / duration)
      const eased = 1 - (1 - t) ** 3
      setValue(Math.round(start + (target - start) * eased))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration, reduce])
  return value
}

const fmt = (claim: ClaimView, value: number) => (claim.unit === 'USD cents' ? money(value) : String(value))
const short = (claim: ClaimView, value: number) => (claim.unit === 'USD cents' ? money(value - (value % 100)) : String(value))

function reportTag(report: ReportView): { state: TagState; text: string } {
  if (report.state === 'blocked') {
    const all = report.claims.every(claim => claim.state === 'blocked')
    return { state: 'blocked', text: all ? 'Blocked' : 'Partly blocked' }
  }
  if (report.state === 'stale' || report.state === 'unknown') return { state: 'withheld', text: 'Withheld' }
  if (report.badge === 'refreshed') return { state: 'refreshed', text: 'Refreshed' }
  return { state: 'current', text: 'Current' }
}

function Claim({ claim, previous, refresh, lead }: {
  claim: ClaimView; previous: number | undefined; refresh: LastRefresh | null; lead: boolean
}) {
  const shown = claim.value ?? claim.savedValue
  const ticking = useTicker(shown, lead ? 1100 : 700)
  const current = claim.state === 'current' && claim.value !== null
  const recomputed = current && !!refresh?.executedArtifactIds.includes(claim.artifactId)
  const reused = current && !!refresh?.reusedArtifactIds.includes(claim.artifactId)
  const delta = current && previous !== undefined && previous !== claim.value ? claim.value! - previous : 0
  const exact = fmt(claim, shown)
  return (
    <div className={`demo-claim${lead ? ' is-lead' : ''} is-${claim.state}${recomputed && delta ? ' is-reinked' : ''}`}>
      <dt className="demo-claim-label">{claim.label}</dt>
      <dd className="demo-claim-body">
        <span className="demo-figure figure" aria-hidden>
          {ticking === shown ? exact : short(claim, ticking)}
        </span>
        <span className="sr-only">
          {current ? exact : claim.state === 'blocked' ? `Blocked. Saved value ${exact} cannot be recovered.` : `Withheld. Saved value ${exact} is not shown as current.`}
        </span>
        <span className="demo-claim-meta" aria-hidden>
          {claim.state === 'stale' || claim.state === 'unknown' ? <span className="demo-flag is-stale">Withheld</span> : null}
          {claim.state === 'blocked' ? <span className="demo-flag is-blocked">Needs {claim.blockedBy.map(name => SOURCE_LABEL[name]).join(', ')}</span> : null}
          {delta !== 0 && <span className="demo-flag is-fresh">{delta > 0 ? '+' : '−'}{fmt(claim, Math.abs(delta))}</span>}
          {reused && <span className="demo-flag is-reused">Reused</span>}
          {recomputed && !delta && !reused && <span className="demo-flag is-quiet">Same value</span>}
        </span>
      </dd>
    </div>
  )
}

function verdict(row: VerifyRow) {
  if (row.numericMatch && row.state === 'current') return { pass: true, text: 'Recompute matches' }
  if (row.error) return { pass: false, text: 'Cannot recompute' }
  if (!row.numericMatch) return { pass: false, text: 'Recompute differs' }
  return { pass: false, text: 'Input changed' }
}

export function Reports({ reports, previous, refresh, checks }: {
  reports: ReportView[]
  previous: Record<string, number>
  refresh: LastRefresh | null
  checks: VerifyRow[] | null
}) {
  return (
    <div className="demo-cards">
      {reports.map(report => {
        const tag = reportTag(report)
        const row = checks?.find(item => item.key === report.key)
        const check = row ? verdict(row) : null
        return (
          <article className={`demo-card is-${report.state}${report.badge ? ` has-${report.badge}` : ''}`} key={report.key}
            aria-labelledby={`demo-card-${report.key}`}>
            <header className="demo-card-head">
              <h3 id={`demo-card-${report.key}`}>{report.title}</h3>
              <StateTag state={tag.state}>{tag.text}</StateTag>
            </header>
            <dl className="demo-claims">
              {report.claims.map((claim, index) => (
                <Claim key={claim.key} claim={claim} lead={index === 0} refresh={refresh}
                  previous={previous[`${report.key}:${claim.key}`]} />
              ))}
            </dl>
            <footer className="demo-card-foot">
              <code>{report.runId}</code>
              {check && (
                <span className={`demo-check ${check.pass ? 'is-pass' : 'is-fail'}`}>
                  {check.pass ? <CircleCheck size={15} strokeWidth={2.2} aria-hidden /> : <CircleX size={15} strokeWidth={2.2} aria-hidden />}
                  {check.text}
                </span>
              )}
            </footer>
          </article>
        )
      })}
    </div>
  )
}

function Counter({ value, label, tone }: { value: number; label: string; tone: string }) {
  const ticking = useTicker(value, 700)
  return (
    <div className={`demo-counter is-${tone}${value === 0 ? ' is-zero' : ''}`}>
      <dt>{label}</dt>
      <dd className="figure">{ticking}</dd>
    </div>
  )
}

export type MeterTone = 'idle' | 'stale' | 'fresh' | 'blocked'

/** ProofFlow's work against the re-run-everything baseline on this sample, computed from the engine. */
function Meter({ label, value, total, tone, baseline, described }: {
  label: string; value: number; total: number; tone: MeterTone; baseline: string; described: string
}) {
  const ticking = useTicker(value, 700)
  return (
    <div className={`demo-meter is-${tone}`}>
      <dt>{label}</dt>
      <dd>
        <span className="demo-meter-figure figure" aria-hidden><strong>{ticking}</strong> of {total}</span>
        <span className="demo-meter-bar" aria-hidden style={{ gridTemplateColumns: `repeat(${total}, 1fr)` }}>
          {Array.from({ length: total }, (_, index) => <span key={index} className={index < value ? 'is-on' : ''} />)}
        </span>
        <span className="demo-meter-base" aria-hidden>{baseline}</span>
        <span className="sr-only">{described}</span>
      </dd>
    </div>
  )
}

export interface Work {
  /** Tool steps ProofFlow re-ran (or will re-run, while a change is pending). */
  steps: number
  stepsTotal: number
  /** Distinct saved records those steps read, against what a full recompute reads. */
  records: number
  recordsTotal: number
  pending: boolean
  tone: MeterTone
}

export function Counters({ work, reused, withheld, blocked }: { work: Work; reused: number; withheld: number; blocked: number }) {
  const verb = work.pending ? 'to re-run' : 're-run'
  return (
    <dl className="demo-counters" aria-label="Live counters">
      <Meter label={`Steps ${verb}`} value={work.steps} total={work.stepsTotal} tone={work.tone}
        baseline={`Full recompute: ${work.stepsTotal}`}
        described={`ProofFlow ${work.pending ? 'will re-run' : 're-ran'} ${work.steps} of ${work.stepsTotal} steps; a full recompute would re-run all ${work.stepsTotal}.`} />
      <Meter label={work.pending ? 'Records to read' : 'Records read'} value={work.records} total={work.recordsTotal} tone={work.tone}
        baseline={`Full recompute: ${work.recordsTotal}`}
        described={`It ${work.pending ? 'will read' : 'read'} ${work.records} of ${work.recordsTotal} saved records; a full recompute reads all ${work.recordsTotal}.`} />
      <Counter value={reused} label="Reused" tone="reused" />
      <Counter value={withheld} label="Withheld" tone="withheld" />
      {blocked > 0 && <Counter value={blocked} label="Blocked" tone="blocked" />}
    </dl>
  )
}
