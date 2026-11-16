import { useEffect, useState } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'
// Shared with the product site on the same origin, so one choice carries across both.
const KEY = 'proofflow-site-theme'

function read(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(read)
  useEffect(() => {
    const root = document.documentElement
    if (choice === 'system') delete root.dataset.theme
    else root.dataset.theme = choice
    try {
      if (choice === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, choice)
    } catch { /* Storage unavailable: the choice still applies for this visit. */ }
  }, [choice])
  return { choice, setChoice }
}
