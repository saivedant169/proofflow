import { useId, useLayoutEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import './Tip.css'

/**
 * A small, crisp tooltip on a real button: opens on hover, focus or tap, closes on Escape,
 * blur or leave. The tip text is always the button's accessible description.
 */
export function Tip({ tip, children, place = 'top', align = 'center', className = '', ...rest }:
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
    tip: ReactNode; children: ReactNode; place?: 'top' | 'bottom'; align?: 'start' | 'center' | 'end'
  }) {
  const [open, setOpen] = useState(false)
  const id = `tip-${useId().replace(/:/g, '')}`
  const tipRef = useRef<HTMLSpanElement>(null)
  // Keep the open tip inside the viewport: nudge it sideways if it would cross an edge.
  useLayoutEffect(() => {
    const tip = tipRef.current
    if (!tip || !open) return
    tip.style.translate = '0px 0px'
    const r = tip.getBoundingClientRect()
    const vw = document.documentElement.clientWidth
    const shift = r.left < 12 ? 12 - r.left : r.right > vw - 12 ? vw - 12 - r.right : 0
    tip.style.translate = `${shift}px 0px`
  }, [open])
  return (
    <span className="tip-wrap" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className={className} aria-describedby={id} {...rest}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onClick={() => setOpen(true)}
        onKeyDown={e => { if (e.key === 'Escape') setOpen(false) }}>
        {children}
      </button>
      <span role="tooltip" id={id} ref={tipRef} className="tip" data-open={open || undefined} data-place={place} data-align={align}>
        {tip}
      </span>
    </span>
  )
}
