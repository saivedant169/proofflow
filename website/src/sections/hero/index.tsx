import { Play } from 'lucide-react'
import { ButtonLink, Source } from '../../components/ui'
import { headline, links } from '../../content/facts'
import LiveMiniature from './LiveMiniature'
import './styles.css'

export default function Hero() {
  const study = headline.modelStudy
  return (
    <section id="top" className="section hero-section" aria-labelledby="top-title">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <h1 id="top-title" className="hero-title">Saved reports that know when they’re out of date.</h1>
          <p className="hero-promise">
            ProofFlow records the inputs behind each number an agent saves, so when one changes it withholds the
            outdated figures and refreshes only the affected work.
          </p>

          <div className="hero-ctas">
            <ButtonLink href={links.liveApp} external>Open live app</ButtonLink>
            <ButtonLink href={links.walkthrough} external variant="secondary"
              icon={<Play size={16} strokeWidth={2.2} aria-hidden />}>
              Watch the 2-minute walkthrough
            </ButtonLink>
            <ButtonLink href={links.repo} external variant="quiet">Repository (judge access)</ButtonLink>
          </div>

          <p className="hero-proof">
            <span className="figure hero-proof-num">{study.refreshed}</span> affected reports refreshed in a frozen{' '}
            {study.invocations}-invocation model study (eight cases, one sample each).{' '}
            <Source path={study.source} />
          </p>
        </div>

        <LiveMiniature />
      </div>
    </section>
  )
}
