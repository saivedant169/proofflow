import { ShieldCheck } from 'lucide-react'
import { ButtonLink, Source } from '../../components/ui'
import { links } from '../../content/facts'
import Stats from './Stats'
import Compare from './Compare'
import Meter from './Meter'
import Calculator from './Calculator'
import Claims from './Claims'
import { verifier } from './data'
import './styles.css'

export default function Results() {
  return (
    <section id="results" className="section stage results-section" aria-labelledby="results-title">
      <div className="rs-wash" aria-hidden="true" />
      <div className="wrap">
        <header className="rs-head">
          <h2 className="rs-title" id="results-title">How it compares to today’s approaches</h2>
          <p className="rs-lede">Six approaches, one real model: ProofFlow matched full context’s 32/32 at 63% lower list cost.</p>
        </header>

        <Stats />

        <div className="rs-viz">
          <Compare />
          <Meter />
          <Calculator />
        </div>

        <Claims />

        <div className="rs-verify">
          <ButtonLink variant="secondary" href={links.publicEvidence} external icon={<ShieldCheck aria-hidden size={18} strokeWidth={2} />}>
            Verify the evidence yourself
          </ButtonLink>
          <span className="rs-verify-note">One offline Python script</span>
          <Source path={verifier.source} />
        </div>
      </div>
    </section>
  )
}
