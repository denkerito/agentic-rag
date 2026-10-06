import { useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { fermaIndagine } from '../api/client'
import { STATI_ATTIVI } from '../api/types'
import { useIndagine } from '../hooks/useIndagine'
import { durata } from '../lib/data'
import { formatoData } from '../lib/formato'
import type { LayoutContext } from '../lib/layoutContext'
import { Icona } from './Icone'
import { Passi } from './Passi'
import { RispostaCard } from './RispostaCard'
import { StatoBadge } from './StatoBadge'

export default function VistaIndagine() {
  const { id } = useParams()
  // key: al cambio di indagine lo stato (passi, stream) riparte da zero
  return id ? <Indagine key={id} id={id} /> : null
}

function Indagine({ id }: { id: string }) {
  const { ricaricaElenco } = useOutletContext<LayoutContext>()
  const { vista, dettaglio, connessione, errore, terminata, ricarica } = useIndagine(
    id,
    ricaricaElenco,
  )
  const [stopRichiesto, setStopRichiesto] = useState(false)
  const [erroreStop, setErroreStop] = useState<string | null>(null)

  async function ferma() {
    setStopRichiesto(true)
    setErroreStop(null)
    try {
      await fermaIndagine(id)
    } catch (e) {
      setStopRichiesto(false)
      setErroreStop(`Impossibile fermare l'indagine: ${String(e)}`)
      ricarica()
    }
  }

  if (errore && !dettaglio) {
    return (
      <div className="pagina">
        <p className="errore-testo">{errore}</p>
      </div>
    )
  }

  const attiva = dettaglio !== null && STATI_ATTIVI.includes(dettaglio.stato) && !terminata
  const u = dettaglio?.utilizzo
  const inizio = dettaglio ? (dettaglio.iniziata_il ?? dettaglio.creata_il) : null

  return (
    <article className="pagina" aria-busy={attiva}>
      <header className={`testata ${attiva ? 'attiva' : ''}`}>
        <div>
          <h1>{dettaglio?.domanda ?? 'Caricamento…'}</h1>
          {dettaglio && inizio && (
            <p className="meta">
              <StatoBadge stato={dettaglio.stato} />
              <span>Avviata {formatoData(dettaglio.creata_il)}</span>
              <span>Durata {durata(inizio, dettaglio.conclusa_il)}</span>
              <span className="mono">{dettaglio.modello}</span>
            </p>
          )}
        </div>
        {attiva && (
          <button type="button" className="btn pericolo" onClick={ferma} disabled={stopRichiesto}>
            <Icona nome="stop" size={14} />
            {stopRichiesto ? 'Interruzione richiesta…' : 'Ferma'}
          </button>
        )}
      </header>

      {erroreStop && <p className="errore-testo">{erroreStop}</p>}
      {connessione === 'riconnessione' && (
        <p className="avviso-testo">Connessione interrotta, riconnessione in corso…</p>
      )}
      {connessione === 'persa' && (
        <p className="errore-testo">Connessione persa: ricarica la pagina per riprendere.</p>
      )}

      {dettaglio?.stato === 'in_coda' && vista.passi.length === 0 && (
        <p className="muted">In coda: l'indagine parte appena c'è una sessione libera.</p>
      )}
      {dettaglio?.stato === 'in_corso' && vista.passi.length === 0 && !terminata && (
        <div className="scheletro" role="status">
          <span className="sr-only">L'agente sta pianificando il primo passo…</span>
          <span className="barra-sk" />
          <span className="barra-sk" />
          <span className="barra-sk" />
        </div>
      )}

      {vista.risposta && <RispostaCard risposta={vista.risposta} />}
      {vista.errore && (
        <section className="card errore" role="alert">
          <h2>Indagine non completata</h2>
          <p>{vista.errore.messaggio}</p>
          <p className="muted">
            Nessuna risposta è stata prodotta: i passi qui sotto restano consultabili.
          </p>
        </section>
      )}
      {vista.interrotta && (
        <section className="card interrotta">
          <h2>Indagine interrotta</h2>
          <p>{vista.interrotta}</p>
        </section>
      )}

      <Passi passi={vista.passi} inCorso={attiva && vista.passi.length > 0} />

      {u && (
        <footer className="utilizzo">
          {u.requests} richieste al modello · {u.tool_calls} chiamate a tool ·{' '}
          {u.input_tokens?.toLocaleString('it-IT')} token in ingresso ·{' '}
          {u.output_tokens?.toLocaleString('it-IT')} in uscita
        </footer>
      )}
    </article>
  )
}
