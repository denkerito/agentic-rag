import type { Stato } from '../api/types'

export const ETICHETTE_STATO: Record<Stato, string> = {
  in_coda: 'In coda',
  in_corso: 'In corso',
  completata: 'Completata',
  fallita: 'Fallita',
  interrotta: 'Interrotta',
}
