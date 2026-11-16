import { useState, type ReactNode } from 'react'
import { Check, Copy } from 'lucide-react'
import { Button } from '../../components/ui'

/**
 * Uses only ProofFlowRuntime.set_source, execute, currentness, affected and refresh, with the
 * signatures in proofflow/runtime.py and the support_by_region input shape in proofflow/analytics.py.
 */
export const RUNTIME_SNIPPET = `from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime

store = ArtifactStore(".state/example")
rt = ProofFlowRuntime(store, HydraGraph(namespace="example"))
t1 = {"ticket_id": "t-1", "region": "EU", "status": "open"}
src = rt.set_source("tickets", [t1])
support = rt.execute("support_by_region", {"tickets": src.current_id})

change = rt.set_source("tickets", [t1, {**t1, "ticket_id": "t-2"}])
rt.currentness(support.id).state   # "stale"
rt.affected([change.previous_id])  # native HydraDB descendants
result = rt.refresh([support.id])  # re-runs one tool on the new version`

const KEYWORDS = new Set(['from', 'import', 'as', 'def', 'return', 'None', 'True', 'False', 'for', 'in', 'if', 'else', 'with', 'class', 'lambda'])
const TOKEN = /(#.*$)|("(?:[^"\\]|\\.)*")|([A-Za-z_][A-Za-z0-9_]*)/g

/** A tiny Python highlighter: keywords, strings and comments. Everything else stays ink. */
function highlight(line: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let key = 0
  for (const m of line.matchAll(TOKEN)) {
    const [text, comment, string, word] = m
    const start = m.index ?? 0
    if (word && !KEYWORDS.has(word)) continue
    if (start > last) out.push(line.slice(last, start))
    const cls = comment ? 'tok-comment' : string ? 'tok-string' : 'tok-keyword'
    out.push(<span key={key++} className={cls}>{text}</span>)
    last = start + text.length
  }
  if (last < line.length) out.push(line.slice(last))
  return out
}

export function CodeSample() {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle')

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(RUNTIME_SNIPPET)
      setStatus('copied')
    } catch {
      setStatus('failed')
    }
    window.setTimeout(() => setStatus('idle'), 2400)
  }

  return (
    <div className="arch-code-block">
      <div className="arch-code-bar">
        <span className="arch-code-lang">Python</span>
        <Button variant="quiet" onClick={copy}
          icon={status === 'copied' ? <Check aria-hidden size={16} /> : <Copy aria-hidden size={16} />}>
          {status === 'copied' ? 'Copied' : 'Copy code'}
        </Button>
      </div>
      <pre className="arch-pre scroll-thin" tabIndex={0} aria-label="Runtime API example in Python">
        <code>
          {RUNTIME_SNIPPET.split('\n').map((line, i) => (
            <span className="arch-line" key={i}>{highlight(line)}{'\n'}</span>
          ))}
        </code>
      </pre>
      <p className="sr-only" aria-live="polite">
        {status === 'copied' ? 'Code copied to the clipboard.' : status === 'failed' ? 'Copy failed. Select the code to copy it.' : ''}
      </p>
      {status === 'failed' && <p className="arch-copy-failed">Copy is blocked here. Select the code to copy it.</p>}
    </div>
  )
}
