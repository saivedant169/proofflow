import type { CSSProperties } from 'react'
import { SectionHead, Source, usd } from '../../components/ui'
import { guidedSample as g, headline } from '../../content/facts'
import './styles.css'

const retail = headline.retail
const RETAIL_SOURCE = 'docs/RETAIL_V2_RESULTS.md'

const pct = (part: number, whole: number) => `${((part / whole) * 100).toFixed(2)}%`
const fmt = (n: number) => n.toLocaleString('en-US')
const barWidth = (w: string) => ({ '--w': w }) as CSSProperties

/** Evidence tokens across the ten held-out cases; both arms refresh 38/38 (docs/RETAIL_V2_RESULTS.md). */
const tokenRows = [
  { label: 'Full context', value: fmt(retail.fullTokens), width: '100%', lead: false },
  { label: 'Dependency path', value: fmt(retail.graphTokens), width: pct(retail.graphTokens, retail.fullTokens), lead: true },
]

/** Fresh affected reports at the same per-case evidence allowance (docs/RETAIL_V2_RESULTS.md). */
const searchRows = [
  { label: 'Dependency path', n: 38, lead: true },
  { label: 'BM25 keyword search', n: 19, lead: false },
  { label: 'Dense BGE vectors', n: 8, lead: false },
].map(r => ({ label: r.label, value: `${r.n}/${retail.of}`, width: pct(r.n, retail.of), lead: r.lead }))

function Bars({ rows }: { rows: { label: string; value: string; width: string; lead: boolean }[] }) {
  return (
    <dl className="bars">
      {rows.map(r => (
        <div key={r.label} className={`bar-row${r.lead ? ' is-lead' : ''}`}>
          <dt>{r.label}</dt>
          <dd className="bar-track"><span className="bar" style={barWidth(r.width)} /></dd>
          <dd className="bar-num figure">{r.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function Problem() {
  return (
    <section id="problem" className="section problem-section" aria-labelledby="problem-title">
      <div className="wrap">
        <SectionHead id="problem-title" title="A saved number can be relevant and still wrong." />

        <ol className="problem-story">
          <li className="beat">
            <h3 className="beat-title">An input changes after the report is saved.</h3>
            <p className="beat-text">A rate gets corrected, a refund arrives, a tool is updated.</p>
            <div className="beat-visual p-chips" aria-hidden>
              <span className="p-chip p-chip-changed">
                EUR→USD <del className="figure">{g.fxBefore}</del> <ins className="figure">{g.fxAfter}</ins>
              </span>
              <span className="p-chip">Refund</span>
              <span className="p-chip">Tool version</span>
            </div>
            <p className="beat-cite"><Source path="docs/SUBMISSION_DRAFT.md" /></p>
          </li>

          <li className="beat">
            <h3 className="beat-title">The old report keeps serving the old figure.</h3>
            <p className="beat-text">Nothing marks it, and the next report may reuse it.</p>
            <div className="beat-visual">
              <p className="p-report-kicker">Without lineage</p>
              <div className="p-report">
                <span className="p-report-label">Company revenue</span>
                <span className="p-report-value figure">{usd(g.companyBeforeCents)}</span>
              </div>
              <p className="p-report-note">
                Still served after the rate became <span className="figure">{g.fxAfter}</span>. With{' '}
                <span className="figure">{g.fxAfter}</span> it is <span className="figure">{usd(g.companyAfterCents)}</span>.
              </p>
              <Source path="README.md" />
            </div>
          </li>

          <li className="beat beat-fixes">
            <h3 className="beat-title">The usual fixes both hurt.</h3>
            <p className="beat-text">Re-reading everything costs context. Searching for similar text misses dependencies.</p>
            <div className="beat-visual fix-paths">
              <figure className="fix">
                <figcaption className="fix-title">
                  Re-read everything
                  <span className="fix-sub">Evidence tokens to refresh the same 38 reports</span>
                </figcaption>
                <Bars rows={tokenRows} />
              </figure>
              <figure className="fix">
                <figcaption className="fix-title">
                  Search for similar text
                  <span className="fix-sub">Affected reports refreshed at the same evidence allowance</span>
                </figcaption>
                <Bars rows={searchRows} />
              </figure>
              <p className="fix-source">
                Retail benchmark, ten held-out cases. <Source path={RETAIL_SOURCE} />
              </p>
            </div>
          </li>
        </ol>

        <p className="problem-pivot">ProofFlow records what every number was made from, so it can tell.</p>
      </div>
    </section>
  )
}
