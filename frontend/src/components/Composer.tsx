import { useState, type FormEvent } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { creaIndagine } from '../api/client'
import { usePlaceholder } from '../hooks/usePlaceholder'
import type { LayoutContext } from '../lib/layoutContext'

const MAX = 2000
const BASE = 'Scrivi la domanda da indagare…'
// frasi che il campo "scrive" da solo finché è vuoto (solo placeholder, non cliccabili)
const FRASI = [
  'Perché il margine è diminuito ad agosto?',
  'Qual è stato il margine di luglio 2025?',
  'Quali sono i costi più alti del trimestre?',
  'Quali contratti scadono nei prossimi mesi?',
] as const

export function Composer() {
  const [domanda, setDomanda] = useState('')
  const [invio, setInvio] = useState(false)
  const [errore, setErrore] = useState<string | null>(null)
  const { ricaricaElenco } = useOutletContext<LayoutContext>()
  const navigate = useNavigate()
  const placeholder = usePlaceholder(FRASI, domanda === '', BASE)

  async function invia(e?: FormEvent) {
    e?.preventDefault()
    const testo = domanda.trim()
    if (!testo || invio) return
    setInvio(true)
    setErrore(null)
    try {
      const { id } = await creaIndagine(testo)
      ricaricaElenco()
      navigate(`/indagini/${id}`)
    } catch (err) {
      setErrore(`Impossibile avviare l'indagine: ${String(err)}`)
      setInvio(false)
    }
  }

  return (
    <form onSubmit={invia} className="composer">
        <label htmlFor="domanda" className="sr-only">
          Domanda
        </label>
        <textarea
          id="domanda"
          autoFocus
          value={domanda}
          maxLength={MAX}
          placeholder={placeholder}
          onChange={(e) => setDomanda(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void invia()
          }}
        />
        <div className="composer-pie">
          <span>
            {domanda.length}/{MAX} · Ctrl+Invio per avviare
          </span>
          <button type="submit" className="btn primario" disabled={invio || !domanda.trim()}>
            {invio ? 'Avvio…' : 'Avvia indagine'}
          </button>
        </div>
        {errore && <p className="errore-testo">{errore}</p>}
    </form>
  )
}
