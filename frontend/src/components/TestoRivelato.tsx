import type { CSSProperties } from 'react'

const RITARDO_MAX = 28 // parole oltre la 28ª compaiono insieme: la rivelazione dura al massimo ~0,8 s

/** Testo che si rivela parola per parola. Il testo completo resta nel DOM per gli screen reader
 *  (le parole animate sono aria-hidden): cambia solo la comparsa, mai il contenuto. */
export function TestoRivelato({ testo, className }: { testo: string; className?: string }) {
  const parole = testo.split(/\s+/).filter(Boolean)
  return (
    <p className={className}>
      <span className="sr-only">{testo}</span>
      <span aria-hidden="true">
        {parole.map((p, i) => (
          <span key={i}>
            <span className="parola" style={{ '--w': Math.min(i, RITARDO_MAX) } as CSSProperties}>
              {p}
            </span>{' '}
          </span>
        ))}
      </span>
    </p>
  )
}
