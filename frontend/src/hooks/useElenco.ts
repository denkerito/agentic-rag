import { useCallback, useEffect, useState } from 'react'
import { elencoIndagini } from '../api/client'
import { STATI_ATTIVI, type IndagineRiga } from '../api/types'

const POLL_ELENCO_MS = 4000

/** Elenco delle indagini; si aggiorna da solo finché ce n'è una attiva. */
export function useElenco() {
  const [indagini, setIndagini] = useState<IndagineRiga[]>([])
  const [errore, setErrore] = useState<string | null>(null)
  const [versione, setVersione] = useState(0)
  const ricarica = useCallback(() => setVersione((v) => v + 1), [])

  useEffect(() => {
    let attuale = true
    elencoIndagini()
      .then((lista) => {
        if (!attuale) return
        setIndagini(lista)
        setErrore(null)
      })
      .catch((e) => attuale && setErrore(String(e)))
    return () => {
      attuale = false
    }
  }, [versione])

  const qualcunaAttiva = indagini.some((i) => STATI_ATTIVI.includes(i.stato))
  useEffect(() => {
    if (!qualcunaAttiva) return
    const t = setInterval(ricarica, POLL_ELENCO_MS)
    return () => clearInterval(t)
  }, [qualcunaAttiva, ricarica])

  return { indagini, errore, ricarica }
}
