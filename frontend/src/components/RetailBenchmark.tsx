import { ArrowUpRight, ChevronDown, CircleAlert, Info } from 'lucide-react'
import retail from '../../../evidence/retail_v2_summary.json'

type ConditionRow = (typeof retail.production)[number]

const percent = (ratio: number, places = 1) => `${(ratio * 100).toFixed(places)}%`
const count = (value: number) => value.toLocaleString('en-US')

function ConditionTable({ rows, caption }: { rows: readonly ConditionRow[]; caption: string }) {
  return <div className="benchmark-table-scroll"><table className="benchmark-table retail-table">
    <caption className="sr-only">{caption}</caption>
    <thead><tr><th scope="col">Evidence selection</th><th scope="col">Correct end states</th><th scope="col">Fresh affected reports</th><th scope="col">Required blocks</th><th scope="col">Mean evidence tokens</th></tr></thead>
    <tbody>{rows.map(row => <tr key={`${row.arm}-${row.condition}`} className={row.arm === 'graph' ? 'highlight-row' : ''}>
      <th scope="row">{row.label}{row.arm === 'exact_flat' && <span className="table-note">Representation control</span>}</th>
      <td><strong>{row.oracle_correct_cases} / {row.planned_cases}</strong></td>
      <td>{row.fresh_affected_reports} / {row.eligible_affected_reports}</td>
      <td>{row.correctly_blocked_reports} / {row.unavailable_reports}</td>
      <td>{count(Math.round(row.mean_context_tokens))}</td>
    </tr>)}</tbody>
  </table></div>
}

export default function RetailBenchmark() {
  const graph = retail.production.find(row => row.arm === 'graph')!
  const fixedGraph = retail.fixed_2048.find(row => row.arm === 'graph')!
  const fixedTie = retail.fixed_2048.every(row => row.oracle_correct_cases === fixedGraph.oracle_correct_cases)
  const developmentEfficiencyPassed = retail.development.token_ratio <= retail.development.threshold
  return <section className="retail-benchmark" aria-labelledby="retail-title">
    <div className="retail-heading"><div><h2 id="retail-title">Public retail, staged corrections</h2><p>{count(retail.scope.test_transaction_lines)} positive GBP transaction lines from <a href={retail.scope.source_url} target="_blank" rel="noreferrer">{retail.scope.source}</a>, across {retail.scope.test_partitions} held-out partitions.<br />Corrections and report recipes are authored experiments, not customer incidents. Deterministic execution; no model calls.</p></div><a className="text-link" href="https://github.com/saivedant169/proofflow/blob/main/docs/RETAIL_V2_RESULTS.md" target="_blank" rel="noreferrer">Retail v2 report<ArrowUpRight size={14} /></a></div>

    <div className="retail-primary panel"><div className="retail-primary-heading"><h3>Production closure · no evidence truncation</h3><span>{retail.primary.passed ? 'Held-out gates passed' : 'Held-out gates not met'}</span></div>
      <div className="retail-measures"><div><strong>{retail.primary.correctness_cases}<small> / {retail.primary.planned_cases}</small></strong><span>correct end states</span></div><div><strong>{percent(retail.primary.token_ratio)}</strong><span>of full-context evidence tokens</span></div><div><strong>{retail.primary.fresh_affected_reports}<small> / {retail.primary.eligible_affected_reports}</small></strong><span>available affected reports refreshed</span></div></div>
      <p className="retail-endstate-note"><Info size={16} /><span>Correct end states include the expected missing-input refusal and a no-op; they are not a count of newly completed answers. Unavailable reports are counted separately: <strong>{retail.primary.blocked_unavailable_reports} / {retail.primary.unavailable_reports} correctly blocked.</strong></span></p>
      <div className="retail-token-detail"><span>{count(retail.primary.graph_tokens)} graph evidence tokens / {count(retail.primary.full_context_tokens)} full-context tokens in total.</span><span>Excluding the no-op: {percent(retail.nonempty_impact.token_ratio, 2)} across {retail.nonempty_impact.cases} nonempty-impact cases.</span></div>
    </div>

    <details className="retail-condition panel"><summary><span><strong>Unlimited production controls</strong><small>Complete graph closure, exact dependency traversal and every record</small></span><ChevronDown size={17} /></summary><ConditionTable rows={retail.production} caption="Retail v2 unlimited production controls" /><p className="benchmark-callout"><Info size={16} /><span>Exact dependency traversal and full context both match ProofFlow's correct end states. This does not establish database-engine exclusivity.</span></p></details>

    <details className="retail-condition panel" open><summary><span><strong>Comparators at each case's graph budget</strong><small>Same information; the complete graph context sets a separate cap for each case</small></span><ChevronDown size={17} /></summary><p className="retail-condition-note">Caps range from {count(graph.min_context_tokens)} to {count(graph.max_context_tokens)} tokens, including the no-op. The first two rows retain their complete closure; BM25, dense and iterative retrieval receive that case's graph token allowance.</p><ConditionTable rows={retail.graph_matched} caption="Retail v2 per-case graph-matched evidence budget comparison" /><p className="benchmark-callout"><Info size={16} /><span>{retail.scope.shared_executor} Exact dependency traversal ties ProofFlow; standalone baseline safety is not evaluated.</span></p></details>

    <details className="retail-condition panel"><summary><span><strong>Fixed 2,048-token diagnostic</strong><small>{fixedTie ? `Every listed arm reaches ${fixedGraph.oracle_correct_cases} / ${fixedGraph.planned_cases} correct end states` : `ProofFlow reaches ${fixedGraph.oracle_correct_cases} / ${fixedGraph.planned_cases} correct end states`} · separate from the comparison above</small></span><ChevronDown size={17} /></summary><p className="retail-condition-note">The correct cases here are the expected refusal and no-op. Finite evidence leaves other cases incomplete, even when some affected reports are refreshed. Higher recall at this budget is not full-case completion.</p><ConditionTable rows={retail.fixed_2048} caption="Retail v2 fixed 2048-token diagnostic, all measured controls" /></details>

    <div className={`retail-development ${developmentEfficiencyPassed ? 'development-passed' : ''}`}><CircleAlert size={18} /><div><strong>{developmentEfficiencyPassed ? 'Development efficiency target met.' : 'Development efficiency gate failed.'}</strong><p>Development used {percent(retail.development.token_ratio, 2)} of full-context tokens against the unchanged {percent(retail.development.threshold, 0)} target. Correct end states: {retail.development.correctness_cases} / {retail.development.planned_cases}. Development is not pooled with the held-out results.</p></div></div>

    <details className="retail-method methodology panel"><summary>Retail source, method and limitations<ArrowUpRight size={17} /></summary><div><p>{retail.scope.text} The source is a bounded positive-sales subset, not a complete merchant ledger. Customer identifiers and product descriptions are omitted from the committed transformation. Staged FX and refunds are assumptions, not historical observations.</p><p>{retail.scope.shared_executor} Evidence selection and execution safety are separate; standalone baseline safety is not evaluated.</p><ul>{retail.limitations.map(limitation => <li key={limitation}>{limitation}</li>)}</ul><p><a className="text-link" href={retail.scope.source_url} target="_blank" rel="noreferrer">Source: {retail.scope.source}<ArrowUpRight size={13} /></a> · {retail.scope.license}</p><p className="mono">Frozen revision: {retail.provenance.code_revision.slice(0, 12)}</p><a className="text-link" href="https://github.com/saivedant169/proofflow/blob/main/evidence/retail_v2_summary.json" target="_blank" rel="noreferrer">Inspect the validated summary<ArrowUpRight size={14} /></a></div></details>
  </section>
}
