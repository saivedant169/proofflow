import { SectionHead, Source } from '../../components/ui'
import { ChainStory } from './ChainStory'
import './styles.css'

export default function HowItWorks() {
  return (
    <section id="how" className="section how-section" aria-labelledby="how-title">
      <div className="wrap how-head">
        <SectionHead
          id="how-title"
          title="Every number keeps its receipts."
          lede="ProofFlow records what each step consumed and produced in HydraDB, so an agent pulls exactly the context a change touched."
        />
      </div>

      <ChainStory />

      <div className="wrap how-sources">
        <Source path="README.md" label="README.md (guided sample, simplified)" />
        <Source path="proofflow/runtime.py" label="proofflow/runtime.py (edges, currentness)" />
        <Source path="proofflow/demo.py" />
      </div>
    </section>
  )
}
