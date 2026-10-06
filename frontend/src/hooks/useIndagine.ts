import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, dettaglioIndagine, urlEventi } from '../api/client'
import {
  STATI_ATTIVI,
  TIPI_EVENTO,
  TIPI_TERMINALI,
  type Evento,
  type IndagineDettaglio,
} from '../api/types'
import { riduci, terminata, vistaIniziale, type Vista } from '../state/passi'

export type Connessione = 'aperta' | 'riconnessione' | 'persa' | 'chiusa'

const POLL_DETTAGLIO_MS = 3000

/** Stato di un'indagine: dettaglio via REST e passi via SSE (EventSource nativo).
 *  Montare con `key={id}` così lo stato riparte pulito al cambio di indagine. */
export function useIndagine(id: string, alTerminale?: () => void) {
  const [vista, setVista] = useState<Vista>(vistaIniziale)
  const [dettaglio, setDettaglio] = useState<IndagineDettaglio | null>(null)
  const [connessione, setConnessione] = useState<Connessione>('aperta')
  const [errore, setErrore] = useState<string | null>(null)
  const [versione, setVersione] = useState(0)
  const ricarica = useCallback(() => setVersione((v) => v + 1), [])

  const alTerminaleRef = useRef(alTerminale)
  useEffect(() => {
    alTerminaleRef.current = alTerminale
  })

  useEffect(() => {
    let attuale = true
    dettaglioIndagine(id)
      .then((d) => {
        if (!attuale) return
        setDettaglio(d)
        setErrore(null)
      })
      .catch((e) => {
        if (!attuale) return
        setErrore(e instanceof ApiError && e.status === 404 ? 'Indagine non trovata.' : String(e))
      })
    return () => {
      attuale = false
    }
  }, [id, versione])

  useEffect(() => {
    const es = new EventSource(urlEventi(id))
    for (const tipo of TIPI_EVENTO) {
      es.addEventListener(tipo, (m) => {
        const msg = m as MessageEvent<string>
        const evento = { tipo, seq: Number(msg.lastEventId), ...JSON.parse(msg.data) } as Evento
        setVista((v) => riduci(v, evento))
        if ((TIPI_TERMINALI as readonly string[]).includes(tipo)) {
          es.close() // altrimenti il browser riconnette dopo la chiusura del server
          setConnessione('chiusa')
          ricarica()
          alTerminaleRef.current?.()
        }
      })
    }
    es.onopen = () => setConnessione('aperta')
    es.onerror = () =>
      setConnessione(es.readyState === EventSource.CLOSED ? 'persa' : 'riconnessione')
    return () => es.close()
  }, [id, ricarica])

  // lo stato (in_coda -> in_corso) non ha un evento: lo si rilegge finché l'indagine è attiva
  const attiva = dettaglio !== null && STATI_ATTIVI.includes(dettaglio.stato)
  useEffect(() => {
    if (!attiva) return
    const t = setInterval(ricarica, POLL_DETTAGLIO_MS)
    return () => clearInterval(t)
  }, [attiva, ricarica])

  return { vista, dettaglio, connessione, errore, terminata: terminata(vista), ricarica }
}
