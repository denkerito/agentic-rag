import type { Stato } from '../api/types'
import { ETICHETTE_STATO } from '../lib/stato'

const VARIANTE: Record<Stato, string> = {
  in_coda: 'warn',
  in_corso: 'accent',
  completata: 'ok',
  fallita: 'danger',
  interrotta: '',
}

export function StatoBadge({ stato }: { stato: Stato }) {
  return (
    <span className={`pill ${VARIANTE[stato]} stato-${stato}`}>
      <span className="dot" aria-hidden="true" />
      {ETICHETTE_STATO[stato]}
    </span>
  )
}

/** Solo il pallino (per l'elenco); il testo è per gli screen reader. */
export function StatoDot({ stato }: { stato: Stato }) {
  return (
    <span
      className={`dot s-${stato} ${stato === 'in_corso' ? 'pulse' : ''}`}
      role="img"
      aria-label={ETICHETTE_STATO[stato]}
    />
  )
}
