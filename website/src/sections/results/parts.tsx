import { useEffect, useRef } from 'react'
import { animate, useInView, useReducedMotion } from 'motion/react'

export const EASE = [0.22, 1, 0.36, 1] as const
export const nf = (n: number) => n.toLocaleString('en-US')

/** Reveal once when the element enters view. With reduced motion, the end state shows at once. */
export function useReveal<T extends Element>(amount = 0.35) {
  const ref = useRef<T>(null)
  const inView = useInView(ref, { once: true, amount })
  const reduce = !!useReducedMotion()
  return { ref, show: inView || reduce, reduce }
}

/**
 * Counts from zero to `to` once `start` is true. The animated digits are aria-hidden;
 * the final value is always available to assistive technology.
 */
export function CountUp({ to, decimals = 0, start, suffix = '', prefix = '', duration = 1.5, delay = 0 }: {
  to: number
  decimals?: number
  start: boolean
  suffix?: string
  prefix?: string
  duration?: number
  delay?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const reduce = !!useReducedMotion()
  const fmt = (v: number) =>
    prefix + v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix

  useEffect(() => {
    const el = ref.current
    if (!el || !start) return
    if (reduce) { el.textContent = fmt(to); return }
    const controls = animate(0, to, {
      duration,
      delay,
      ease: EASE,
      onUpdate: v => { el.textContent = fmt(v) },
    })
    return () => controls.stop()
    // fmt is derived from the same props listed here
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start, to, reduce])

  return (
    <>
      <span ref={ref} aria-hidden="true">{fmt(reduce ? to : 0)}</span>
      <span className="sr-only">{fmt(to)}</span>
    </>
  )
}
