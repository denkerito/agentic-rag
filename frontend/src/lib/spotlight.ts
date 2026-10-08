import { useEffect, type PointerEvent, type RefObject } from 'react'

/** Salva la posizione del puntatore (relativa all'elemento) in --mx/--my: il CSS la usa per i bagliori. */
export function seguiPuntatore(e: PointerEvent<HTMLElement>): void {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${e.clientX - r.left}px`)
  el.style.setProperty('--my', `${e.clientY - r.top}px`)
}

const INERZIA = 0.18

/**
 * Spotlight a tutto schermo: segue il puntatore su tutta la finestra (coordinate viewport in --sx/--sy)
 * con un'interpolazione per frame, così il movimento è morbido anche a scatti del mouse.
 */
export function useSpotlight(ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const el = ref.current
    if (!el || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const ridotto = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let tx = window.innerWidth / 2
    let ty = window.innerHeight * 0.24
    let x = tx
    let y = ty
    let frame = 0

    const scrivi = () => {
      el.style.setProperty('--sx', `${x.toFixed(1)}px`)
      el.style.setProperty('--sy', `${y.toFixed(1)}px`)
    }
    const passo = () => {
      x += (tx - x) * INERZIA
      y += (ty - y) * INERZIA
      const fermo = Math.abs(tx - x) < 0.3 && Math.abs(ty - y) < 0.3
      if (fermo) {
        x = tx
        y = ty
      }
      scrivi()
      frame = fermo ? 0 : requestAnimationFrame(passo)
    }
    const muovi = (e: globalThis.PointerEvent) => {
      tx = e.clientX
      ty = e.clientY
      if (ridotto) {
        x = tx
        y = ty
        scrivi()
      } else if (!frame) {
        frame = requestAnimationFrame(passo)
      }
    }

    scrivi()
    window.addEventListener('pointermove', muovi, { passive: true })
    return () => {
      window.removeEventListener('pointermove', muovi)
      cancelAnimationFrame(frame)
    }
  }, [ref])
}
