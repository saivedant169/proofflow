import { useCallback, useEffect, useState } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'
const KEY = 'proofflow-site-theme'

function read(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

function systemDark() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

/** Resolved theme that is actually showing, for components that draw on canvas/SVG. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(read)
  const [dark, setDark] = useState(() => choice === 'dark' || (choice === 'system' && systemDark()))

  useEffect(() => {
    const root = document.documentElement
    if (choice === 'system') delete root.dataset.theme
    else root.dataset.theme = choice
    try {
      if (choice === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, choice)
    } catch { /* storage unavailable: the choice still applies for this visit */ }
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setDark(choice === 'dark' || (choice === 'system' && media.matches))
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [choice])

  const cycle = useCallback(() => {
    setChoice(current => (current === 'system' ? (systemDark() ? 'light' : 'dark') : current === 'dark' ? 'light' : 'dark'))
  }, [])

  return { choice, dark, setChoice, cycle }
}
