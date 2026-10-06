import type { PointerEvent } from 'react'

/** Salva la posizione del puntatore (relativa all'elemento) in --mx/--my: il CSS la usa per i bagliori. */
export function seguiPuntatore(e: PointerEvent<HTMLElement>): void {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${e.clientX - r.left}px`)
  el.style.setProperty('--my', `${e.clientY - r.top}px`)
}
