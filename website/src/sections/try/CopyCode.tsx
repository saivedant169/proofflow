import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Check, Copy } from 'lucide-react'

type Status = 'idle' | 'copied' | 'failed'

export type CommandSet = {
  id: string
  label: string
  /** Lines copied to the clipboard. */
  lines: string[]
  /** Shown after the commands as a dimmed shell comment; never copied. */
  note?: string
}

/**
 * Compact terminal with tabs and one-click copy. If the clipboard is unavailable,
 * it selects the commands and says so.
 */
export default function CopyCode({ sets, label }: { sets: CommandSet[]; label: string }) {
  const [current, setCurrent] = useState(sets[0].id)
  const [status, setStatus] = useState<Status>('idle')
  const codeRef = useRef<HTMLElement>(null)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const timer = useRef<number | undefined>(undefined)
  const id = useId()
  const set = sets.find(s => s.id === current) ?? sets[0]
  const text = set.lines.join('\n')

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const select = (next: string) => {
    window.clearTimeout(timer.current)
    setStatus('idle')
    setCurrent(next)
  }

  const onTabKey = (e: KeyboardEvent, i: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const n = (i + (e.key === 'ArrowRight' ? 1 : -1) + sets.length) % sets.length
    select(sets[n].id)
    tabRefs.current[n]?.focus()
  }

  const selectText = () => {
    const node = codeRef.current
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
      timer.current = window.setTimeout(() => setStatus('idle'), 2200)
    } catch {
      selectText()
      setStatus('failed')
    }
  }

  return (
    <div className="try-term stage">
      <div className="try-term-bar">
        <span className="try-term-dots" aria-hidden><i /><i /><i /></span>
        <div className="try-term-tabs" role="tablist" aria-label={label}>
          {sets.map((s, i) => (
            <button key={s.id} ref={n => { tabRefs.current[i] = n }} type="button" role="tab"
              id={`${id}-tab-${s.id}`} aria-selected={s.id === current} aria-controls={`${id}-panel`}
              tabIndex={s.id === current ? 0 : -1} onClick={() => select(s.id)} onKeyDown={e => onTabKey(e, i)}>
              {s.label}
            </button>
          ))}
        </div>
        <button type="button" className={`try-copy${status === 'copied' ? ' is-copied' : ''}`} onClick={copy}
          aria-describedby={`${id}-status`}>
          {status === 'copied'
            ? <Check size={15} strokeWidth={2.4} aria-hidden />
            : <Copy size={15} strokeWidth={2} aria-hidden />}
          <span>{status === 'copied' ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="scroll-thin" id={`${id}-panel`} role="tabpanel" tabIndex={0}
        aria-labelledby={`${id}-tab-${set.id}`}>
        <code ref={codeRef}>
          {set.lines.map(line => (
            <span key={line} className="try-term-line"><span className="try-term-prompt" aria-hidden>$ </span>{line}{'\n'}</span>
          ))}
        </code>
        {set.note && <span className="try-term-note">{'# '}{set.note}</span>}
      </pre>
      <p className={`try-copy-status${status === 'failed' ? ' is-failed' : ''}`} id={`${id}-status`} aria-live="polite">
        {status === 'copied' && <span className="sr-only">Commands copied to your clipboard.</span>}
        {status === 'failed' && 'Clipboard blocked. The commands are selected; press Ctrl+C or ⌘C.'}
      </p>
    </div>
  )
}
