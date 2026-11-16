import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Menu, Monitor, Moon, Sun, X } from 'lucide-react'
import { SECTIONS, SECTION_IDS } from '../content/sections'
import { links } from '../content/facts'
import { useActiveSection, useScrollProgress } from '../lib/useActiveSection'
import { useTheme, type ThemeChoice } from '../lib/theme'
import { ButtonLink } from './ui'
import './Chrome.css'

const THEME_LABEL: Record<ThemeChoice, string> = { system: 'System theme', light: 'Light theme', dark: 'Dark theme' }
const LEAD_STAGE = '#main > :first-child > .stage:first-child'

/**
 * True while the given viewport line (px from the top, or a function of the viewport height) crosses an element
 * with the `.stage` class. Chrome uses it to switch to the night-ledger tokens over dark stages in both themes.
 */
function useOverStage(line: number | ((vh: number) => number)) {
  const [over, setOver] = useState(false)
  const lineRef = useRef(line)
  lineRef.current = line
  useEffect(() => {
    let frame = 0
    const check = () => {
      frame = 0
      const l = lineRef.current
      const y = typeof l === 'function' ? l(window.innerHeight) : l
      let hit = false
      const navH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 72
      for (const el of document.querySelectorAll<HTMLElement>('main .stage')) {
        const r = el.getBoundingClientRect()
        // A stage that opens the page also paints the band under the bar (see Chrome.css).
        const top = el.matches(LEAD_STAGE) ? r.top - navH : r.top
        // Only blocks that span (nearly) the full width read as a backdrop for the chrome.
        if (top <= y && r.bottom > y && r.width >= window.innerWidth * 0.9) { hit = true; break }
      }
      setOver(hit)
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(check) }
    check()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    // Sections may mount or resize after first paint (lazy media, fonts).
    const late = window.setTimeout(schedule, 1200)
    return () => {
      cancelAnimationFrame(frame)
      window.clearTimeout(late)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [])
  return over
}

function ThemeSwitch() {
  const { choice, setChoice } = useTheme()
  const options: { value: ThemeChoice; icon: typeof Sun }[] = [
    { value: 'light', icon: Sun },
    { value: 'system', icon: Monitor },
    { value: 'dark', icon: Moon },
  ]
  return (
    <div className="theme-switch" role="radiogroup" aria-label="Color theme">
      {options.map(({ value, icon: Icon }) => (
        <button key={value} type="button" role="radio" aria-checked={choice === value}
          aria-label={THEME_LABEL[value]} title={THEME_LABEL[value]}
          className={choice === value ? 'is-on' : ''} onClick={() => setChoice(value)}>
          {choice === value && <motion.span layoutId="theme-thumb" className="theme-thumb" aria-hidden
            transition={{ type: 'spring', stiffness: 520, damping: 40 }} />}
          <Icon size={15} strokeWidth={2} aria-hidden />
        </button>
      ))}
    </div>
  )
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <a className={`wordmark ${className}`} href="#top" aria-label="ProofFlow, back to top">
      <svg viewBox="0 0 28 28" width="26" height="26" aria-hidden>
        <path d="M8 21V7m0 0h6.5a4.5 4.5 0 0 1 0 9H8" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="21" cy="21" r="2.6" className="wordmark-dot" />
      </svg>
      <span>ProofFlow</span>
    </a>
  )
}

export function Nav() {
  const active = useActiveSection(SECTION_IDS)
  const progress = useScrollProgress()
  const overStage = useOverStage(36)
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const menuBtn = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setOpen(false); menuBtn.current?.focus() }
    }
    // Close the sheet once the viewport is wide enough to show the inline section links (Chrome.css, 1200px).
    const wide = window.matchMedia('(min-width: 1201px)')
    const onWide = () => wide.matches && setOpen(false)
    window.addEventListener('keydown', onKey)
    wide.addEventListener('change', onWide)
    return () => {
      window.removeEventListener('keydown', onKey)
      wide.removeEventListener('change', onWide)
    }
  }, [open])

  const navItems = SECTIONS.filter(s => s.nav)
  const cls = ['site-nav', scrolled && 'is-scrolled', open && 'is-open', overStage && 'stage is-over-stage']
    .filter(Boolean).join(' ')

  return (
    <header className={cls}>
      <div className="site-nav-inner">
        <Wordmark />
        <nav aria-label="Sections" className="site-nav-links">
          {navItems.map(s => (
            <a key={s.id} href={`#${s.id}`} aria-current={active === s.id ? 'location' : undefined}>
              {active === s.id && (
                <motion.span layoutId="nav-active" className="nav-indicator" aria-hidden
                  transition={{ type: 'spring', stiffness: 420, damping: 38 }} />
              )}
              <span className="nav-link-label">{s.label}</span>
            </a>
          ))}
        </nav>
        <div className="site-nav-actions">
          <ThemeSwitch />
          <ButtonLink href={links.liveApp} external className="nav-cta">Open live app</ButtonLink>
          <button ref={menuBtn} type="button" className="nav-menu-btn" aria-expanded={open} aria-controls="mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen(v => !v)}>
            {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
          </button>
        </div>
      </div>
      <span className="nav-progress" aria-hidden style={{ transform: `scaleX(${progress})` }} />

      <AnimatePresence>
        {open && (
          <motion.nav id="mobile-nav" className="mobile-nav" aria-label="Sections"
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
            <ul>
              {SECTIONS.map(s => (
                <li key={s.id}>
                  <a href={`#${s.id}`} onClick={() => setOpen(false)} aria-current={active === s.id ? 'location' : undefined}>
                    <span className="mobile-node" aria-hidden />
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
            <ButtonLink href={links.liveApp} external>Open live app</ButtonLink>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  )
}

/** The page's own lineage thread: each section is a node; filled portion = reading progress. */
export function LineageRail() {
  const active = useActiveSection(SECTION_IDS)
  const progress = useScrollProgress()
  const overStage = useOverStage(vh => vh / 2)
  const activeIndex = SECTION_IDS.indexOf(active)
  return (
    <nav className={`lineage-rail${overStage ? ' stage is-over-stage' : ''}`} aria-label="Page progress">
      <div className="rail-line" aria-hidden><div className="rail-fill" style={{ transform: `scaleY(${progress})` }} /></div>
      <ol>
        {SECTIONS.map((s, i) => (
          <li key={s.id} className={i < activeIndex ? 'is-past' : i === activeIndex ? 'is-active' : ''}>
            <a href={`#${s.id}`} aria-current={i === activeIndex ? 'location' : undefined}>
              <span className="rail-node" aria-hidden />
              <span className="rail-label">{s.label}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}
