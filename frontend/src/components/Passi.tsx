import type { ToolResult } from '../api/types'
import type { Passo, PassoTool } from '../state/passi'
import { IdChips } from './FonteChip'

const TITOLI: Record<string, string> = {
  query_sql: 'Query SQL',
  cerca_documenti: 'Ricerca nei documenti',
  apri_documento: 'Apertura documento',
}

function Esito({ tool, esito }: { tool: string; esito: ToolResult }) {
  let riepilogo: string
  if (tool === 'query_sql') {
    const n = esito.n_righe ?? 0
    riepilogo = `${n} ${n === 1 ? 'riga' : 'righe'}${esito.troncato ? ' (risultato troncato)' : ''}`
  } else if (tool === 'cerca_documenti') {
    riepilogo = esito.n_pertinenti
      ? `${esito.n_pertinenti} ${esito.n_pertinenti === 1 ? 'risultato pertinente' : 'risultati pertinenti'}`
      : 'Nessun documento pertinente'
  } else {
    riepilogo = esito.troncato ? 'Documento aperto (parte troncata)' : 'Documento aperto'
  }
  return (
    <div className="esito">
      <span>{riepilogo}</span>
      {esito.ids.length > 0 && (
        <div className="fonti-passo">
          <span className="muted">Fonti trovate:</span> <IdChips ids={esito.ids} />
        </div>
      )}
    </div>
  )
}

function Argomenti({ passo }: { passo: PassoTool }) {
  const { tool, args } = passo
  if (tool === 'query_sql') return <pre className="codice">{String(args.sql ?? '')}</pre>
  if (tool === 'apri_documento') {
    return (
      <p className="args">
        {String(args.doc_id ?? '')}
        {args.offset ? ` (da carattere ${String(args.offset)})` : ''}
      </p>
    )
  }
  const filtri = Object.entries(args).filter(([k, v]) => k !== 'query' && v != null)
  return (
    <p className="args">
      “{String(args.query ?? '')}”
      {filtri.map(([k, v]) => (
        <span key={k} className="filtro">
          {k.replace('_', ' ')}: {String(v)}
        </span>
      ))}
    </p>
  )
}

function PassoView({ passo, numero }: { passo: Passo; numero: number }) {
  if (passo.kind === 'scartata') {
    return (
      <li className="passo avviso">
        <h3>
          {numero}. Risposta scartata dal controllo sulle fonti
        </h3>
        <p>{passo.motivo}</p>
        <p className="muted">L'agente riformula la risposta citando solo fonti verificate.</p>
      </li>
    )
  }
  const stato = passo.retry ? 'avviso' : passo.esito ? 'ok' : 'attesa'
  return (
    <li className={`passo ${stato}`}>
      <h3>
        {numero}. {TITOLI[passo.tool] ?? passo.tool}
      </h3>
      <Argomenti passo={passo} />
      {passo.esito && <Esito tool={passo.tool} esito={passo.esito} />}
      {passo.retry && (
        <p className="esito">
          Richiesta rifiutata: {passo.retry.motivo.split('\n')[0]}
          <span className="muted"> — l'agente riprova.</span>
        </p>
      )}
      {stato === 'attesa' && <p className="muted">In esecuzione…</p>}
    </li>
  )
}

export function Passi({ passi }: { passi: Passo[] }) {
  if (passi.length === 0) return null
  return (
    <ol className="passi" aria-live="polite" aria-label="Passi dell'indagine">
      {passi.map((p, i) => (
        <PassoView key={p.kind === 'tool' ? p.callId : `s${p.seq}`} passo={p} numero={i + 1} />
      ))}
    </ol>
  )
}
