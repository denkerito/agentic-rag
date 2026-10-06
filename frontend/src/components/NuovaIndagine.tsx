import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { creaIndagine } from '../api/client'

const MAX = 2000

export function NuovaIndagine({ onCreata }: { onCreata: () => void }) {
  const [domanda, setDomanda] = useState('')
  const [invio, setInvio] = useState(false)
  const [errore, setErrore] = useState<string | null>(null)
  const navigate = useNavigate()

  async function invia(e?: FormEvent) {
    e?.preventDefault()
    const testo = domanda.trim()
    if (!testo || invio) return
    setInvio(true)
    setErrore(null)
    try {
      const { id } = await creaIndagine(testo)
      setDomanda('')
      onCreata()
      navigate(`/indagini/${id}`)
    } catch (err) {
      setErrore(`Impossibile avviare l'indagine: ${String(err)}`)
    } finally {
      setInvio(false)
    }
  }

  return (
    <form onSubmit={invia} className="nuova">
      <label htmlFor="domanda">Nuova indagine</label>
      <textarea
        id="domanda"
        value={domanda}
        maxLength={MAX}
        rows={4}
        placeholder="Es. Perché il margine è diminuito ad agosto?"
        onChange={(e) => setDomanda(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void invia()
        }}
      />
      <div className="nuova-azioni">
        <span className="muted">
          {domanda.length}/{MAX}
        </span>
        <button type="submit" className="primario" disabled={invio || !domanda.trim()}>
          {invio ? 'Avvio…' : 'Avvia indagine'}
        </button>
      </div>
      {errore && <p className="errore-testo">{errore}</p>}
    </form>
  )
}
