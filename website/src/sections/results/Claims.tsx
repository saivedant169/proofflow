import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Plus } from 'lucide-react'
import { Source } from '../../components/ui'
import { notClaimed } from './data'
import { EASE } from './parts'

/** "What we don't claim": five chips; hover previews, click or Enter pins the explanation. */
export default function Claims() {
  const [pinned, setPinned] = useState<number | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const reduce = !!useReducedMotion()
  const active = hover ?? pinned
  const item = active !== null ? notClaimed[active] : null

  return (
    <div className="rs-claims" onMouseLeave={() => setHover(null)}>
      <div className="rs-claims-row">
        <h3 className="rs-claims-title" id="rs-claims-title">What we don’t claim</h3>
        <ul className="rs-chips" aria-labelledby="rs-claims-title">
          {notClaimed.map((c, i) => {
            const on = active === i
            return (
              <li key={c.chip}>
                <button
                  type="button"
                  className={`rs-chip${on ? ' is-on' : ''}`}
                  aria-expanded={pinned === i}
                  aria-controls="rs-claim-detail"
                  onMouseEnter={() => setHover(i)}
                  onFocus={() => setHover(i)}
                  onBlur={() => setHover(null)}
                  onClick={() => setPinned(pinned === i ? null : i)}
                >
                  <span>{c.chip}</span>
                  <Plus className="rs-chip-icon" size={14} strokeWidth={2.25} aria-hidden />
                </button>
              </li>
            )
          })}
        </ul>
      </div>
      <div id="rs-claim-detail" className="rs-claim-detail" aria-live="polite">
        <AnimatePresence initial={false} mode="wait">
          {item && (
            <motion.div
              key={item.chip}
              className="rs-claim-body"
              initial={reduce ? false : { opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -4 }}
              transition={{ duration: reduce ? 0 : 0.18, ease: EASE }}
            >
              <p>{item.text}</p>
              <span className="rs-claim-sources">{item.sources.map(s => <Source key={s} path={s} />)}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
