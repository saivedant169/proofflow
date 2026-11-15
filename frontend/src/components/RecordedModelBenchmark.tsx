import { ArrowUpRight, ChevronDown, Info } from 'lucide-react'
import study from '../../../evidence/model_comparison_v4_summary.json'

const evidenceCommit = 'https://github.com/saivedant169/proofflow/blob/f0b51c0925e092c6ab3566c96ebb14abd59e7af4'
const runPath = 'results/model-v4-test-run-1'
const armNames: Record<string, string> = {
  graph: 'Graph · ProofFlow',
  exact_flat: 'Exact-flat traversal',
  bm25: 'BM25',
  dense: 'Dense · BGE',
  iterative_hybrid: 'Iterative hybrid',
  full_context: 'Full context',
}
const caseNames: Record<string, string> = {
  M01: 'Local refund',
  M02: 'Local exchange rate',
  M03: 'Joint source change',
  M04: 'Changes on multiple dates',
  M05: 'Tool version change',
  M06: 'Equal-value revalidation',
  M07: 'Missing source',
  M08: 'Canonical no-op',
}

const count = new Intl.NumberFormat('en-US')
const input = study.provider_input_excluding_no_op
const inputReduction = ((1 - input.graph / input.full_context) * 100).toFixed(2)

export default function RecordedModelBenchmark() {
  return <section aria-labelledby="model-comparison-title">
    <div className="retail-heading">
      <div>
        <h2 id="model-comparison-title">Recorded model comparison</h2>
        <p>{study.model} / {study.effort} effort · {study.cli_calls} CLI calls · {study.cli_turns} CLI turns. No live rerun.<br />
          {study.cases.length} authored cases over {count.format(study.test_rows)} real March 2011 positive-sales rows from UCI Online Retail.
        </p>
      </div>
      <a className="text-link" href={`${evidenceCommit}/docs/MODEL_COMPARISON_RESULTS.md`} target="_blank" rel="noreferrer">Audited results<ArrowUpRight size={14} /></a>
    </div>

    <div className="panel model-comparison">
      <div className="model-input-summary">
        <div><strong>{inputReduction}%</strong><span>fewer provider input tokens<br />for graph vs. full context</span></div>
        <p><b>{count.format(input.graph)}</b> graph / <b>{count.format(input.full_context)}</b> full context, excluding the no-op.<br />
          Includes uncached input, cache writes and cache reads.</p>
      </div>
      <table className="benchmark-table model-comparison-table">
        <caption className="sr-only">Recorded model outcomes by evidence selection method</caption>
        <thead><tr><th scope="col">Evidence selection</th><th scope="col">Fresh affected reports</th><th scope="col">Recoverable cases completed</th></tr></thead>
        <tbody>{study.arms.map(arm => <tr key={arm.id} className={arm.id === 'graph' ? 'highlight-row' : undefined}>
          <th scope="row">{armNames[arm.id]}</th>
          <td>{arm.fresh_affected} / {study.eligible_affected_reports}</td>
          <td>{arm.correction_cases_completed} / {study.recoverable_cases}</td>
        </tr>)}</tbody>
      </table>
      <p className="benchmark-callout"><Info size={16} /><span><strong>{study.unavailable_reports} / {study.unavailable_reports} unavailable reports blocked by every arm.</strong> Six cases required correction; the missing-source and no-op cases earned no fresh-report credit. Freshness includes lineage revalidation when numbers are unchanged.</span></p>
      <p className="benchmark-callout"><Info size={16} /><span>Graph and exact-flat tied on refresh outcomes and used identical prompts in {study.matching_graph_exact_flat_prompts} / {study.cases.length} cases. Every arm used the same Hydra-assisted executor to check currentness and refresh reports. The five capped arms shared adaptive caps of {count.format(study.evidence_caps.min)}–{count.format(study.evidence_caps.max)} evidence tokens, set by each case’s full graph closure. Full context was uncapped.</span></p>
    </div>

    <details className="retail-condition panel">
      <summary><span><strong>All cases, misses and method</strong><small>See the outcomes for every case and arm</small></span><ChevronDown size={17} /></summary>
      <div className="benchmark-table-scroll" role="region" aria-label="Per-case results table" tabIndex={0}>
        <table className="benchmark-table retail-table">
          <caption className="sr-only">Fresh affected reports by case and evidence selection method</caption>
          <thead><tr><th scope="col">Case</th>{study.arms.map(arm => <th scope="col" key={arm.id}>{armNames[arm.id]}</th>)}</tr></thead>
          <tbody>{study.cases.map(row => <tr key={row.id}>
            <th scope="row">{row.id} · {caseNames[row.id]}</th>
            {row.eligible > 0
              ? row.fresh_by_arm.map((fresh, index) => <td key={study.arms[index].id}>{fresh} / {row.eligible}</td>)
              : <td colSpan={study.arms.length}>{row.unavailable > 0 ? `All arms blocked ${row.unavailable} unavailable reports` : 'No affected reports to refresh'}</td>}
          </tr>)}</tbody>
        </table>
      </div>
      <p className="benchmark-callout"><Info size={16} /><span>A completed correction case required every recoverable affected report to be fresh. Each case and arm had one recorded sample. CLI turns do not count backend requests. Input tokens alone don’t establish a cost, speed or database engine advantage.</span></p>
      <div className="model-evidence-links">
        <a className="text-link" href={`${evidenceCommit}/${runPath}/publication/audit.json`} target="_blank" rel="noreferrer">Independent audit<ArrowUpRight size={14} /></a>
        <a className="text-link" href={`${evidenceCommit}/${runPath}/publication/provider_metrics.json`} target="_blank" rel="noreferrer">Provider counters<ArrowUpRight size={14} /></a>
        <a className="text-link" href={`${evidenceCommit}/${runPath}/publication/publication_manifest.json`} target="_blank" rel="noreferrer">Complete evidence inventory<ArrowUpRight size={14} /></a>
        <span className="mono">Frozen revision: {study.provenance.frozen_revision.slice(0, 12)}</span>
      </div>
    </details>
  </section>
}
