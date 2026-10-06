import type { Stato } from '../api/types'

const ETICHETTE: Record<Stato, string> = {
  in_coda: 'In coda',
  in_corso: 'In corso',
  completata: 'Completata',
  fallita: 'Fallita',
  interrotta: 'Interrotta',
}

export function StatoBadge({ stato }: { stato: Stato }) {
  return <span className={`badge stato-${stato}`}>{ETICHETTE[stato]}</span>
}
