import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

/**
 * A "receipt" disclosure: the trigger shows a number; hover, focus or click unfolds the exact figure and its
 * source underneath. Escape or an outside click dismisses it (WCAG 1.4.13). Styles live in hero/styles.css.
 */
export default function Tip({ trigger, children, className = '' }: { trigger: ReactNode; children: ReactNode; className?: string }) {
  const id = useId()
  const ref = useRef<HTMLSpanElement>(null)
  // auto: follows hover/focus; open: pinned by click; closed: dismissed until the pointer leaves.
  const [mode, setMode] = useState<'auto' | 'open' | 'closed'>('auto')

  useEffect(() => {
    if (mode === 'auto') return
    const onDown = (e: PointerEvent) => { if (!ref.current?.contains(e.target as Node)) setMode('auto') }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [mode])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && ref.current?.matches(':hover, :focus-within')) setMode('closed')
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <span ref={ref} className={`tip ${className}`} data-mode={mode}
      onPointerLeave={() => mode === 'closed' && setMode('auto')}
      onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setMode('auto') }}>
      <button type="button" className="tip-trigger" aria-expanded={mode === 'open'} aria-controls={id}
        onClick={() => setMode(m => (m === 'open' ? 'closed' : 'open'))}>
        {trigger}
      </button>
      <span id={id} className="tip-panel" role="note">{children}</span>
    </span>
  )
}
