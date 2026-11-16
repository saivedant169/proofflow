import { useState, useSyncExternalStore } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { Source } from '../../components/ui'
import { PIPELINE, type PipelineStep } from './data'

const WIDE = '(min-width: 900px)'

const subscribeWide = (cb: () => void) => {
  const mq = window.matchMedia(WIDE)
  mq.addEventListener('change', cb)
  return () => mq.removeEventListener('change', cb)
}
const getWide = () => window.matchMedia(WIDE).matches
const getWideServer = () => true

function useWide() {
  return useSyncExternalStore(subscribeWide, getWide, getWideServer)
}

function StepDetail({ step }: { step: PipelineStep }) {
  return (
    <div className="eval-detail-body">
      {step.files && (
        <ul className="eval-files" aria-label="Frozen files">
          {step.files.map(f => (
            <li key={f.path}>
              <code>{f.path}</code>
              <span>{f.note}</span>
            </li>
          ))}
        </ul>
      )}
      {step.code && (
        <pre className="eval-code scroll-thin" tabIndex={0} aria-label={`Commands for: ${step.title}`}>
          <code>
            {step.code.map((line, i) => (
              <span key={i} className={line.startsWith('#') ? 'is-comment' : undefined}>
                {line || ' '}
                {'\n'}
              </span>
            ))}
          </code>
        </pre>
      )}
      <p className="eval-detail-text">{step.detail}</p>
      <p className="eval-sources">
        {step.sources.map(s => <Source key={s} path={s} />)}
      </p>
    </div>
  )
}

export default function Pipeline() {
  const wide = useWide()
  const [open, setOpen] = useState<number | null>(0)
  // On wide screens one step is always shown in the shared panel.
  const active = wide ? (open ?? 0) : open
  const reached = active ?? -1

  const toggle = (i: number) => {
    if (wide) setOpen(i)
    else setOpen(prev => (prev === i ? null : i))
  }

  const current = active !== null ? PIPELINE[active] : null

  return (
    <div className="eval-pipeline">
      <ol className="eval-steps" aria-label="Evaluation pipeline, in order">
        {PIPELINE.map((step, i) => {
          const isOpen = active === i
          const panelId = wide ? 'eval-detail-shared' : `eval-detail-${step.id}`
          return (
            <li
              key={step.id}
              className={`eval-step${isOpen ? ' is-open' : ''}${i <= reached ? ' is-reached' : ''}${i < reached ? ' is-passed' : ''}`}
            >
              <span className="eval-node" aria-hidden />
              {i < PIPELINE.length - 1 && <span className="eval-seg" aria-hidden><span /></span>}
              <h3 className="eval-step-title">
                <button type="button" aria-expanded={isOpen} aria-controls={panelId} onClick={() => toggle(i)}>
                  <span className="eval-step-num figure">{i + 1}</span>
                  <span className="eval-step-name">{step.title}</span>
                  <ChevronDown className="eval-chev" size={18} strokeWidth={2} aria-hidden />
                </button>
              </h3>
              <p className="eval-step-summary">{step.summary}</p>
              {!wide && (
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      id={panelId}
                      className="eval-detail eval-detail-inline"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                    >
                      <StepDetail step={step} />
                    </motion.div>
                  )}
                </AnimatePresence>
              )}
            </li>
          )
        })}
      </ol>

      {wide && current && (
        <div id="eval-detail-shared" className="eval-detail eval-detail-shared panel" role="region"
          aria-label={`Step ${(active ?? 0) + 1}: ${current.title}`}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={current.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.16 }}
            >
              <h4 className="eval-detail-title">
                <span className="figure">{(active ?? 0) + 1}</span> {current.title}
              </h4>
              <StepDetail step={current} />
            </motion.div>
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
