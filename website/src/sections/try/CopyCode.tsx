import { useEffect, useId, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'

type Status = 'idle' | 'copied' | 'failed'

/** Command block with a copy button. If the clipboard is unavailable, selects the text and says so. */
export default function CopyCode({ label, lines }: { label: string; lines: string[] }) {
  const [status, setStatus] = useState<Status>('idle')
  const preRef = useRef<HTMLPreElement>(null)
  const timer = useRef<number | undefined>(undefined)
  const id = useId()
  const text = lines.join('\n')

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const selectText = () => {
    const node = preRef.current
    const sel = window.getSelection()
    if (!node || !sel) return
    const range = document.createRange()
    range.selectNodeContents(node)
    sel.removeAllRanges()
    sel.addRange(range)
  }

  const copy = async () => {
    window.clearTimeout(timer.current)
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(text)
      setStatus('copied')
      timer.current = window.setTimeout(() => setStatus('idle'), 2400)
    } catch {
      selectText()
      setStatus('failed')
    }
  }

  return (
    <div className="try-code">
      <div className="try-code-bar">
        <span className="try-code-label" id={`${id}-label`}>{label}</span>
        <button type="button" className="try-copy" onClick={copy} aria-describedby={`${id}-status`}>
          {status === 'copied'
            ? <Check size={15} strokeWidth={2.2} aria-hidden />
            : <Copy size={15} strokeWidth={2} aria-hidden />}
          <span>{status === 'copied' ? 'Copied' : 'Copy commands'}</span>
        </button>
      </div>
      <pre ref={preRef} className="scroll-thin" tabIndex={0} aria-labelledby={`${id}-label`}><code>{text}</code></pre>
      <p className={`try-copy-status${status === 'failed' ? ' is-failed' : ''}`} id={`${id}-status`} aria-live="polite">
        {status === 'copied' && 'Commands copied to your clipboard.'}
        {status === 'failed' && 'Your browser blocked clipboard access. The commands are selected; press Ctrl+C or ⌘C to copy them.'}
      </p>
    </div>
  )
}
