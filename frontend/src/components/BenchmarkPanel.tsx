import { useState } from 'react'
import { ArrowUpRight, FileJson, Info } from 'lucide-react'
import summary from '../../../evidence/benchmark_summary.json'
import RecordedAgent from './RecordedAgent'

type Budget = '512' | '1024' | '2048' | 'all'
const names: Record<string, string> = { graph: 'ProofFlow · HydraDB', bm25: 'BM25', dense: 'Dense · BGE', hybrid: 'Hybrid', iterative_hybrid: 'Iterative hybrid', exact_flat: 'Exact dependency cache' }
const arms = ['graph', 'bm25', 'dense', 'hybrid', 'iterative_hybrid', 'exact_flat'] as const

export default function BenchmarkPanel() {
  const [budget, setBudget] = useState<Budget>('2048')
  const data = summary.retrieval
  return <main className="benchmark-page">
    <div className="benchmark-intro"><h1>Evidence earns its place.</h1><p>Twelve frozen scenarios. The same records. A real dense baseline.<br />A useful advantage, with the limits in view.</p></div>
    <section className="benchmark-section panel"><div className="benchmark-controls"><div><h2>Affected evidence recovered</h2><p>Mean recall across 12 authored held-out scenarios</p></div><label>Evidence budget<select value={budget} onChange={event => setBudget(event.target.value as Budget)}><option value="512">512 tokens</option><option value="1024">1,024 tokens</option><option value="2048">2,048 tokens · primary</option><option value="all">Unlimited · diagnostic</option></select></label></div>
      <div className="benchmark-table-scroll"><table className="benchmark-table"><thead><tr><th>Evidence selection</th><th>Recall</th><th>Complete affected set</th><th>Mean evidence tokens</th></tr></thead><tbody>{arms.map(arm => {
        const row = data[arm][budget]
        return <tr key={arm} className={arm === 'graph' ? 'highlight-row' : ''}><th>{names[arm]}{arm === 'exact_flat' && <span className="table-note">Representation control</span>}</th><td><div className="recall-cell"><strong>{(row.mean_recall * 100).toFixed(1)}%</strong><span className="recall-track"><i style={{ width: `${row.mean_recall * 100}%` }} /></span></div></td><td>{row.exact_affected_sets} / {row.scenarios}</td><td>{Math.round(row.mean_context_tokens).toLocaleString()}</td></tr>
      })}</tbody></table></div>
      <p className="benchmark-callout"><Info size={16} /><span>The exact dependency cache ties ProofFlow. This measures the value of explicit dependencies, not exclusive correctness from a graph database.</span></p>
    </section>
    <section className="benchmark-section execution-results"><div><h2>Did the selected evidence finish the work?</h2><p>Actual tool refresh at the primary 2,048-token budget.<br />Affected reports with available inputs: 29.</p></div><div className="outcome-columns">{(['graph', 'bm25', 'dense', 'iterative_hybrid'] as const).map(arm => <div key={arm}><span>{names[arm]}</span><strong>{summary.execution[arm].fresh_affected_reports}<small> / 29</small></strong><p>fresh affected reports</p></div>)}</div></section>
    <div className="benchmark-limit"><strong>Full context completes 29 / 29.</strong><p>With every record supplied, the shared executor refreshes all eligible reports using about 8,035 evidence tokens on average. Every arm blocks both unavailable reports and serves zero incorrectly current reports. A correct block is not a completed report.</p></div>
    <details className="methodology panel"><summary>Read the method and limitations<ArrowUpRight size={17} /></summary><div><p>{summary.scope}</p><p>{summary.shared_executor}</p><p>BM25 and BAAI/bge-small-en-v1.5 receive identical rendered records, exact-ID seeds and scope. Dense inputs are chunked with the model tokenizer, preserving every field. The deterministic reader follows only paths present in returned evidence. Calculations are checked against independent numeric arithmetic.</p><p>All budgets and test cases were frozen before this run. Missed dependencies at finite budgets remain misses. These authored scenarios do not establish broad superiority across tasks, and this table is separate from any model-planning experiment.</p><p className="mono">Frozen revision: {summary.run_manifest.code.revision.slice(0, 12)}</p><a className="text-link" href="https://github.com/saivedant169/proofflow/blob/main/docs/BENCHMARK_RESULTS.md" target="_blank" rel="noreferrer"><FileJson size={16} />Report and raw evidence in the repository<ArrowUpRight size={14} /></a></div></details>
    <RecordedAgent />
  </main>
}
