import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { SectionHead, Source } from '../../components/ui'
import Pipeline from './Pipeline'
import { RETAINED_FAILURES, VERIFIED, VERIFIED_LABELS } from './data'
import './styles.css'

const EASE = [0.22, 1, 0.36, 1] as const

export default function Evaluation() {
  const [openFact, setOpenFact] = useState<number | null>(null)
  const [showFailures, setShowFailures] = useState(false)
  const reduce = !!useReducedMotion()

  return (
    <section id="evaluation" className="section evaluation-section" aria-labelledby="evaluation-title">
      <div className="wrap">
        <SectionHead
          id="evaluation-title"
          title="Built to be checked, not trusted."
          lede="Protocols frozen before scoring, held-out cases run once, results audited offline and re-verified on every push."
        />

        <Pipeline />

        <div className="ev-proof">
          <h3 className="ev-sub">Verified in the product</h3>
          <ul className="ev-facts">
            {VERIFIED.map((f, i) => {
              const isOpen = openFact === i
              const hosted = f.figure.includes('→')
              return (
                <li key={f.label} className={`ev-fact${isOpen ? ' is-open' : ''}`} onMouseLeave={() => { if (isOpen) setOpenFact(null) }}>
                  <button
                    type="button"
                    className="ev-fact-btn"
                    aria-expanded={isOpen}
                    aria-describedby={`ev-fact-${i}`}
                    onClick={() => setOpenFact(isOpen ? null : i)}
                  >
                    <span className="ev-fact-num figure">{hosted ? '642' : f.figure}</span>
                    <span className="ev-fact-label">{VERIFIED_LABELS[i]}</span>
                    {hosted && <span className="ev-fact-sub figure">{f.figure}</span>}
                  </button>
                  <div className="ev-pop" id={`ev-fact-${i}`} role="note">
                    <p className="ev-pop-title">{f.label}</p>
                    <p>{f.detail}</p>
                    <p className="ev-sources">{f.sources.map(s => <Source key={s} path={s} />)}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>

        <div className={`ev-failures${showFailures ? ' is-open' : ''}`}>
          <button
            type="button"
            className="ev-failures-btn"
            aria-expanded={showFailures}
            aria-controls="ev-failure-list"
            onClick={() => setShowFailures(v => !v)}
          >
            <span className="ev-failures-num figure">{RETAINED_FAILURES.length}</span>
            <span className="ev-failures-label">
              Failures kept on record
              <span className="ev-failures-hint">{showFailures ? 'Hide' : 'Show all'} <ChevronDown size={16} strokeWidth={2} aria-hidden className="ev-chev" /></span>
            </span>
          </button>
          <AnimatePresence initial={false}>
            {showFailures && (
              <motion.div
                id="ev-failure-list"
                className="ev-failure-wrap"
                initial={reduce ? false : { height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={reduce ? undefined : { height: 0, opacity: 0 }}
                transition={{ duration: reduce ? 0 : 0.34, ease: EASE }}
              >
                <ol className="ev-failure-list">
                  {RETAINED_FAILURES.map((f, i) => (
                    <li key={f.what}>
                      <span className="ev-failure-idx figure" aria-hidden="true">{i + 1}</span>
                      <div>
                        <p className="ev-failure-what">{f.what}</p>
                        <p className="ev-failure-kept">{f.kept}</p>
                        <Source path={f.source} />
                      </div>
                    </li>
                  ))}
                </ol>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  )
}
