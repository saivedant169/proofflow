import { useEffect, type RefObject } from 'react'
import { FIELD, fieldPath, type FieldPointer } from './field'

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/**
 * One rAF loop for the hero stage: the background thread field leans toward the pointer and breathes slowly,
 * and --px / --py (−1…1) are published on the stage for subtle CSS parallax. Runs only while the stage is on
 * screen and the tab is visible; never with reduced motion. No React state per frame.
 */
export function useStageMotion(stageRef: RefObject<HTMLElement | null>, fieldRef: RefObject<SVGSVGElement | null>, enabled: boolean) {
  useEffect(() => {
    const stage = stageRef.current
    const field = fieldRef.current
    if (!enabled || !stage || !field) return

    const target = { x: 0, y: 0, active: false }
    const cur = { x: 0, y: 0 }
    const fp: FieldPointer & { tx: number; ty: number; ta: number } = { x: FIELD.w / 2, y: FIELD.h / 2, a: 0, tx: FIELD.w / 2, ty: FIELD.h / 2, ta: 0 }
    const paths = Array.from(field.querySelectorAll<SVGPathElement>('path[data-i]'))
    let raf = 0
    let onScreen = true

    const onMove = (e: PointerEvent) => {
      const r = stage.getBoundingClientRect()
      target.x = clamp((e.clientX - (r.left + r.width / 2)) / (r.width / 2), -1, 1)
      target.y = clamp((e.clientY - (r.top + r.height / 2)) / (r.height / 2), -1, 1)
      target.active = true
      const m = field.getScreenCTM()
      if (m) {
        const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse())
        fp.tx = p.x
        fp.ty = p.y
        fp.ta = 1
      }
    }
    const onLeave = () => {
      target.active = false
      fp.ta = 0
    }

    const tick = (t: number) => {
      cur.x += ((target.active ? target.x : 0) - cur.x) * 0.06
      cur.y += ((target.active ? target.y : 0) - cur.y) * 0.06
      fp.x += (fp.tx - fp.x) * 0.1
      fp.y += (fp.ty - fp.y) * 0.1
      fp.a += (fp.ta - fp.a) * 0.05
      stage.style.setProperty('--px', cur.x.toFixed(4))
      stage.style.setProperty('--py', cur.y.toFixed(4))
      for (let i = 0; i < paths.length; i++) paths[i].setAttribute('d', fieldPath(i, t, fp))
      raf = requestAnimationFrame(tick)
    }

    const start = () => {
      if (!raf && onScreen && document.visibilityState === 'visible') raf = requestAnimationFrame(tick)
    }
    const stop = () => {
      cancelAnimationFrame(raf)
      raf = 0
    }

    const io = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting
      if (onScreen) start()
      else stop()
    })
    io.observe(stage)
    const onVis = () => (document.visibilityState === 'visible' ? start() : stop())
    document.addEventListener('visibilitychange', onVis)
    stage.addEventListener('pointermove', onMove)
    stage.addEventListener('pointerleave', onLeave)
    start()

    return () => {
      stop()
      io.disconnect()
      document.removeEventListener('visibilitychange', onVis)
      stage.removeEventListener('pointermove', onMove)
      stage.removeEventListener('pointerleave', onLeave)
      stage.style.removeProperty('--px')
      stage.style.removeProperty('--py')
    }
  }, [stageRef, fieldRef, enabled])
}
