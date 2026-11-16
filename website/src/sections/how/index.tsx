import { SectionHead, Source } from '../../components/ui'
import { ChainFigure } from './ChainFigure'
import { StateLegend } from './StateLegend'
import './styles.css'

export default function HowItWorks() {
  return (
    <section id="how" className="section how-section" aria-labelledby="how-title">
      <div className="wrap">
        <SectionHead
          id="how-title"
          title="Every number keeps its receipts"
          lede="ProofFlow records what each calculation consumed and what it produced. When an input changes, it knows exactly which saved numbers depend on it."
        />

        <ChainFigure />

        <div className="how-notes">
          <p className="how-note">
            Simplified from the guided sample. Refresh there runs four tools: the conversion, the company total and
            both report compositions.
          </p>
          <p className="how-source-row">
            <Source path="README.md" label="README.md (guided sample)" />
            <Source path="proofflow/runtime.py" label="proofflow/runtime.py (edges)" />
            <Source path="proofflow/demo.py" />
          </p>
        </div>

        <StateLegend />
      </div>
    </section>
  )
}
