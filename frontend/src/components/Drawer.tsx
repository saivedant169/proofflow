import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export default function Drawer({ title, subtitle, onClose, children, wide = false }: { title: string; subtitle?: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const panel = useRef<HTMLElement>(null)
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const listener = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'Tab' && panel.current) {
        const controls = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]'))
        const first = controls[0], last = controls[controls.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', listener)
    return () => { document.removeEventListener('keydown', listener); document.body.style.overflow = oldOverflow; before?.focus() }
  }, [onClose])
  return <div className="drawer-layer"><button className="drawer-backdrop" tabIndex={-1} onClick={onClose} aria-label="Close panel" /><aside ref={panel} role="dialog" aria-modal="true" aria-labelledby="drawer-title" className={`drawer ${wide ? 'drawer-wide' : ''}`}>
    <div className="drawer-header"><div><h2 id="drawer-title">{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" onClick={onClose} aria-label="Close panel"><X size={21} /></button></div>{children}
  </aside></div>
}
