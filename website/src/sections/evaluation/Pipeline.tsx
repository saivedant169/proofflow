import { useRef, useState } from 'react'
import { AnimatePresence, motion, useInView, useReducedMotion } from 'motion/react'
import { ChevronDown, Lock, PackageCheck, Play, RefreshCw, ScanSearch, type LucideIcon } from 'lucide-react'
import { Source } from '../../components/ui'
import { PIPELINE, STEP_TAGS, type PipelineStep } from './data'

const EASE = [0.22, 1, 0.36, 1] as const
const ICONS: Record<string, LucideIcon> = {
  freeze: Lock,
  run: Play,
  audit: ScanSearch,
  verify: PackageCheck,
  ci: RefreshCw,
}

function StepDetail({ step }: { step: PipelineStep }) {
  return (
    <div className="ev-detail-grid">
      <div className="ev-detail-text">
        <p>{step.detail}</p>
        <p className="ev-sources">{step.sources.map(s => <Source key={s} path={s} />)}</p>
      </div>
      {step.code ? (
        <pre className="ev-code scroll-thin" tabIndex={0} aria-label={`Commands for: ${step.title}`}>
          <code>
            {step.code.map((line, i) => (
              <span key={i} className={line.startsWith('#') ? 'is-comment' : undefined}>{line || ' '}{'\n'}</span>
            ))}
          </code>
        </pre>
      ) : step.files ? (
        <ul className="ev-files" aria-label="Frozen files">
          {step.files.map(f => (
            <li key={f.path}><code>{f.path}</code><span>{f.note}</span></li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export default function Pipeline() {
  const [open, setOpen] = useState<number | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.4 })
  const reduce = !!useReducedMotion()
  const show = inView || reduce
  const current = open !== null ? PIPELINE[open] : null

  return (
    <div className="ev-pipe" ref={ref}>
      <ol className="ev-thread" aria-label="Evaluation pipeline, in order">
        <span className="ev-line" aria-hidden="true">
          <motion.span
            className="ev-line-fill"
            initial={false}
            animate={{ scaleX: show ? 1 : 0, scaleY: show ? 1 : 0 }}
            transition={{ duration: reduce ? 0 : 1.6, ease: EASE, delay: reduce ? 0 : 0.2 }}
          />
          {!reduce && show && (
            <motion.span
              className="ev-pulse"
              initial={{ left: '0%', opacity: 0 }}
              animate={{ left: '100%', opacity: [0, 1, 1, 0] }}
              transition={{ duration: 1.8, ease: EASE, delay: 0.2, times: [0, 0.1, 0.85, 1] }}
            />
          )}
        </span>
        {PIPELINE.map((step, i) => {
          const Icon = ICONS[step.id]
          const t = STEP_TAGS[step.id]
          const isOpen = open === i
          return (
            <motion.li
              key={step.id}
              className={`ev-step${isOpen ? ' is-open' : ''}`}
              initial={false}
              animate={{ opacity: show ? 1 : 0, y: show ? 0 : 12 }}
              transition={{ duration: reduce ? 0 : 0.5, ease: EASE, delay: reduce ? 0 : 0.2 + i * 0.28 }}
            >
              <button
                type="button"
                className="ev-step-btn"
                aria-expanded={isOpen}
                aria-controls="ev-step-detail"
                onClick={() => setOpen(isOpen ? null : i)}
              >
                <span className="ev-node" aria-hidden="true"><Icon size={22} strokeWidth={1.75} /></span>
                <span className="ev-step-name">
                  <span className="ev-step-num figure">{i + 1}</span>
                  {t.name}
                  <ChevronDown className="ev-chev" size={16} strokeWidth={2} aria-hidden />
                </span>
                <span className="ev-step-tag figure">{t.tag}</span>
                <span className="ev-step-tag-label">{t.tagLabel}</span>
              </button>
            </motion.li>
          )
        })}
      </ol>

      <div id="ev-step-detail" className="ev-detail-slot" role="region" aria-label={current ? `Step ${(open ?? 0) + 1}: ${current.title}` : 'Step details'}>
        <AnimatePresence initial={false} mode="wait">
          {current && (
            <motion.div
              key={current.id}
              className="ev-detail"
              initial={reduce ? false : { height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={reduce ? undefined : { height: 0, opacity: 0 }}
              transition={{ duration: reduce ? 0 : 0.3, ease: EASE }}
            >
              <div className="ev-detail-inner">
                <p className="ev-detail-title">{current.title}</p>
                <StepDetail step={current} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
