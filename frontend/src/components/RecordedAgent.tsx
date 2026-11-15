import { ArrowUpRight, CheckCircle2, ChevronDown } from 'lucide-react'
import composition from '../../../evidence/agent_composition.json'
import { formatValue, toolLabels } from '../lib/format'

export default function RecordedAgent() {
  const date = new Date(composition.recorded_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  return <details className="recorded-agent panel"><summary><span><strong>Recorded agent workflow</strong><small>{composition.calls} local Fable 5.2 calls · high reasoning · {date}</small></span><ChevronDown size={17} /></summary><div className="recorded-content">
    <p className="recorded-disclosure">Recorded local model run, not a live hosted model. The model chose these tool plans; the registered tools computed every numeric value.</p>
    <ol className="agent-runs">{composition.runs.map((run, index) => <li key={run.raw_plan}>
      <div className="agent-run-heading"><span>Request {index + 1}</span><strong>{run.executed_tool_count} {run.executed_tool_count === 1 ? 'tool executed' : 'tools executed'}{index === 1 && ` · ${composition.refresh.cross_run_artifacts_reused} prior artifacts reused`}</strong></div>
      <blockquote>“{run.task}”</blockquote>
      <div className="agent-tool-list">{run.steps.map((step, i) => <span key={step.step_id}>{i > 0 && <span className="tool-separator">/</span>}{toolLabels[step.tool] ?? step.tool}</span>)}</div>
      <dl className="agent-values">{run.report.sections.map(section => <div key={section.key}><dt>{section.label}</dt><dd>{formatValue(section.value, section.unit)}</dd></div>)}</dl>
    </li>)}</ol>
    <div className="agent-refresh-proof"><CheckCircle2 size={20} /><div><strong>{composition.checks_passed} / {composition.checks_total} execution checks passed</strong><p>{composition.refresh.source_change} triggered {composition.refresh.executed_tool_count} tool executions across both reports. Support was preserved, old shared handles were rebound, and the refreshed values matched fresh recomputation.</p></div></div>
    <div className="recorded-footer"><span>Two authored requests. This demonstrates composition and reuse; it is separate from the retrieval comparison above.</span><a className="text-link" href="https://github.com/saivedant169/proofflow/blob/main/evidence/agent_composition.json" target="_blank" rel="noreferrer">Inspect the recorded run<ArrowUpRight size={14} /></a></div>
  </div></details>
}
