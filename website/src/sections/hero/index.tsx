import { useRef } from 'react'
import { useReducedMotion } from 'motion/react'
import { Play } from 'lucide-react'
import { ButtonLink } from '../../components/ui'
import { links } from '../../content/facts'
import MetricsStrip from './MetricsStrip'
import Plot from './Plot'
import { FIELD, fieldPath } from './field'
import { useStageMotion } from './useStageMotion'
import './styles.css'

const FIELD_LINES = Array.from({ length: FIELD.lines }, (_, i) => i)

export default function Hero() {
  const reduce = useReducedMotion() ?? false
  const stageRef = useRef<HTMLDivElement>(null)
  const fieldRef = useRef<SVGSVGElement>(null)
  useStageMotion(stageRef, fieldRef, !reduce)

  return (
    <section id="top" className="hero-section" aria-labelledby="top-title">
      <div className="hero-stage stage" ref={stageRef}>
        <svg className="hero-field" ref={fieldRef} viewBox={`0 0 ${FIELD.w} ${FIELD.h}`} preserveAspectRatio="xMidYMid slice"
          aria-hidden focusable="false">
          {FIELD_LINES.map(i => <path key={i} data-i={i} d={fieldPath(i)} style={{ opacity: 0.4 + 0.6 * (((i * 7) % 5) / 4) }} />)}
        </svg>

        <div className="wrap hero-grid">
          <div className="hero-copy">
            <p className="hero-kicker"><span aria-hidden className="hero-kicker-dot" /><span><strong>HydraDB Hackathon · Track 2</strong> — context layer for agents</span></p>
            <h1 id="top-title" className="hero-title">Full‑context accuracy at vector‑search cost.</h1>
            <p className="hero-lede">
              ProofFlow traverses the dependency path in HydraDB, so agents refresh exactly what a changed input affected, nothing more.
            </p>
            <div className="hero-ctas">
              <ButtonLink href={links.liveApp} external>Open live app</ButtonLink>
              <ButtonLink href={links.walkthrough} external variant="secondary"
                icon={<Play size={16} strokeWidth={2.2} aria-hidden />}>
                Watch the film
              </ButtonLink>
            </div>
          </div>

          <div className="hero-visual">
            <Plot />
          </div>
        </div>
      </div>

      <MetricsStrip />
    </section>
  )
}
