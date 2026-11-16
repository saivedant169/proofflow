import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme, type ThemeChoice } from '../lib/theme'

const options: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'system', label: 'System theme', icon: Monitor },
  { value: 'dark', label: 'Dark theme', icon: Moon },
]

export default function ThemeSwitch() {
  const { choice, setChoice } = useTheme()
  return <div className="theme-switch" role="radiogroup" aria-label="Color theme">
    {options.map(({ value, label, icon: Icon }) => <button key={value} type="button" role="radio" aria-checked={choice === value} aria-label={label} title={label} className={choice === value ? 'is-on' : undefined} onClick={() => setChoice(value)}>
      <Icon size={15} strokeWidth={2} aria-hidden="true" />
    </button>)}
  </div>
}
