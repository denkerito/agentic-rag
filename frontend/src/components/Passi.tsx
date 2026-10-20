import { useState, type CSSProperties } from 'react'
import type { Passo, PassoTool } from '../state/passi'
import { riepilogo, TOOL } from '../lib/strumenti'
import { IdChips } from './FonteChip'
import { Icona, type NomeIcona } from './Icone'

function Argomenti({ passo }: { passo: PassoTool }) {
  const { tool, args } = passo
  if (tool === 'query_sql') {
    const sql = String(args.sql ?? '')
    return (
      <details className="sql">
        <summary>{sql.replace(/\s+/g, ' ')}</summary>
        <pre>{sql}</pre>
      </details>
    )
  }
  if (tool === 'apri_documento') {
    return (
      <p className="passo-dettaglio">
        <span className="mono">{String(args.doc_id ?? '')}</span>
        {args.offset ? ` · da carattere ${String(args.offset)}` : ''}
      </p>
    )
  }
  const filtri = Object.entries(args).filter(([k, v]) => k !== 'query' && v != null)
  return (
    <p className="passo-dettaglio">
      {args.query != null ? `“${String(args.query)}”` : filtri.length ? 'Filtri' : 'Tutti i documenti'}
      {filtri.map(([k, v]) => (
        <span key={k}> · {k.replaceAll('_', ' ')}: {String(v)}</span>
      ))}
    </p>
  )
}

function PassoView({ passo, numero }: { passo: Passo; numero: number }) {
  const stile = { '--i': numero - 1 } as CSSProperties
  if (passo.kind === 'scartata') {
    return (
      <li className="passo avviso" style={stile}>
        <span className="nodo">
          <Icona nome="alert" size={16} />
        </span>
        <div className="passo-corpo">
          <div className="passo-testa">
            <h3>
              <span className="n">{numero}</span>Risposta scartata dal controllo sulle fonti
            </h3>
          </div>
          <p className="motivo">{passo.motivo.split('\n')[0]}</p>
          <p className="passo-dettaglio">L'agente riformula la risposta citando solo fonti verificate.</p>
        </div>
      </li>
    )
  }
  const stato = passo.retry ? 'avviso' : passo.esito ? 'ok' : 'attesa'
  const info = TOOL[passo.tool] ?? { titolo: passo.tool, icona: 'database' as NomeIcona }
  return (
    <li className={`passo ${stato}`} style={stile}>
      <span className="nodo">
        {stato === 'attesa' ? (
          <span className="spinner" role="status" aria-label="In esecuzione" />
        ) : stato === 'avviso' ? (
          <Icona nome="alert" size={16} />
        ) : (
          <Icona nome={info.icona} size={16} />
        )}
      </span>
      <div className="passo-corpo">
        <div className="passo-testa">
          <h3>
            <span className="n">{numero}</span>
            {info.titolo}
          </h3>
          {passo.esito && <span className="riepilogo">{riepilogo(passo.tool, passo.esito)}</span>}
          {passo.retry && <span className="riepilogo">Richiesta rifiutata, l'agente riprova</span>}
        </div>
        <Argomenti passo={passo} />
        {passo.retry && <p className="motivo">{passo.retry.motivo.split('\n')[0]}</p>}
        {passo.esito && passo.esito.ids.length > 0 && (
          <div className="fonti-passo">
            <span>Fonti trovate:</span> <IdChips ids={passo.esito.ids} />
          </div>
        )}
      </div>
    </li>
  )
}

/** `inCorso`: in coda alla timeline compare "l'agente sta ragionando" finché l'indagine è attiva. */
export function Passi({ passi, inCorso = false }: { passi: Passo[]; inCorso?: boolean }) {
  const [aperti, setAperti] = useState(true)
  if (passi.length === 0) return null
  return (
    <section className="sezione" aria-label="Passi dell'indagine">
      <div className="sezione-testa">
        <h2>Passi dell'indagine · {passi.length}</h2>
        <button
          type="button"
          className="toggle"
          aria-expanded={aperti}
          onClick={() => setAperti(!aperti)}
        >
          <Icona nome="chevron" size={16} />
          {aperti ? 'Comprimi' : 'Espandi'}
        </button>
      </div>
      {aperti && (
        <ol className="passi" aria-live="polite">
          {passi.map((p, i) => (
            <PassoView key={p.kind === 'tool' ? p.callId : `s${p.seq}`} passo={p} numero={i + 1} />
          ))}
          {inCorso && (
            <li className="passo pensa" style={{ '--i': passi.length } as CSSProperties}>
              <span className="nodo" aria-hidden="true">
                <span className="punti">
                  <i />
                  <i />
                  <i />
                </span>
              </span>
              <div className="passo-corpo" role="status">
                <p className="brilla-testo">L'agente sta ragionando…</p>
              </div>
            </li>
          )}
        </ol>
      )}
    </section>
  )
}
