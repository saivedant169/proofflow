import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import type { DemoSession } from './engine'
import type { NodeView, Slot } from './model'
import Inspector from './Inspector'
import Activity, { type LogEntry } from './Activity'

export type DrawerTab = 'step' | 'activity'

/** Slide-over (bottom sheet on phones) holding the per-node inspector and the activity log. Non-modal:
 *  the graph stays clickable so another node can be inspected without closing it. */
export default function Drawer({ open, tab, onTab, onClose, session, slot, node, log }: {
  open: boolean
  tab: DrawerTab
  onTab: (tab: DrawerTab) => void
  onClose: () => void
  session: DemoSession
  slot: Slot | null
  node: NodeView | null
  log: LogEntry[]
}) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const frame = requestAnimationFrame(() => closeRef.current?.focus({ preventScroll: true }))
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      cancelAnimationFrame(frame)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  const tabs: { id: DrawerTab; label: string }[] = [
    { id: 'step', label: 'Step' },
    { id: 'activity', label: 'Activity' },
  ]

  // Rendered only while open, so a closed drawer can never overlay another section.
  if (!open) return null

  return (
    <>
      <div className="demo-scrim" onClick={onClose} aria-hidden />
      <aside className="demo-drawer" role="dialog" aria-modal="false" aria-label="Details">
        <div className="demo-drawer-head">
          <span className="demo-drawer-grip" aria-hidden />
          <div className="demo-tabs" role="tablist" aria-label="Details">
            {tabs.map(item => (
              <button key={item.id} type="button" role="tab" id={`demo-tab-${item.id}`}
                aria-selected={tab === item.id} aria-controls={`demo-panel-${item.id}`}
                tabIndex={tab === item.id ? 0 : -1}
                className={`demo-tab${tab === item.id ? ' is-active' : ''}`}
                onClick={() => onTab(item.id)}
                onKeyDown={event => {
                  if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                    const nextTab = item.id === 'step' ? 'activity' : 'step'
                    onTab(nextTab)
                    document.getElementById(`demo-tab-${nextTab}`)?.focus()
                  }
                }}>
                {item.label}
                {item.id === 'activity' && <span className="demo-tab-count figure">{log.length}</span>}
              </button>
            ))}
          </div>
          <button ref={closeRef} type="button" className="demo-drawer-close" onClick={onClose} aria-label="Close details">
            <X size={18} strokeWidth={2.2} aria-hidden />
          </button>
        </div>
        <div className="demo-drawer-body" role="tabpanel" id={`demo-panel-${tab}`} aria-labelledby={`demo-tab-${tab}`} tabIndex={0}>
          {tab === 'step'
            ? <Inspector session={session} slot={slot} node={node} />
            : <Activity entries={log} />}
        </div>
      </aside>
    </>
  )
}
