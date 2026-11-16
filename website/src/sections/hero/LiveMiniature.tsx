import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { animate, motion, useInView, useReducedMotion } from 'motion/react'
import { PenLine, RefreshCw, RotateCcw } from 'lucide-react'
import { Button, Source, StateTag, usd, type ClaimState } from '../../components/ui'
import { guidedSample as g } from '../../content/facts'

/**
 * Live miniature of the guided sample: three saved claims wired to four inputs.
 * Values are the README guided-sample table (before / after EUR→USD 1.10→1.20).
 */

type Step = 'current' | 'withheld' | 'refreshed'
type ClaimId = 'company' | 'eu' | 'support'
type SourceId = 'orders' | 'refunds' | 'fx' | 'tickets'

const CLAIMS: { id: ClaimId; label: string; affected: boolean }[] = [
  { id: 'company', label: 'Company revenue', affected: true },
  { id: 'eu', label: 'EU revenue', affected: true },
  { id: 'support', label: 'EU support tickets', affected: false },
]

const SOURCES: { id: SourceId; label: string }[] = [
  { id: 'orders', label: 'Orders' },
  { id: 'refunds', label: 'Refunds' },
  { id: 'fx', label: 'EUR→USD' },
  { id: 'tickets', label: 'Support tickets' },
]

/** Which inputs each claim was made from (proofflow/analytics.py tool specs). */
const THREADS: { id: string; claim: ClaimId; source: SourceId }[] = [
  { id: 'company-orders', claim: 'company', source: 'orders' },
  { id: 'company-refunds', claim: 'company', source: 'refunds' },
  { id: 'company-fx', claim: 'company', source: 'fx' },
  { id: 'eu-orders', claim: 'eu', source: 'orders' },
  { id: 'eu-refunds', claim: 'eu', source: 'refunds' },
  { id: 'eu-fx', claim: 'eu', source: 'fx' },
  { id: 'support-tickets', claim: 'support', source: 'tickets' },
]

const BUTTON: Record<Step, { label: string; icon: typeof PenLine }> = {
  current: { label: `Correct EUR rate to ${g.fxAfter}`, icon: PenLine },
  withheld: { label: 'Refresh affected', icon: RefreshCw },
  refreshed: { label: 'Reset sample', icon: RotateCcw },
}

const STATUS: Record<Step, string> = {
  current: `Saved with EUR→USD at ${g.fxBefore}. All three claims are current.`,
  withheld: `Rate corrected to ${g.fxAfter}. Both revenue claims are withheld; the support count is not affected.`,
  refreshed: `${g.refreshToolCalls} tools ran. Revenue now uses ${g.fxAfter}; the support count was reused, not recalculated.`,
}

const PULSE_MS = 820

function claimState(step: Step, affected: boolean): ClaimState {
  if (step === 'current') return 'current'
  if (step === 'withheld') return affected ? 'withheld' : 'current'
  return affected ? 'refreshed' : 'reused'
}

type Geometry = { w: number; h: number; paths: Record<string, string> }

export default function LiveMiniature() {
  const reduce = useReducedMotion() ?? false
  const [step, setStep] = useState<Step>('current')
  // What the claims display. Lags behind `step` while the change pulse travels.
  const [shown, setShown] = useState<Step>('current')
  const [inkRound, setInkRound] = useState(0)
  const [cents, setCents] = useState<{ company: number; eu: number }>({ company: g.companyBeforeCents, eu: g.euBeforeCents })
  const [geo, setGeo] = useState<Geometry | null>(null)

  const graphRef = useRef<HTMLDivElement>(null)
  // On phones the widget sits below the fold: draw the threads when it is first seen.
  const inView = useInView(graphRef, { once: true, amount: 0.35 })
  const claimPorts = useRef<Partial<Record<ClaimId, HTMLSpanElement | null>>>({})
  const sourcePorts = useRef<Partial<Record<SourceId, HTMLSpanElement | null>>>({})

  // Measure port positions and draw threads between them in pixel space.
  useLayoutEffect(() => {
    const el = graphRef.current
    if (!el) return
    const measure = () => {
      const box = el.getBoundingClientRect()
      const centre = (n: HTMLElement | null | undefined) => {
        if (!n) return null
        const r = n.getBoundingClientRect()
        return { x: r.left + r.width / 2 - box.left, y: r.top + r.height / 2 - box.top }
      }
      const paths: Record<string, string> = {}
      for (const t of THREADS) {
        const s = centre(sourcePorts.current[t.source])
        const c = centre(claimPorts.current[t.claim])
        if (!s || !c) continue
        const mx = (s.x + c.x) / 2
        paths[t.id] = `M${s.x.toFixed(1)} ${s.y.toFixed(1)} C${mx.toFixed(1)} ${s.y.toFixed(1)} ${mx.toFixed(1)} ${c.y.toFixed(1)} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`
      }
      setGeo({ w: box.width, h: box.height, paths })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    // Chips can wrap (for example the FX chip on phones) and shift ports without resizing the graph.
    el.querySelectorAll('ul, li').forEach(node => ro.observe(node))
    document.fonts?.ready.then(measure).catch(() => {})
    return () => ro.disconnect()
  }, [])

  // Claims switch to withheld when the pulse arrives (instantly with reduced motion).
  useEffect(() => {
    if (reduce || step !== 'withheld') {
      setShown(step)
      return
    }
    const t = window.setTimeout(() => setShown('withheld'), PULSE_MS)
    return () => window.clearTimeout(t)
  }, [step, reduce])

  // Refreshed numbers count from the old value to the new one.
  useEffect(() => {
    if (step !== 'refreshed') {
      setCents({ company: g.companyBeforeCents, eu: g.euBeforeCents })
      return
    }
    if (reduce) {
      setCents({ company: g.companyAfterCents, eu: g.euAfterCents })
      return
    }
    const toDollar = (v: number) => Math.round(v / 100) * 100
    const controls = animate(0, 1, {
      duration: 0.9,
      delay: 0.45,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: p =>
        setCents({
          company: toDollar(g.companyBeforeCents + (g.companyAfterCents - g.companyBeforeCents) * p),
          eu: toDollar(g.euBeforeCents + (g.euAfterCents - g.euBeforeCents) * p),
        }),
    })
    return () => controls.stop()
  }, [step, reduce])

  const advance = () => {
    if (step === 'current') setStep('withheld')
    else if (step === 'withheld') {
      setStep('refreshed')
      setInkRound(n => n + 1)
    } else setStep('current')
  }

  const fxChanged = step !== 'current'
  const value = (id: ClaimId) =>
    id === 'support' ? String(g.euSupportTickets) : usd(id === 'company' ? cents.company : cents.eu)
  const { label: buttonLabel, icon: ButtonIcon } = BUTTON[step]

  return (
    <figure className="hero-demo" aria-labelledby="hero-mini-title">
      <div className={`hero-mini panel${reduce ? '' : ' is-animated'}`} data-step={step}>
        <div className="mini-head">
          <p id="hero-mini-title" className="mini-title">Company weekly report and EU operations brief</p>
          <p className="mini-sub">Two saved reports built from one shared revenue calculation</p>
        </div>

        <div className="mini-graph" ref={graphRef}>
          {geo && (
            <svg className="mini-threads" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`} aria-hidden focusable="false">
              {THREADS.map((t, i) => {
                const d = geo.paths[t.id]
                if (!d) return null
                const onFx = t.source === 'fx'
                const redraw = onFx && inkRound > 0
                return (
                  <motion.path
                    key={redraw ? `${t.id}-${inkRound}` : t.id}
                    d={d}
                    className={`thread${onFx ? ' thread-fx' : ''}${t.claim !== 'support' ? ' thread-revenue' : ''}`}
                    initial={reduce ? false : { pathLength: 0 }}
                    animate={{ pathLength: inView || reduce ? 1 : 0 }}
                    transition={redraw ? { duration: 0.6, ease: [0.65, 0, 0.35, 1] } : { duration: 0.9, delay: 0.15 + i * 0.05, ease: [0.65, 0, 0.35, 1] }}
                  />
                )
              })}
              {THREADS.filter(t => t.source === 'fx').map(t => {
                const d = geo.paths[t.id]
                if (!d) return null
                return (
                  <g key={`stale-${t.id}`}>
                    <path d={d} className="thread-stale" />
                    {step === 'withheld' && !reduce && <path d={d} pathLength={1} className="thread-pulse" />}
                  </g>
                )
              })}
            </svg>
          )}

          <p className="mini-col-label mini-col-claims" aria-hidden>Claims</p>
          <p className="mini-col-label mini-col-inputs" aria-hidden>Inputs</p>

          <ul className="mini-claims" aria-label="Report claims">
            {CLAIMS.map(c => {
              const state = claimState(shown, c.affected)
              return (
                <li key={c.id} className="mini-claim" data-state={state}>
                  <span className="mini-claim-label">{c.label}</span>
                  <span className="mini-claim-line">
                    {state === 'withheld' && <span className="sr-only">Outdated value, not served:</span>}
                    <span className="mini-value figure">{value(c.id)}</span>
                    <StateTag state={state} />
                  </span>
                  <span className="mini-port" ref={n => { claimPorts.current[c.id] = n }} aria-hidden />
                </li>
              )
            })}
          </ul>

          <ul className="mini-sources" aria-label="Inputs">
            {SOURCES.map(s => (
              <li key={s.id} className="mini-source" data-changed={s.id === 'fx' && step === 'withheld' ? 'true' : undefined}>
                <span className="mini-port" ref={n => { sourcePorts.current[s.id] = n }} aria-hidden />
                <span className="mini-source-label">{s.label}</span>
                {s.id === 'fx' && (
                  <span className="mini-fx figure">
                    {fxChanged ? (
                      <>
                        {step === 'withheld' && <del><span className="sr-only">was </span>{g.fxBefore}</del>}
                        <ins><span className="sr-only">now </span>{g.fxAfter}</ins>
                      </>
                    ) : g.fxBefore}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>

        <p className="sr-only">
          Company revenue and EU revenue are calculated from orders, refunds and the EUR to USD rate. EU support tickets is
          calculated from support tickets only, so a rate correction does not affect it.
        </p>

        <div className="mini-controls">
          <Button variant={step === 'refreshed' ? 'secondary' : 'primary'} onClick={advance}
            icon={<ButtonIcon size={17} strokeWidth={2.2} aria-hidden />}>
            {buttonLabel}
          </Button>
          <p className="mini-status" aria-live="polite">{STATUS[step]}</p>
        </div>
      </div>
      <figcaption className="hero-demo-caption">
        A replay of the guided sample’s arithmetic. The live app runs it on SQLite and HydraDB.
        <Source path="README.md" />
      </figcaption>
    </figure>
  )
}
