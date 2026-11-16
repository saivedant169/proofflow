import { useEffect, useState } from 'react'
import { Menu, Monitor, Moon, Sun, X } from 'lucide-react'
import { SECTIONS, SECTION_IDS } from '../content/sections'
import { links } from '../content/facts'
import { useActiveSection, useScrollProgress } from '../lib/useActiveSection'
import { useTheme, type ThemeChoice } from '../lib/theme'
import { ButtonLink } from './ui'
import './Chrome.css'

const THEME_LABEL: Record<ThemeChoice, string> = { system: 'System theme', light: 'Light theme', dark: 'Dark theme' }

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
          <Icon size={16} strokeWidth={2} aria-hidden />
        </button>
      ))}
    </div>
  )
}

export function Wordmark() {
  return (
    <a className="wordmark" href="#top" aria-label="ProofFlow, back to top">
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
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const navItems = SECTIONS.filter(s => s.nav)
  return (
    <header className={`site-nav ${scrolled ? 'is-scrolled' : ''}`}>
      <div className="site-nav-inner">
        <Wordmark />
        <nav aria-label="Sections" className="site-nav-links">
          {navItems.map(s => (
            <a key={s.id} href={`#${s.id}`} aria-current={active === s.id ? 'location' : undefined}>{s.label}</a>
          ))}
        </nav>
        <div className="site-nav-actions">
          <ThemeSwitch />
          <ButtonLink href={links.liveApp} external className="nav-cta">Open live app</ButtonLink>
          <button type="button" className="nav-menu-btn" aria-expanded={open} aria-controls="mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen(v => !v)}>
            {open ? <X size={22} aria-hidden /> : <Menu size={22} aria-hidden />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" className="mobile-nav" aria-label="Sections">
          {SECTIONS.map(s => (
            <a key={s.id} href={`#${s.id}`} onClick={() => setOpen(false)} aria-current={active === s.id ? 'location' : undefined}>{s.label}</a>
          ))}
          <ButtonLink href={links.liveApp} external>Open live app</ButtonLink>
        </nav>
      )}
    </header>
  )
}

/** The page's own lineage thread: each section is a node; filled portion = reading progress. */
export function LineageRail() {
  const active = useActiveSection(SECTION_IDS)
  const progress = useScrollProgress()
  const activeIndex = SECTION_IDS.indexOf(active)
  return (
    <nav className="lineage-rail" aria-label="Page progress">
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
